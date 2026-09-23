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


      const poOnboardingNextBtn = document.getElementById('po-onboarding-next-btn');
      if (poOnboardingNextBtn) {
        poOnboardingNextBtn.addEventListener('click', () => {
          profileOptimizationMode = 'normal';
          document.getElementById('po-onboarding-next-btn-container').classList.add('hidden');
          const modal3 = document.getElementById('modal-onboarding-gtm-explore');
          if (modal3) {
            modal3.classList.remove('hidden');
            console.log('[FLOW] User clicked Next/Done -> Displaying GTM Exploration choice modal');
          }
        });
      }
    // Onboarding Modal 2 Handlers: Profile Optimization Choice
    const onboardingOptYesBtn = document.getElementById('onboarding-opt-yes-btn');
    const onboardingOptSkipBtn = document.getElementById('onboarding-opt-skip-btn');

    if (onboardingOptYesBtn) {
      onboardingOptYesBtn.addEventListener('click', () => {
          profileOptimizationMode = 'onboarding';
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

