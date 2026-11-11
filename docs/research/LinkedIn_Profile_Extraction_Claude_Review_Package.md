# Technical Reference Package: LinkedIn Profile DOM Extraction & Extension Flow

**Target Document:** For Independent Code Review by External AI (Claude)  
**System:** FameWeb LinkedIn Lead Generator & Profile Optimization  
**Repository:** `D:\Programming\FameWebs_Internship\linkedin_lead_generator`  
**Date:** November 2026  
**Status:** Read-Only Reference Package (No Credentials / No Private Tokens / No PII)

---

## 1. Executive Summary & Problem Definition

### Context
FameWeb is a web application (Flask + PostgreSQL + Vanilla JS) that optimizes user LinkedIn profiles for GTM (Go-To-Market) positioning using Google Gemini.

Because LinkedIn does not provide public profile APIs without Enterprise partnerships, FameWeb uses an unpacked Chrome Extension (Manifest V3) named **FameWeb LinkedIn Integrator** (v1.0.1). The extension runs locally in the user's browser, communicates with the FameWeb web app via `window.postMessage`, locates the user's authenticated LinkedIn tab, navigates to their own profile, progressively scrolls to trigger lazy loading, parses visible DOM sections (Name, Headline, About, Experience, Education, Skills, Certifications), and sends the sanitized JSON structure back to FameWeb to persist in `UsersLinkedinDetails`.

### The Core Problem Under Review
1. Tab discovery (`CHECK_LINKEDIN_ACTIVE_TAB`) works reliably and finds the open LinkedIn tab (`status: "LINKEDIN_TAB_FOUND"`).
2. Profile extraction request (`EXTRACT_OWN_PROFILE`) executes, navigates or redirects, and completes with HTTP 200 persistence on FameWeb.
3. **However, only the user's basic identity (Name) is ever extracted.**
   - Experience: `0 roles`
   - Education: `0 entries`
   - Skills: `0 skills`
   - About: `Not found`
4. In extension version **v1.0.1**, bounded progressive scrolling (`autoScrollAndLoadSections()`) and explicit milestone diagnostics were added to `content_linkedin.js`:
   - `[LinkedIn Extraction] AUTO_SCROLL_STARTED`
   - `[LinkedIn Extraction] EXPERIENCE_SECTION_IN_VIEW`
   - `[LinkedIn Extraction] EDUCATION_SECTION_IN_VIEW`
   - `[LinkedIn Extraction] SKILLS_SECTION_IN_VIEW`
   - `[LinkedIn Extraction] AUTO_SCROLL_COMPLETED`
   - `[LinkedIn Extraction] PROFILE_SECTION_DISCOVERY`
   - `[LinkedIn Extraction] DOM_EXTRACTION_COMPLETED`
5. **Critical Finding:** When the user clicks "Import My LinkedIn Profile" in FameWeb, **none of these logs appear in the LinkedIn tab's Developer Tools Console.**
   - The extraction returns quickly with only the `name` populated.
   - FameWeb UI shows:
     > **Partial Profile Import: Tony Stark**  
     > *Only basic header information (name) could be found on the open page.*  
     > *Experience: 0 roles | Skills: 0 skills | About: Not found*  
     > *Tip: Open your LinkedIn tab, scroll down once so LinkedIn renders your Experience & Skills sections, then click Re-import below.*

An independent architecture and code review is required to determine why `content_linkedin.js` is either:
- Not being executed in the target tab/frame,
- Running against a stale script version cached by Chrome,
- Running against an unexpected LinkedIn URL/DOM structure, or
- Bypassing the scroll and section discovery routines due to an execution branch or timing mismatch in `background.js` or `content_linkedin.js`.

---

## 2. Architecture & Complete Message Flow

```
[ FameWeb Web Page ]
  (http://localhost:5000/profile-optimization)
         │
         │  1. window.postMessage("FAMEWEB_EXT_CHECK_TAB_REQUEST")
         ▼
[ content_fameweb.js ] (Content script on http://localhost:5000/*)
         │
         │  2. chrome.runtime.sendMessage({ action: "CHECK_LINKEDIN_ACTIVE_TAB" })
         ▼
[ background.js ] (MV3 Service Worker)
         │  Queries chrome.tabs.query({ url: "*://*.linkedin.com/*" })
         │  Returns selected tab info
         ▼
[ content_fameweb.js ]
         │  3. window.postMessage("FAMEWEB_EXT_CHECK_TAB_RESPONSE")
         ▼
[ profile-optimization.js ]
         │
         │  4. window.postMessage("FAMEWEB_EXT_IMPORT_REQUEST", { targetProfileUrl })
         ▼
[ content_fameweb.js ]
         │
         │  5. chrome.runtime.sendMessage({ action: "EXTRACT_OWN_PROFILE", ... })
         ▼
[ background.js ] (MV3 Service Worker)
         │  a. checkLinkedInSession() via chrome.cookies.getAll({ domain: ".linkedin.com" })
         │  b. findBestLinkedInTab()
         │  c. ensureLinkedInContentScript(tabId)
         │  d. chrome.tabs.sendMessage(tabId, { action: "DISCOVER_OWN_PROFILE" })
         │  e. If not on profile URL: chrome.tabs.update(tabId, { url: destinationUrl })
         │     + wait for tabs.onUpdated (status === 'complete')
         │     + re-verify ensureLinkedInContentScript(tabId)
         │  f. chrome.tabs.sendMessage(tabId, { action: "WAIT_FOR_PROFILE_RENDER" })
         │  g. chrome.tabs.sendMessage(tabId, { action: "EXTRACT_OWN_PROFILE_DOM" })
         ▼
[ content_linkedin.js ] (Injected into https://*.linkedin.com/*)
         │  a. autoScrollAndLoadSections(): Steps down 650px increments (max 5 steps / 3.8s)
         │  b. inspectProfilePage()
         │  c. extractProfileFromDom():
         │     - Name & Photo: top card selectors
         │     - Headline & Location
         │     - findSection(["about"]): expands 'see more', grabs text
         │     - findSection(["experience"]): parses role items
         │     - findSection(["education"]): parses school items
         │     - findSection(["skills"]): parses skill list
         │     - findSection(["certifications"]): parses cert items
         │  d. Returns { success: true, data: { name, headline, about, experience, ... }, metadata }
         ▼
[ background.js ]
         │  Returns extraction payload to caller
         ▼
[ content_fameweb.js ]
         │  6. window.postMessage("FAMEWEB_EXT_IMPORT_RESPONSE", { success, data })
         ▼
[ profile-optimization.js ]
         │  7. HTTP POST /api/profile-optimization/import-extension-profile
         │     Header: X-CSRFToken, Content-Type: application/json
         │     Body: JSON.stringify(extracted_data)
         ▼
[ Flask Backend: app.py & app/routes/onboarding.py ]
         │  - import_extension_profile()
         │  - Validates payload structure and sanitized field limits
         │  - Queries/creates UsersLinkedinDetails
         │  - Persists scalar fields and JSONB arrays (experience, education, skills, profile_data)
         │  - Commits transaction
         │  - Returns JSON { success: true, sections_imported: [...], ... }
         ▼
[ profile-optimization.js ]
         │  - Updates preview card DOM without reloading
         │  - If substantive sections present -> Success banner
         │  - If only Name present -> Warning banner ("Partial Profile Import")
```

---

## 3. Detailed Component Breakdown & Complete Source Code

### 3.1 `linkedin_extension/manifest.json`

```json
{
  "manifest_version": 3,
  "name": "FameWeb LinkedIn Integrator",
  "version": "1.0.1",
  "description": "Locally connects FameWeb to your active LinkedIn session securely without sharing passwords or raw cookies.",
  "permissions": [
    "cookies",
    "tabs",
    "activeTab",
    "storage",
    "scripting"
  ],
  "host_permissions": [
    "https://*.linkedin.com/*",
    "http://localhost/*",
    "http://127.0.0.1/*",
    "http://localhost:5000/*",
    "http://127.0.0.1:5000/*"
  ],
  "background": {
    "service_worker": "background.js"
  },
  "content_scripts": [
    {
      "matches": [
        "https://*.linkedin.com/*"
      ],
      "js": [
        "content_linkedin.js"
      ],
      "run_at": "document_idle"
    },
    {
      "matches": [
        "http://localhost/*",
        "http://127.0.0.1/*",
        "http://localhost:5000/*",
        "http://127.0.0.1:5000/*"
      ],
      "js": [
        "content_fameweb.js"
      ],
      "run_at": "document_start"
    }
  ],
  "action": {
    "default_popup": "popup.html",
    "default_title": "FameWeb LinkedIn Integrator"
  }
}
```

