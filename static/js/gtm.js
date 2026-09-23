    // GTM Opportunities DOM Elements
    const gtmFindBtn = document.getElementById('gtm-find-btn');
    const gtmProgressContainer = document.getElementById('gtm-progress-container');
    const gtmProgressStatus = document.getElementById('gtm-progress-status');
    const gtmFeedContainer = document.getElementById('gtm-feed-container');
    const gtmCountBadge = document.getElementById('gtm-count-badge');
    const gtmDetailModal = document.getElementById('gtm-detail-modal');
    const gtmModalCloseBtn = document.getElementById('gtm-modal-close-btn');

    // ===== GTM OPPORTUNITIES MODULE =====

    // Load editable context summary from /api/gtm-context

    const gtmSaveBtn = document.getElementById('gtm-save-btn');
    const poGtmSaveBtn = document.getElementById('po-gtm-save-btn');

    async function handleGtmContextSave(source) {
      let offer, icp, context, saveBtn, saveStatus;
      if (source === 'po') {
        offer = document.getElementById('po-gtm-ctx-offer').value;
        icp = document.getElementById('po-gtm-ctx-icp').value;
        context = document.getElementById('po-gtm-ctx-context').value;
        saveBtn = poGtmSaveBtn;
        saveStatus = document.getElementById('po-gtm-save-status');
      } else {
        offer = document.getElementById('gtm-ctx-offer').value;
        icp = document.getElementById('gtm-ctx-icp').value;
        context = document.getElementById('gtm-ctx-context').value;
        saveBtn = gtmSaveBtn;
        saveStatus = document.getElementById('gtm-save-status');
      }

      if (!saveBtn) return;
      const originalHTML = saveBtn.innerHTML;
      saveBtn.disabled = true;
      saveBtn.innerHTML = '<span class="material-symbols-outlined text-[18px] animate-spin">sync</span><span>Saving...</span>';

      try {
        const res = await fetch('/api/onboarding/save-gtm-context', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ offer: offer, target_icp: icp, additional_context: context })
        });
        const data = await res.json();
        if (res.ok && data.success) {
           savedGtmContext = data.data; // Keep in sync globally
           
           // Sync BOTH UIs proactively (Test A & B)
           const gOfferEl = document.getElementById('gtm-ctx-offer');
           const gIcpEl = document.getElementById('gtm-ctx-icp');
           const gContextEl = document.getElementById('gtm-ctx-context');
           const pOfferEl = document.getElementById('po-gtm-ctx-offer');
           const pIcpEl = document.getElementById('po-gtm-ctx-icp');
           const pContextEl = document.getElementById('po-gtm-ctx-context');
           
           if (gOfferEl) gOfferEl.value = offer;
           if (gIcpEl) gIcpEl.value = icp;
           if (gContextEl) gContextEl.value = context;
           if (pOfferEl) pOfferEl.value = offer;
           if (pIcpEl) pIcpEl.value = icp;
           if (pContextEl) pContextEl.value = context;

           if (saveStatus) {
             saveStatus.classList.remove('opacity-0');
             setTimeout(() => {
               saveStatus.classList.add('opacity-0');
             }, 3000);
           }
        } else {
          alert(data.error || 'Failed to save context.');
        }
      } catch (err) {
        alert('An error occurred while saving context.');
      } finally {
        saveBtn.disabled = false;
        saveBtn.innerHTML = originalHTML;
      }
    }

    if (gtmSaveBtn) {
      gtmSaveBtn.addEventListener('click', async (e) => {
        if (e && e.preventDefault) e.preventDefault();
        await handleGtmContextSave('gtm');
      });
    }
    
    if (poGtmSaveBtn) {
      poGtmSaveBtn.addEventListener('click', async (e) => {
        if (e && e.preventDefault) e.preventDefault();
        await handleGtmContextSave('po');
      });
    }
    async function loadGtmContextSummary() {
      const offerEl = document.getElementById('gtm-ctx-offer');
      const icpEl = document.getElementById('gtm-ctx-icp');
      const contextEl = document.getElementById('gtm-ctx-context');
      const statusEl = document.getElementById('gtm-context-status');

      try {
        const res = await fetch('/api/gtm-context');
        const data = await res.json();
        if (res.ok && data.success && data.data) {
          if (offerEl) offerEl.value = data.data.offer || '';
            if (poOfferEl) poOfferEl.value = data.data.offer || '';
            if (poIcpEl) poIcpEl.value = data.data.target_icp || '';
            if (poContextEl) poContextEl.value = data.data.additional_context || '';
            if (poStatusEl) poStatusEl.textContent = 'Loaded from onboarding';
          if (icpEl) icpEl.value = data.data.target_icp || '';
          if (contextEl) contextEl.value = data.data.additional_context || '';
          if (statusEl) statusEl.textContent = 'Loaded from onboarding';
        } else {
          const msg = data.error || 'Context unavailable.';
          if (offerEl) offerEl.value = '';
          if (icpEl) icpEl.value = '';
          if (contextEl) contextEl.value = '';
          if (statusEl) statusEl.textContent = msg;
        }
      } catch (err) {
        if (statusEl) statusEl.textContent = 'Could not load context.';
      }
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
          const category = opp.industry || opp.category_tag || 'Qualified Target';
          const score = opp.overall_score || 0;

          const subtextParts = [opp.industry, opp.company_size || opp.employee_count, opp.location].filter(Boolean);
          const subtext = subtextParts.length > 0 ? subtextParts.join(' • ') : 'Public Company Record';

          const whyNow = opp.why_now || 'Identified timing and fit alignment.';
          const recAction = opp.recommended_action || 'Review public evidence and initiate outreach.';

          const rawEvidence = Array.isArray(opp.evidence) && opp.evidence.length > 0 ? opp.evidence : (Array.isArray(opp.signals) ? opp.signals : []);
          let signalsHtml = '';
          if (rawEvidence.length > 0) {
            signalsHtml = rawEvidence.slice(0, 2).map(ev => {
              const sigTitle = ev.signal || ev.title || ev.signal_type || 'Signal';
              const sigSummary = ev.description || ev.snippet || ev.summary || '';
              const sourceTitle = ev.source_title || 'Source';
              const sourceUrl = ev.source_url || '';
              const linkHtml = sourceUrl ? `<a href="${sourceUrl}" target="_blank" rel="noopener noreferrer" class="text-primary-container hover:underline text-[11px] inline-flex items-center gap-0.5 shrink-0 ml-1"><span>${sourceTitle}</span><span class="material-symbols-outlined text-[12px]">open_in_new</span></a>` : '';
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
                    ${website && website !== '#' ? `<a href="${website}" target="_blank" rel="noopener noreferrer" class="text-primary-container hover:underline font-label-sm text-label-sm flex items-center gap-0.5"><span class="material-symbols-outlined text-[14px]">open_in_new</span></a>` : ''}
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
            <span class="material-symbols-outlined text-[42px] text-text-muted">explore</span>
            <span class="font-headline-sm text-headline-sm text-text-primary">No GTM opportunities discovered yet.</span>
            <span class="font-body-sm text-body-sm text-text-secondary max-w-[480px]">Click Find Opportunities above to run the AI discovery pipeline using your saved ICP and offer.</span>
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
      const reasonEl = document.getElementById('gtm-modal-reason');
      const evidenceList = document.getElementById('gtm-modal-evidence-list');

      const name = opp.company_name || 'Company';
      if (avatar) avatar.textContent = name.substring(0, 1).toUpperCase();
      if (companyName) companyName.textContent = name;

      const siteUrl = opp.website || opp.company_url || '';
      if (websiteLink) {
        websiteLink.href = siteUrl || '#';
        if (siteUrl && siteUrl !== '#') {
          websiteLink.classList.remove('hidden');
        } else {
          websiteLink.classList.add('hidden');
        }
      }

      const subParts = [opp.industry, opp.company_size || opp.employee_count, opp.location].filter(Boolean);
      if (subtext) subtext.textContent = subParts.length > 0 ? subParts.join(' • ') : 'Public Web Record';

      if (overallScore) overallScore.textContent = opp.overall_score || 0;
      if (icpScore) icpScore.textContent = `${opp.icp_fit_score || 0}/100`;
      if (intentScore) intentScore.textContent = `${opp.intent_score || 0}/100`;
      if (timingScore) timingScore.textContent = `${opp.timing_score || 0}/100`;
      if (confidence) confidence.textContent = opp.confidence || opp.confidence_level || 'medium';

      if (whyNow) whyNow.textContent = opp.why_now || 'No timing trigger specified.';
      if (action) action.textContent = opp.recommended_action || 'Review evidence and initiate outreach.';
      if (reasonEl) reasonEl.textContent = opp.reason || 'Evaluated based on public evidence.';

      if (evidenceList) {
        evidenceList.innerHTML = '';
        const evList = Array.isArray(opp.evidence) && opp.evidence.length > 0 ? opp.evidence : (Array.isArray(opp.signals) ? opp.signals : []);
        if (evList.length > 0) {
          evList.forEach(ev => {
            const item = document.createElement('div');
            item.className = 'p-3 rounded-xl bg-surface-canvas border border-border-default/60 flex flex-col gap-1';

            const title = ev.signal || ev.title || ev.signal_type || 'Evidence Signal';
            const desc = ev.description || ev.snippet || ev.summary || '';
            const sourceTitle = ev.source_title || 'Web Evidence';
            const sourceUrl = ev.source_url || '';

            const linkHtml = sourceUrl ? `<a href="${sourceUrl}" target="_blank" rel="noopener noreferrer" class="text-primary-container hover:underline text-[12px] inline-flex items-center gap-1"><span>${sourceTitle}</span><span class="material-symbols-outlined text-[13px]">open_in_new</span></a>` : '';

            item.innerHTML = `
              <div class="flex items-center justify-between">
                <span class="font-label-md text-label-md text-text-primary font-semibold flex items-center gap-1.5">
                  <span class="material-symbols-outlined text-[16px] text-primary-container">verified</span>
                  ${title}
                </span>
                ${linkHtml}
              </div>
              ${desc ? `<p class="font-body-sm text-body-sm text-text-secondary">${desc}</p>` : ''}
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

    // Find Opportunities Pipeline Event Handler
    async function handleGtmFind() {
      console.log('[GTM DEBUG] Button clicked');

      const errContainer = document.getElementById('gtm-error-container');
      const errText = document.getElementById('gtm-error-msg');
      if (errContainer) errContainer.classList.add('hidden');

      if (!gtmFindBtn) {
        console.warn('[GTM DEBUG] Validation blocked request: gtmFindBtn element missing');
        return;
      }

      const originalHTML = gtmFindBtn.innerHTML;
      gtmFindBtn.disabled = true;
      gtmFindBtn.classList.add('opacity-80', 'cursor-not-allowed');
      gtmFindBtn.innerHTML = `
        <span class="material-symbols-outlined text-[18px] animate-spin">sync</span>
        <span>Finding Opportunities...</span>
      `;

      const step1 = document.getElementById('gtm-step1');
      const step2 = document.getElementById('gtm-step2');
      const step3 = document.getElementById('gtm-step3');

      if (gtmProgressContainer) gtmProgressContainer.classList.remove('hidden');

      setGtmStepState(step1, 'active', '1. Searching Public Web...');
      setGtmStepState(step2, 'pending', '2. Collecting Evidence...');
      setGtmStepState(step3, 'pending', '3. Scoring Opportunities...');

      const t1 = setTimeout(() => {
        setGtmStepState(step1, 'completed', '1. Searching Public Web...');
        setGtmStepState(step2, 'active', '2. Collecting Evidence...');
      }, 4000);

      const t2 = setTimeout(() => {
        setGtmStepState(step2, 'completed', '2. Collecting Evidence...');
        setGtmStepState(step3, 'active', '3. Scoring Opportunities...');
      }, 10000);

      try {
        console.log('[GTM DEBUG] Sending POST /api/gtm-opportunities/find');
        console.log('[GTM DEBUG] Request sent');
        console.log("[GTM FRONTEND DEBUG] Fetching:", '/api/gtm-opportunities/find');

        const res = await fetch('/api/gtm-opportunities/find', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({})
        });

        console.log("[GTM FRONTEND DEBUG] Response:", res.status, res.url);
        console.log('[GTM DEBUG] Response status:', res.status);

        let data;
        try {
          data = await res.json();
          console.log('[GTM DEBUG] Response body:', data);
        } catch (jsonErr) {
          console.error('[GTM DEBUG] Invalid JSON response:', jsonErr);
          throw new Error('Invalid server response format.');
        }

        clearTimeout(t1);
        clearTimeout(t2);

        if (!res.ok || !data.success) {
          throw new Error(data.error || `Server returned HTTP ${res.status}`);
        }

        setGtmStepState(step1, 'completed', '1. Searching Public Web...');
        setGtmStepState(step2, 'completed', '2. Collecting Evidence...');
        setGtmStepState(step3, 'completed', '3. Scoring Opportunities...');

        renderGtmFeed(data.opportunities || []);

        setTimeout(() => {
          if (gtmProgressContainer) gtmProgressContainer.classList.add('hidden');
        }, 1200);

      } catch (err) {
        clearTimeout(t1);
        clearTimeout(t2);
        console.error('[GTM DEBUG] FETCH ERROR:', err);
        if (gtmProgressContainer) gtmProgressContainer.classList.add('hidden');
        if (errContainer && errText) {
          errText.innerHTML = `Unable to find opportunities.<br><br><strong>Reason:</strong><br>${err.message || 'GTM opportunity discovery failed.'}`;
          errContainer.classList.remove('hidden');
        }
      } finally {
        gtmFindBtn.disabled = false;
        gtmFindBtn.classList.remove('opacity-80', 'cursor-not-allowed');
        gtmFindBtn.innerHTML = originalHTML;
      }
    }

    if (gtmFindBtn) {
      gtmFindBtn.addEventListener('click', (e) => {
        if (e && e.preventDefault) e.preventDefault();
        handleGtmFind();
      });
    }

    if (gtmSaveBtn) {
      gtmSaveBtn.addEventListener('click', async (e) => {
        if (e && e.preventDefault) e.preventDefault();
        const offer = document.getElementById('gtm-ctx-offer').value;
        const icp = document.getElementById('gtm-ctx-icp').value;
        const context = document.getElementById('gtm-ctx-context').value;
        
        const originalHTML = gtmSaveBtn.innerHTML;
        gtmSaveBtn.disabled = true;
        gtmSaveBtn.innerHTML = '<span class="material-symbols-outlined text-[18px] animate-spin">sync</span><span>Saving...</span>';
        
        try {
          const res = await fetch('/api/onboarding/save-gtm-context', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ offer: offer, target_icp: icp, additional_context: context })
          });
          const data = await res.json();
          if (res.ok && data.success) {
             const saveStatus = document.getElementById('gtm-save-status');
             if (saveStatus) {
               saveStatus.classList.remove('opacity-0');
               setTimeout(() => {
                 saveStatus.classList.add('opacity-0');
               }, 3000);
             }
          } else {
            alert(data.error || 'Failed to save context.');
          }
        } catch (err) {
          alert('Network error while saving context.');
        } finally {
          gtmSaveBtn.disabled = false;
          gtmSaveBtn.innerHTML = originalHTML;
        }
      });
    }

    const gtmRetryBtn = document.getElementById('gtm-retry-btn');
    if (gtmRetryBtn) {
      gtmRetryBtn.addEventListener('click', (e) => {
        if (e && e.preventDefault) e.preventDefault();
        handleGtmFind();
      });
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

    // ===== Write with AI Logic =====
    const aiWriteBtns = document.querySelectorAll('.ai-write-btn');
    const allGtmGroups = document.querySelectorAll('.gtm-field-group');

    function closeAllAIPanels() {
      allGtmGroups.forEach(group => {
        const panel = group.querySelector('.ai-panel');
        if (panel) {
          panel.classList.add('hidden');
          panel.classList.remove('flex');
        }
        // Remove dimmed state
        group.classList.remove('opacity-40', 'pointer-events-none');
        // Clear inputs & previews
        const instruction = group.querySelector('.ai-instruction');
        const previewContainer = group.querySelector('.ai-preview-container');
        const useBtn = group.querySelector('.ai-use-btn');
        if (instruction) instruction.value = '';
        if (previewContainer) previewContainer.classList.add('hidden');
        if (useBtn) useBtn.classList.add('hidden');
      });
      
      // Re-enable all write buttons
      aiWriteBtns.forEach(btn => btn.disabled = false);
    }

    aiWriteBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        closeAllAIPanels();
        
        const groupId = btn.getAttribute('data-group');
        const currentGroup = document.getElementById(groupId);
        
        // Dim other groups
        allGtmGroups.forEach(group => {
          if (group.id !== groupId) {
            group.classList.add('opacity-40', 'pointer-events-none');
          }
        });
        
        // Show panel
        const panel = currentGroup.querySelector('.ai-panel');
        if (panel) {
          panel.classList.remove('hidden');
          panel.classList.add('flex');
        }
        
        // Disable all write buttons while one is open
        aiWriteBtns.forEach(b => b.disabled = true);
      });
    });

    document.querySelectorAll('.ai-cancel-btn').forEach(btn => {
      btn.addEventListener('click', closeAllAIPanels);
    });

    document.querySelectorAll('.ai-rewrite-btn').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const group = e.target.closest('.gtm-field-group');
        const instructionInput = group.querySelector('.ai-instruction');
        const instruction = instructionInput.value.trim();
        
        if (!instruction) {
          alert('Please describe what you want to say first.');
          instructionInput.focus();
          return;
        }

        const writeBtn = group.querySelector('.ai-write-btn');
        const fieldName = writeBtn.getAttribute('data-field');
        const targetId = writeBtn.getAttribute('data-target');
        const currentValue = document.getElementById(targetId).value;
        
        const rewriteBtn = group.querySelector('.ai-rewrite-btn');
        const originalHTML = rewriteBtn.innerHTML;
        rewriteBtn.disabled = true;
        rewriteBtn.innerHTML = '<span class="material-symbols-outlined text-[16px] animate-spin">sync</span> <span class="btn-text">Generating...</span>';
        
        try {
          const res = await fetch('/api/gtm-context/write-with-ai', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ field: fieldName, current_value: currentValue, instruction: instruction })
          });
          const data = await res.json();
          
          if (res.ok && data.success) {
            const previewContainer = group.querySelector('.ai-preview-container');
            const previewText = group.querySelector('.ai-preview-text');
            const useBtn = group.querySelector('.ai-use-btn');
            
            previewText.textContent = data.generated_text;
            previewContainer.classList.remove('hidden');
            useBtn.classList.remove('hidden');
            
            // Change button text to Rewrite
            rewriteBtn.innerHTML = '<span class="material-symbols-outlined text-[16px]">refresh</span> <span class="btn-text">Rewrite</span>';
          } else {
            alert(data.error || 'Failed to generate content.');
            rewriteBtn.innerHTML = originalHTML;
          }
        } catch (err) {
          alert('Network error while generating content.');
          rewriteBtn.innerHTML = originalHTML;
        } finally {
          rewriteBtn.disabled = false;
        }
      });
    });

    document.querySelectorAll('.ai-use-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const group = e.target.closest('.gtm-field-group');
        const previewText = group.querySelector('.ai-preview-text').textContent;
        const writeBtn = group.querySelector('.ai-write-btn');
        const targetId = writeBtn.getAttribute('data-target');
        
        const targetTextarea = document.getElementById(targetId);
        if (targetTextarea) {
          targetTextarea.value = previewText;
        }
        
        closeAllAIPanels();
      });
    });


