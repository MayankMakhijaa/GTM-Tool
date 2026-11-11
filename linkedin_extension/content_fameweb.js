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
  const BRIDGE_EVENT_SEARCH_REQUEST = "FAMEWEB_EXT_SEARCH_REQUEST";
  const BRIDGE_EVENT_SEARCH_RESPONSE = "FAMEWEB_EXT_SEARCH_RESPONSE";

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
            version: response?.version || "1.0.3"
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
            error: lastErr ? lastErr.message : response?.error,
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

    // E. Open LinkedIn Search Request
    if (type === BRIDGE_EVENT_SEARCH_REQUEST) {
      console.log(`[Extension Bridge] Request received: ${requestId} (OPEN_LINKEDIN_SEARCH)`);
      if (!isExtensionRuntimeAvailable()) {
        console.warn(`[Extension Bridge] chrome.runtime unavailable for OPEN_LINKEDIN_SEARCH (reqId: ${requestId})`);
        window.postMessage({
          type: BRIDGE_EVENT_SEARCH_RESPONSE,
          requestId: requestId,
          success: false,
          error: "EXTENSION_CONTEXT_INVALID",
          message: "Chrome extension was updated or invalidated. Please refresh the FameWeb page."
        }, "*");
        return;
      }

      try {
        chrome.runtime.sendMessage({
          action: "OPEN_LINKEDIN_SEARCH",
          requestId: requestId,
          searchUrl: event.data.searchUrl,
          queryContext: event.data.queryContext || {}
        }, (response) => {
          const lastErr = chrome.runtime.lastError;
          console.log(`[Extension Bridge] Response dispatched to page: ${requestId} (OPEN_LINKEDIN_SEARCH)`, {
            success: !lastErr && !!response?.success,
            status: response?.status,
            count: response?.count || 0,
            error: lastErr ? lastErr.message : response?.error
          });
          window.postMessage({
            type: BRIDGE_EVENT_SEARCH_RESPONSE,
            requestId: requestId,
            success: !lastErr && !!response?.success,
            ...(response || {}),
            status: response?.status || (!lastErr && !!response?.success ? "RESULTS_EXTRACTED" : "SEARCH_FAILED"),
            error: lastErr ? lastErr.message : response?.error,
            message: lastErr ? lastErr.message : response?.message
          }, "*");
        });
      } catch (err) {
        console.error(`[Extension Bridge] Error calling sendMessage for OPEN_LINKEDIN_SEARCH:`, err);
        window.postMessage({
          type: BRIDGE_EVENT_SEARCH_RESPONSE,
          requestId: requestId,
          success: false,
          error: "RUNTIME_EXCEPTION",
          message: err.message
        }, "*");
      }
      return;
    }
  });

  // Announce ready state
  window.postMessage({ type: "FAMEWEB_EXTENSION_READY", version: "1.0.2" }, "*");
})();