---

### 3.2 `linkedin_extension/content_fameweb.js` (Complete File)

```javascript
// Content script injected into FameWeb localhost pages (http://localhost/*, http://127.0.0.1/*)
// Acts as a bridge between FameWeb DOM and the FameWeb LinkedIn Integrator Chrome extension.

(function() {
  const BRIDGE_EVENT_PING = "FAMEWEB_EXT_PING";
  const BRIDGE_EVENT_PONG = "FAMEWEB_EXT_PONG";
  const BRIDGE_EVENT_VERIFY_REQUEST = "FAMEWEB_EXT_VERIFY_REQUEST";
  const BRIDGE_EVENT_VERIFY_RESPONSE = "FAMEWEB_EXT_VERIFY_RESPONSE";
  const BRIDGE_EVENT_CHECK_TAB_REQUEST = "FAMEWEB_EXT_CHECK_TAB_REQUEST";
  const BRIDGE_EVENT_CHECK_TAB_RESPONSE = "FAMEWEB_EXT_CHECK_TAB_RESPONSE";
  const BRIDGE_EVENT_IMPORT_REQUEST = "FAMEWEB_EXT_IMPORT_REQUEST";
  const BRIDGE_EVENT_IMPORT_RESPONSE = "FAMEWEB_EXT_IMPORT_RESPONSE";

  // Prevent registering duplicate listeners if script is ever re-injected
  if (window.__famewebExtensionBridgeInitialized) {
    return;
  }
  window.__famewebExtensionBridgeInitialized = true;

  // Helper to safely check if Chrome extension runtime is active and context is valid
  function isExtensionRuntimeAvailable() {
    try {
      return typeof chrome !== "undefined" &&
             chrome.runtime &&
             typeof chrome.runtime.sendMessage === "function" &&
             !!chrome.runtime.id;
    } catch (e) {
      return false;
    }
  }

  // Mark DOM element or dataset to indicate extension presence immediately
  try {
    document.documentElement.dataset.famewebExtensionInstalled = "true";
  } catch (e) {}

  // 1. Listen for window messages dispatched from FameWeb frontend
  window.addEventListener("message", (event) => {
    // Only accept messages from the current window
    if (event.source !== window || !event.data || typeof event.data !== "object") {
      return;
    }

    const { type, requestId } = event.data;

    // A. Ping Handshake
    if (type === BRIDGE_EVENT_PING) {
      if (!isExtensionRuntimeAvailable()) {
        window.postMessage({
          type: BRIDGE_EVENT_PONG,
          requestId: requestId,
          installed: false,
          error: "EXTENSION_CONTEXT_INVALID",
          message: "Chrome extension context invalidated. Please refresh the page."
        }, "*");
        return;
      }

      try {
        chrome.runtime.sendMessage({ action: "PING_EXTENSION" }, (response) => {
          const lastErr = chrome.runtime.lastError;
          window.postMessage({
            type: BRIDGE_EVENT_PONG,
            requestId: requestId,
            installed: !lastErr && !!response?.extensionInstalled,
            version: response?.version || "1.0.0"
          }, "*");
        });
      } catch (err) {
        window.postMessage({
          type: BRIDGE_EVENT_PONG,
          requestId: requestId,
          installed: false,
          error: "RUNTIME_ERROR",
          message: err.message
        }, "*");
      }
      return;
    }

    // B. Verify LinkedIn Session Request
    if (type === BRIDGE_EVENT_VERIFY_REQUEST) {
      if (!isExtensionRuntimeAvailable()) {
        window.postMessage({
          type: BRIDGE_EVENT_VERIFY_RESPONSE,
          requestId: requestId,
          success: false,
          status: "VERIFICATION_FAILED",
          error: "EXTENSION_CONTEXT_INVALID",
          message: "Chrome extension context invalidated. Please refresh the page."
        }, "*");
        return;
      }

      try {
        chrome.runtime.sendMessage({ action: "VERIFY_LINKEDIN_SESSION" }, (response) => {
          const lastErr = chrome.runtime.lastError;
          if (lastErr || !response) {
            window.postMessage({
              type: BRIDGE_EVENT_VERIFY_RESPONSE,
              requestId: requestId,
              success: false,
              status: "VERIFICATION_FAILED",
              message: lastErr ? lastErr.message : "Extension background failed to respond."
            }, "*");
          } else {
            window.postMessage({
              type: BRIDGE_EVENT_VERIFY_RESPONSE,
              requestId: requestId,
              ...response
            }, "*");
          }
        });
      } catch (err) {
        window.postMessage({
          type: BRIDGE_EVENT_VERIFY_RESPONSE,
          requestId: requestId,
          success: false,
          status: "VERIFICATION_FAILED",
          error: "RUNTIME_ERROR",
          message: err.message
        }, "*");
      }
      return;
    }

    // C. Check Active LinkedIn Tab
    if (type === BRIDGE_EVENT_CHECK_TAB_REQUEST) {
      console.log(`[Extension Bridge] Request received: ${requestId} (CHECK_TAB)`);
      if (!isExtensionRuntimeAvailable()) {
        console.warn(`[Extension Bridge] chrome.runtime unavailable for CHECK_TAB (reqId: ${requestId})`);
        window.postMessage({
          type: BRIDGE_EVENT_CHECK_TAB_RESPONSE,
          requestId: requestId,
          success: false,
          status: "EXTENSION_CONTEXT_INVALID",
          error: "EXTENSION_CONTEXT_INVALID",
          message: "Chrome extension was updated or invalidated. Please refresh the FameWeb page."
        }, "*");
        return;
      }

      try {
        chrome.runtime.sendMessage({ action: "CHECK_LINKEDIN_ACTIVE_TAB", requestId: requestId }, (response) => {
          const lastErr = chrome.runtime.lastError;
          console.log(`[Extension Bridge] Response dispatched to page: ${requestId} (CHECK_TAB)`, {
            success: !lastErr && !!response?.success,
            status: response?.status,
            error: lastErr ? lastErr.message : response?.error
          });
          window.postMessage({
            type: BRIDGE_EVENT_CHECK_TAB_RESPONSE,
            requestId: requestId,
            success: !lastErr && !!response?.success,
            ...(response || {}),
            message: lastErr ? lastErr.message : response?.message
          }, "*");
        });
      } catch (err) {
        console.error(`[Extension Bridge] Error calling sendMessage for CHECK_TAB:`, err);
        window.postMessage({
          type: BRIDGE_EVENT_CHECK_TAB_RESPONSE,
          requestId: requestId,
          success: false,
          status: "TAB_CHECK_FAILED",
          error: "RUNTIME_EXCEPTION",
          message: err.message
        }, "*");
      }
      return;
    }

    // D. User-Initiated Own Profile DOM Import
    if (type === BRIDGE_EVENT_IMPORT_REQUEST) {
      console.log(`[Extension Bridge] Request received: ${requestId} (EXTRACT_PROFILE)`);
      if (!isExtensionRuntimeAvailable()) {
        console.warn(`[Extension Bridge] chrome.runtime unavailable for EXTRACT_PROFILE (reqId: ${requestId})`);
        window.postMessage({
          type: BRIDGE_EVENT_IMPORT_RESPONSE,
          requestId: requestId,
          success: false,
          error: "EXTENSION_CONTEXT_INVALID",
          message: "Chrome extension was updated or invalidated. Please refresh the FameWeb page."
        }, "*");
        return;
      }

      try {
        chrome.runtime.sendMessage({
          action: "EXTRACT_OWN_PROFILE",
          requestId: requestId,
          targetProfileUrl: event.data.targetProfileUrl || null
        }, (response) => {
          const lastErr = chrome.runtime.lastError;
          console.log(`[Extension Bridge] Response dispatched to page: ${requestId} (EXTRACT_PROFILE)`, {
            success: !lastErr && !!response?.success,
            hasData: !!response?.data,
            error: lastErr ? lastErr.message : response?.error
          });
          window.postMessage({
            type: BRIDGE_EVENT_IMPORT_RESPONSE,
            requestId: requestId,
            success: !lastErr && !!response?.success,
            ...(response || {}),
            message: lastErr ? lastErr.message : response?.message
          }, "*");
        });
      } catch (err) {
        console.error(`[Extension Bridge] Error calling sendMessage for EXTRACT_PROFILE:`, err);
        window.postMessage({
          type: BRIDGE_EVENT_IMPORT_RESPONSE,
          requestId: requestId,
          success: false,
          error: "RUNTIME_EXCEPTION",
          message: err.message
        }, "*");
      }
      return;
    }
  });

  // Notify page that extension bridge is actively listening
  try {
    window.postMessage({ type: "FAMEWEB_EXT_READY", version: "1.0.0" }, "*");
  } catch (e) {}
})();
```

