import re

with open("static/js/app.js", "r") as f:
    content = f.read()

# Replace checkFamewebSessionStatus implementation
old_func = """    async function checkFamewebSessionStatus(options = {}) {
      if (sessionStatusText) sessionStatusText.textContent = 'Checking...';
      try {
        const res = await fetch('/api/linkedin-session-status');
        const data = await res.json();
        if (res.ok && data.success && data.data) {
          const isAuth = data.data.authenticated;
          const name = data.data.name || (data.data.user ? data.data.user.name : null) || 'LinkedIn Member';
          const photo = data.data.profile_photo_url;
          currentUserContext = data.data.user;
          savedGtmContext = data.data.gtm_context;"""

new_func = """    async function checkFamewebSessionStatus(options = {}) {
      if (sessionStatusText) sessionStatusText.textContent = 'Checking...';
      try {
        const res = await fetch('/api/auth/me');
        const data = await res.json();
        const isAuth = data.authenticated;
        if (isAuth && data.user) {
          const user = data.user;
          const name = user.name || 'Fameweb User';
          const photo = null; // Fameweb auth doesn't have photo yet
          currentUserContext = user;
          savedGtmContext = null;"""

content = content.replace(old_func, new_func)

# Fix logout logic
old_logout = """    // --- UI Listeners ---
    if (logoutSessionBtn) {
      logoutSessionBtn.addEventListener('click', async () => {
        if (!confirm('Are you sure you want to log out of your LinkedIn session?')) return;
        logoutSessionBtn.disabled = true;
        try {
          const res = await fetch('/api/logout-linkedin-session', { method: 'POST' });
          if (res.ok) {
            const data = await res.json();
            if (data.success) {
              if (profileUrlInput) {
                profileUrlInput.value = '';
                profileUrlInput.placeholder = 'Connect LinkedIn to load your profile';
                profileUrlInput.readOnly = true;
                profileUrlInput.disabled = true;
              }
              if (extractProfileBtn) {
                extractProfileBtn.disabled = true;
              }
              if (currentProfileContainer) currentProfileContainer.classList.add('hidden');
              if (optimizationResultContainer) optimizationResultContainer.classList.add('hidden');
              checkFamewebSessionStatus();
            }
          }
        } catch (err) {
          console.error('Logout error:', err);
        } finally {
          logoutSessionBtn.disabled = false;
        }
      });
    }"""

new_logout = """    // --- UI Listeners ---
    const handleLogout = async () => {
        if (!confirm('Are you sure you want to log out of Fameweb?')) return;
        try {
          const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
          const res = await fetch('/api/auth/logout', { 
              method: 'POST',
              headers: csrfToken ? { 'X-CSRFToken': csrfToken } : {}
          });
          if (res.ok) {
            window.location.reload();
          }
        } catch (err) {
          console.error('Logout error:', err);
        }
    };

    if (logoutSessionBtn) {
      logoutSessionBtn.addEventListener('click', handleLogout);
    }
    const headerLogout = document.getElementById('header-app-logout-btn');
    if (headerLogout) {
        headerLogout.addEventListener('click', handleLogout);
    }
    const sidebarLogout = document.getElementById('sidebar-app-logout-btn');
    if (sidebarLogout) {
        sidebarLogout.addEventListener('click', handleLogout);
    }"""

content = content.replace(old_logout, new_logout)

with open("static/js/app.js", "w") as f:
    f.write(content)

print("Patched app.js")
