// FameWeb LinkedIn Integrator - Background Service Worker (Manifest V3)
// Strictly enforces zero transmission of raw sensitive cookies or session tokens.

const FAMEWEB_ORIGINS = [
  "http://localhost:5000",
  "http://127.0.0.1:5000",
  "http://localhost",
  "http://127.0.0.1"
];

// Verify whether LinkedIn is currently logged in using cookie presence check (boolean check only)
async function checkLinkedInSession() {
  try {
    const cookies = await chrome.cookies.getAll({ domain: ".linkedin.com" });
    const hasLiAt = cookies.some(c => c.name === "li_at" && c.value && c.value.length > 5);
    const hasJsession = cookies.some(c => c.name === "JSESSIONID");

    if (hasLiAt) {
      return {
        status: "CONNECTED",
        authenticated: true,
        message: "Active LinkedIn session verified."
      };
    } else {
      return {
        status: "NOT_LOGGED_IN",
        authenticated: false,
        message: "No active LinkedIn session found. Please log in at https://www.linkedin.com"
      };
    }
  } catch (err) {
    return {
      status: "VERIFICATION_FAILED",
      authenticated: false,
      message: err.message || "Failed to query LinkedIn session."
    };
  }
}

// Ensure content script is injected into the LinkedIn tab and verified with target version
async function ensureLinkedInContentScript(tabId) {
  const TARGET_VERSION = "1.0.3";
  try {
    const pingResult = await new Promise((resolve) => {
      chrome.tabs.sendMessage(tabId, { action: "PING" }, (res) => {
        const err = chrome.runtime.lastError;
        if (err || !res) {
          resolve({ ok: false, error: err ? err.message : "no_response" });
        } else {
          resolve({ ok: true, version: res.version, url: res.url });
        }
      });
      setTimeout(() => resolve({ ok: false, error: "ping_timeout" }), 500);
    });

    console.log(`[Extension Background] [SCRIPT_CHECK] Tab ${tabId} PING result:`, pingResult);

    const needsInject = !pingResult.ok || pingResult.version !== TARGET_VERSION;

    if (needsInject && chrome.scripting) {
      console.log(`[Extension Background] Injecting content_linkedin.js v${TARGET_VERSION} into tab ${tabId} (previous: ${pingResult.version || 'none'}, reason: ${pingResult.error || 'version_mismatch'})`);
      await chrome.scripting.executeScript({
        target: { tabId: tabId },
        files: ["content_linkedin.js"]
      });
      // Short delay after injection
      await new Promise(r => setTimeout(r, 300));

      // Post-injection verification
      const verifyPing = await new Promise((resolve) => {
        chrome.tabs.sendMessage(tabId, { action: "PING" }, (res) => {
          const err = chrome.runtime.lastError;
          if (err || !res) {
            resolve({ ok: false, error: err ? err.message : "verify_failed" });
          } else {
            resolve({ ok: true, version: res.version });
          }
        });
        setTimeout(() => resolve({ ok: false, error: "verify_timeout" }), 500);
      });
      console.log(`[Extension Background] [SCRIPT_CHECK] Tab ${tabId} Post-injection verification:`, verifyPing);
      return verifyPing;
    }

    return pingResult;
  } catch (err) {
    console.warn(`[Extension Background] Script injection notice:`, err.message);
    return { ok: false, error: err.message };
  }
}