---

### 3.3 `linkedin_extension/background.js` (Complete File)

```javascript
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

// Ensure content script is injected into the LinkedIn tab
async function ensureLinkedInContentScript(tabId) {
  try {
    const ping = await new Promise((resolve) => {
      chrome.tabs.sendMessage(tabId, { action: "PING" }, (res) => {
        const err = chrome.runtime.lastError;
        resolve(!err && !!res);
      });
      setTimeout(() => resolve(false), 400);
    });

    if (!ping && chrome.scripting) {
      console.log(`[Extension Background] Injecting content_linkedin.js into tab ${tabId}`);
      await chrome.scripting.executeScript({
        target: { tabId: tabId },
        files: ["content_linkedin.js"]
      });
      // Short delay after injection
      await new Promise(r => setTimeout(r, 200));
    }
  } catch (err) {
    console.debug(`[Extension Background] Script injection notice:`, err.message);
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
async function autoNavigateAndExtractProfile(targetProfileUrl = null, reqId = "unknown") {
  console.log(`[Extension Background] EXTRACT_OWN_PROFILE started: ${reqId}`);

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
  console.log(`[Extension Background] Target tab: ${tabId}`);

  // Ensure content script is running in target tab
  await ensureLinkedInContentScript(tabId);
  console.log(`[Extension Background] Content script availability: verified for tab ${tabId}`);

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

  // Step 3: Determine own-profile destination URL
  let destinationUrl = targetProfileUrl && targetProfileUrl.includes('/in/') ? targetProfileUrl : null;

  if (!destinationUrl) {
    // Try to discover profile URL from target tab's DOM
    const discovery = await sendToTab({ action: "DISCOVER_OWN_PROFILE" }, 5000);
    console.log(`[Extension Background] Own-profile discovery: ${discovery.discoveryMethod || discovery.error || 'done'}`);
    if (discovery.success && discovery.profileUrl) {
      destinationUrl = discovery.profileUrl;
    } else if (discovery.error === "NOT_AUTHENTICATED" || discovery.isLoginPage) {
      return {
        success: false,
        error: "NOT_LOGGED_IN",
        message: "Your LinkedIn session is not authenticated. Please log in to LinkedIn."
      };
    } else if (discovery.error === "CHALLENGE_DETECTED") {
      return {
        success: false,
        error: "CHALLENGE_DETECTED",
        message: "LinkedIn verification challenge detected. Please resolve it in your LinkedIn tab."
      };
    } else {
      // Safe LinkedIn fallback redirect route
      destinationUrl = "https://www.linkedin.com/in/me/";
    }
  }

  // Step 4: Check if already on the destination profile page
  const currentTabUrl = (targetTab.url || "").split('?')[0].replace(/\/+$/, '');
  const cleanDest = destinationUrl.split('?')[0].replace(/\/+$/, '');
  const isAlreadyThere = currentTabUrl === cleanDest || (cleanDest.endsWith('/in/me') && currentTabUrl.includes('/in/'));

  if (!isAlreadyThere) {
    console.log(`[Extension Background] Navigation: navigating tab ${tabId} to ${destinationUrl}`);
    // Navigate tab to destination profile URL
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
      }, 5000);

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

    // Small delay for script initialization
    await new Promise(r => setTimeout(r, 400));
  } else {
    console.log(`[Extension Background] Navigation: tab ${tabId} already on profile page`);
  }

  // Step 5: Wait for profile DOM rendering & lazy load scroll
  console.log(`[Extension Background] Profile render wait: starting check on tab ${tabId}`);
  const renderCheck = await sendToTab({ action: "WAIT_FOR_PROFILE_RENDER", maxRetries: 8, intervalMs: 400 }, 6000);
  console.log(`[Extension Background] Profile render wait: result = ${renderCheck.rendered ? 'rendered' : renderCheck.error || 'done'}`);
  if (!renderCheck.success && renderCheck.error === "SESSION_EXPIRED") {
    return {
      success: false,
      error: "SESSION_EXPIRED",
      message: "LinkedIn redirected to sign-in page. Please log in to your LinkedIn account."
    };
  }
  if (!renderCheck.success && renderCheck.error === "CHALLENGE_DETECTED") {
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
  return extraction;
}

// Handle internal messages from content scripts and popup
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || typeof message !== "object") return;

  const action = message.action;

  if (action === "PING_EXTENSION") {
    sendResponse({
      success: true,
      extensionInstalled: true,
      version: "1.0.1"
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
    console.log(`[Extension Background] Request received: ${reqId} (EXTRACT_PROFILE). Target URL:`, targetUrl);
    autoNavigateAndExtractProfile(targetUrl, reqId).then(result => {
      console.log(`[Extension Background] Request completed: ${reqId} (EXTRACT_PROFILE). Success:`, result?.success);
      sendResponse(result || { success: false, error: "EXTRACTION_EMPTY" });
    }).catch(err => {
      console.error(`[Extension Background] Error in autoNavigateAndExtractProfile (${reqId}):`, err);
      sendResponse({ success: false, error: "AUTOMATIC_EXTRACTION_ERROR", message: err.message });
    });
    return true;
  }
});
```

---

### 3.4 `linkedin_extension/content_linkedin.js` (Complete File)

