(function() {
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

    // GTM Opportunities DOM Elements
    const gtmOfferInput = document.getElementById('gtm-offer-input');
    const gtmIcpInput = document.getElementById('gtm-icp-input');
    const gtmContextInput = document.getElementById('gtm-context-input');
    const gtmFindBtn = document.getElementById('gtm-find-btn');
    const gtmProgressContainer = document.getElementById('gtm-progress-container');
    const gtmProgressStatus = document.getElementById('gtm-progress-status');
    const gtmFeedContainer = document.getElementById('gtm-feed-container');
    const gtmCountBadge = document.getElementById('gtm-count-badge');
    const gtmDetailModal = document.getElementById('gtm-detail-modal');
    const gtmModalCloseBtn = document.getElementById('gtm-modal-close-btn');

    // Profile Optimization DOM Elements
    const extractProfileBtn = document.getElementById('extract-profile-btn');
    const optimizeProfileBtn = document.getElementById('optimize-profile-btn');
    const profileUrlInput = document.getElementById('profile-url-input');
    const currentProfileContainer = document.getElementById('current-profile-container');
    const extractedProfileContent = document.getElementById('extracted-profile-content');
    const optimizationResultContainer = document.getElementById('optimization-result-container');
    const optOverallScore = document.getElementById('opt-overall-score');
    const optSummaryText = document.getElementById('opt-summary-text');
    const optCategoryScores = document.getElementById('opt-category-scores');
    const comparisonRowsContainer = document.getElementById('comparison-rows-container');

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

    // Progressive Extraction DOM Elements
    const extractionProgressContainer = document.getElementById('extraction-progress-container');
    const extractionCurrentStatusTitle = document.getElementById('extraction-current-status-title');
    const extractionProgressCounter = document.getElementById('extraction-progress-counter');
    const extractionSectionChecklist = document.getElementById('extraction-section-checklist');
    const extractionSpinner = document.getElementById('extraction-spinner');

    let currentExtractedData = null;
    let currentDownloadUrl = null;

    // Extraction Type DOM Elements
    const extTypeComplete = document.getElementById('ext-type-complete');
    const extTypeSelected = document.getElementById('ext-type-selected');
    const selectedSectionsContainer = document.getElementById('selected-sections-container');
    const extractProfileBtnText = document.getElementById('extract-profile-btn-text');

    if (extTypeComplete && extTypeSelected) {
      extTypeComplete.addEventListener('change', () => {
        if (extTypeComplete.checked) {
          if (selectedSectionsContainer) selectedSectionsContainer.classList.add('hidden');
          if (extractProfileBtnText) extractProfileBtnText.textContent = 'Extract Profile';
        }
      });
      extTypeSelected.addEventListener('change', () => {
        if (extTypeSelected.checked) {
          if (selectedSectionsContainer) {
            selectedSectionsContainer.classList.remove('hidden');
            selectedSectionsContainer.classList.add('flex');
          }
          if (extractProfileBtnText) extractProfileBtnText.textContent = 'Extract Selected Sections';
        }
      });
    }

    const defaultChecklistSections = [
      { id: 'name', label: 'Name' },
      { id: 'headline', label: 'Headline' },
      { id: 'about', label: 'About' },
      { id: 'experience', label: 'Experience' },
      { id: 'education', label: 'Education' },
      { id: 'skills', label: 'Skills' },
      { id: 'certifications', label: 'Certifications' },
      { id: 'projects', label: 'Projects' }
    ];
    let sectionStates = {};

    function initExtractionChecklist(selectedSectionIds) {
      if (!extractionSectionChecklist) return;
      sectionStates = {};
      const activeSections = (selectedSectionIds && selectedSectionIds.length > 0)
        ? defaultChecklistSections.filter(s => selectedSectionIds.includes(s.id))
        : defaultChecklistSections;
      activeSections.forEach(s => {
        sectionStates[s.id] = { label: s.label, status: 'pending' };
      });
      renderChecklistUI();
    }

    function updateChecklistSection(sectionId, status) {
      if (!sectionStates[sectionId]) {
        sectionStates[sectionId] = { label: sectionId, status: status };
      } else {
        sectionStates[sectionId].status = status;
      }
      renderChecklistUI();
    }

    function renderChecklistUI() {
      if (!extractionSectionChecklist) return;
      let completedCount = 0;
      const keys = Object.keys(sectionStates);
      const totalCount = keys.length;
      let html = '';

      keys.forEach(id => {
        const item = sectionStates[id];
        let iconHtml = '';
        let textClass = 'text-text-muted';
        let bgClass = 'bg-surface-canvas border-border-default/50';

        if (item.status === 'completed') {
          completedCount++;
          iconHtml = `<span class="material-symbols-outlined text-[16px] text-status-success-text shrink-0">check_circle</span>`;
          textClass = 'text-text-primary font-medium';
          bgClass = 'bg-status-success-bg/40 border-status-success-border/60';
        } else if (item.status === 'extracting') {
          iconHtml = `<span class="material-symbols-outlined text-[16px] text-primary-container animate-spin shrink-0">sync</span>`;
          textClass = 'text-primary-container font-semibold';
          bgClass = 'bg-status-score-high-bg border-primary-container/30';
        } else {
          iconHtml = `<span class="material-symbols-outlined text-[16px] text-text-muted shrink-0">radio_button_unchecked</span>`;
        }

        html += `
          <div class="p-2 px-3 rounded-lg border flex items-center gap-2 text-body-sm ${bgClass}">
            ${iconHtml}
            <span class="${textClass} truncate">${item.label}</span>
          </div>
        `;
      });

      extractionSectionChecklist.innerHTML = html;
      if (extractionProgressCounter) {
        extractionProgressCounter.textContent = `${completedCount} / ${totalCount} Sections`;
      }
    }

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
      } else if (actualTarget === 'gtm-opportunities') {
        if (savedGtmContext) {
          if (gtmOfferInput && !gtmOfferInput.value) gtmOfferInput.value = savedGtmContext.offer || '';
          if (gtmIcpInput && !gtmIcpInput.value) gtmIcpInput.value = savedGtmContext.target_icp || '';
          if (gtmContextInput && !gtmContextInput.value) gtmContextInput.value = savedGtmContext.additional_context || '';
        }
        if (typeof fetchGtmOpportunities === 'function') fetchGtmOpportunities();
      } else if (actualTarget === 'email' && typeof fetchHistoricalEmailLeads === 'function') {
        fetchHistoricalEmailLeads();
      } else if (actualTarget === 'history' && typeof fetchHistoricalAllLeads === 'function') {
        fetchHistoricalAllLeads();
      }

      window.scrollTo({ top: 0, behavior: 'smooth' });
    };

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

            // Populate saved GTM context into GTM & Profile Optimization inputs
            if (savedGtmContext) {
              if (gtmOfferInput) gtmOfferInput.value = savedGtmContext.offer || '';
              if (gtmIcpInput) gtmIcpInput.value = savedGtmContext.target_icp || '';
              if (gtmContextInput) gtmContextInput.value = savedGtmContext.additional_context || '';
            }

            // Onboarding Check & Navigation
            const onboardingCompleted = data.data.onboarding_completed;
            const modalGtm = document.getElementById('modal-onboarding-gtm');
            const modalOpt = document.getElementById('modal-onboarding-profile-opt');
            const modalGtmExp = document.getElementById('modal-onboarding-gtm-explore');

            if (typeof resetInactivityTimer === 'function') resetInactivityTimer();

            console.log(`[FLOW] LinkedIn authentication successful. onboarding_completed = ${onboardingCompleted}`);

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

    // Fetch historical email leads from /api/email-leads
    async function fetchHistoricalEmailLeads() {
      try {
        const res = await fetch('/api/email-leads');
        const data = await res.json();
        if (res.ok && data.success) {
          renderEmailTable(data.leads || []);
        }
      } catch (err) {
        console.error('Failed to fetch historical email leads:', err);
      }
    }

    // Fetch all historical leads from /api/history-leads
    async function fetchHistoricalAllLeads() {
      try {
        const res = await fetch('/api/history-leads');
        const data = await res.json();
        if (res.ok && data.success) {
          renderHistoryTable(data.leads || []);
        }
      } catch (err) {
        console.error('Failed to fetch all historical leads:', err);
      }
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

    // Render Extracted Profile Verification View
    function renderExtractedProfile(data) {
      const p = (data && data.profile) ? data.profile : (data || {});
      let html = '';

      html += `
        <div class="p-space-md bg-surface-canvas rounded-xl flex items-start justify-between gap-space-md border border-border-default/60">
          <div class="flex items-center gap-space-md">
            <div class="w-14 h-14 rounded-full bg-primary-container flex items-center justify-center text-on-primary font-headline-lg text-[18px] shrink-0 font-bold overflow-hidden shadow-sm">
              ${p.profile_photo_url ? `<img src="${p.profile_photo_url}" class="w-full h-full object-cover" />` : (p.name ? p.name.substring(0,2).toUpperCase() : 'PRO')}
            </div>
            <div class="flex flex-col gap-0.5">
              <h3 class="font-headline-sm text-headline-sm text-text-primary">${p.name || 'Profile Name Not Extracted'}</h3>
              ${p.headline ? `<p class="font-body-md text-body-md text-primary-container font-medium">${p.headline}</p>` : '<p class="font-body-md text-body-md text-text-muted italic">Headline not available</p>'}
              ${p.current_position ? `<span class="font-label-sm text-label-sm text-text-secondary">${p.current_position}</span>` : ''}
            </div>
          </div>
        </div>
      `;

      if (p.about) {
        html += `
          <div class="p-space-md bg-surface-canvas rounded-xl flex flex-col gap-1.5 border border-border-default/60">
            <h4 class="font-label-md text-label-md text-text-muted uppercase tracking-wider">About</h4>
            <p class="font-body-md text-body-md text-text-primary whitespace-pre-line">${p.about}</p>
          </div>
        `;
      }

      if (p.top_skills && p.top_skills.length > 0) {
        html += `
          <div class="p-space-md bg-surface-canvas rounded-xl flex flex-col gap-1.5 border border-border-default/60">
            <h4 class="font-label-md text-label-md text-text-muted uppercase tracking-wider mb-1">Top Skills (${p.top_skills.length})</h4>
            <div class="flex flex-wrap gap-2">
              ${p.top_skills.map(s => `<span class="px-3 py-1 rounded-lg bg-surface-card border border-border-default font-label-sm text-label-sm text-primary-container font-medium">${s}</span>`).join('')}
            </div>
          </div>
        `;
      }

      if (p.experience && p.experience.length > 0) {
        html += `
          <div class="p-space-md bg-surface-canvas rounded-xl flex flex-col gap-space-xs border border-border-default/60">
            <h4 class="font-label-md text-label-md text-text-muted uppercase tracking-wider mb-1">Experience (${p.experience.length})</h4>
            <div class="flex flex-col gap-3 divide-y divide-border-default/60">
        `;
        p.experience.forEach(exp => {
          html += `
            <div class="pt-2.5 first:pt-0 flex flex-col gap-0.5">
              <div class="flex items-center justify-between">
                <span class="font-label-md text-label-md text-text-primary font-semibold">${exp.title || exp.role || 'Role'}</span>
                <span class="font-label-sm text-label-sm text-text-muted">${exp.start_date || exp.dates || ''}</span>
              </div>
              <span class="font-body-sm text-body-sm text-primary-container font-medium">${exp.company || ''} ${exp.location ? 'â€¢ ' + exp.location : ''}</span>
              ${exp.description ? `<p class="font-body-sm text-body-sm text-text-secondary pt-1 whitespace-pre-line">${exp.description}</p>` : ''}
            </div>
          `;
        });
        html += `</div></div>`;
      }

      if (p.education && p.education.length > 0) {
        html += `
          <div class="p-space-md bg-surface-canvas rounded-xl flex flex-col gap-space-xs border border-border-default/60">
            <h4 class="font-label-md text-label-md text-text-muted uppercase tracking-wider mb-1">Education (${p.education.length})</h4>
            <div class="flex flex-col gap-2 divide-y divide-border-default/60">
        `;
        p.education.forEach(edu => {
          html += `
            <div class="pt-2 first:pt-0 flex items-center justify-between">
              <div class="flex flex-col">
                <span class="font-label-md text-label-md text-text-primary font-medium">${edu.institution || ''}</span>
                <span class="font-body-sm text-body-sm text-text-secondary">${edu.degree || ''} ${edu.field_of_study ? 'â€¢ ' + edu.field_of_study : ''}</span>
                ${edu.description ? `<p class="font-body-sm text-body-sm text-text-muted pt-0.5">${edu.description}</p>` : ''}
              </div>
              <span class="font-label-sm text-label-sm text-text-muted shrink-0">${edu.start_date || edu.dates || ''}</span>
            </div>
          `;
        });
        html += `</div></div>`;
      }

      if (p.skills && p.skills.length > 0) {
        html += `
          <div class="p-space-md bg-surface-canvas rounded-xl flex flex-col gap-1.5 border border-border-default/60">
            <h4 class="font-label-md text-label-md text-text-muted uppercase tracking-wider mb-1">Full Skills (${p.skills.length})</h4>
            <div class="flex flex-wrap gap-2">
              ${p.skills.map(s => {
                const sName = typeof s === 'object' ? s.name : s;
                return `<span class="px-3 py-1 rounded-lg bg-surface-card border border-border-default font-label-sm text-label-sm text-text-primary">${sName}</span>`;
              }).join('')}
            </div>
          </div>
        `;
      }

      if (p.certifications && p.certifications.length > 0) {
        html += `
          <div class="p-space-md bg-surface-canvas rounded-xl flex flex-col gap-space-xs border border-border-default/60">
            <h4 class="font-label-md text-label-md text-text-muted uppercase tracking-wider mb-1">Certifications (${p.certifications.length})</h4>
            <div class="flex flex-col gap-2">
              ${p.certifications.map(c => `
                <div class="flex items-center justify-between">
                  <span class="font-label-md text-label-md text-text-primary font-medium">${typeof c === 'object' ? c.name : c}</span>
                  ${typeof c === 'object' && c.issuing_organization ? `<span class="font-body-sm text-body-sm text-text-secondary">${c.issuing_organization}</span>` : ''}
                </div>
              `).join('')}
            </div>
          </div>
        `;
      }

      if (p.honors_awards && p.honors_awards.length > 0) {
        html += `
          <div class="p-space-md bg-surface-canvas rounded-xl flex flex-col gap-space-xs border border-border-default/60">
            <h4 class="font-label-md text-label-md text-text-muted uppercase tracking-wider mb-1">Honors & Awards (${p.honors_awards.length})</h4>
            <div class="flex flex-col gap-2">
              ${p.honors_awards.map(h => `
                <div class="flex flex-col">
                  <span class="font-label-md text-label-md text-text-primary font-medium">${h.title}</span>
                  ${h.issuer ? `<span class="font-body-sm text-body-sm text-text-secondary">${h.issuer}</span>` : ''}
                </div>
              `).join('')}
            </div>
          </div>
        `;
      }

      if (p.featured && p.featured.length > 0) {
        html += `
          <div class="p-space-md bg-surface-canvas rounded-xl flex flex-col gap-space-xs border border-border-default/60">
            <h4 class="font-label-md text-label-md text-text-muted uppercase tracking-wider mb-1">Featured Items (${p.featured.length})</h4>
            <div class="flex flex-col gap-2">
              ${p.featured.map(f => `
                <div class="p-2.5 rounded-lg bg-surface-card border border-border-default flex flex-col gap-0.5">
                  <span class="font-label-md text-label-md text-text-primary font-medium">${typeof f === 'object' ? f.title : f}</span>
                  ${typeof f === 'object' && f.description ? `<p class="font-body-sm text-body-sm text-text-secondary line-clamp-2">${f.description}</p>` : ''}
                </div>
              `).join('')}
            </div>
          </div>
        `;
      }

      extractedProfileContent.innerHTML = html;
    }

    // Render Optimization Result Comparison
    function renderOptimizationResult(data) {
      optOverallScore.textContent = data.overall_score || 78;
      optSummaryText.textContent = data.summary_assessment || "Strategic positioning and discoverability analysis completed.";

      const cats = data.category_scores || {};
      let catHtml = '';
      Object.keys(cats).forEach(key => {
        const score = cats[key];
        catHtml += `
          <div class="p-2 px-3.5 rounded-xl bg-surface-canvas flex flex-col items-center justify-center border border-border-default/60 shadow-sm">
            <span class="font-label-sm text-[11px] text-text-muted capitalize">${key}</span>
            <span class="font-label-md text-label-md font-bold text-primary-container">${score}/100</span>
          </div>
        `;
      });
      optCategoryScores.innerHTML = catHtml;

      const recs = data.recommendations || [];
      comparisonRowsContainer.innerHTML = '';

      recs.forEach((rec) => {
        const card = document.createElement('div');
        card.className = 'grid grid-cols-1 lg:grid-cols-2 p-space-md gap-space-md hover:bg-surface-canvas/30 transition-colors group';

        const prioColor = rec.priority === 'high' ? 'bg-status-score-high-bg text-status-score-high-text' : (rec.priority === 'medium' ? 'bg-status-success-bg text-status-success-text' : 'bg-surface-subtle text-text-muted');

        const isNoChange = (rec.change_required === false) || (rec.action_type === 'none') || (!rec.suggested) || (rec.suggested.toLowerCase().includes('no changes recommended'));
        const isAskChatGPT = rec.action_type === 'ask_chatgpt';

        const currentText = rec.current && rec.current.trim() !== '' ? rec.current : 'Not available';
        const suggestedText = isNoChange ? 'No changes recommended.' : (rec.suggested || '');

        let actionButtonHtml = '';
        if (isNoChange) {
          actionButtonHtml = `
            <div class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-status-success-bg text-status-success-text font-label-md text-label-md font-semibold border border-status-success-border/60">
              <span class="material-symbols-outlined text-[16px]">task_alt</span>
              <span>You're good to go âœ“</span>
            </div>
          `;
        } else if (isAskChatGPT) {
          actionButtonHtml = `
            <button type="button" class="ask-chatgpt-btn px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-label-md text-label-md transition-all flex items-center gap-1.5 shadow-sm active:scale-[0.98]">
              <span class="material-symbols-outlined text-[16px]">open_in_new</span>
              <span>Ask ChatGPT</span>
            </button>
          `;
        } else { // Copy
          actionButtonHtml = `
            <button type="button" class="copy-suggestion-btn px-4 py-2 rounded-xl bg-primary-container hover:bg-primary text-on-primary font-label-md text-label-md transition-all flex items-center gap-1.5 shadow-sm active:scale-[0.98]">
              <span class="material-symbols-outlined text-[16px]">content_copy</span>
              <span>Copy</span>
            </button>
          `;
        }

        card.innerHTML = `
          <!-- Left Column: CURRENT -->
          <div class="flex flex-col gap-2 lg:pr-space-md border-b lg:border-b-0 lg:border-r border-border-default/60 pb-space-md lg:pb-0">
            <div class="flex items-center justify-between">
              <span class="font-label-md text-label-md font-semibold text-text-primary uppercase tracking-wider">${rec.title || rec.section}</span>
              <span class="px-2 py-0.5 rounded-full text-[10px] font-mono bg-surface-subtle text-text-muted">Current</span>
            </div>
            <div class="p-3.5 rounded-xl bg-surface-canvas font-body-md text-body-md text-text-secondary whitespace-pre-line border border-border-default/40">
              ${currentText}
            </div>
          </div>

          <!-- Right Column: SUGGESTED -->
          <div class="flex flex-col gap-2 justify-between">
            <div class="flex flex-col gap-2">
              <div class="flex items-center justify-between">
                <span class="font-label-md text-label-md font-semibold text-primary-container uppercase tracking-wider">AI Suggestion</span>
                <span class="px-2.5 py-0.5 rounded-full text-[11px] font-label-sm font-semibold capitalize ${prioColor}">${rec.priority && rec.priority !== 'none' ? rec.priority + ' Priority' : 'Verified'}</span>
              </div>

              <div class="p-3.5 rounded-xl ${isNoChange ? 'bg-surface-canvas border border-border-default/40' : 'bg-status-success-bg/40 border border-status-success-border/60'} font-body-md text-body-md text-text-primary whitespace-pre-line">
                ${suggestedText}
              </div>

              ${rec.reason ? `
                <div class="p-2.5 px-3 rounded-lg bg-surface-canvas flex items-start gap-2 text-text-secondary font-body-sm text-body-sm">
                  <span class="material-symbols-outlined text-[16px] text-primary-container shrink-0 mt-0.5">info</span>
                  <span><strong>WHY:</strong> ${rec.reason}</span>
                </div>
              ` : ''}
            </div>

            <div class="flex justify-end gap-2 pt-2">
              ${actionButtonHtml}
            </div>
          </div>
        `;

        // Event listeners for action buttons
        const copyBtn = card.querySelector('.copy-suggestion-btn');
        if (copyBtn) {
          copyBtn.addEventListener('click', () => {
            navigator.clipboard.writeText(rec.suggested || '');
            const orig = copyBtn.innerHTML;
            copyBtn.className = 'copy-suggestion-btn px-4 py-2 rounded-xl bg-status-success-bg text-status-success-text font-label-md text-label-md border border-status-success-border flex items-center gap-1.5 shadow-sm';
            copyBtn.innerHTML = `<span class="material-symbols-outlined text-[16px]">check</span><span>Copied!</span>`;
            setTimeout(() => {
              copyBtn.className = 'copy-suggestion-btn px-4 py-2 rounded-xl bg-primary-container hover:bg-primary text-on-primary font-label-md text-label-md transition-all flex items-center gap-1.5 shadow-sm active:scale-[0.98]';
              copyBtn.innerHTML = orig;
            }, 2000);
          });
        }

        const askBtn = card.querySelector('.ask-chatgpt-btn');
        if (askBtn) {
          askBtn.addEventListener('click', () => {
            const promptText = `I am optimizing my LinkedIn profile for lead generation. Based on my profile analysis, I need to create/add content for section '${rec.title || rec.section}'. Context & Recommendation: ${rec.suggested}. Reason: ${rec.reason || ''}. Please help me draft high-converting content for this section based on these details.`;
            
            // Clipboard fallback: Always copy prompt to clipboard in case ChatGPT doesn't prefill query parameters
            if (navigator.clipboard && navigator.clipboard.writeText) {
              navigator.clipboard.writeText(promptText).catch(() => {});
            }

            // Safely URL-encode the prompt using URL API
            const chatgptUrl = new URL('https://chatgpt.com/');
            chatgptUrl.searchParams.set('q', promptText);

            window.open(chatgptUrl.toString(), '_blank');

            const origHTML = askBtn.innerHTML;
            askBtn.innerHTML = `<span class="material-symbols-outlined text-[16px]">check</span><span>Prompt Copied & Opened</span>`;
            setTimeout(() => { askBtn.innerHTML = origHTML; }, 3000);
          });
        }

        comparisonRowsContainer.appendChild(card);
      });
    }

    // Extract Profile Event Handler
    if (extractProfileBtn) {
      extractProfileBtn.addEventListener('click', async () => {
        const url = profileUrlInput ? profileUrlInput.value.trim() : '';
        if (!url) {
          alert('Please connect your LinkedIn account first to load your profile.');
          return;
        }

        const isSelectedType = extTypeSelected && extTypeSelected.checked;
        let selectedSections = null;

        if (isSelectedType) {
          const checkedBoxes = Array.from(document.querySelectorAll('.section-checkbox:checked')).map(cb => cb.value);
          if (checkedBoxes.length === 0) {
            alert('Please select at least one section to continue.');
            return;
          }
          selectedSections = checkedBoxes;
        }

        if (extTypeComplete) extTypeComplete.disabled = true;
        if (extTypeSelected) extTypeSelected.disabled = true;
        document.querySelectorAll('.section-checkbox').forEach(cb => cb.disabled = true);

        const originalHTML = extractProfileBtn.innerHTML;
        extractProfileBtn.disabled = true;
        extractProfileBtn.classList.add('opacity-80', 'cursor-not-allowed');
        extractProfileBtn.innerHTML = `
          <svg class="animate-spin h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          <span>Extracting profile...</span>
        `;

        if (extractionProgressContainer) extractionProgressContainer.classList.remove('hidden');
        initExtractionChecklist(selectedSections);

        let partialProfile = {
          tenant_id: "default_tenant",
          user_id: "pro_user",
          source_url: url,
          selected_sections: selectedSections,
          profile: {
            name: null,
            profile_photo_url: null,
            headline: null,
            about: null,
            current_position: null,
            top_skills: [],
            experience: [],
            education: [],
            skills: [],
            certifications: [],
            featured: [],
            honors_awards: []
          }
        };

        try {
          let fetchUrl = `/api/extract-profile-stream?profile_url=${encodeURIComponent(url)}`;
          if (selectedSections && selectedSections.length > 0) {
            fetchUrl += `&selected_sections=${encodeURIComponent(selectedSections.join(','))}`;
          }

          const response = await fetch(fetchUrl);
          if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.error || 'Profile extraction failed.');
          }

          const reader = response.body.getReader();
          const decoder = new TextDecoder();
          let buffer = '';

          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const parts = buffer.split('\n\n');
            buffer = parts.pop();

            for (const part of parts) {
              if (part.startsWith('data: ')) {
                const jsonStr = part.substring(6).trim();
                if (!jsonStr) continue;
                const event = JSON.parse(jsonStr);

                if (event.event === 'error') {
                  throw new Error(event.error);
                } else if (event.event === 'status') {
                  if (extractionCurrentStatusTitle) extractionCurrentStatusTitle.textContent = event.message || 'Extracting Profile...';
                } else if (event.event === 'section_start') {
                  updateChecklistSection(event.section, 'extracting');
                  if (extractionCurrentStatusTitle) extractionCurrentStatusTitle.textContent = `Extracting ${event.label || event.section}...`;
                } else if (event.event === 'section_complete') {
                  updateChecklistSection(event.section, 'completed');

                  if (event.section === 'name') {
                    partialProfile.profile.name = event.data;
                    if (event.photo_url) partialProfile.profile.profile_photo_url = event.photo_url;
                  } else if (event.section === 'headline') {
                    partialProfile.profile.headline = event.data;
                  } else if (event.section === 'about') {
                    partialProfile.profile.about = event.data;
                    if (event.top_skills) partialProfile.profile.top_skills = event.top_skills;
                  } else if (event.section === 'experience') {
                    partialProfile.profile.experience = event.data || [];
                    if (partialProfile.profile.experience.length > 0) {
                      const top = partialProfile.profile.experience[0];
                      partialProfile.profile.current_position = top.company ? `${top.title} @ ${top.company}` : top.title;
                    }
                  } else if (event.section === 'education') {
                    partialProfile.profile.education = event.data || [];
                  } else if (event.section === 'skills') {
                    partialProfile.profile.skills = event.data || [];
                  } else if (event.section === 'certifications') {
                    partialProfile.profile.certifications = event.data || [];
                  } else if (event.section === 'projects') {
                    partialProfile.profile.projects = event.data || [];
                  }

                  currentExtractedData = partialProfile;
                  renderExtractedProfile(currentExtractedData);
                  currentProfileContainer.classList.remove('hidden');

                } else if (event.event === 'complete') {
                  currentExtractedData = event.full_profile || partialProfile;
                  renderExtractedProfile(currentExtractedData);
                  currentProfileContainer.classList.remove('hidden');
                  if (extractionCurrentStatusTitle) extractionCurrentStatusTitle.textContent = 'Extraction Complete âœ“';
                  if (extractionSpinner) extractionSpinner.className = 'material-symbols-outlined text-[18px] text-status-success-text';
                }
              }
            }
          }

          extractProfileBtn.innerHTML = `
            <span class="material-symbols-outlined text-[18px]">check</span>
            <span>Extracted</span>
          `;
          setTimeout(() => { extractProfileBtn.innerHTML = originalHTML; }, 2000);

        } catch (err) {
          alert(err.message || 'Profile extraction failed. Please verify your LinkedIn session and try again.');
          extractProfileBtn.innerHTML = originalHTML;
        } finally {
          if (extTypeComplete) extTypeComplete.disabled = false;
          if (extTypeSelected) extTypeSelected.disabled = false;
          document.querySelectorAll('.section-checkbox').forEach(cb => cb.disabled = false);

          extractProfileBtn.classList.remove('opacity-80', 'cursor-not-allowed');
          extractProfileBtn.disabled = false;
        }
      });
    }

    // Optimize Profile Event Handler
    if (optimizeProfileBtn) {
      optimizeProfileBtn.addEventListener('click', async () => {
        if (!currentExtractedData) {
          alert('Please extract a profile first.');
          return;
        }

        const originalHTML = optimizeProfileBtn.innerHTML;
        optimizeProfileBtn.disabled = true;
        optimizeProfileBtn.classList.add('opacity-80', 'cursor-not-allowed');
        optimizeProfileBtn.innerHTML = `
          <svg class="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          <span>Analyzing & Optimizing...</span>
        `;

        try {
          const res = await fetch('/api/optimize-profile', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ profile: currentExtractedData })
          });
          const result = await res.json();

          if (!res.ok || !result.success) {
            throw new Error(result.error || 'Profile optimization failed.');
          }

          renderOptimizationResult(result.data);
          optimizationResultContainer.classList.remove('hidden');
          optimizationResultContainer.scrollIntoView({ behavior: 'smooth' });

          // Unhide Modal 3 (GTM Exploration Choice) after profile optimization completes
          const modal3 = document.getElementById('modal-onboarding-gtm-explore');
          if (modal3 && (!savedGtmContext || !savedGtmContext.onboarding_completed)) {
            modal3.classList.remove('hidden');
            console.log('[FLOW] Profile optimization completed -> Displaying GTM Exploration choice modal');
          }

          optimizeProfileBtn.innerHTML = `
            <span class="material-symbols-outlined text-[20px]">check</span>
            <span>Optimization Complete</span>
          `;
          setTimeout(() => { optimizeProfileBtn.innerHTML = originalHTML; }, 2500);

        } catch (err) {
          alert(err.message || 'Profile optimization failed.');
          optimizeProfileBtn.innerHTML = originalHTML;
        } finally {
          optimizeProfileBtn.classList.remove('opacity-80', 'cursor-not-allowed');
          optimizeProfileBtn.disabled = false;
        }
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

    // Onboarding Modal 1 Handler: Save 3 Questions
    const onboardingSaveBtn = document.getElementById('onboarding-gtm-save-btn');
    if (onboardingSaveBtn) {
      onboardingSaveBtn.addEventListener('click', async () => {
        const offerInput = document.getElementById('onboarding-offer-input');
        const icpInput = document.getElementById('onboarding-icp-input');
        const contextInput = document.getElementById('onboarding-context-input');

        const offer = offerInput ? offerInput.value.trim() : '';
        const target_icp = icpInput ? icpInput.value.trim() : '';
        const additional_context = contextInput ? contextInput.value.trim() : '';

        if (!offer || !target_icp) {
          alert('Please enter what you are offering and your target ICP.');
          return;
        }

        onboardingSaveBtn.disabled = true;
        onboardingSaveBtn.classList.add('opacity-70', 'cursor-not-allowed');

        try {
          const res = await fetch('/api/onboarding/save-gtm-context', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ offer, target_icp, additional_context })
          });
          const data = await res.json();
          if (!res.ok || !data.success) {
            throw new Error(data.error || 'Failed to save onboarding responses.');
          }

          savedGtmContext = data.data;

          // Pre-fill inputs for GTM Opportunities module
          if (gtmOfferInput) gtmOfferInput.value = offer;
          if (gtmIcpInput) gtmIcpInput.value = target_icp;
          if (gtmContextInput) gtmContextInput.value = additional_context;

          const modal1 = document.getElementById('modal-onboarding-gtm');
          const modal2 = document.getElementById('modal-onboarding-profile-opt');

          if (modal1) modal1.classList.add('hidden');
          if (modal2) modal2.classList.remove('hidden');

        } catch (err) {
          alert(err.message || 'Failed to save onboarding answers.');
        } finally {
          onboardingSaveBtn.disabled = false;
          onboardingSaveBtn.classList.remove('opacity-70', 'cursor-not-allowed');
        }
      });
    }

    // Onboarding Modal 2 Handlers: Profile Optimization Choice
    const onboardingOptYesBtn = document.getElementById('onboarding-opt-yes-btn');
    const onboardingOptSkipBtn = document.getElementById('onboarding-opt-skip-btn');

    if (onboardingOptYesBtn) {
      onboardingOptYesBtn.addEventListener('click', () => {
        const modal2 = document.getElementById('modal-onboarding-profile-opt');
        if (modal2) modal2.classList.add('hidden');

        console.log('[FLOW] User clicked Yes, Optimize Profile -> Navigating to Profile Optimization view (sidebar = visible)');
        switchTab('profile-optimization');

        // Trigger profile extraction if connected and input has value
        if (extractProfileBtn && !extractProfileBtn.disabled) {
          if (!currentExtractedData && profileUrlInput && profileUrlInput.value) {
            extractProfileBtn.click();
          }
        }
      });
    }

    if (onboardingOptSkipBtn) {
      onboardingOptSkipBtn.addEventListener('click', () => {
        const modal2 = document.getElementById('modal-onboarding-profile-opt');
        const modal3 = document.getElementById('modal-onboarding-gtm-explore');

        if (modal2) modal2.classList.add('hidden');
        if (modal3) modal3.classList.remove('hidden');
        console.log('[FLOW] User skipped Profile Optimization -> Showing GTM Exploration choice modal');
      });
    }

    // Onboarding Modal 3 Handlers: GTM Exploration Choice
    const onboardingGtmExploreBtn = document.getElementById('onboarding-gtm-explore-btn');
    const onboardingDashboardBtn = document.getElementById('onboarding-dashboard-btn');

    if (onboardingGtmExploreBtn) {
      onboardingGtmExploreBtn.addEventListener('click', () => {
        const modal3 = document.getElementById('modal-onboarding-gtm-explore');
        if (modal3) modal3.classList.add('hidden');

        if (savedGtmContext) {
          if (gtmOfferInput) gtmOfferInput.value = savedGtmContext.offer || '';
          if (gtmIcpInput) gtmIcpInput.value = savedGtmContext.target_icp || '';
          if (gtmContextInput) gtmContextInput.value = savedGtmContext.additional_context || '';
        }

        console.log('[FLOW] User clicked Explore GTM Opportunities -> Navigating to GTM Opportunities view (sidebar = visible)');
        switchTab('gtm-opportunities');
      });
    }

    if (onboardingDashboardBtn) {
      onboardingDashboardBtn.addEventListener('click', () => {
        const modal1 = document.getElementById('modal-onboarding-gtm');
        const modal2 = document.getElementById('modal-onboarding-profile-opt');
        const modal3 = document.getElementById('modal-onboarding-gtm-explore');

        if (modal1) modal1.classList.add('hidden');
        if (modal2) modal2.classList.add('hidden');
        if (modal3) modal3.classList.add('hidden');

        console.log('[FLOW] User clicked Go to Dashboard -> Navigating to Main Dashboard (sidebar = hidden)');
        switchTab('main-dashboard');
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

    if (sidebarAppLogoutBtn) sidebarAppLogoutBtn.addEventListener('click', () => handleAppLogout());
    if (headerAppLogoutBtn) headerAppLogoutBtn.addEventListener('click', () => handleAppLogout());

    // Render Dashboard table (current run)
    function renderDashboardTable(leads) {
      dashboardTableBody.innerHTML = '';
      if (leads && leads.length > 0) {
        leads.slice(0, 10).forEach(lead => {
          const row = document.createElement('tr');
          row.className = 'hover:bg-surface-canvas/60 transition-colors group';

          const initials = lead.name ? lead.name.substring(0, 2).toUpperCase() : '??';
          const name = lead.name || 'Unknown';
          const company = lead.company || '-';
          const role = lead.role || '-';
          const need = lead.business_need || '-';
          const intent = lead.intent || '-';
          const score = lead.lead_score || 0;

          const profileUrl = lead.profile_url || '';
          const profileHtml = profileUrl ? 
            `<a href="${profileUrl}" target="_blank" rel="noopener noreferrer" class="inline-flex items-center gap-1 text-primary-container hover:underline font-label-sm text-label-sm">
               <span>View Profile</span>
               <span class="material-symbols-outlined text-[14px]">open_in_new</span>
             </a>` : '<span class="text-text-muted text-label-sm">-</span>';

          row.innerHTML = `
            <td class="py-3.5 px-4 whitespace-nowrap">
              <span class="inline-flex items-center px-2 py-0.5 rounded-md font-label-md text-label-sm bg-status-score-high-bg text-status-score-high-text font-mono font-semibold">
                ${score}/100
              </span>
            </td>
            <td class="py-3.5 px-4 whitespace-nowrap">
              <div class="flex items-center gap-2.5">
                <div class="w-7 h-7 rounded-full bg-primary-fixed flex items-center justify-center text-on-primary-fixed font-label-md text-[11px] shrink-0 font-medium">
                  ${initials}
                </div>
                <div class="flex flex-col min-w-0">
                  <span class="font-label-md text-label-md text-text-primary truncate">${name}</span>
                </div>
              </div>
            </td>
            <td class="py-3.5 px-4 whitespace-nowrap font-medium text-text-primary">${company}</td>
            <td class="py-3.5 px-4 whitespace-nowrap text-text-secondary">${role}</td>
            <td class="py-3.5 px-4 text-text-secondary">
              <div class="line-clamp-1 max-w-[360px]" title="${need}">
                ${need}
              </div>
            </td>
            <td class="py-3.5 px-4 whitespace-nowrap">
              <span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-status-success-bg text-status-success-text font-label-sm text-label-sm">
                ${intent}
              </span>
            </td>
            <td class="py-3.5 px-4 whitespace-nowrap text-right">
              ${profileHtml}
            </td>
          `;
          dashboardTableBody.appendChild(row);
        });
      } else {
        dashboardTableBody.innerHTML = `
          <tr>
            <td colspan="7" class="py-8 text-center text-text-muted">
              No leads generated yet. Paste a LinkedIn post URL above to get started.
            </td>
          </tr>
        `;
      }
    }

    // Render Email table (historical email store)
    function renderEmailTable(leads) {
      if (!emailTableBody) return;

      const emailLeads = (leads || []).filter(l => l && l.email && typeof l.email === 'string' && l.email.trim() !== '');

      const countBadge = document.getElementById('email-leads-count-badge');
      if (countBadge) {
        countBadge.textContent = `${emailLeads.length} Email Qualified`;
      }

      emailTableBody.innerHTML = '';
      if (emailLeads.length > 0) {
        emailLeads.forEach(lead => {
          const row = document.createElement('tr');
          row.className = 'hover:bg-surface-canvas/60 transition-colors group';

          const initials = lead.name ? lead.name.substring(0, 2).toUpperCase() : '??';
          const name = lead.name || 'Unknown';
          const company = lead.company || '-';
          const need = lead.business_need || '-';
          const reason = lead.reason || '-';
          const score = lead.lead_score || 0;
          const email = lead.email.trim();

          row.innerHTML = `
            <td class="py-3.5 px-4 whitespace-nowrap">
              <span class="inline-flex items-center px-2 py-0.5 rounded-md font-label-md text-label-sm bg-status-score-high-bg text-status-score-high-text font-mono font-semibold">
                ${score}/100
              </span>
            </td>
            <td class="py-3.5 px-4 whitespace-nowrap">
              <div class="flex items-center gap-2.5">
                <div class="w-7 h-7 rounded-full bg-primary-fixed flex items-center justify-center text-on-primary-fixed font-label-md text-[11px] shrink-0 font-medium">
                  ${initials}
                </div>
                <div class="flex flex-col min-w-0">
                  <span class="font-label-md text-label-md text-text-primary truncate">${name}</span>
                </div>
              </div>
            </td>
            <td class="py-3.5 px-4 whitespace-nowrap font-medium text-text-primary">${company}</td>
            <td class="py-3.5 px-4 text-text-secondary">
              <div class="line-clamp-1 max-w-[260px]" title="${need}">
                ${need}
              </div>
            </td>
            <td class="py-3.5 px-4 text-text-secondary">
              <div class="line-clamp-1 max-w-[240px]" title="${reason}">
                ${reason}
              </div>
            </td>
            <td class="py-3.5 px-4 whitespace-nowrap text-right">
              <a href="mailto:${encodeURIComponent(email)}" class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-primary-container hover:bg-primary text-on-primary font-label-md text-label-md transition-all shadow-sm shrink-0">
                <span class="material-symbols-outlined text-[16px]">send</span>
                <span>Send Mail</span>
              </a>
            </td>
          `;
          emailTableBody.appendChild(row);
        });
      } else {
        emailTableBody.innerHTML = `
          <tr>
            <td colspan="6" class="py-12 text-center text-text-muted">
              <div class="flex flex-col items-center justify-center gap-2">
                <span class="material-symbols-outlined text-[36px] text-text-muted">mail_lock</span>
                <span class="font-headline-sm text-headline-sm text-text-primary">No leads with email addresses yet.</span>
                <span class="font-body-sm text-body-sm text-text-secondary">Generate leads from a LinkedIn post to discover public email contacts.</span>
              </div>
            </td>
          </tr>
        `;
      }
    }

    // Render History table (all historical qualified leads)
    function renderHistoryTable(leads) {
      if (!historyTableBody) return;

      const countBadge = document.getElementById('history-leads-count-badge');
      if (countBadge) {
        countBadge.textContent = `${(leads || []).length} Total Leads`;
      }

      historyTableBody.innerHTML = '';
      if (leads && leads.length > 0) {
        let lastDateLabel = null;

        leads.forEach(lead => {
          const dateLabel = lead.run_date_label || 'History Vault';

          if (dateLabel !== lastDateLabel) {
            lastDateLabel = dateLabel;
            const headerRow = document.createElement('tr');
            headerRow.className = 'bg-surface-subtle/80 border-y border-border-default';
            headerRow.innerHTML = `
              <td colspan="7" class="py-2.5 px-4 font-headline-sm text-headline-sm text-text-primary">
                <div class="flex items-center gap-2">
                  <span class="material-symbols-outlined text-[18px] text-primary-container">calendar_today</span>
                  <span>${dateLabel}</span>
                </div>
              </td>
            `;
            historyTableBody.appendChild(headerRow);
          }

          const row = document.createElement('tr');
          row.className = 'hover:bg-surface-canvas/60 transition-colors group';

          const initials = lead.name ? lead.name.substring(0, 2).toUpperCase() : '??';
          const name = lead.name || 'Unknown';
          const company = lead.company || '-';
          const role = lead.role || '-';
          const need = lead.business_need || '-';
          const intent = lead.intent || '-';
          const score = lead.lead_score || 0;

          const profileUrl = lead.profile_url || '';
          const profileHtml = profileUrl ? 
            `<a href="${profileUrl}" target="_blank" rel="noopener noreferrer" class="inline-flex items-center gap-1 text-primary-container hover:underline font-label-sm text-label-sm">
               <span>View Profile</span>
               <span class="material-symbols-outlined text-[14px]">open_in_new</span>
             </a>` : '<span class="text-text-muted text-label-sm">-</span>';

          row.innerHTML = `
            <td class="py-3.5 px-4 whitespace-nowrap">
              <span class="inline-flex items-center px-2 py-0.5 rounded-md font-label-md text-label-sm bg-status-score-high-bg text-status-score-high-text font-mono font-semibold">
                ${score}/100
              </span>
            </td>
            <td class="py-3.5 px-4 whitespace-nowrap">
              <div class="flex items-center gap-2.5">
                <div class="w-7 h-7 rounded-full bg-primary-fixed flex items-center justify-center text-on-primary-fixed font-label-md text-[11px] shrink-0 font-medium">
                  ${initials}
                </div>
                <div class="flex flex-col min-w-0">
                  <span class="font-label-md text-label-md text-text-primary truncate">${name}</span>
                </div>
              </div>
            </td>
            <td class="py-3.5 px-4 whitespace-nowrap font-medium text-text-primary">${company}</td>
            <td class="py-3.5 px-4 whitespace-nowrap text-text-secondary">${role}</td>
            <td class="py-3.5 px-4 text-text-secondary">
              <div class="line-clamp-1 max-w-[360px]" title="${need}">
                ${need}
              </div>
            </td>
            <td class="py-3.5 px-4 whitespace-nowrap">
              <span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-status-success-bg text-status-success-text font-label-sm text-label-sm">
                ${intent}
              </span>
            </td>
            <td class="py-3.5 px-4 whitespace-nowrap text-right">
              ${profileHtml}
            </td>
          `;
          historyTableBody.appendChild(row);
        });
      } else {
        historyTableBody.innerHTML = `
          <tr>
            <td colspan="7" class="py-12 text-center text-text-muted">
              <div class="flex flex-col items-center justify-center gap-2">
                <span class="material-symbols-outlined text-[36px] text-text-muted">history_toggle_off</span>
                <span class="font-headline-sm text-headline-sm text-text-primary">No historical leads recorded yet.</span>
                <span class="font-body-sm text-body-sm text-text-secondary">Run lead generation on a LinkedIn post to save data to output/*.xlsx.</span>
              </div>
            </td>
          </tr>
        `;
      }
    }

    if (downloadBtn) {
      downloadBtn.addEventListener('click', () => {
        if (!currentDownloadUrl) {
          alert('Please generate leads first before downloading Excel.');
          return;
        }
        window.location.href = currentDownloadUrl;
      });
    }

    if (generateBtn) {
      generateBtn.addEventListener('click', async () => {
        const commentsText = commentsInput ? commentsInput.value.trim() : '';
        if (!commentsText) {
          alert('Please paste LinkedIn comments before generating leads.');
          return;
        }

        const originalHTML = generateBtn.innerHTML;
        generateBtn.disabled = true;
        generateBtn.classList.add('opacity-80', 'cursor-not-allowed');
        generateBtn.innerHTML = `
          <svg class="animate-spin h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          <span>Generating leads...</span>
        `;
        
        try {
          const response = await fetch('/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ comments_text: commentsText })
          });
          
          const result = await response.json();
          
          if (!response.ok || !result.success) {
            throw new Error(result.error || 'Failed to generate leads.');
          }

          // Update metrics
          metricSpans[0].textContent = result.comments_analyzed;
          metricSpans[1].textContent = result.qualified_leads_count;
          metricSpans[2].innerHTML = `${result.avg_lead_intent}<span class="font-body-sm text-body-sm text-text-muted font-normal">/100</span>`;
          metricSpans[3].textContent = `${result.processing_time}s`;
          
          currentDownloadUrl = result.download_url;

          // Render dashboard table for current run
          renderDashboardTable(result.leads || []);

          // Refresh historical email and all leads from output/*.xlsx
          fetchHistoricalEmailLeads();
          fetchHistoricalAllLeads();

          generateBtn.innerHTML = `
            <span class="material-symbols-outlined text-[18px]">check</span>
            <span>Completed (${result.qualified_leads_count} Leads)</span>
          `;
          
          setTimeout(() => {
            generateBtn.innerHTML = originalHTML;
          }, 2500);

        } catch (error) {
          alert(error.message);
          generateBtn.innerHTML = originalHTML;
        } finally {
          generateBtn.classList.remove('opacity-80', 'cursor-not-allowed');
          generateBtn.disabled = false;
        }
      });
    }

    // Fetch GTM Opportunities from /api/gtm-opportunities
    async function fetchGtmOpportunities() {
      try {
        const res = await fetch('/api/gtm-opportunities');
        const data = await res.json();
        if (res.ok && data.success) {
          renderGtmFeed(data.opportunities || []);
        }
      } catch (err) {
        console.error('Failed to fetch GTM opportunities:', err);
      }
    }

    // Render GTM Error State UI
    function renderGtmErrorState(status, errorMessage) {
      if (!gtmFeedContainer) return;

      let title = "Unable to find opportunities";
      let description = errorMessage || "Something went wrong while generating opportunities. Please try again.";

      if (status === 429) {
        title = "Unable to find opportunities";
        description = "Gemini API quota has been exceeded. Please try again after the quota resets.";
      } else if (status === 401 || status === 403) {
        title = "Unable to connect to the AI service.";
        description = "Please check the Gemini API configuration.";
      } else if (status === 404) {
        title = "The configured AI model is currently unavailable.";
        description = "Please check the Gemini model configuration.";
      } else if (status >= 500 && status < 600) {
        title = "Something went wrong while generating opportunities.";
        description = "Please try again.";
      } else if (status === 0 || !status) {
        title = "Unable to reach the backend.";
        description = "Please make sure the application server is running and try again.";
      }

      if (gtmCountBadge) {
        gtmCountBadge.textContent = "Error";
      }

      gtmFeedContainer.innerHTML = `
        <div class="bg-surface-card rounded-xl p-8 sm:p-12 text-center flex flex-col items-center justify-center gap-4 border border-error/30 bg-error-container/10 shadow-sm animate-in fade-in duration-200">
          <div class="w-12 h-12 rounded-2xl bg-error-container/40 text-error flex items-center justify-center shrink-0">
            <span class="material-symbols-outlined text-[28px]">error</span>
          </div>
          <div class="flex flex-col gap-1 max-w-md">
            <h3 class="font-headline-sm text-lg text-text-primary font-semibold">${title}</h3>
            <p class="font-body-md text-body-md text-text-secondary">${description}</p>
          </div>
          <button id="gtm-error-retry-btn" type="button" class="h-10 px-6 rounded-xl bg-primary-container hover:bg-primary text-on-primary font-label-md text-label-md font-semibold transition-all flex items-center justify-center gap-2 shadow-sm active:scale-[0.98]">
            <span class="material-symbols-outlined text-[18px]">refresh</span>
            <span>Retry</span>
          </button>
        </div>
      `;

      const retryBtn = document.getElementById('gtm-error-retry-btn');
      if (retryBtn && gtmFindBtn) {
        retryBtn.addEventListener('click', () => {
          gtmFindBtn.click();
        });
      }
    }

    // Render GTM Opportunities Feed Cards
    function renderGtmFeed(opps) {
      if (!gtmFeedContainer) return;
      if (gtmCountBadge) {
        gtmCountBadge.textContent = `${(opps || []).length} opportunities found`;
      }

      gtmFeedContainer.innerHTML = '';
      if (opps && opps.length > 0) {
        opps.forEach(opp => {
          const card = document.createElement('div');
          card.className = 'bg-surface-card rounded-xl p-space-md shadow-sm border border-border-default/60 hover:border-primary-container/40 transition-all flex flex-col gap-3 group';

          const companyName = opp.company_name || 'Target Company';
          const initial = companyName.substring(0, 1).toUpperCase();
          const website = opp.website || opp.company_url || '#';
          const category = opp.category_tag || opp.industry || 'Qualified Target';
          const score = opp.overall_score || 0;

          const subtextParts = [opp.industry, opp.company_size || opp.employee_count, opp.location].filter(Boolean);
          const subtext = subtextParts.length > 0 ? subtextParts.join(' â€¢ ') : 'Public Company Record';

          const whyNow = opp.why_now || 'Identified timing and fit alignment.';
          const recAction = opp.recommended_action || 'Review public evidence and initiate outreach.';

          const evidenceItems = (Array.isArray(opp.evidence) && opp.evidence.length > 0) ? opp.evidence : (Array.isArray(opp.signals) ? opp.signals : []);
          let signalsHtml = '';
          if (evidenceItems.length > 0) {
            signalsHtml = evidenceItems.slice(0, 2).map(ev => {
              if (typeof ev === 'string') {
                return `
                  <div class="p-2 px-3 rounded-lg bg-surface-canvas border border-border-default/40 flex items-start gap-2 text-body-sm text-text-secondary">
                    <span class="material-symbols-outlined text-[16px] text-primary-container shrink-0 mt-0.5">verified</span>
                    <span class="font-medium text-text-primary text-[12px]">${ev}</span>
                  </div>
                `;
              }
              const sigTitle = ev.signal || ev.title || ev.signal_type || 'Web Evidence';
              const sigSummary = ev.description || ev.snippet || ev.summary || '';
              const sourceTitle = ev.source_title || 'Source';
              const sourceUrl = ev.source_url || '';
              const linkHtml = (sourceUrl && sourceUrl !== '#') ? `<a href="${sourceUrl}" target="_blank" rel="noopener noreferrer" class="text-primary-container hover:underline text-[11px] inline-flex items-center gap-0.5 shrink-0 ml-1"><span>${sourceTitle}</span><span class="material-symbols-outlined text-[12px]">open_in_new</span></a>` : '';
              return `
                <div class="p-2 px-3 rounded-lg bg-surface-canvas border border-border-default/40 flex items-start gap-2 text-body-sm text-text-secondary">
                  <span class="material-symbols-outlined text-[16px] text-primary-container shrink-0 mt-0.5">verified</span>
                  <div class="flex flex-col min-w-0">
                    <span class="font-medium text-text-primary text-[12px]">${sigTitle}${linkHtml}</span>
                    ${sigSummary ? `<span class="text-[12px] text-text-secondary line-clamp-1">${sigSummary}</span>` : ''}
                  </div>
                </div>
              `;
            }).join('');
          }

          card.innerHTML = `
            <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border-default/50 pb-3">
              <div class="flex items-center gap-3">
                <div class="w-10 h-10 rounded-xl bg-primary-container text-on-primary font-bold flex items-center justify-center text-headline-sm shrink-0">
                  ${initial}
                </div>
                <div class="flex flex-col min-w-0">
                  <div class="flex items-center gap-2">
                    <h3 class="font-headline-sm text-headline-sm text-text-primary truncate">${companyName}</h3>
                    ${website !== '#' ? `<a href="${website}" target="_blank" rel="noopener noreferrer" class="text-primary-container hover:underline font-label-sm text-label-sm flex items-center gap-0.5"><span class="material-symbols-outlined text-[14px]">open_in_new</span></a>` : ''}
                  </div>
                  <span class="font-label-sm text-label-sm text-text-secondary">${subtext}</span>
                </div>
              </div>

              <div class="flex items-center gap-2 shrink-0">
                <span class="px-2.5 py-0.5 rounded-full bg-surface-canvas text-text-secondary font-label-sm text-label-sm font-medium border border-border-default/60">${category}</span>
                <div class="px-3 py-1 rounded-xl bg-status-score-high-bg text-primary-container font-mono font-bold text-label-md border border-primary-container/20 flex items-center gap-1">
                  <span class="text-[11px] text-text-muted font-normal">Score:</span>
                  <span>${score}</span>
                </div>
              </div>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div class="p-3 rounded-xl bg-status-success-bg/30 border border-status-success-border/50 flex flex-col gap-1">
                <span class="font-label-sm text-[11px] text-status-success-text font-bold uppercase tracking-wider flex items-center gap-1">
                  <span class="material-symbols-outlined text-[14px]">schedule</span>
                  Why Now?
                </span>
                <p class="font-body-sm text-body-sm text-text-primary line-clamp-2">${whyNow}</p>
              </div>

              <div class="p-3 rounded-xl bg-surface-canvas border border-border-default/50 flex flex-col gap-1">
                <span class="font-label-sm text-[11px] text-text-muted font-bold uppercase tracking-wider flex items-center gap-1">
                  <span class="material-symbols-outlined text-[14px] text-primary-container">lightbulb</span>
                  Recommended Action
                </span>
                <p class="font-body-sm text-body-sm text-text-primary line-clamp-2">${recAction}</p>
              </div>
            </div>

            ${signalsHtml ? `<div class="flex flex-col gap-1.5 pt-1">${signalsHtml}</div>` : ''}

            <div class="flex justify-end pt-1">
              <button type="button" class="view-gtm-detail-btn px-4 py-1.5 rounded-xl bg-surface-canvas hover:bg-surface-subtle text-text-primary font-label-md text-label-md font-semibold transition-all border border-border-default/60 flex items-center gap-1.5 shadow-sm active:scale-[0.98]">
                <span>View Deep Analysis</span>
                <span class="material-symbols-outlined text-[16px]">chevron_right</span>
              </button>
            </div>
          `;

          const detailBtn = card.querySelector('.view-gtm-detail-btn');
          if (detailBtn) {
            detailBtn.addEventListener('click', () => openGtmDetailModal(opp));
          }

          gtmFeedContainer.appendChild(card);
        });
      } else {
        gtmFeedContainer.innerHTML = `
          <div class="bg-surface-card rounded-xl p-12 text-center text-text-muted flex flex-col items-center justify-center gap-3 border border-border-default/60">
            <span class="material-symbols-outlined text-[42px] text-text-muted">search_off</span>
            <span class="font-headline-sm text-headline-sm text-text-primary">No opportunities found</span>
            <span class="font-body-sm text-body-sm text-text-secondary max-w-[480px]">We couldn't identify suitable opportunities from the available public evidence. Try refining the ICP or offer.</span>
          </div>
        `;
      }
    }

    // Open GTM Detail Modal Drawer
    function openGtmDetailModal(opp) {
      if (!gtmDetailModal) return;

      const avatar = document.getElementById('gtm-modal-avatar');
      const companyName = document.getElementById('gtm-modal-company-name');
      const websiteLink = document.getElementById('gtm-modal-website-link');
      const subtext = document.getElementById('gtm-modal-subtext');

      const overallScore = document.getElementById('gtm-modal-overall-score');
      const icpScore = document.getElementById('gtm-modal-icp-score');
      const intentScore = document.getElementById('gtm-modal-intent-score');
      const timingScore = document.getElementById('gtm-modal-timing-score');
      const confidence = document.getElementById('gtm-modal-confidence');

      const whyNow = document.getElementById('gtm-modal-why-now');
      const action = document.getElementById('gtm-modal-action');
      const evidenceList = document.getElementById('gtm-modal-evidence-list');

      const name = opp.company_name || 'Company';
      if (avatar) avatar.textContent = name.substring(0, 1).toUpperCase();
      if (companyName) companyName.textContent = name;
      
      const siteUrl = opp.website || opp.company_url;
      if (websiteLink) {
        websiteLink.href = siteUrl || '#';
        websiteLink.style.display = (siteUrl && siteUrl !== '#') ? 'inline-flex' : 'none';
      }

      const subParts = [opp.industry, opp.company_size || opp.employee_count, opp.location].filter(Boolean);
      if (subtext) subtext.textContent = subParts.length > 0 ? subParts.join(' â€¢ ') : 'Public Web Record';

      if (overallScore) overallScore.textContent = opp.overall_score || 0;
      if (icpScore) icpScore.textContent = `${opp.icp_fit_score || 0}/100`;
      if (intentScore) intentScore.textContent = `${opp.intent_score || 0}/100`;
      if (timingScore) timingScore.textContent = `${opp.timing_score || 0}/100`;
      if (confidence) confidence.textContent = opp.confidence || opp.confidence_level || 'medium';

      if (whyNow) whyNow.textContent = opp.why_now || 'No timing trigger specified.';
      if (action) action.textContent = opp.recommended_action || 'Review evidence and initiate outreach.';

      if (evidenceList) {
        evidenceList.innerHTML = '';
        const evList = (Array.isArray(opp.evidence) && opp.evidence.length > 0) ? opp.evidence : (Array.isArray(opp.signals) ? opp.signals : []);
        if (evList.length > 0) {
          evList.forEach(ev => {
            const item = document.createElement('div');
            item.className = 'p-3 rounded-xl bg-surface-canvas border border-border-default/60 flex flex-col gap-1';

            let title = 'Evidence Signal';
            let summary = '';
            let sourceTitle = 'Web Evidence';
            let sourceUrl = '';

            if (typeof ev === 'string') {
              title = ev;
            } else if (typeof ev === 'object' && ev !== null) {
              title = ev.signal || ev.title || ev.signal_type || 'Evidence Signal';
              summary = ev.description || ev.snippet || ev.summary || '';
              sourceTitle = ev.source_title || 'Web Evidence';
              sourceUrl = ev.source_url || '';
            }

            const linkHtml = (sourceUrl && sourceUrl !== '#') ? `<a href="${sourceUrl}" target="_blank" rel="noopener noreferrer" class="text-primary-container hover:underline text-[12px] inline-flex items-center gap-1"><span>${sourceTitle}</span><span class="material-symbols-outlined text-[13px]">open_in_new</span></a>` : '';

            item.innerHTML = `
              <div class="flex items-center justify-between">
                <span class="font-label-md text-label-md text-text-primary font-semibold flex items-center gap-1.5">
                  <span class="material-symbols-outlined text-[16px] text-primary-container">verified</span>
                  ${title}
                </span>
                ${linkHtml}
              </div>
              ${summary ? `<p class="font-body-sm text-body-sm text-text-secondary">${summary}</p>` : ''}
            `;
            evidenceList.appendChild(item);
          });
        } else {
          evidenceList.innerHTML = `<p class="font-body-sm text-body-sm text-text-muted italic">No external web signals registered.</p>`;
        }
      }

      gtmDetailModal.classList.remove('hidden');
    }

    if (gtmModalCloseBtn) {
      gtmModalCloseBtn.addEventListener('click', () => {
        if (gtmDetailModal) gtmDetailModal.classList.add('hidden');
      });
    }

    if (gtmDetailModal) {
      gtmDetailModal.addEventListener('click', (e) => {
        if (e.target === gtmDetailModal) {
          gtmDetailModal.classList.add('hidden');
        }
      });
    }

    // Find Opportunities Handler â€” exposed globally so onclick attribute also works
    window.handleGtmFind = async function(e) {
        if (e && e.preventDefault) e.preventDefault();
        console.log('[GTM DEBUG] handleGtmFind called');

        const gtmFindBtnLocal = document.getElementById('gtm-find-btn');
        if (gtmFindBtnLocal && gtmFindBtnLocal.disabled) {
          console.log('[GTM DEBUG] Button is disabled, ignoring duplicate call');
          return;
        }

        const offerEl = document.getElementById('gtm-offer-input');
        const icpEl = document.getElementById('gtm-icp-input');
        const contextEl = document.getElementById('gtm-context-input');

        let offer = offerEl ? offerEl.value.trim() : '';
        let target_icp = icpEl ? icpEl.value.trim() : '';
        let additional_context = contextEl ? contextEl.value.trim() : '';

        // Fallback to saved GTM onboarding context if textareas are empty
        if ((!offer || !target_icp) && savedGtmContext) {
          console.log('[GTM DEBUG] Textareas empty in DOM, using saved user onboarding context as fallback');
          if (!offer && savedGtmContext.offer) {
            offer = savedGtmContext.offer;
            if (offerEl) offerEl.value = offer;
          }
          if (!target_icp && savedGtmContext.target_icp) {
            target_icp = savedGtmContext.target_icp;
            if (icpEl) icpEl.value = target_icp;
          }
          if (!additional_context && savedGtmContext.additional_context) {
            additional_context = savedGtmContext.additional_context;
            if (contextEl) contextEl.value = additional_context;
          }
        }

        console.log('[GTM DEBUG] Validation check:', { offer_present: !!offer, icp_present: !!target_icp });

        if (!offer || !target_icp) {
          alert('Please specify what you sell and your target audience.');
          return;
        }

        const originalHTML = gtmFindBtnLocal ? gtmFindBtnLocal.innerHTML : '';
        if (gtmFindBtnLocal) {
          gtmFindBtnLocal.disabled = true;
          gtmFindBtnLocal.classList.add('opacity-80', 'cursor-not-allowed');
          gtmFindBtnLocal.innerHTML = `
          <span class="material-symbols-outlined text-[18px] animate-spin">sync</span>
          <span>Discovering Opportunities...</span>
        `;
        }

        const step1 = document.getElementById('gtm-step1');
        const step2 = document.getElementById('gtm-step2');
        const step3 = document.getElementById('gtm-step3');

        if (gtmProgressContainer) gtmProgressContainer.classList.remove('hidden');

        setGtmStepState(step1, 'active', '1. Building Search Strategy...');
        setGtmStepState(step2, 'pending', '2. Collecting Web Data...');
        setGtmStepState(step3, 'pending', '3. Analyzing Opportunities...');

        const t1 = setTimeout(() => {
          setGtmStepState(step1, 'completed', '1. Building Search Strategy...');
          setGtmStepState(step2, 'active', '2. Collecting Web Data...');
        }, 3000);

        const t2 = setTimeout(() => {
          setGtmStepState(step2, 'completed', '2. Collecting Web Data...');
          setGtmStepState(step3, 'active', '3. Analyzing Opportunities...');
        }, 8000);

        try {
          const payload = {
            offer: offer,
            target_icp: target_icp,
            icp: target_icp,
            additional_context: additional_context,
            context: additional_context
          };

          console.log('[GTM DEBUG] Dispatching request POST /api/gtm-opportunities/find payload:', payload);

          const res = await fetch('/api/gtm-opportunities/find', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });
          
          let data = null;
          try {
            data = await res.json();
          } catch (jsonErr) {
            data = null;
          }

          console.log('[GTM DEBUG] Response received status:', res.status, data);

          clearTimeout(t1);
          clearTimeout(t2);

          if (!res.ok || !data || !data.success) {
            const status = res.status;
            const errMsg = data ? data.error : null;
            renderGtmErrorState(status, errMsg);
            if (gtmProgressContainer) gtmProgressContainer.classList.add('hidden');
            return;
          }

          setGtmStepState(step1, 'completed', '1. Building Search Strategy...');
          setGtmStepState(step2, 'completed', '2. Collecting Web Data...');
          setGtmStepState(step3, 'completed', '3. Analyzing Opportunities...');

          renderGtmFeed(data.opportunities || []);

          setTimeout(() => {
            if (gtmProgressContainer) gtmProgressContainer.classList.add('hidden');
          }, 1500);

        } catch (err) {
          clearTimeout(t1);
          clearTimeout(t2);
          renderGtmErrorState(0, err.message);
          if (gtmProgressContainer) gtmProgressContainer.classList.add('hidden');
        } finally {
          const btnFinal = document.getElementById('gtm-find-btn');
          if (btnFinal) {
            btnFinal.disabled = false;
            btnFinal.classList.remove('opacity-80', 'cursor-not-allowed');
            btnFinal.innerHTML = originalHTML;
          }
        }
    };

    // Also wire up via addEventListener for completeness
    if (gtmFindBtn) {
      gtmFindBtn.addEventListener('click', window.handleGtmFind);
    }

    function setGtmStepState(stepEl, state, labelText) {
      if (!stepEl) return;
      if (state === 'active') {
        stepEl.className = 'p-2 px-3 rounded-lg border flex items-center gap-2 bg-status-score-high-bg border-primary-container/30';
        stepEl.innerHTML = `<span class="material-symbols-outlined text-[16px] text-primary-container animate-spin">sync</span><span class="text-primary-container font-medium truncate">${labelText}</span>`;
      } else if (state === 'completed') {
        stepEl.className = 'p-2 px-3 rounded-lg border flex items-center gap-2 bg-status-success-bg/40 border-status-success-border/60';
        stepEl.innerHTML = `<span class="material-symbols-outlined text-[16px] text-status-success-text">check_circle</span><span class="text-text-primary font-medium truncate">${labelText}</span>`;
      } else {
        stepEl.className = 'p-2 px-3 rounded-lg border flex items-center gap-2 bg-surface-canvas border-border-default/50';
        stepEl.innerHTML = `<span class="material-symbols-outlined text-[16px] text-text-muted">radio_button_unchecked</span><span class="text-text-muted truncate">${labelText}</span>`;
      }
    }

    // Initial load fetch
    fetchHistoricalEmailLeads();
    fetchHistoricalAllLeads();
    fetchGtmOpportunities();
  })();