// Select the most appropriate authenticated LinkedIn tab among open tabs
async function findBestLinkedInTab() {
  console.log("[FameWeb Background] Querying open tabs matching *://*.linkedin.com/*");
  const tabs = await chrome.tabs.query({ url: "*://*.linkedin.com/*" });
  if (!tabs || tabs.length === 0) {
    console.log("[FameWeb Background] No open LinkedIn tab found.");
    return {
      found: false,
      status: "NO_LINKEDIN_TAB",
      error: "NO_LINKEDIN_TAB",
      message: "No open LinkedIn tab found. Please open LinkedIn in your browser and sign in."
    };
  }

  console.log(`[FameWeb Background] Found ${tabs.length} open LinkedIn tabs.`);

  // Find best tab synchronously by inspecting URLs
  let bestTab = null;
  let fallbackTab = null;

  for (const tab of tabs) {
    const url = tab.url || "";
    if (url.includes("/login") || url.includes("/checkpoint") || url.includes("/uas/login")) {
      continue;
    }

    if (!fallbackTab) fallbackTab = tab;

    if (url.includes("/in/")) {
      bestTab = tab;
      break;
    }
  }

  const selectedTab = bestTab || fallbackTab || tabs[0];
  const selectedUrl = selectedTab.url || "";
  const isProfile = selectedUrl.includes("/in/");

  console.log(`[FameWeb Background] Selected tab ID: ${selectedTab.id}, URL: ${selectedUrl}`);

  return {
    found: true,
    status: "LINKEDIN_TAB_FOUND",
    tab: selectedTab,
    tabId: selectedTab.id,
    url: selectedUrl,
    current_url: selectedUrl,
    isProfileUrl: isProfile,
    isLoginPage: selectedUrl.includes("/login") || selectedUrl.includes("/checkpoint")
  };
}