```javascript
// Content script running on LinkedIn tabs (https://*.linkedin.com/*)
// 1. Verifies whether LinkedIn DOM indicates an active authenticated session without reading cookies.
// 2. Extracts visible own-profile DOM data upon explicit user request from FameWeb.
// Strictly enforces zero transmission of cookies, session tokens, or authentication headers.

(function() {
  const EXTENSION_CONTENT_VERSION = "1.0.1";
  console.log(`[LinkedIn Content] content_linkedin.js v${EXTENSION_CONTENT_VERSION} initialized on ${window.location.pathname}`);

  function checkDomAuthState() {
    // Check common authenticated elements on LinkedIn desktop:
    // e.g. global nav search, profile photo / me menu, feed nav
    const hasNav = !!document.querySelector('.global-nav, .feed-shared-update-v2, nav[aria-label="Primary Navigation"], #global-nav');
    const hasMeDropdown = !!document.querySelector('.global-nav__me, img[alt*="photo"], .feed-identity-module');
    const isLoginPage = window.location.pathname.includes('/login') || window.location.pathname.includes('/checkpoint');

    return hasNav || hasMeDropdown || !isLoginPage;
  }

  function cleanText(text) {
    if (!text) return "";
    return text.replace(/\s+/g, " ").trim();
  }

  // Determine if current page is likely the user's own profile or a profile page
  function inspectProfilePage() {
    const path = window.location.pathname;
    const isProfileUrl = path.startsWith('/in/') || path.startsWith('/in');
    
    // Check for self-profile edit indicators (buttons like "Edit public profile & URL", "Add profile section", edit pencil icons, or presence of /in/me)
    const hasEditProfileButton = !!document.querySelector('button[aria-label*="Edit"], a[href*="public-profile-settings"], button[aria-label*="Add profile section"], .pv-top-card__edit-photo, .profile-action-compose-button');
    const hasMeMenuMatch = path.includes('/in/me');
    
    // Get candidate vanity name from URL
    const urlParts = path.split('/').filter(Boolean);
    const vanityName = urlParts.length >= 2 ? urlParts[1] : '';

    return {
      isProfileUrl,
      isSelfProfileLikely: hasEditProfileButton || hasMeMenuMatch,
      vanityName,
      currentUrl: window.location.href.split('?')[0]
    };
  }

  // Discover user's own profile URL from navigation or profile widgets
  function discoverOwnProfileUrl() {
    // Strategy A: If already on a self profile page
    const pageCheck = inspectProfilePage();
    if (pageCheck.isProfileUrl && pageCheck.isSelfProfileLikely) {
      return { found: true, url: window.location.href.split('?')[0], method: 'current_self_profile' };
    }

    // Strategy B: Inspect global navigation "Me" / identity dropdown links
    // LinkedIn renders anchors to /in/<vanity> in .global-nav__me or profile link inside dropdown
    const navMeSelectors = [
      'a[href*="/in/"][data-control-name="identity_welcome_message"]',
      '.global-nav__me-content a[href*="/in/"]',
      'a.ember-view[href*="/in/"][href*="profile"]',
      '.feed-identity-module a[href*="/in/"]',
      'a.feed-identity-module__actor-link',
      'a[href*="/in/"][aria-label*="profile" i]',
      'a[href*="/in/"][class*="identity"]',
      '.global-nav__me a[href*="/in/"]'
    ];

    for (const sel of navMeSelectors) {
      const el = document.querySelector(sel);
      if (el && el.href && el.href.includes('/in/')) {
        const cleanHref = el.href.split('?')[0].replace(/\/+$/, '');
        // Ensure not generic /in/ or /in/me
        if (cleanHref.split('/in/')[1]) {
          return { found: true, url: cleanHref, method: 'nav_me_link' };
        }
      }
    }

    // Strategy C: Left rail identity card on feed (/feed/)
    const feedIdentityLinks = document.querySelectorAll('.feed-identity-module a, .identity-headline a');
    for (const link of feedIdentityLinks) {
      if (link.href && link.href.includes('/in/')) {
        const cleanHref = link.href.split('?')[0].replace(/\/+$/, '');
        if (cleanHref.split('/in/')[1]) {
          return { found: true, url: cleanHref, method: 'feed_identity_card' };
        }
      }
    }

    // Strategy D: Check any anchor in header containing /in/ (excluding company or search)
    const allInLinks = Array.from(document.querySelectorAll('header a[href*="/in/"], nav a[href*="/in/"]'));
    for (const link of allInLinks) {
      if (link.href && link.href.includes('/in/')) {
        const cleanHref = link.href.split('?')[0].replace(/\/+$/, '');
        const handle = cleanHref.split('/in/')[1];
        if (handle && !['feed', 'mynetwork', 'jobs', 'messaging', 'notifications'].includes(handle.toLowerCase())) {
          return { found: true, url: cleanHref, method: 'nav_header_link' };
        }
      }
    }

    // Strategy E: Safe LinkedIn self-profile redirect route
    // Navigating to https://www.linkedin.com/in/me/ natively redirects logged-in user to their own profile
    return { found: true, url: 'https://www.linkedin.com/in/me/', method: 'linkedin_me_redirect' };
  }

  // Progressively scroll down to trigger LinkedIn's lazy-loading observers for deeper sections
  async function autoScrollAndLoadSections() {
    const startTime = Date.now();
    console.log("[LinkedIn Extraction] AUTO_SCROLL_STARTED (+0ms)");

    const maxDurationMs = 3800; // Strict hard deadline to avoid exceeding background timeout
    const deadline = startTime + maxDurationMs;
    const maxSteps = 5; // Fixed small number of steps
    const stepSize = 650; // Scroll increment
    let currentStep = 0;

    try {
      while (currentStep < maxSteps && Date.now() < deadline) {
        currentStep++;
        const targetY = currentStep * stepSize;
        window.scrollTo({ top: targetY, behavior: 'instant' });

        const elapsed = Date.now() - startTime;
        console.log(`[LinkedIn Extraction] Scroll step ${currentStep}/${maxSteps} to ${targetY}px (+${elapsed}ms)`);

        // Brief delay for LinkedIn lazy-load observers to fire
        await new Promise(r => setTimeout(r, 180));

        // Check visibility of specific core sections
        const expEl = document.querySelector('#experience, section[id*="experience" i]');
        const eduEl = document.querySelector('#education, section[id*="education" i]');
        const skillsEl = document.querySelector('#skills, section[id*="skills" i]');

        if (expEl) {
          console.log(`[LinkedIn Extraction] EXPERIENCE_SECTION_IN_VIEW (+${Date.now() - startTime}ms)`);
        }
        if (eduEl) {
          console.log(`[LinkedIn Extraction] EDUCATION_SECTION_IN_VIEW (+${Date.now() - startTime}ms)`);
        }
        if (skillsEl) {
          console.log(`[LinkedIn Extraction] SKILLS_SECTION_IN_VIEW (+${Date.now() - startTime}ms)`);
        }

        // Early break if critical lower sections have rendered
        if ((expEl && eduEl && skillsEl) || (expEl && currentStep >= 4)) {
          console.log(`[LinkedIn Extraction] Core sections detected early at step ${currentStep} (+${Date.now() - startTime}ms)`);
          break;
        }
      }
    } finally {
      // Always restore scroll position to top even on error or timeout
      window.scrollTo({ top: 0, behavior: 'instant' });
      const totalElapsed = Date.now() - startTime;
      console.log(`[LinkedIn Extraction] AUTO_SCROLL_COMPLETED (+${totalElapsed}ms)`);
    }
  }

  // Robust, multi-strategy DOM extraction for visible profile sections
  function extractProfileFromDom() {
    const pageCheck = inspectProfilePage();
    const warnings = [];

    if (!pageCheck.isProfileUrl) {
      return {
        success: false,
        error: "NOT_ON_PROFILE_PAGE",
        message: "The active tab is not a LinkedIn profile page (URL should contain /in/)."
      };
    }

    // 1. Name & Photo
    let name = "";
    const nameEl = document.querySelector(
      'h1.text-heading-xlarge, ' +
      'h1.inline.t-24, ' +
      'main h1, ' +
      '.pv-top-card--list h1, ' +
      '.artdeco-entity-lockup__title, ' +
      '.pv-text-details__left-panel h1'
    );
    if (nameEl) {
      name = cleanText(nameEl.innerText);
    }
    if (!name && document.title && document.title.includes('|')) {
      const titleCandidate = document.title.split('|')[0].trim();
      if (!titleCandidate.toLowerCase().includes('linkedin') && !titleCandidate.toLowerCase().includes('feed')) {
        name = titleCandidate;
      }
    }

    let photoUrl = "";
    const photoEl = document.querySelector(
      'img.pv-top-card-profile-picture__image, ' +
      'img.pv-top-card__photo, ' +
      '.pv-top-card__photo img, ' +
      '.presence-entity__image, ' +
      'img[alt*="profile picture"], ' +
      'img[alt*="photo"]'
    );
    if (photoEl && photoEl.src && !photoEl.src.includes('data:image')) {
      photoUrl = photoEl.src;
    }

    // 2. Headline
    let headline = "";
    const headlineEl = document.querySelector(
      '.text-body-medium.break-words, ' +
      '.pv-text-details__left-panel .text-body-medium, ' +
      'div[data-generated-suggestion-target], ' +
      '.pv-top-card--list-bullet .text-body-medium'
    );
    if (headlineEl) {
      headline = cleanText(headlineEl.innerText);
    }

    // 3. Location
    let location = "";
    const locationEl = document.querySelector(
      '.text-body-small.inline.t-black--light.break-words, ' +
      '.pv-text-details__left-panel span.text-body-small, ' +
      '.pv-top-card--list-bullet + span, ' +
      'span.text-body-small[class*="secondary"]'
    );
    if (locationEl) {
      location = cleanText(locationEl.innerText);
    }

    // Helper: Find section container by matching heading text or anchor ID
    function findSection(keywords, anchorId) {
      // 1. Try finding by anchor ID directly or parent section
      if (anchorId) {
        const anchorEl = document.getElementById(anchorId);
        if (anchorEl) {
          const parentSec = anchorEl.closest('section');
          if (parentSec) return parentSec;
          const parentDiv = anchorEl.closest('.artdeco-card');
          if (parentDiv) return parentDiv;
        }
      }

      // 2. Try section/div with id containing anchorId or keyword
      if (anchorId) {
        const secById = document.querySelector(`section[id*="${anchorId}" i], div[id*="${anchorId}" i], [data-section*="${anchorId}" i]`);
        if (secById) {
          const directSec = secById.tagName === 'SECTION' ? secById : (secById.closest('section') || secById);
          if (directSec) return directSec;
        }
      }

      // 3. Scan all sections and artdeco cards in main / document
      const allSections = document.querySelectorAll('main section, section, .artdeco-card, [data-view-name*="profile"]');
      for (const sec of allSections) {
        const headerEls = sec.querySelectorAll('h2, .pvs-header__title, header, .pvs-header__container, [data-field="title"], span.text-heading-large');
        for (const header of headerEls) {
          const hText = (header.innerText || header.textContent || "").toLowerCase().trim();
          if (keywords.some(k => hText.includes(k))) {
            return sec;
          }
        }
      }
      return null;
    }

    // Helper: Expand inline 'see more' buttons inside a section
    function expandSeeMoreButtons(container, sectionName = "") {
      if (!container) return;
      try {
        const seeMoreBtns = container.querySelectorAll(
          'button.inline-show-more-text__button, ' +
          'button[aria-label*="see more" i], ' +
          '.pv-profile-section__see-more-inline, ' +
          'button[aria-label*="Show more" i]'
        );
        let clickCount = 0;
        seeMoreBtns.forEach(btn => {
          if (typeof btn.click === 'function') {
            btn.click();
            clickCount++;
          }
        });
        if (clickCount > 0) {
          console.log(`[LinkedIn Extraction] SECTION_EXPANSION: ${sectionName || 'section'} (${clickCount} buttons clicked)`);
        }
      } catch (e) {}
    }

    // 4. About Section
    let about = "";
    const aboutSec = findSection(["about", "summary"], "about");
    if (aboutSec) {
      console.log(`[LinkedIn Extraction] PROFILE_SECTION_DISCOVERY: about section found`);
      expandSeeMoreButtons(aboutSec, "about");
      const aboutTextEl = aboutSec.querySelector(
        '.inline-show-more-text, ' +
        '[data-field="about"], ' +
        '.pv-about__summary-text, ' +
        '.display-flex.ph5.pv3 span[aria-hidden="true"], ' +
        '.pv-shared-text-with-see-more span, ' +
        '.text-body-medium span'
      );
      if (aboutTextEl) {
        about = cleanText(aboutTextEl.innerText);
      } else {
        const allSpans = Array.from(aboutSec.querySelectorAll('span[aria-hidden="true"]'))
          .map(s => cleanText(s.innerText))
          .filter(t => t && !t.toLowerCase().includes('about') && !t.toLowerCase().includes('see more'));
        if (allSpans.length > 0) {
          about = allSpans.join("\n");
        } else {
          const allText = cleanText(aboutSec.innerText);
          about = allText.replace(/^(about|summary)\s*/i, "");
        }
      }
    } else {
      warnings.push("About section was not found on the visible profile page.");
    }

    // 5. Experience Section
    const experience = [];
    const expSec = findSection(["experience", "work experience"], "experience");
    if (expSec) {
      console.log(`[LinkedIn Extraction] PROFILE_SECTION_DISCOVERY: experience section found`);
      expandSeeMoreButtons(expSec, "experience");
      const items = expSec.querySelectorAll(
        'li.artdeco-list__item, ' +
        'li.pvs-list__item, ' +
        '.pvs-entity, ' +
        'li[class*="experience"], ' +
        'div[data-view-name="profile-component-entity"]'
      );
      items.forEach(item => {
        // Collect visible non-empty lines from aria-hidden spans or direct text containers
        const lines = Array.from(item.querySelectorAll('span[aria-hidden="true"], div.display-flex, span.visually-hidden'))
          .map(el => cleanText(el.innerText || el.textContent))
          .filter(t => t && !t.toLowerCase().includes('show all') && !t.toLowerCase().includes('skills:'));

        // Deduplicate adjacent identical strings
        const uniqueLines = [];
        lines.forEach(l => {
          if (!uniqueLines.includes(l)) uniqueLines.push(l);
        });

        if (uniqueLines.length > 0) {
          const title = uniqueLines[0] || "";
          const company = uniqueLines.length > 1 ? uniqueLines[1] : "";
          const dates = uniqueLines.length > 2 ? uniqueLines[2] : "";
          const expLocation = uniqueLines.length > 3 && !uniqueLines[3].includes("·") ? uniqueLines[3] : "";
          const desc = uniqueLines.slice(3).join("\n");

          if (title && title.length < 150) {
            experience.push({
              title,
              company,
              start_date: dates,
              location: expLocation,
              description: desc
            });
          }
        }
      });
    } else {
      warnings.push("Experience section was not found on the visible profile page.");
    }

    // 6. Education Section
    const education = [];
    const eduSec = findSection(["education"], "education");
    if (eduSec) {
      console.log(`[LinkedIn Extraction] PROFILE_SECTION_DISCOVERY: education section found`);
      expandSeeMoreButtons(eduSec, "education");
      const items = eduSec.querySelectorAll(
        'li.artdeco-list__item, ' +
        'li.pvs-list__item, ' +
        '.pvs-entity, ' +
        'li[class*="education"], ' +
        'div[data-view-name="profile-component-entity"]'
      );
      items.forEach(item => {
        const lines = Array.from(item.querySelectorAll('span[aria-hidden="true"], div.display-flex, span.visually-hidden'))
          .map(el => cleanText(el.innerText || el.textContent))
          .filter(t => t && !t.toLowerCase().includes('show all'));

        const uniqueLines = [];
        lines.forEach(l => {
          if (!uniqueLines.includes(l)) uniqueLines.push(l);
        });

        if (uniqueLines.length > 0) {
          education.push({
            school: uniqueLines[0] || "",
            degree: uniqueLines.length > 1 ? uniqueLines[1] : "",
            field_of_study: uniqueLines.length > 2 ? uniqueLines[2] : "",
            dates: uniqueLines.length > 3 ? uniqueLines[3] : ""
          });
        }
      });
    }

    // 7. Skills Section
    const skills = [];
    const skillsSec = findSection(["skills"], "skills");
    if (skillsSec) {
      console.log(`[LinkedIn Extraction] PROFILE_SECTION_DISCOVERY: skills section found`);
      expandSeeMoreButtons(skillsSec, "skills");
      const items = skillsSec.querySelectorAll(
        'li.artdeco-list__item, ' +
        'li.pvs-list__item, ' +
        '.pvs-entity, ' +
        'li[class*="skill"], ' +
        'div[data-view-name="profile-component-entity"], ' +
        '.hoverable-link-text'
      );
      items.forEach(item => {
        const sNameEl = item.querySelector('span[aria-hidden="true"], a');
        const sName = cleanText(sNameEl ? sNameEl.innerText : item.innerText);
        if (sName && sName.length < 80 && !sName.toLowerCase().includes('show all') && !sName.toLowerCase().includes('endorse')) {
          if (!skills.includes(sName)) {
            skills.push(sName);
          }
        }
      });
    }

    // 8. Certifications Section
    const certifications = [];
    const certSec = findSection(["licenses & certifications", "certifications", "licenses"], "certifications");
    if (certSec) {
      console.log(`[LinkedIn Extraction] PROFILE_SECTION_DISCOVERY: certifications section found`);
      expandSeeMoreButtons(certSec, "certifications");
      const items = certSec.querySelectorAll(
        'li.artdeco-list__item, ' +
        'li.pvs-list__item, ' +
        '.pvs-entity, ' +
        'div[data-view-name="profile-component-entity"]'
      );
      items.forEach(item => {
        const lines = Array.from(item.querySelectorAll('span[aria-hidden="true"], div.display-flex'))
          .map(el => cleanText(el.innerText))
          .filter(Boolean);
        if (lines.length > 0) {
          certifications.push({
            name: lines[0] || "",
            authority: lines.length > 1 ? lines[1] : "",
            issued: lines.length > 2 ? lines[2] : ""
          });
        }
      });
    }

    // Current position inference
    let current_position = "";
    if (experience.length > 0) {
      const firstExp = experience[0];
      current_position = firstExp.company ? `${firstExp.title} @ ${firstExp.company}` : firstExp.title;
    } else if (headline) {
      current_position = headline.split('|')[0].trim();
    }

    const sectionsCount = [
      name, headline, about,
      experience.length > 0,
      education.length > 0,
      skills.length > 0,
      certifications.length > 0
    ].filter(Boolean).length;

    console.log(`[LinkedIn Content] Extracted summary:`, {
      name: !!name,
      headline: !!headline,
      about: !!about,
      experience: experience.length,
      education: education.length,
      skills: skills.length,
      certifications: certifications.length
    });

    return {
      success: true,
      data: {
        name,
        headline,
        about,
        location,
        current_position,
        profile_url: pageCheck.currentUrl,
        vanity_name: pageCheck.vanityName,
        profile_photo_url: photoUrl,
        experience,
        education,
        skills,
        certifications
      },
      metadata: {
        sections_found: sectionsCount,
        is_self_profile_likely: pageCheck.isSelfProfileLikely,
        extracted_at: new Date().toISOString(),
        warnings: warnings
      }
    };
  }

  // Listen for messages from background.js
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (!request || typeof request !== "object") return;

    if (request.action === "PING") {
      sendResponse({ status: "PONG", url: window.location.href.split('?')[0] });
      return true;
    }

    if (request.action === "CHECK_DOM_AUTH") {
      const isAuth = checkDomAuthState();
      const isLoginPage = window.location.pathname.includes('/login') || window.location.pathname.includes('/checkpoint');
      const isChallenge = !!document.querySelector('#captcha-internal, .challenge-dialog, iframe[src*="challenge"], [data-control-name="challenge"]');
      sendResponse({
        authenticated: isAuth,
        isLoginPage,
        isChallenge,
        currentUrl: window.location.href.split('?')[0]
      });
      return true;
    }

    if (request.action === "DISCOVER_OWN_PROFILE") {
      const isAuth = checkDomAuthState();
      const isLoginPage = window.location.pathname.includes('/login') || window.location.pathname.includes('/checkpoint');
      const isChallenge = !!document.querySelector('#captcha-internal, .challenge-dialog, iframe[src*="challenge"], [data-control-name="challenge"]');

      if (!isAuth || isLoginPage) {
        sendResponse({
          success: false,
          error: "NOT_AUTHENTICATED",
          isLoginPage: true,
          message: "LinkedIn tab is not logged in. Please sign in to LinkedIn."
        });
        return true;
      }

      if (isChallenge) {
        sendResponse({
          success: false,
          error: "CHALLENGE_DETECTED",
          message: "LinkedIn is presenting a security or verification challenge. Please resolve it in the LinkedIn tab."
        });
        return true;
      }

      const discovery = discoverOwnProfileUrl();
      const pageCheck = inspectProfilePage();
      sendResponse({
        success: true,
        authenticated: true,
        profileUrl: discovery.url,
        discoveryMethod: discovery.method,
        currentPage: pageCheck
      });
      return true;
    }

    if (request.action === "WAIT_FOR_PROFILE_RENDER") {
      const maxRetries = request.maxRetries || 10;
      const intervalMs = request.intervalMs || 500;
      let attempts = 0;

      const checkRenderInterval = setInterval(() => {
        attempts++;
        const isAuth = checkDomAuthState();
        const isLoginPage = window.location.pathname.includes('/login') || window.location.pathname.includes('/checkpoint');
        const isChallenge = !!document.querySelector('#captcha-internal, .challenge-dialog, iframe[src*="challenge"]');

        if (isLoginPage) {
          clearInterval(checkRenderInterval);
          sendResponse({ success: false, error: "SESSION_EXPIRED", message: "Redirected to login page." });
          return;
        }

        if (isChallenge) {
          clearInterval(checkRenderInterval);
          sendResponse({ success: false, error: "CHALLENGE_DETECTED", message: "LinkedIn verification challenge detected." });
          return;
        }

        const nameEl = document.querySelector('h1.text-heading-xlarge, h1.inline.t-24, main h1, .pv-top-card--list h1, .pv-text-details__left-panel h1');
        const hasSections = !!document.querySelector('.pv-profile-card, section.artdeco-card, #about, #experience');

        if (nameEl || hasSections || attempts >= maxRetries) {
          clearInterval(checkRenderInterval);
          const pageCheck = inspectProfilePage();
          sendResponse({
            success: !!nameEl || hasSections,
            rendered: !!nameEl || hasSections,
            attempts: attempts,
            pageCheck: pageCheck
          });
        }
      }, intervalMs);

      return true;
    }

    if (request.action === "INSPECT_CURRENT_PAGE") {
      const check = inspectProfilePage();
      sendResponse({ success: true, ...check });
      return true;
    }

    if (request.action === "EXTRACT_OWN_PROFILE_DOM") {
      const reqId = request.requestId || "unknown";
      const startTime = Date.now();
      console.log(`[LinkedIn Content] DOM extraction requested: ${reqId} (+0ms)`);
      (async () => {
        try {
          // Progressively load sections via viewport scrolling before reading DOM
          await autoScrollAndLoadSections();

          const extractionStart = Date.now();
          console.log(`[LinkedIn Content] Reading DOM structures (+${extractionStart - startTime}ms)`);
          const result = extractProfileFromDom();
          const totalElapsed = Date.now() - startTime;
          console.log(`[LinkedIn Extraction] DOM_EXTRACTION_COMPLETED: ${reqId} in ${totalElapsed}ms. Success: ${result.success}`);
          sendResponse(result);
        } catch (err) {
          const totalElapsed = Date.now() - startTime;
          console.error(`[LinkedIn Content] DOM extraction failed: ${reqId} after ${totalElapsed}ms`, err);
          sendResponse({
            success: false,
            error: "EXTRACTION_EXCEPTION",
            message: err.message || "Failed to parse profile DOM"
          });
        }
      })();
      return true;
    }
  });
})();
```

