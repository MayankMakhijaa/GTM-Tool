import re

with open("static/js/app.js", "r") as f:
    content = f.read()

# Fix unauthenticated else block
old_else = """          } else {
            if (sessionStatusBadge) sessionStatusBadge.className = 'flex items-center gap-1.5 px-3 py-1 rounded-full bg-status-warning-bg text-status-warning-text font-label-sm text-label-sm font-medium border border-status-warning-border';
            if (sessionStatusDot) sessionStatusDot.className = 'w-2 h-2 rounded-full bg-status-warning-text';
            if (sessionStatusText) sessionStatusText.textContent = 'Not Connected';

            if (connectedProfileInfo) connectedProfileInfo.classList.add('hidden');
            if (connectedProfileName) connectedProfileName.textContent = '';
            if (openSessionBtn) openSessionBtn.classList.remove('hidden');
            if (logoutSessionBtn) logoutSessionBtn.classList.add('hidden');

            if (headerBadge) headerBadge.classList.add('hidden');
            if (headerLogoutBtn) headerLogoutBtn.classList.add('hidden');

            if (profileUrlInput) {
              profileUrlInput.value = '';
              profileUrlInput.placeholder = 'Connect LinkedIn to load your profile';
              profileUrlInput.readOnly = true;
              profileUrlInput.disabled = true;
            }
            if (extractProfileBtn) {
              extractProfileBtn.disabled = true;
            }

            if (!options.skipNavigation) switchTab('welcome-page');
            console.log('[FLOW] Unauthenticated -> Displaying Welcome Page.');
          }
        }
      } catch (err) {
        console.error('Failed to check LinkedIn session status:', err);"""

new_else = """        } else {
          // Handle unauthenticated case
          if (sessionStatusBadge) sessionStatusBadge.className = 'flex items-center gap-1.5 px-3 py-1 rounded-full bg-status-warning-bg text-status-warning-text font-label-sm text-label-sm font-medium border border-status-warning-border';
          if (sessionStatusDot) sessionStatusDot.className = 'w-2 h-2 rounded-full bg-status-warning-text';
          if (sessionStatusText) sessionStatusText.textContent = 'Not Connected';

          if (connectedProfileInfo) connectedProfileInfo.classList.add('hidden');
          if (connectedProfileName) connectedProfileName.textContent = '';
          if (openSessionBtn) openSessionBtn.classList.remove('hidden');
          if (logoutSessionBtn) logoutSessionBtn.classList.add('hidden');

          if (headerBadge) headerBadge.classList.add('hidden');
          if (headerLogoutBtn) headerLogoutBtn.classList.add('hidden');

          if (profileUrlInput) {
            profileUrlInput.value = '';
            profileUrlInput.placeholder = 'Connect to load your profile';
            profileUrlInput.readOnly = true;
            profileUrlInput.disabled = true;
          }
          if (extractProfileBtn) {
            extractProfileBtn.disabled = true;
          }

          if (!options.skipNavigation) switchTab('welcome-page');
          console.log('[FLOW] Unauthenticated -> Displaying Welcome Page.');
        }
      } catch (err) {
        console.error('Failed to check Fameweb session status:', err);"""

content = content.replace(old_else, new_else)

old_onboarding = """            // Onboarding Check & Navigation
            const onboardingCompleted = data.data.onboarding_completed;"""

new_onboarding = """            // Onboarding Check & Navigation
            const onboardingCompleted = user.onboarding_step !== 'LINKEDIN';"""

content = content.replace(old_onboarding, new_onboarding)

# Also fix the fetch(/api/open-linkedin-session) block because we don't open LinkedIn automatically anymore
old_login_btn = """    if (openSessionBtn) {
      openSessionBtn.addEventListener('click', async () => {
        openSessionBtn.disabled = true;
        openSessionBtn.classList.add('opacity-70', 'cursor-not-allowed');
        try {
          // 1. Pre-check if existing session is already authenticated
          const statusRes = await fetch('/api/linkedin-session-status');
          const statusData = await statusRes.json();

          if (statusRes.ok && statusData.success && statusData.data && statusData.data.authenticated) {
            console.log('[FLOW] Session pre-check: Existing authenticated LinkedIn session detected. Proceeding directly.');
            await checkFamewebSessionStatus({ isInitialBootstrap: true });
            return;
          }

          // 2. If not authenticated, open Playwright Chromium session
          await fetch('/api/open-linkedin-session', { method: 'POST' });
          await checkFamewebSessionStatus({ isInitialBootstrap: true });
        } catch (err) {
          console.error('Error opening session browser:', err);
        } finally {
          openSessionBtn.disabled = false;
          openSessionBtn.classList.remove('opacity-70', 'cursor-not-allowed');
        }
      });
    }"""

new_login_btn = """    if (openSessionBtn) {
      openSessionBtn.addEventListener('click', async () => {
          // Do nothing, we removed LinkedIn Playwright login from Fameweb
          // They should use the Fameweb login form instead
          console.warn('LinkedIn Playwright auth is disabled for Fameweb auth.');
      });
    }"""

content = content.replace(old_login_btn, new_login_btn)

with open("static/js/app.js", "w") as f:
    f.write(content)

print("Patched app.js part 2")