// Automatically navigate and extract profile from LinkedIn
async function autoNavigateAndExtractProfile(targetProfileUrl = null, reqId = "unknown", senderTab = null) {
  console.log(`[Extension Background] EXTRACT_OWN_PROFILE started: ${reqId}`);
  const originTabId = senderTab ? senderTab.id : null;
  const originWindowId = senderTab ? senderTab.windowId : null;

  // Step 1: Check if LinkedIn session is active
  const sessionCheck = await checkLinkedInSession();
  if (!sessionCheck.authenticated) {
    console.warn(`[Extension Background] LinkedIn session check failed: ${reqId}`);
    return {
      success: false,
      error: "NOT_LOGGED_IN",
      message: "You are not logged in to LinkedIn. Please open LinkedIn and sign in."
    };
  }

  // Step 2: Locate LinkedIn tab
  const tabLoc = await findBestLinkedInTab();
  if (!tabLoc.found) {
    console.warn(`[Extension Background] No target tab found: ${reqId}`);
    return {
      success: false,
      error: tabLoc.error,
      message: tabLoc.message
    };
  }

  const targetTab = tabLoc.tab;
  const tabId = targetTab.id;
  console.log(`[Extension Background] Target tab: ${tabId}, windowId: ${targetTab.windowId}`);

  // Helper promise for messaging tab with timeout
  const sendToTab = (msg, timeoutMs = 8000) => new Promise((resolve) => {
    let resolved = false;
    const timer = setTimeout(() => {
      if (!resolved) {
        resolved = true;
        console.warn(`[Extension Background] sendToTab timed out (${msg.action}) on tab ${tabId}`);
        resolve({ success: false, error: "TAB_MESSAGE_TIMEOUT", message: `Tab message timed out: ${msg.action}` });
      }
    }, timeoutMs);

    chrome.tabs.sendMessage(tabId, msg, (res) => {
      if (resolved) return;
      resolved = true;
      clearTimeout(timer);
      const err = chrome.runtime.lastError;
      if (err) {
        resolve({ success: false, error: "MESSAGE_ERROR", message: err.message });
      } else {
        resolve(res || { success: false, error: "EMPTY_RESPONSE" });
      }
    });
  });

  // Helper to safely restore focus to original FameWeb tab/window
  const restoreOriginFocus = async () => {
    try {
      if (originTabId) {
        await chrome.tabs.update(originTabId, { active: true });
      }
      if (originWindowId) {
        await chrome.windows.update(originWindowId, { focused: true });
      }
    } catch (e) {
      console.debug("[Extension Background] Notice restoring original tab focus:", e.message);
    }
  };

  try {
    // Bring LinkedIn tab and window into focus so lazy loading and IntersectionObserver fire
    try {
      if (targetTab.windowId) {
        await chrome.windows.update(targetTab.windowId, { focused: true });
      }
      await chrome.tabs.update(tabId, { active: true });
    } catch (focusErr) {
      console.warn("[Extension Background] Could not activate LinkedIn tab/window:", focusErr.message);
    }

    // Ensure content script is running in target tab with version check
    await ensureLinkedInContentScript(tabId);
    console.log(`[Extension Background] Content script availability: verified for tab ${tabId}`);

    // Step 3: Determine own-profile destination URL
    // ALWAYS verify self-profile ownership; never blindly trust an arbitrary /in/ URL
    let destinationUrl = null;
    const pageCheck = await sendToTab({ action: "INSPECT_CURRENT_PAGE" }, 4000);

    if (pageCheck && pageCheck.success && pageCheck.isSelfProfileLikely && pageCheck.currentUrl) {
      console.log(`[Extension Background] Target tab is already verified self-profile: ${pageCheck.currentUrl}`);
      destinationUrl = pageCheck.currentUrl;
    } else {
      // Discover own profile from DOM navigation elements
      const discovery = await sendToTab({ action: "DISCOVER_OWN_PROFILE" }, 5000);
      console.log(`[Extension Background] Own-profile discovery: ${discovery.discoveryMethod || discovery.error || 'done'}`);
      if (discovery.success && discovery.profileUrl && discovery.discoveryMethod !== "current_self_profile") {
        destinationUrl = discovery.profileUrl;
      } else if (discovery.error === "NOT_AUTHENTICATED" || discovery.isLoginPage) {
        await restoreOriginFocus();
        return {
          success: false,
          error: "NOT_LOGGED_IN",
          message: "Your LinkedIn session is not authenticated. Please log in to LinkedIn."
        };
      } else if (discovery.error === "CHALLENGE_DETECTED") {
        await restoreOriginFocus();
        return {
          success: false,
          error: "CHALLENGE_DETECTED",
          message: "LinkedIn verification challenge detected. Please resolve it in your LinkedIn tab."
        };
      } else {
        // Safe LinkedIn route: /in/me/ natively redirects logged-in user to their own profile
        destinationUrl = "https://www.linkedin.com/in/me/";
      }
    }

    // Step 4: Check if already on the destination profile page
    const currentTabUrl = (targetTab.url || "").split('?')[0].replace(/\/+$/, '');
    const cleanDest = destinationUrl.split('?')[0].replace(/\/+$/, '');
    const isAlreadyThere = currentTabUrl === cleanDest && pageCheck?.isSelfProfileLikely;

    if (!isAlreadyThere) {
      console.log(`[Extension Background] Navigation: navigating tab ${tabId} to ${destinationUrl}`);
      await new Promise((resolve) => {
        chrome.tabs.update(tabId, { url: destinationUrl }, (updatedTab) => {
          resolve(updatedTab);
        });
      });

      // Wait for tab load completion with strict timeout
      await new Promise((resolve) => {
        let resolved = false;
        const timer = setTimeout(() => {
          if (!resolved) {
            resolved = true;
            chrome.tabs.onUpdated.removeListener(listener);
            console.log(`[Extension Background] Navigation load timer expired, continuing to DOM check`);
            resolve();
          }
        }, 6000);

        const listener = (tid, changeInfo) => {
          if (tid === tabId && changeInfo.status === 'complete') {
            if (!resolved) {
              resolved = true;
              clearTimeout(timer);
              chrome.tabs.onUpdated.removeListener(listener);
              console.log(`[Extension Background] Navigation: tab load complete`);
              resolve();
            }
          }
        };
        chrome.tabs.onUpdated.addListener(listener);
      });

      // Re-verify/inject content script after navigation
      await ensureLinkedInContentScript(tabId);
      await new Promise(r => setTimeout(r, 400));
    } else {
      console.log(`[Extension Background] Navigation: tab ${tabId} already on self profile page`);
    }

    // Step 5: Wait for profile DOM rendering & lazy load scroll
    console.log(`[Extension Background] Profile render wait: starting check on tab ${tabId}`);
    const renderCheck = await sendToTab({ action: "WAIT_FOR_PROFILE_RENDER", maxRetries: 10, intervalMs: 400 }, 7000);
    console.log(`[Extension Background] Profile render wait: result = ${renderCheck.rendered ? 'rendered' : renderCheck.error || 'done'}`);
    if (!renderCheck.success && renderCheck.error === "SESSION_EXPIRED") {
      await restoreOriginFocus();
      return {
        success: false,
        error: "SESSION_EXPIRED",
        message: "LinkedIn redirected to sign-in page. Please log in to your LinkedIn account."
      };
    }
    if (!renderCheck.success && renderCheck.error === "CHALLENGE_DETECTED") {
      await restoreOriginFocus();
      return {
        success: false,
        error: "CHALLENGE_DETECTED",
        message: "LinkedIn is showing a verification challenge or CAPTCHA. Please complete it in the browser."
      };
    }

    // Step 6: Extract profile DOM (includes progressive section scrolling inside content_linkedin.js)
    console.log(`[Extension Background] Dispatching EXTRACT_OWN_PROFILE_DOM to tab ${tabId}`);
    const extraction = await sendToTab({ action: "EXTRACT_OWN_PROFILE_DOM", requestId: reqId }, 15000);
    console.log(`[Extension Background] Extraction response returned: ${reqId}. Success = ${extraction?.success}`);

    // Step 7: Sequential detail page extraction for Experience, Education, Skills, and Certifications
    if (extraction && extraction.success && extraction.data) {
      const DETAIL_SECTIONS = [
        { kind: "experience", url: "https://www.linkedin.com/in/me/details/experience/" },
        { kind: "education", url: "https://www.linkedin.com/in/me/details/education/" },
        { kind: "skills", url: "https://www.linkedin.com/in/me/details/skills/" },
        { kind: "certifications", url: "https://www.linkedin.com/in/me/details/certifications/" }
      ];

      for (const section of DETAIL_SECTIONS) {
        try {
          console.log(`[Extension Background] Navigating to detail page (${section.kind}): ${section.url}`);
          await new Promise((resolve) => {
            chrome.tabs.update(tabId, { url: section.url }, (updatedTab) => resolve(updatedTab));
          });

          await new Promise((resolve) => {
            let resolved = false;
            const timer = setTimeout(() => {
              if (!resolved) {
                resolved = true;
                chrome.tabs.onUpdated.removeListener(listener);
                console.log(`[Extension Background] Detail load timer expired for ${section.kind}`);
                resolve();
              }
            }, 6000);

            const listener = (tid, changeInfo) => {
              if (tid === tabId && changeInfo.status === 'complete') {
                if (!resolved) {
                  resolved = true;
                  clearTimeout(timer);
                  chrome.tabs.onUpdated.removeListener(listener);
                  console.log(`[Extension Background] Detail page loaded: ${section.kind}`);
                  resolve();
                }
              }
            };
            chrome.tabs.onUpdated.addListener(listener);
          });

          await ensureLinkedInContentScript(tabId);
          await new Promise(r => setTimeout(r, 400));

          console.log(`[Extension Background] Requesting detail list DOM for ${section.kind}`);
          const detailRes = await sendToTab({ action: "EXTRACT_DETAIL_LIST_DOM", kind: section.kind, requestId: reqId }, 12000);

          if (detailRes && detailRes.success && Array.isArray(detailRes.items) && detailRes.items.length > 0) {
            console.log(`[Extension Background] Detail page extracted ${detailRes.items.length} items for ${section.kind}`);
            extraction.data[section.kind] = detailRes.items;
          } else {
            console.warn(`[Extension Background] Detail extraction fallback for ${section.kind}: preserving top-card subset`);
          }
        } catch (detailErr) {
          console.warn(`[Extension Background] Detail extraction failed for ${section.kind}:`, detailErr.message);
        }
      }

      // Return tab to /in/me/ so user is left on their main profile
      try {
        console.log(`[Extension Background] Returning tab to /in/me/`);
        await new Promise((resolve) => {
          chrome.tabs.update(tabId, { url: "https://www.linkedin.com/in/me/" }, () => resolve());
        });
        await new Promise(r => setTimeout(r, 600));
      } catch (retErr) {
        console.warn(`[Extension Background] Failed to return tab to /in/me/:`, retErr.message);
      }

      // Update metadata and diagnostic counts
      const expCount = (extraction.data.experience || []).length;
      const eduCount = (extraction.data.education || []).length;
      const skillsCount = (extraction.data.skills || []).length;
      const certCount = (extraction.data.certifications || []).length;
      let sectionsCount = 0;
      if (extraction.data.name) sectionsCount++;
      if (extraction.data.about) sectionsCount++;
      if (expCount > 0) sectionsCount++;
      if (eduCount > 0) sectionsCount++;
      if (skillsCount > 0) sectionsCount++;
      if (certCount > 0) sectionsCount++;

      if (extraction.metadata) {
        extraction.metadata.sections_found = sectionsCount;
        if (extraction.metadata.diagnostic) {
          extraction.metadata.diagnostic.experience_count = expCount;
          extraction.metadata.diagnostic.education_count = eduCount;
          extraction.metadata.diagnostic.skills_count = skillsCount;
          extraction.metadata.diagnostic.certifications_count = certCount;
          extraction.metadata.diagnostic.multi_page_merged = true;
        }
      }
    }

    await restoreOriginFocus();
    return extraction;
  } catch (err) {
    console.error(`[Extension Background] Exception in autoNavigateAndExtractProfile:`, err);
    await restoreOriginFocus();
    return {
      success: false,
      error: "EXTRACTION_EXCEPTION",
      message: err.message || "An error occurred during profile extraction."
    };
  }
}