---

### 3.5 `static/js/profile-optimization.js` (Relevant Extraction Handlers)

```javascript
    // Helper: Check active LinkedIn tab status
    const checkActiveLinkedInTab = function() {
        return new Promise((resolve) => {
            const reqId = 'tab_' + Date.now();
            let timer = null;

            const listener = (event) => {
                if (event.source !== window || !event.data || typeof event.data !== 'object') return;
                if (event.data.type === 'FAMEWEB_EXT_CHECK_TAB_RESPONSE' && event.data.requestId === reqId) {
                    console.log(`[Profile Import] Response received by page: ${reqId}`);
                    window.removeEventListener('message', listener);
                    if (timer) clearTimeout(timer);
                    resolve(event.data);
                }
            };

            timer = setTimeout(() => {
                console.warn(`[Profile Import] Timeout reached: ${reqId} (CHECK_TAB)`);
                window.removeEventListener('message', listener);
                resolve({
                    success: false,
                    error: 'EXTENSION_TIMEOUT',
                    message: 'Chrome extension tab query timed out. Please check your extension.'
                });
            }, 8000);

            window.addEventListener('message', listener);
            console.log(`[Profile Import] Request dispatched: ${reqId} (CHECK_TAB)`);
            window.postMessage({
                type: 'FAMEWEB_EXT_CHECK_TAB_REQUEST',
                requestId: reqId
            }, '*');
        });
    };

    // Helper: Request profile extraction from extension bridge
    const requestProfileExtraction = function(targetProfileUrl = null) {
        return new Promise((resolve) => {
            const reqId = 'import_' + Date.now();
            let timer = null;

            const listener = (event) => {
                if (event.source !== window || !event.data || typeof event.data !== 'object') return;
                if (event.data.type === 'FAMEWEB_EXT_IMPORT_RESPONSE' && event.data.requestId === reqId) {
                    console.log(`[Profile Import] Response received by page: ${reqId}`);
                    window.removeEventListener('message', listener);
                    if (timer) clearTimeout(timer);
                    resolve(event.data);
                }
            };

            timer = setTimeout(() => {
                console.warn(`[Profile Import] Timeout reached: ${reqId} (EXTRACT_PROFILE)`);
                window.removeEventListener('message', listener);
                resolve({
                    success: false,
                    error: 'EXTRACTION_TIMEOUT',
                    message: 'Profile extraction timed out. Please check that your LinkedIn profile tab is open.'
                });
            }, 25000);

            window.addEventListener('message', listener);
            console.log(`[Profile Import] Request dispatched: ${reqId} (EXTRACT_PROFILE)`);
            window.postMessage({
                type: 'FAMEWEB_EXT_IMPORT_REQUEST',
                requestId: reqId,
                targetProfileUrl: targetProfileUrl
            }, '*');
        });
    };

    // Main Import Trigger Handler
    if (btnImport) {
        btnImport.addEventListener('click', async () => {
            const originalText = importBtnText ? importBtnText.innerText : 'Import My LinkedIn Profile';
            btnImport.disabled = true;

            try {
                // Step 1: Detect open LinkedIn tab
                if (importBtnText) importBtnText.innerText = 'Checking LinkedIn Tab...';
                showImportFeedback('loading', 'Checking for active LinkedIn tab...');

                const tabStatus = await checkActiveLinkedInTab();

                if (!tabStatus.success) {
                    // handle error...
                    return;
                }

                // Step 4: Automatically navigate & extract profile DOM
                if (importBtnText) importBtnText.innerText = 'Extracting Profile...';
                showImportFeedback('loading', 'Opening your LinkedIn profile and extracting visible information...');

                const extResult = await requestProfileExtraction(savedProfileUrl);

                if (!extResult.success || !extResult.data) {
                    showImportFeedback('error', 'Unable to automatically extract profile', [
                        extResult.message || 'Could not identify or extract profile information from LinkedIn DOM.'
                    ]);
                    return;
                }

                const extracted = extResult.data;

                // Step 5: Post to FameWeb Backend
                if (importBtnText) importBtnText.innerText = 'Importing to FameWeb...';
                showImportFeedback('loading', 'Importing your profile into FameWeb...');

                const res = await fetch('/api/profile-optimization/import-extension-profile', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: JSON.stringify(extracted)
                });

                const data = await res.json();

                if (res.ok && data.success) {
                    const sections = (data.sections_imported || []).join(', ');
                    const warnings = (data.warnings || []).concat(extracted._warnings || []);
                    const importedCount = (data.sections_imported || []).length;
                    const hasSubstantiveContent = importedCount > 1 || (data.experience_count > 0 || data.skills_count > 0 || data.data?.about);

                    // Update UI preview card elements...

                    if (hasSubstantiveContent) {
                        showImportFeedback('success', `LinkedIn profile imported successfully: ${data.data?.name || extracted.name}`, ...);
                    } else {
                        // PARTIAL IMPORT WARNING TRIGGERED HERE:
                        showImportFeedback(
                            'warning',
                            `Partial Profile Import: ${data.data?.name || extracted.name}`,
                            [
                                `Only basic header information (${sections || 'Name'}) could be found on the open page.`,
                                `Experience: 0 roles | Skills: 0 skills | About: Not found`,
                                'Tip: Open your LinkedIn tab, scroll down once so LinkedIn renders your Experience & Skills sections, then click Re-import below.'
                            ],
                            ...
                        );
                    }
                }
            } finally {
                btnImport.disabled = false;
                if (importBtnText) importBtnText.innerText = originalText;
            }
        });
    }
```

