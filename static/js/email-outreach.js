    window.emailLeadsData = {};
    // Fetch historical email leads from /api/email-leads
    async function fetchHistoricalEmailLeads() {
      try {
        const res = await fetch('/api/email-leads');
        const data = await res.json();
        if (res.ok && data.success) {
          const leads = data.leads || [];
          window.emailLeadsData = {};
          leads.forEach(l => {
            if (l.lead_id) window.emailLeadsData[l.lead_id] = l;
          });
          renderEmailTable(leads);
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
              <span class="font-body-sm text-body-sm text-primary-container font-medium">${exp.company || ''} ${exp.location ? '• ' + exp.location : ''}</span>
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
                <span class="font-body-sm text-body-sm text-text-secondary">${edu.degree || ''} ${edu.field_of_study ? '• ' + edu.field_of_study : ''}</span>
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
              <span>You're good to go ✓</span>
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
                  if (extractionCurrentStatusTitle) extractionCurrentStatusTitle.textContent = 'Extraction Complete ✓';
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
            body: JSON.stringify({ profile: currentExtractedData, gtm_context: savedGtmContext })
          });
          const result = await res.json();

          if (!res.ok || !result.success) {
            throw new Error(result.error || 'Profile optimization failed.');
          }

          renderOptimizationResult(result.data);
          optimizationResultContainer.classList.remove('hidden');
          optimizationResultContainer.scrollIntoView({ behavior: 'smooth' });


            // Unhide Next/Done button if in onboarding mode
            if (profileOptimizationMode === 'onboarding') {
              const nextBtnContainer = document.getElementById('po-onboarding-next-btn-container');
              if (nextBtnContainer) {
                nextBtnContainer.classList.remove('hidden');
                console.log('[FLOW] Profile optimization completed (Onboarding Mode) -> Displaying Next/Done button');
              }
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

          const initials = lead.full_name ? lead.full_name.substring(0, 2).toUpperCase() : (lead.name ? lead.name.substring(0, 2).toUpperCase() : '??');
          const name = lead.full_name || lead.name || 'Unknown';
          const company = lead.company || '-';
          const need = lead.business_need || '-';
          const reason = lead.reason || '-';
          const score = lead.score || lead.lead_score || 0;
          const email = lead.email ? lead.email.trim() : '';

          row.innerHTML = `
            <td class="py-3.5 px-4 whitespace-nowrap">
              <input type="checkbox" class="email-row-checkbox w-4 h-4 rounded border-border-default text-primary focus:ring-primary bg-surface-canvas cursor-pointer" data-lead-id="${lead.lead_id || ''}" data-email="${encodeURIComponent(email)}" data-firstname="${encodeURIComponent(lead.first_name || (name ? name.split(' ')[0] : ''))}" data-fullname="${encodeURIComponent(name)}" data-company="${encodeURIComponent(company)}" data-role="${encodeURIComponent(lead.role || '')}" data-need="${encodeURIComponent(need)}" data-score="${score}" data-reason="${encodeURIComponent(reason)}">
            </td>
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
            <td colspan="7" class="py-12 text-center text-text-muted">
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

    // ===== Email Composer Logic =====
    const composerImageInput = document.getElementById('composer-image-input');
    const composerAttachmentInput = document.getElementById('composer-attachment-input');
    const composerAttachmentsContainer = document.getElementById('composer-attachments-container');
    const selectAllCheckbox = document.getElementById('email-select-all');
    const selectAllLabel = document.getElementById('email-select-all-label');
    const composerToText = document.getElementById('composer-to-text');
    const btnSimulateSend = document.getElementById('btn-simulate-send');

    if (composerImageInput) {
      composerImageInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
          const reader = new FileReader();
          reader.onload = (ev) => {
            document.execCommand('insertImage', false, ev.target.result);
          };
          reader.readAsDataURL(file);
        }
        composerImageInput.value = '';
      });
    }

    let attachments = [];
    if (composerAttachmentInput) {
      composerAttachmentInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
          attachments.push(file.name);
          renderAttachments();
        }
        composerAttachmentInput.value = '';
      });
    }
    
    function renderAttachments() {
      if (!composerAttachmentsContainer) return;
      composerAttachmentsContainer.innerHTML = attachments.map((att, idx) => `
        <div class="flex items-center gap-1.5 px-2 py-1 rounded bg-surface-subtle border border-border-default font-label-sm text-text-primary text-[12px]">
          <span class="material-symbols-outlined text-[14px] text-text-secondary">attachment</span>
          <span>${att}</span>
          <button type="button" class="material-symbols-outlined text-[14px] hover:text-status-error-text transition-colors" onclick="removeAttachment(${idx})">close</button>
        </div>
      `).join('');
    }
    
    window.removeAttachment = function(idx) {
      attachments.splice(idx, 1);
      renderAttachments();
    };

    const composerToolbar = document.getElementById('composer-toolbar');
    const composerBody = document.getElementById('composer-body');
    const composerPreview = document.getElementById('composer-preview');
    const composerTemplateBanner = document.getElementById('composer-template-banner');
    const composerTemplateBannerCount = document.getElementById('composer-template-banner-count');
    const btnEditTemplate = document.getElementById('btn-edit-template');
    
    let isForcedTemplateMode = false;
    
    if (btnEditTemplate) {
      btnEditTemplate.addEventListener('click', () => {
        isForcedTemplateMode = true;
        const checkboxes = Array.from(emailTableBody.querySelectorAll('.email-row-checkbox')).filter(c => c.checked);
        updateComposerMode(1, checkboxes);
      });
    }

    const extractTemplateString = (html) => {
      const tempDiv = document.createElement('div');
      tempDiv.innerHTML = html;
      const chips = tempDiv.querySelectorAll('.email-placeholder');
      chips.forEach(chip => {
        const key = chip.getAttribute('data-placeholder');
        const openBrace = '{' + '{';
        const closeBrace = '}' + '}';
        const textNode = document.createTextNode(openBrace + key + closeBrace);
        chip.parentNode.replaceChild(textNode, chip);
      });
      return tempDiv.innerHTML;
    };

    function generatePreviewHtmlForLead(leadCheckbox, subjectTpl, bodyTplHtml) {
        const leadId = leadCheckbox.getAttribute('data-lead-id');
        const dbLead = (window.emailLeadsData && leadId) ? window.emailLeadsData[leadId] : null;
        
        let data = {};
        if (dbLead) {
            data = {
              first_name: dbLead.first_name || (dbLead.full_name ? dbLead.full_name.split(' ')[0] : ''),
              full_name: dbLead.full_name || '',
              company_name: dbLead.company || '',
              role: dbLead.role || '',
              business_need: dbLead.business_need || '',
              lead_score: dbLead.score || '',
              reason: dbLead.reason || '',
              email: dbLead.email || ''
            };
        } else {
          // Fallback to DOM attributes if not in DB
          data = {
            first_name: decodeURIComponent(leadCheckbox.getAttribute('data-firstname') || ''),
            full_name: decodeURIComponent(leadCheckbox.getAttribute('data-fullname') || ''),
            company_name: decodeURIComponent(leadCheckbox.getAttribute('data-company') || ''),
            role: decodeURIComponent(leadCheckbox.getAttribute('data-role') || ''),
            business_need: decodeURIComponent(leadCheckbox.getAttribute('data-need') || ''),
            lead_score: leadCheckbox.getAttribute('data-score') || '',
            reason: decodeURIComponent(leadCheckbox.getAttribute('data-reason') || ''),
            email: decodeURIComponent(leadCheckbox.getAttribute('data-email') || '')
          };
        }
        
        const resolveTemplate = (str) => {
          return str.replace(/\{\{(first_name|full_name|company_name|role|business_need|lead_score|reason|email|result_metric|sender_name|sender_role|sender_link)\}\}/g, (match, key) => {
            return data[key] !== undefined ? data[key] : '';
          });
        };
        
        const bodyStr = extractTemplateString(bodyTplHtml);
        return {
          subject: resolveTemplate(subjectTpl),
          body: resolveTemplate(bodyStr),
          name: data.full_name || data.first_name || 'Recipient'
        };
    }

    function updateComposerMode(checkedCount, checkedBoxes) {
      if (!composerToolbar || !composerBody || !composerPreview || !composerTemplateBanner) return;
      
      if (checkedCount !== 1) {
        isForcedTemplateMode = false;
      }
      
      if (checkedCount === 1 && !isForcedTemplateMode) {
        // 1 Recipient: Preview Mode
        composerToolbar.classList.add('hidden');
        composerBody.classList.add('hidden');
        composerTemplateBanner.classList.add('hidden');
        composerPreview.classList.remove('hidden');
        composerPreview.classList.add('flex');
        
        const previewData = generatePreviewHtmlForLead(
          checkedBoxes[0], 
          document.getElementById('composer-subject').value, 
          composerBody.innerHTML
        );
        
        document.getElementById('composer-preview-lead-name').textContent = previewData.name;
        document.getElementById('composer-preview-body').innerHTML = previewData.body;
      } else {
        // 0 or N Recipients: Template Mode
        composerToolbar.classList.remove('hidden');
        composerBody.classList.remove('hidden');
        composerPreview.classList.add('hidden');
        composerPreview.classList.remove('flex');
        
        if (checkedCount > 1) {
          composerTemplateBanner.classList.remove('hidden');
          composerTemplateBannerCount.textContent = `${checkedCount} recipients selected`;
        } else {
          composerTemplateBanner.classList.add('hidden');
        }
      }
    }

    function updateComposerToField() {
      if (!emailTableBody || !composerToText || !selectAllCheckbox || !selectAllLabel) return;
      const checkboxes = Array.from(emailTableBody.querySelectorAll('.email-row-checkbox'));
      const total = checkboxes.length;
      if (total === 0) {
        selectAllLabel.textContent = `Select All (0 leads)`;
        composerToText.textContent = 'Select leads from Email Contacts below';
        updateComposerMode(0, []);
        return;
      }
      
      const checked = checkboxes.filter(c => c.checked);
      selectAllCheckbox.checked = (checked.length === total && total > 0);
      selectAllCheckbox.indeterminate = (checked.length > 0 && checked.length < total);
      
      selectAllLabel.textContent = `Select All (${total} leads)`;
      
      if (checked.length === 0) {
        composerToText.textContent = 'Select leads from Email Contacts below';
      } else {
        composerToText.textContent = `${checked.length} recipients selected`;
      }
      
      updateComposerMode(checked.length, checked);
    }

    if (selectAllCheckbox) {
      selectAllCheckbox.addEventListener('change', (e) => {
        const checkboxes = emailTableBody.querySelectorAll('.email-row-checkbox');
        checkboxes.forEach(c => c.checked = e.target.checked);
        updateComposerToField();
      });
    }

    if (emailTableBody) {
      emailTableBody.addEventListener('change', (e) => {
        if (e.target.classList.contains('email-row-checkbox')) {
          updateComposerToField();
        }
      });
    }
    
    if (btnSimulateSend) {
      btnSimulateSend.addEventListener('click', () => {
        const checkboxes = Array.from(emailTableBody.querySelectorAll('.email-row-checkbox')).filter(c => c.checked);
        if (checkboxes.length === 0) {
          alert('Please select at least one recipient from the Email Contacts table.');
          return;
        }
        
        const subjectTpl = document.getElementById('composer-subject').value;
        const bodyTplHtml = document.getElementById('composer-body').innerHTML;
        
        const previewData = generatePreviewHtmlForLead(checkboxes[0], subjectTpl, bodyTplHtml);
        
        document.getElementById('email-preview-subject').textContent = previewData.subject;
        document.getElementById('email-preview-body').innerHTML = previewData.body;
        document.getElementById('email-preview-count').textContent = checkboxes.length - 1;
        
        const countContainer = document.getElementById('email-preview-count-container');
        if (checkboxes.length > 1) {
          countContainer.classList.remove('hidden');
        } else {
          countContainer.classList.add('hidden');
        }
        
        document.getElementById('email-preview-modal').classList.remove('hidden');
      });
    }

