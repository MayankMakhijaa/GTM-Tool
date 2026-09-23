    const generateBtn = document.getElementById('generate-leads-btn');
    const downloadBtn = document.getElementById('download-excel-btn');
    const commentsInput = document.getElementById('linkedin-comments');

    const dashboardTableBody = document.getElementById('dashboard-table-body');
    const emailTableBody = document.getElementById('email-table-body');
    const historyTableBody = document.getElementById('history-table-body');
    const metricSpans = document.querySelectorAll('.font-stat-value');

    const navDashboard = document.getElementById('nav-dashboard');
    const navProfileOptimization = document.getElementById('nav-profile-optimization');
    const navGtmOpportunities = document.getElementById('nav-gtm-opportunities');
    const navEmail = document.getElementById('nav-email');
    const navHistory = document.getElementById('nav-history');

    const viewWelcomePage = document.getElementById('view-welcome-page');
    const viewMainDashboard = document.getElementById('view-main-dashboard');
    const viewProfileOptimization = document.getElementById('view-profile-optimization');
    const viewGtmOpportunities = document.getElementById('view-gtm-opportunities');
    const viewEmailLeads = document.getElementById('view-email-leads');
    const viewHistory = document.getElementById('view-history');

    // LinkedIn Session DOM Elements
    const sessionStatusBadge = document.getElementById('session-status-badge');
    const sessionStatusDot = document.getElementById('session-status-dot');
    const sessionStatusText = document.getElementById('session-status-text');
    const openSessionBtn = document.getElementById('open-session-btn');
    const logoutSessionBtn = document.getElementById('logout-session-btn');
    const checkSessionBtn = document.getElementById('check-session-btn');
    const connectedProfileInfo = document.getElementById('connected-profile-info');
    const connectedProfileAvatar = document.getElementById('connected-profile-avatar');
    const connectedProfileName = document.getElementById('connected-profile-name');

    window.switchTab = function(target) {
      const allViews = {
        'welcome-page': document.getElementById('view-welcome-page') || document.getElementById('view-logged-out'),
        'logged-out': document.getElementById('view-welcome-page') || document.getElementById('view-logged-out'),
        'main-dashboard': document.getElementById('view-main-dashboard'),
        'lead-gen-post': document.getElementById('view-lead-gen-post'),
        'profile-optimization': document.getElementById('view-profile-optimization'),
        'gtm-opportunities': document.getElementById('view-gtm-opportunities'),
        'email': document.getElementById('view-email-leads'),
        'history': document.getElementById('view-history')
      };

      let actualTarget = target;
      if (target === 'dashboard') {
        actualTarget = 'main-dashboard';
      } else if (target === 'logged-out') {
        actualTarget = 'welcome-page';
      }

      Object.keys(allViews).forEach(k => {
        if (allViews[k]) allViews[k].classList.add('hidden');
      });

      if (allViews[actualTarget]) {
        allViews[actualTarget].classList.remove('hidden');
      }

        if (actualTarget !== 'profile-optimization') profileOptimizationMode = 'normal';
      const isModulePage = ['profile-optimization', 'gtm-opportunities', 'lead-gen-post', 'email', 'history'].includes(actualTarget);
      const appSidebar = document.getElementById('app-sidebar');
      const mainContentWrapper = document.getElementById('main-content-wrapper');
      const appHeader = document.getElementById('app-header');

      if (isModulePage) {
        if (appSidebar) appSidebar.classList.remove('hidden');
        if (mainContentWrapper) {
          mainContentWrapper.classList.remove('pl-0');
          mainContentWrapper.classList.add('pl-60');
        }
        if (appHeader) {
          appHeader.classList.remove('left-0');
          appHeader.classList.add('left-60');
        }
        console.log(`[FLOW] Navigated to module view '${actualTarget}' -> Sidebar = visible`);
      } else {
        if (appSidebar) appSidebar.classList.add('hidden');
        if (mainContentWrapper) {
          mainContentWrapper.classList.remove('pl-60');
          mainContentWrapper.classList.add('pl-0');
        }
        if (appHeader) {
          appHeader.classList.remove('left-60');
          appHeader.classList.add('left-0');
        }
        console.log(`[FLOW] Navigated to home view '${actualTarget}' -> Sidebar = hidden`);
      }

      const navLinks = document.querySelectorAll('#main-nav a');
      navLinks.forEach(link => {
        const p = link.getAttribute('data-path');
        if (p === target || (target === 'main-dashboard' && p === 'dashboard')) {
          link.className = 'flex items-center gap-space-sm px-space-sm py-2 rounded-xl transition-colors bg-status-score-high-bg text-primary-container font-label-md';
        } else {
          link.className = 'flex items-center gap-space-sm px-space-sm py-2 rounded-xl text-text-secondary hover:bg-surface-subtle hover:text-on-surface transition-colors font-body-md text-body-md';
        }
      });

      // Module Data Fetching Triggers
      if (actualTarget === 'profile-optimization' && typeof checkLinkedInSessionStatus === 'function') {
        checkLinkedInSessionStatus({ skipNavigation: true });
          if (typeof loadGtmContextSummary === 'function') loadGtmContextSummary();
      } else if (actualTarget === 'gtm-opportunities') {
        if (typeof loadGtmContextSummary === 'function') loadGtmContextSummary();
        if (typeof fetchGtmOpportunities === 'function') fetchGtmOpportunities();
      } else if (actualTarget === 'email' && typeof fetchHistoricalEmailLeads === 'function') {
        fetchHistoricalEmailLeads();
      } else if (actualTarget === 'history' && typeof fetchHistoricalAllLeads === 'function') {
        fetchHistoricalAllLeads();
      }

      window.scrollTo({ top: 0, behavior: 'smooth' });
    };

      let profileOptimizationMode = 'normal';
    let currentUserContext = null;
    let savedGtmContext = null;

    async function checkLinkedInSessionStatus(options = {}) {
      if (sessionStatusText) sessionStatusText.textContent = 'Checking...';
      try {
        const res = await fetch('/api/linkedin-session-status');
        const data = await res.json();
        if (res.ok && data.success && data.data) {
          const isAuth = data.data.authenticated;
          const name = data.data.name || (data.data.user ? data.data.user.name : null) || 'LinkedIn Member';
          const photo = data.data.profile_photo_url;
          currentUserContext = data.data.user;
          savedGtmContext = data.data.gtm_context;

          const headerBadge = document.getElementById('header-user-badge');
          const headerName = document.getElementById('header-user-name');
          const headerAvatar = document.getElementById('header-user-avatar');
          const headerLogoutBtn = document.getElementById('header-app-logout-btn');

          const sidebarName = document.getElementById('sidebar-user-name');
          const sidebarAvatar = document.getElementById('sidebar-user-avatar');
          const welcomeHeading = document.getElementById('main-dashboard-welcome-heading');

          if (isAuth) {
            if (sessionStatusBadge) sessionStatusBadge.className = 'flex items-center gap-1.5 px-3 py-1 rounded-full bg-status-success-bg text-status-success-text font-label-sm text-label-sm font-semibold border border-status-success-border';
            if (sessionStatusDot) sessionStatusDot.className = 'w-2 h-2 rounded-full bg-status-success-text';
            if (sessionStatusText) sessionStatusText.textContent = 'Connected';

            if (connectedProfileInfo) connectedProfileInfo.classList.remove('hidden');
            if (connectedProfileName) connectedProfileName.textContent = name;
            if (connectedProfileAvatar) {
              if (photo) {
                connectedProfileAvatar.innerHTML = `<img src="${photo}" class="w-full h-full object-cover" />`;
              } else {
                const init = name ? name.substring(0, 2).toUpperCase() : 'LI';
                connectedProfileAvatar.innerHTML = `<span>${init}</span>`;
              }
            }

            if (headerBadge) headerBadge.classList.remove('hidden');
            if (headerLogoutBtn) headerLogoutBtn.classList.remove('hidden');
            if (headerName) headerName.textContent = name;
            if (headerAvatar) {
              if (photo) headerAvatar.innerHTML = `<img src="${photo}" class="w-full h-full object-cover" />`;
              else headerAvatar.innerHTML = `<span>${name.substring(0, 2).toUpperCase()}</span>`;
            }

            if (sidebarName) sidebarName.textContent = name;
            if (sidebarAvatar) {
              if (photo) sidebarAvatar.innerHTML = `<img src="${photo}" class="w-full h-full object-cover" />`;
              else sidebarAvatar.innerHTML = `<span>${name.substring(0, 2).toUpperCase()}</span>`;
            }

            if (welcomeHeading) welcomeHeading.textContent = `Welcome, ${name.split(' ')[0]}`;

            if (openSessionBtn) openSessionBtn.classList.add('hidden');
            if (logoutSessionBtn) logoutSessionBtn.classList.remove('hidden');

            if (profileUrlInput) {
              if (data.data.profile_url) {
                profileUrlInput.value = data.data.profile_url;
              }
              profileUrlInput.readOnly = true;
              profileUrlInput.disabled = true;
            }
            if (extractProfileBtn) {
              extractProfileBtn.disabled = false;
            }

            // GTM context display is loaded separately via /api/gtm-context when the GTM view is opened

            // Onboarding Check & Navigation
            const onboardingCompleted = data.data.onboarding_completed;
            const modalGtm = document.getElementById('modal-onboarding-gtm');
            const modalOpt = document.getElementById('modal-onboarding-profile-opt');
            const modalGtmExp = document.getElementById('modal-onboarding-gtm-explore');

            if (typeof resetInactivityTimer === 'function') resetInactivityTimer();

            console.log(`[FLOW] LinkedIn authentication successful. onboarding_completed = ${onboardingCompleted}`);

            if (options.isInitialBootstrap) {
              if (typeof fetchHistoricalEmailLeads === 'function') fetchHistoricalEmailLeads();
              if (typeof fetchHistoricalAllLeads === 'function') fetchHistoricalAllLeads();
              if (typeof loadGtmContextSummary === 'function') loadGtmContextSummary();
              if (typeof fetchGtmOpportunities === 'function') fetchGtmOpportunities();
            }

            if (!onboardingCompleted) {
              if (modalOpt) modalOpt.classList.add('hidden');
              if (modalGtmExp) modalGtmExp.classList.add('hidden');
              if (modalGtm) modalGtm.classList.remove('hidden');
              if (!options.skipNavigation) switchTab('welcome-page');
              console.log('[FLOW] First-time user -> Showing 3-question onboarding modal over Welcome Page.');
            } else {
              if (modalGtm) modalGtm.classList.add('hidden');
              if (modalOpt) modalOpt.classList.add('hidden');
              if (modalGtmExp) modalGtmExp.classList.add('hidden');
              if (!options.skipNavigation) switchTab('main-dashboard');
              console.log('[FLOW] Returning user -> Authenticated session active.');
            }

          } else {
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
        console.error('Failed to check LinkedIn session status:', err);
        if (sessionStatusText) sessionStatusText.textContent = 'Status Unknown';
        if (!options.skipNavigation) switchTab('welcome-page');
      }
    }

    if (openSessionBtn) {
      openSessionBtn.addEventListener('click', async () => {
        openSessionBtn.disabled = true;
        openSessionBtn.classList.add('opacity-70', 'cursor-not-allowed');
        try {
          // 1. Pre-check if existing session is already authenticated
          const statusRes = await fetch('/api/linkedin-session-status');
          const statusData = await statusRes.json();

          if (statusRes.ok && statusData.success && statusData.data && statusData.data.authenticated) {
            console.log('[FLOW] Session pre-check: Existing authenticated LinkedIn session detected. Proceeding directly.');
            await checkLinkedInSessionStatus({ isInitialBootstrap: true });
            return;
          }

          // 2. If not authenticated, open Playwright Chromium session
          await fetch('/api/open-linkedin-session', { method: 'POST' });
          await checkLinkedInSessionStatus({ isInitialBootstrap: true });
        } catch (err) {
          console.error('Error opening session browser:', err);
        } finally {
          openSessionBtn.disabled = false;
          openSessionBtn.classList.remove('opacity-70', 'cursor-not-allowed');
        }
      });
    }

    if (logoutSessionBtn) {
      logoutSessionBtn.addEventListener('click', async () => {
        if (!confirm('Are you sure you want to log out of your LinkedIn session?')) return;
        logoutSessionBtn.disabled = true;
        try {
          const res = await fetch('/api/logout-linkedin-session', { method: 'POST' });
          const data = await res.json();
          if (data.success) {
            currentExtractedData = null;
            if (profileUrlInput) {
              profileUrlInput.value = '';
              profileUrlInput.placeholder = 'Connect LinkedIn to load your profile';
            }
            if (extractProfileBtn) {
              extractProfileBtn.disabled = true;
            }
            if (currentProfileContainer) currentProfileContainer.classList.add('hidden');
            if (optimizationResultContainer) optimizationResultContainer.classList.add('hidden');
            checkLinkedInSessionStatus();
          }
        } catch (err) {
          console.error('Logout error:', err);
        } finally {
          logoutSessionBtn.disabled = false;
        }
      });
    }

    if (checkSessionBtn) {
      checkSessionBtn.addEventListener('click', () => {
        checkLinkedInSessionStatus();
      });
    }

    const navLeadGenPost = document.getElementById('nav-lead-gen-post');

    if (navDashboard) {
      navDashboard.addEventListener('click', (e) => {
        e.preventDefault();
        switchTab('dashboard');
      });
    }

    if (navProfileOptimization) {
      navProfileOptimization.addEventListener('click', (e) => {
        e.preventDefault();
        switchTab('profile-optimization');
      });
    }

    if (navGtmOpportunities) {
      navGtmOpportunities.addEventListener('click', (e) => {
        e.preventDefault();
        switchTab('gtm-opportunities');
      });
    }

    if (navLeadGenPost) {
      navLeadGenPost.addEventListener('click', (e) => {
        e.preventDefault();
        switchTab('lead-gen-post');
      });
    }

    if (navEmail) {
      navEmail.addEventListener('click', (e) => {
        e.preventDefault();
        switchTab('email');
      });
    }

    if (navHistory) {
      navHistory.addEventListener('click', (e) => {
        e.preventDefault();
        switchTab('history');
      });
    }

    // Logged Out Connect CTA Button ("Continue with LinkedIn")
    const loggedOutConnectBtn = document.getElementById('logged-out-connect-btn');
    if (loggedOutConnectBtn) {
      loggedOutConnectBtn.addEventListener('click', async () => {
        loggedOutConnectBtn.disabled = true;
        loggedOutConnectBtn.classList.add('opacity-70', 'cursor-not-allowed');
        try {
          // 1. Pre-check if existing session is already authenticated
          const statusRes = await fetch('/api/linkedin-session-status');
          const statusData = await statusRes.json();

          if (statusRes.ok && statusData.success && statusData.data && statusData.data.authenticated) {
            console.log('[FLOW] Session pre-check: Existing authenticated LinkedIn session detected. Proceeding directly.');
            await checkLinkedInSessionStatus({ isInitialBootstrap: true });
            return;
          }

          // 2. If not authenticated, open Playwright Chromium session
          await fetch('/api/open-linkedin-session', { method: 'POST' });
          await checkLinkedInSessionStatus({ isInitialBootstrap: true });
        } catch (err) {
          console.error('Error connecting LinkedIn session:', err);
        } finally {
          loggedOutConnectBtn.disabled = false;
          loggedOutConnectBtn.classList.remove('opacity-70', 'cursor-not-allowed');
        }
      });
    }

    // 30-Minute Application Inactivity Timeout Management
    let inactivityTimer = null;
    const INACTIVITY_TIMEOUT_MS = 30 * 60 * 1000; // 30 minutes

    function resetInactivityTimer() {
      if (inactivityTimer) clearTimeout(inactivityTimer);
      if (currentUserContext || (sessionStatusText && sessionStatusText.textContent === 'Connected')) {
        inactivityTimer = setTimeout(() => {
          console.log('[FLOW] 30-minute application inactivity timeout reached. Expiring application session.');
          handleAppLogout({ isTimeout: true });
        }, INACTIVITY_TIMEOUT_MS);
      }
    }

    ['pointerdown', 'keydown', 'scroll', 'click'].forEach(eventType => {
      window.addEventListener(eventType, () => {
        resetInactivityTimer();
      }, { passive: true });
    });

    async function handleAppLogout(options = {}) {
      if (!options || !options.isTimeout) {
        if (!confirm('Log out of application workspace?')) return;
      } else {
        alert('Application session expired due to 30 minutes of inactivity.\n\nPlease click "Continue with LinkedIn" to re-authenticate.');
      }

      if (inactivityTimer) {
        clearTimeout(inactivityTimer);
        inactivityTimer = null;
      }

      try {
        await fetch('/api/app-logout', { method: 'POST' });
        currentUserContext = null;
        savedGtmContext = null;

        const headerBadge = document.getElementById('header-user-badge');
        const headerName = document.getElementById('header-user-name');
        const headerAvatar = document.getElementById('header-user-avatar');
        const headerLogoutBtn = document.getElementById('header-app-logout-btn');

        if (headerBadge) headerBadge.classList.add('hidden');
        if (headerLogoutBtn) headerLogoutBtn.classList.add('hidden');
        if (headerName) headerName.textContent = '';
        if (headerAvatar) headerAvatar.innerHTML = '';

        const sidebarName = document.getElementById('sidebar-user-name');
        const sidebarAvatar = document.getElementById('sidebar-user-avatar');
        if (sidebarName) sidebarName.textContent = '';
        if (sidebarAvatar) sidebarAvatar.innerHTML = '';

        if (connectedProfileInfo) connectedProfileInfo.classList.add('hidden');
        if (connectedProfileName) connectedProfileName.textContent = '';
        if (connectedProfileAvatar) connectedProfileAvatar.innerHTML = '';

        if (openSessionBtn) {
          openSessionBtn.classList.remove('hidden', 'opacity-70', 'cursor-not-allowed');
          openSessionBtn.disabled = false;
        }
        if (logoutSessionBtn) logoutSessionBtn.classList.add('hidden');

        if (sessionStatusBadge) sessionStatusBadge.className = 'flex items-center gap-1.5 px-3 py-1 rounded-full bg-status-warning-bg text-status-warning-text font-label-sm text-label-sm font-medium border border-status-warning-border';
        if (sessionStatusDot) sessionStatusDot.className = 'w-2 h-2 rounded-full bg-status-warning-text';
        if (sessionStatusText) sessionStatusText.textContent = 'Not Connected';

        const modal1 = document.getElementById('modal-onboarding-gtm');
        const modal2 = document.getElementById('modal-onboarding-profile-opt');
        const modal3 = document.getElementById('modal-onboarding-gtm-explore');

        if (modal1) modal1.classList.add('hidden');
        if (modal2) modal2.classList.add('hidden');
        if (modal3) modal3.classList.add('hidden');

        console.log('[FLOW] Application logout -> Redirecting to Welcome Page (sidebar = hidden)');
        switchTab('welcome-page');
      } catch (err) {
        console.error('App logout failed:', err);
      }
    }

    const sidebarAppLogoutBtn = document.getElementById('sidebar-app-logout-btn');
    const headerAppLogoutBtn = document.getElementById('header-app-logout-btn');
    if (sidebarAppLogoutBtn) sidebarAppLogoutBtn.addEventListener('click', () => handleAppLogout());
    if (headerAppLogoutBtn) headerAppLogoutBtn.addEventListener('click', () => handleAppLogout());

    // Initial application bootstrap
    document.addEventListener('DOMContentLoaded', () => {
        if (typeof checkLinkedInSessionStatus === 'function') {
            checkLinkedInSessionStatus({ isInitialBootstrap: true });
        }
    });