---

### 3.6 Backend Persistence Endpoint & Model

#### Route: `POST /api/profile-optimization/import-extension-profile`
Mapped to `import_extension_profile()` in `app/routes/onboarding.py`:

```python
@onboarding_bp.route('/profile/import-extension', methods=['POST'])
@login_required
def import_extension_profile():
    user_id = request.user_id
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({"success": False, "error": "INVALID_PAYLOAD"}), 400

    profile = data.get("profile") or data.get("data") or data
    name = clean_str(profile.get("name"), 200)
    headline = clean_str(profile.get("headline"), 500)
    about = clean_str(profile.get("about"), 4000)
    location = clean_str(profile.get("location"), 200)
    current_pos = clean_str(profile.get("current_position"), 300)
    profile_url = clean_str(profile.get("profile_url"), 500)
    vanity_name = clean_str(profile.get("vanity_name"), 100)

    # Experience list
    raw_exp = profile.get("experience")
    clean_exp = []
    if isinstance(raw_exp, list):
        for item in raw_exp[:25]:
            if isinstance(item, dict):
                clean_exp.append({
                    "title": clean_str(item.get("title"), 200) or "",
                    "company": clean_str(item.get("company"), 200) or "",
                    "start_date": clean_str(item.get("start_date") or item.get("dates"), 100) or "",
                    "location": clean_str(item.get("location"), 150) or "",
                    "description": clean_str(item.get("description"), 2000) or ""
                })

    # Education list
    raw_edu = profile.get("education")
    clean_edu = []
    if isinstance(raw_edu, list):
        for item in raw_edu[:15]:
            if isinstance(item, dict):
                clean_edu.append({
                    "school": clean_str(item.get("school"), 200) or "",
                    "degree": clean_str(item.get("degree"), 200) or "",
                    "field_of_study": clean_str(item.get("field_of_study"), 200) or "",
                    "dates": clean_str(item.get("dates"), 100) or ""
                })

    # Skills list
    raw_skills = profile.get("skills")
    clean_skills = []
    if isinstance(raw_skills, list):
        for s in raw_skills[:100]:
            cleaned = clean_str(s, 100)
            if cleaned and cleaned not in clean_skills:
                clean_skills.append(cleaned)

    # Persist in UsersLinkedinDetails
    linkedin = db_session.query(UsersLinkedinDetails).filter_by(user_id=user_id).first()
    if not linkedin:
        linkedin = UsersLinkedinDetails(user_id=user_id)
        db_session.add(linkedin)

    if name: linkedin.name = name
    if headline: linkedin.headline = headline
    if about: linkedin.about = about
    if location: linkedin.location = location
    if current_pos: linkedin.current_position = current_pos
    if profile_url and "linkedin.com" in profile_url: linkedin.profile_url = profile_url
    if vanity_name: linkedin.linkedin_id = vanity_name
    if clean_exp: linkedin.experience = clean_exp
    if clean_edu: linkedin.education = clean_edu
    if clean_skills: linkedin.skills = clean_skills

    # Rich fields into profile_data JSONB
    existing_pdata = dict(linkedin.profile_data or {})
    photo_url = clean_str(profile.get("profile_photo_url"), 1000)
    if photo_url: existing_pdata["profile_photo_url"] = photo_url
    linkedin.profile_data = existing_pdata
    linkedin.connection_status = ConnectionStatus.CONNECTED.value
    linkedin.last_verified_at = datetime.utcnow()

    db_session.commit()

    return jsonify({
        "success": True,
        "sections_imported": imported_sections,
        "experience_count": len(clean_exp),
        "education_count": len(clean_edu),
        "skills_count": len(clean_skills),
        "certifications_count": len(clean_certs),
        "data": { ... }
    }), 200
```