// Per-tab in-flight extraction locks to serialize searches and prevent concurrent navigation collision
const tabExtractionLocks = new Map();

// Automatically clean up locks if a tab is closed
if (chrome.tabs && chrome.tabs.onRemoved) {
  chrome.tabs.onRemoved.addListener((closedTabId) => {
    if (tabExtractionLocks.has(closedTabId)) {
      console.log(`[Extension Background] Releasing extraction lock for closed tab ${closedTabId}`);
      tabExtractionLocks.delete(closedTabId);
    }
  });
}

// Execute user-controlled LinkedIn search navigation and visible DOM result extraction
async function openLinkedInSearchAndExtract(searchUrl, queryContext = {}, reqId = "unknown", senderTab = null) {
  console.log(`[Extension Background] OPEN_LINKEDIN_SEARCH started: ${reqId}. Target: ${searchUrl}`);
  const originTabId = senderTab ? senderTab.id : null;
  const originWindowId = senderTab ? senderTab.windowId : null;

  // Step 1: Session check
  const sessionCheck = await checkLinkedInSession();
  if (!sessionCheck.authenticated) {
    return {
      success: false,
      error: "NOT_LOGGED_IN",
      message: "No active LinkedIn session found. Please open LinkedIn and sign in."
    };
  }

  // Step 2: Locate or open a LinkedIn tab
  let targetTab = null;
  let tabId = null;
  let tabCreatedNew = false;

  const tabLoc = await findBestLinkedInTab();
  if (tabLoc.found && tabLoc.tab) {
    targetTab = tabLoc.tab;
    tabId = targetTab.id;
    console.log(`[Extension Background] [SEARCH_TAB] Search tab selected from existing tabs: ID ${tabId}, URL: ${targetTab.url}`);
  } else {
    // Open a new LinkedIn tab for the search if none exists
    targetTab = await new Promise((resolve) => {
      chrome.tabs.create({ url: searchUrl, active: true }, (newTab) => resolve(newTab));
    });
    tabId = targetTab.id;
    tabCreatedNew = true;
    console.log(`[Extension Background] [SEARCH_TAB] New LinkedIn search tab created: ID ${tabId}, URL: ${searchUrl}`);
  }

  // Step 3: Check and acquire per-tab lock to prevent concurrent extraction races
  if (tabExtractionLocks.has(tabId)) {
    const activeReq = tabExtractionLocks.get(tabId);
    console.warn(`[Extension Background] Tab ${tabId} is currently locked by active search ${activeReq}. Rejecting concurrent search ${reqId}`);
    return {
      success: false,
      status: "TAB_BUSY",
      error: "TAB_BUSY",
      message: `An extraction is already in progress on this LinkedIn tab (${activeReq}). Please wait for it to complete.`,
      count: 0,
      results: []
    };
  }

  tabExtractionLocks.set(tabId, reqId);
  console.log(`[Extension Background] Acquired extraction lock on tab ${tabId} for request ${reqId}`);

  // Helper promise for messaging tab with timeout
  const sendToTab = (msg, timeoutMs = 12000) => new Promise((resolve) => {
    let resolved = false;
    const timer = setTimeout(() => {
      if (!resolved) {
        resolved = true;
        console.warn(`[Extension Background] sendToTab timed out (${msg.action}) on tab ${tabId} after ${timeoutMs}ms`);
        resolve({ success: false, error: "TAB_MESSAGE_TIMEOUT", message: `Tab message timed out: ${msg.action}` });
      }
    }, timeoutMs);

    chrome.tabs.sendMessage(tabId, msg, (res) => {
      if (resolved) return;
      resolved = true;
      clearTimeout(timer);
      const err = chrome.runtime.lastError;
      if (err) {
        console.warn(`[Extension Background] sendToTab chrome.runtime.lastError (${msg.action}) on tab ${tabId}:`, err.message);
        resolve({ success: false, error: "MESSAGE_ERROR", message: err.message });
      } else {
        resolve(res || { success: false, error: "EMPTY_RESPONSE" });
      }
    });
  });

  try {
    // Activate target tab so lazy loaded result cards render
    if (targetTab.windowId) {
      await chrome.windows.update(targetTab.windowId, { focused: true });
    }
    await chrome.tabs.update(tabId, { active: true });

    // Detailed stage logs for target tab
    console.log(`[Extension Background] [STAGE 1: TAB_SELECTED] Target Tab ID: ${tabId}, initial URL: ${targetTab.url}, windowId: ${targetTab.windowId}`);

    // Navigate tab to search URL
    console.log(`[Extension Background] [STAGE 2: NAVIGATING] Navigating tab ${tabId} to search URL: ${searchUrl}`);
    await new Promise((resolve) => {
      chrome.tabs.update(tabId, { url: searchUrl }, (updated) => resolve(updated));
    });

    // Wait for tab load completion
    let navStatus = "TIMER_EXPIRED";
    await new Promise((resolve) => {
      let resolved = false;
      const timer = setTimeout(() => {
        if (!resolved) {
          resolved = true;
          chrome.tabs.onUpdated.removeListener(listener);
          console.log(`[Extension Background] [STAGE 3: NAV_WAIT] Tab navigation wait timer expired for tab ${tabId}`);
          resolve();
        }
      }, 7000);

      const listener = (tid, changeInfo, tabObj) => {
        if (tid === tabId && changeInfo.status === 'complete') {
          if (!resolved) {
            resolved = true;
            clearTimeout(timer);
            chrome.tabs.onUpdated.removeListener(listener);
            navStatus = "STATUS_COMPLETE";
            console.log(`[Extension Background] [STAGE 3: NAV_WAIT] Tab navigation completed: tab ${tabId}, title: "${tabObj?.title}", url: ${tabObj?.url}`);
    console.log(`[Extension Background] [SEARCH_TAB] Search navigation completed on tab ${tabId}: "${tabObj?.url}"`);
            resolve();
          }
        }
      };
      chrome.tabs.onUpdated.addListener(listener);
    });

    // Inspect tab state after navigation
    const currentTabState = await new Promise((resolve) => {
      chrome.tabs.get(tabId, (t) => resolve(t || {}));
    });
    console.log(`[Extension Background] [STAGE 4: TAB_VERIFIED] Tab ${tabId} post-nav: url="${currentTabState.url}", title="${currentTabState.title}", status="${currentTabState.status}"`);

    // Ensure content script is active
    const scriptCheck = await ensureLinkedInContentScript(tabId);
    console.log(`[Extension Background] [STAGE 5: SCRIPT_CHECK] ensureLinkedInContentScript result:`, scriptCheck);
    await new Promise(r => setTimeout(r, 400));

    // Request visible search results from content_linkedin.js with bounded wait inside
    console.log(`[Extension Background] [STAGE 6: DISPATCH_EXTRACT] Requesting EXTRACT_SEARCH_RESULTS_DOM on tab ${tabId}`);
    const resultsResponse = await sendToTab({
      action: "EXTRACT_SEARCH_RESULTS_DOM",
      requestId: reqId,
      queryContext: queryContext
    }, 15000);

    console.log(`[Extension Background] [STAGE 7: RESPONSE_RECEIVED] Response received from tab ${tabId}:`, {
      success: resultsResponse?.success,
      status: resultsResponse?.status,
      count: resultsResponse?.count,
      error: resultsResponse?.error,
      diagnostic: resultsResponse?.diagnostic
    });
    console.log(`[Extension Background] [SEARCH_TAB] Extraction response received from LinkedIn search tab ${tabId}. Status: ${resultsResponse?.status}`);

    // DEBUGGING / DOM INSPECTION: Keep the LinkedIn search tab open and in active focus.
    // Do NOT close the tab, and do NOT switch focus back to the origin tab, allowing the developer/user
    // to inspect the rendered LinkedIn DOM, profile cards, and network attributes in DevTools.
    console.log(`[Extension Background] [SEARCH_TAB] Search tab ${tabId} intentionally kept open and active for DOM inspection.`);

    const count = (resultsResponse?.results || []).length;
    const unverifiedSignals = resultsResponse?.unverified_signals || [];
    const isSuccess = !!resultsResponse?.success && (count > 0 || unverifiedSignals.length > 0);
    const status = resultsResponse?.status || (count > 0 ? "RESULTS_EXTRACTED" : (unverifiedSignals.length > 0 ? "ANONYMOUS_OUT_OF_NETWORK_RESULTS" : "NO_RESULTS"));

    console.log(`[Extension Background] [STAGE 8: FINAL_OUTCOME] Search result for ${reqId}: status=${status}, verifiedCount=${count}, unverifiedSignalsCount=${unverifiedSignals.length}`);

    return {
      success: isSuccess,
      status: status,
      tabId: tabId,
      tabUrl: currentTabState.url || searchUrl,
      tabTitle: currentTabState.title || "",
      navigationStatus: navStatus,
      searchUrl: searchUrl,
      queryContext: queryContext,
      results: resultsResponse?.results || [],
      unverified_signals: unverifiedSignals,
      count: count,
      diagnostic: resultsResponse?.diagnostic || null,
      renderState: resultsResponse?.renderState || null,
      error: resultsResponse?.error || (count === 0 && unverifiedSignals.length === 0 ? status : undefined),
      message: resultsResponse?.message || (count === 0 ? `Zero prospects extracted (status: ${status})` : `Extracted ${count} prospects`)
    };
  } catch (err) {
    console.error(`[Extension Background] Error in openLinkedInSearchAndExtract:`, err);
    console.log(`[Extension Background] [SEARCH_TAB] Search tab ${tabId} intentionally kept open despite error for DOM inspection.`);
    return {
      success: false,
      status: "SEARCH_EXECUTION_ERROR",
      error: "SEARCH_EXECUTION_ERROR",
      message: err.message || "Failed to execute LinkedIn search",
      count: 0,
      results: []
    };
  } finally {
    if (tabId && tabExtractionLocks.has(tabId)) {
      tabExtractionLocks.delete(tabId);
      console.log(`[Extension Background] Released extraction lock on tab ${tabId} for request ${reqId}`);
    }
  }
}

