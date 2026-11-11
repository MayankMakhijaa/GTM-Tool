// Popup script to query background service worker for LinkedIn session status

document.addEventListener('DOMContentLoaded', () => {
  const badge = document.getElementById('session-badge');
  const msg = document.getElementById('session-msg');

  chrome.runtime.sendMessage({ action: "VERIFY_LINKEDIN_SESSION" }, (response) => {
    if (chrome.runtime.lastError || !response) {
      badge.textContent = "Error";
      badge.className = "badge badge-error";
      msg.textContent = chrome.runtime.lastError ? chrome.runtime.lastError.message : "Service worker unavailable";
      return;
    }

    if (response.status === "CONNECTED" && response.authenticated) {
      badge.textContent = "Connected";
      badge.className = "badge badge-success";
      msg.textContent = "Active LinkedIn session verified.";
    } else {
      badge.textContent = "Not Logged In";
      badge.className = "badge badge-warning";
      msg.textContent = "Log into LinkedIn in your browser to verify session.";
    }
  });
});