#### Database Model: `app/models/all_models.py`
```python
class UsersLinkedinDetails(Base):
    __tablename__ = 'users_linkedin_details'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user_table.user_id'), unique=True, nullable=False)
    oidc_sub = Column(String, unique=True, nullable=True)
    linkedin_id = Column(String, unique=True, nullable=True)
    profile_url = Column(String, nullable=True)
    name = Column(String, nullable=True)
    headline = Column(String, nullable=True)
    about = Column(String, nullable=True)
    current_position = Column(String, nullable=True)
    location = Column(String, nullable=True)
    experience = Column(JSONB, nullable=True)
    education = Column(JSONB, nullable=True)
    skills = Column(JSONB, nullable=True)
    profile_data = Column(JSONB, nullable=True)
    profile_source = Column(String, nullable=True)
    profile_completeness = Column(String, nullable=True)
    optimization_suggestions = Column(JSONB, nullable=True)
    auth_data_encrypted = Column(String, nullable=True)
    connection_status = Column(String, nullable=True)
    consent_at = Column(DateTime, nullable=True)
    last_verified_at = Column(DateTime, nullable=True)
    last_used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

---

## 4. Debugging History & Known Symptoms

| Date / Phase | Issue Encountered | Root Cause Identified | Fix Applied | Result |
| :--- | :--- | :--- | :--- | :--- |
| **Stage 1** | Extension runtime error: `Cannot read properties of undefined (reading 'sendMessage')` | `content_fameweb.js` ran before runtime ready or was accessed after extension reload. | Added `isExtensionRuntimeAvailable()` check and fallback warnings. | Resolved runtime crash. |
| **Stage 2** | Page reloaded instantly after tab discovery, clearing all state. | Hard-coded `window.location.reload()` after 1.4s in `profile-optimization.js`. | Removed reload; updated preview DOM dynamically and showed persistent toast/banner. | Resolved UI flickers. |
| **Stage 3** | Import request timed out: `Tab message timed out: EXTRACT_OWN_PROFILE_DOM` | `autoScrollAndLoadSections()` scrolled down infinite feed height with `step = 600` until > 15s. | Bounded scroll to max 5 steps, 650px increment, 3.8s hard deadline. | Timeout resolved. HTTP 200 returned in < 2 seconds. |
| **Stage 4** | Partial Import: Only name saved. Experience, Skills, Education = 0. | Sections not in DOM or not loaded before extraction ran. | Added `autoScrollAndLoadSections()` and stage milestone logs in v1.0.1. | **Current Issue:** None of the stage logs appear in the LinkedIn console. |

---

## 5. Actual Runtime Evidence vs. Expected Behavior

### 5.1 Confirmed Browser Console Output (FameWeb tab)
```text
[Profile Import] Request dispatched: tab_1793993508395 (CHECK_TAB)
[Extension Bridge] Request received: tab_1793993508395 (CHECK_TAB)
[Extension Bridge] Response dispatched to page: tab_1793993508395 (CHECK_TAB)
[Profile Import] Response received by page: tab_1793993508395
[Profile Import] Promise resolved: tab_1793993508395