// Handle internal messages from content scripts and popup
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || typeof message !== "object") return;

  const action = message.action;

  if (action === "PING_EXTENSION") {
    sendResponse({
      success: true,
      extensionInstalled: true,
      version: "1.0.3"
    });
    return true;
  }

  if (action === "VERIFY_LINKEDIN_SESSION") {
    checkLinkedInSession().then(result => {
      sendResponse({
        success: true,
        extensionInstalled: true,
        ...result
      });
    }).catch(err => {
      sendResponse({
        success: false,
        extensionInstalled: true,
        status: "VERIFICATION_FAILED",
        authenticated: false,
        message: err.message
      });
    });
    return true; // Keep message channel open for async response
  }

  // Check what LinkedIn page is currently open before extracting
  if (action === "CHECK_LINKEDIN_ACTIVE_TAB") {
    const reqId = message.requestId || "unknown";
    console.log(`[Extension Background] Request received: ${reqId} (CHECK_TAB)`);
    findBestLinkedInTab().then(res => {
      console.log(`[Extension Background] Request completed: ${reqId} (CHECK_TAB):`, res.status);
      sendResponse({
        success: res.found,
        status: res.status || (res.found ? "LINKEDIN_TAB_FOUND" : "NO_LINKEDIN_TAB"),
        tabId: res.tabId,
        url: res.url,
        current_url: res.current_url,
        isProfileUrl: res.isProfileUrl,
        isLoginPage: res.isLoginPage,
        error: res.error,
        message: res.message
      });
    }).catch(err => {
      console.error(`[Extension Background] Error in findBestLinkedInTab (${reqId}):`, err);
      sendResponse({
        success: false,
        status: "TAB_CHECK_FAILED",
        error: "TAB_QUERY_ERROR",
        message: err.message
      });
    });
    return true;
  }

  // Execute fully automatic profile discovery, navigation, and DOM extraction
  if (action === "EXTRACT_OWN_PROFILE") {
    const reqId = message.requestId || "unknown";
    const targetUrl = message.targetProfileUrl || null;
    const senderTab = sender.tab || null;
    console.log(`[Extension Background] Request received: ${reqId} (EXTRACT_PROFILE). Target URL:`, targetUrl);
    autoNavigateAndExtractProfile(targetUrl, reqId, senderTab).then(result => {
      console.log(`[Extension Background] Request completed: ${reqId} (EXTRACT_PROFILE). Success:`, result?.success);
      sendResponse(result || { success: false, error: "EXTRACTION_EMPTY" });
    }).catch(err => {
      console.error(`[Extension Background] Error in autoNavigateAndExtractProfile (${reqId}):`, err);
      sendResponse({ success: false, error: "AUTOMATIC_EXTRACTION_ERROR", message: err.message });
    });
    return true;
  }

  // Execute user-initiated LinkedIn search and return visible DOM results
  if (action === "OPEN_LINKEDIN_SEARCH") {
    const reqId = message.requestId || "unknown";
    const searchUrl = message.searchUrl;
    const queryContext = message.queryContext || {};
    const senderTab = sender.tab || null;

    console.log(`[Extension Background] Request received: ${reqId} (OPEN_LINKEDIN_SEARCH)`);
    if (!searchUrl) {
      sendResponse({ success: false, error: "MISSING_SEARCH_URL", message: "searchUrl is required." });
      return true;
    }

    openLinkedInSearchAndExtract(searchUrl, queryContext, reqId, senderTab).then(res => {
      console.log(`[Extension Background] Search completed: ${reqId} (${res.count || 0} results)`);
      sendResponse(res);
    }).catch(err => {
      console.error(`[Extension Background] Error in openLinkedInSearchAndExtract (${reqId}):`, err);
      sendResponse({ success: false, error: "SEARCH_FAILED", message: err.message, results: [] });
    });
    return true;
  }
});