[Profile Import] Request dispatched: import_1793993508418 (EXTRACT_PROFILE)
[Extension Bridge] Request received: import_1793993508418 (EXTRACT_PROFILE)
[Extension Bridge] Response dispatched to page: import_1793993508418 (EXTRACT_PROFILE)
[Profile Import] Response received by page: import_1793993508418
[Profile Import] Promise resolved: import_1793993508418
```

### 5.2 Confirmed Network Response from Backend
`POST http://localhost:5000/api/profile-optimization/import-extension-profile` &rarr; Status **200 OK**:
```json
{
  "success": true,
  "message": "LinkedIn profile successfully imported from active browser session.",
  "sections_imported": ["name"],
  "experience_count": 0,
  "education_count": 0,
  "skills_count": 0,
  "certifications_count": 0,
  "warnings": [
    "About section was not found on the visible profile page.",
    "Experience section was not found on the visible profile page."
  ],
  "data": {
    "name": "Tony Stark",
    "headline": null,
    "about": false,
    "location": null,
    "current_position": null,
    "experience_count": 0,
    "education_count": 0
  }
}
```

### 5.3 What is NOT Appearing
In the **LinkedIn tab console** (`https://www.linkedin.com/in/...`), the following expected logs from `content_linkedin.js` **do not appear**:
- `[LinkedIn Extraction] AUTO_SCROLL_STARTED`
- `[LinkedIn Extraction] Scroll step 1/5...`
- `[LinkedIn Extraction] EXPERIENCE_SECTION_IN_VIEW`
- `[LinkedIn Extraction] AUTO_SCROLL_COMPLETED`
- `[LinkedIn Extraction] PROFILE_SECTION_DISCOVERY`
- `[LinkedIn Extraction] DOM_EXTRACTION_COMPLETED`

---

## 6. Key Hypotheses for the External Reviewer (Claude)

We ask the external AI to evaluate the following potential failure mechanisms:

### Hypothesis A: Multiple Script Instances / Stale Execution via Scripting API
In `background.js`:
```javascript
async function ensureLinkedInContentScript(tabId) {
  try {
    const ping = await new Promise((resolve) => {
      chrome.tabs.sendMessage(tabId, { action: "PING" }, (res) => {
        const err = chrome.runtime.lastError;
        resolve(!err && !!res);
      });
      setTimeout(() => resolve(false), 400);
    });

    if (!ping && chrome.scripting) {
      console.log(`[Extension Background] Injecting content_linkedin.js into tab ${tabId}`);
      await chrome.scripting.executeScript({
        target: { tabId: tabId },
        files: ["content_linkedin.js"]
      });
    }
  } ...
}
```
If a tab was opened *before* reloading the extension in `chrome://extensions`, the old content script may already respond to `{ action: "PING" }` with `PONG`. As a result, `!ping` evaluates to `false`, and the new `content_linkedin.js` (with v1.0.1 and scrolling/logging) **is never injected**, leaving the old script running in the tab!

### Hypothesis B: Tab Selection Mismatch (`findBestLinkedInTab`)
In `background.js`:
```javascript
const tabs = await chrome.tabs.query({ url: "*://*.linkedin.com/*" });
for (const tab of tabs) {
  const url = tab.url || "";
  if (url.includes("/login") || url.includes("/checkpoint") || url.includes("/uas/login")) continue;
  if (!fallbackTab) fallbackTab = tab;
  if (url.includes("/in/")) {
    bestTab = tab;
    break;
  }
}
const selectedTab = bestTab || fallbackTab || tabs[0];
```
If the user has multiple LinkedIn tabs open (e.g., Tab A is the LinkedIn feed `/feed/`, Tab B is an arbitrary profile or mini-tab, or background notifications), which tab is selected? Could `sendToTab` be communicating with a different tab or an iframe?

### Hypothesis C: Premature Navigation Bypass
In `background.js`:
```javascript
const currentTabUrl = (targetTab.url || "").split('?')[0].replace(/\/+$/, '');
const cleanDest = destinationUrl.split('?')[0].replace(/\/+$/, '');
const isAlreadyThere = currentTabUrl === cleanDest || (cleanDest.endsWith('/in/me') && currentTabUrl.includes('/in/'));
```
If `destinationUrl` is `https://www.linkedin.com/in/me/` and `currentTabUrl` is `https://www.linkedin.com/in/tony-stark-ab2064440`, `isAlreadyThere` is true! It skips navigation.
Then `WAIT_FOR_PROFILE_RENDER`:
```javascript
const nameEl = document.querySelector('h1.text-heading-xlarge, h1.inline.t-24, main h1, ...');
const hasSections = !!document.querySelector('.pv-profile-card, section.artdeco-card, #about, #experience');
if (nameEl || hasSections || attempts >= maxRetries) { ... sendResponse({ success: true }); }
```
Because `nameEl` is immediately present in the DOM (the top card renders first), `WAIT_FOR_PROFILE_RENDER` immediately resolves on attempt 1 without waiting for lower sections to load.

### Hypothesis D: Selector Drift in LinkedIn DOM (2025/2026 Layout)
LinkedIn's web layout frequently updates CSS class names and attributes.
- Are sections using custom element wrappers or shadow DOM?
- Does LinkedIn use `div[data-view-name="profile-card"]` instead of `#experience` / `#education`?
- Are lower sections loaded strictly on user pointer interactions or IntersectionObserver that does not trigger on `window.scrollTo`?

---

## 7. Implementation Constraints & Guardrails

When reviewing or proposing recommendations, keep in mind:
1. **Zero External Paid APIs:** Do not suggest Proxycurl, BrightData, RapidAPI, ScrapingBee, etc.
2. **Zero Voyager / Private API Endpoints:** Do not use reverse-engineered `/voyager/api` endpoints or simulate raw HTTP headers with cookies.
3. **Zero Raw Secret / Cookie Transmission:** The extension must never read, serialize, transmit, or persist the user's `li_at` cookie or passwords.
4. **User-Initiated Own-Profile Extraction Only:** The extension only runs when the user explicitly clicks "Import My LinkedIn Profile" on FameWeb.
5. **Preserve Application Architecture:** Do not modify database schemas, migrations, or the existing Gemini prompt pipeline.

