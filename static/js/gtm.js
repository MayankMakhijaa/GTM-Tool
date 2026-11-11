/**
 * GTM Research Dashboard Controller
 * Connects to PostgreSQL-backed GTM endpoints, handles asynchronous job polling,
 * and dynamically renders qualified leads and telemetry.
 */
document.addEventListener('DOMContentLoaded', () => {
    const btnStartResearch = document.getElementById('btn-start-research-btn') || document.getElementById('btn-start-research');
    const btnSaveLead = document.getElementById('btn-save-lead');
    const btnDraftOutreach = document.getElementById('btn-draft-outreach');
    const btnExportCsv = document.getElementById('btn-export-csv');

    const inputTargetLeads = document.getElementById('input-target-leads');
    const selectPersonaFilter = document.getElementById('select-persona-filter');

    // Context & Alerts
    const icpBanner = document.getElementById('gtm-icp-banner');
    const sessionAlert = document.getElementById('gtm-session-alert');
    const sessionAlertText = document.getElementById('gtm-session-alert-text');

    // Progress Banner Elements
    const progressContainer = document.getElementById('gtm-progress-container');
    const progressStatusTitle = document.getElementById('progress-status-title');
    const progressPercentageLabel = document.getElementById('progress-percentage-label');
    const progressBarFill = document.getElementById('progress-bar-fill');
    const telemetryCandidates = document.getElementById('telemetry-candidates');
    const telemetryStep = document.getElementById('telemetry-step');
    const telemetryStatus = document.getElementById('telemetry-status');

    // Table Elements
    const tableBody = document.getElementById('prospects-table-body');
    const pipelineCountBadge = document.getElementById('pipeline-count-badge');
    const pipelineFooterCount = document.getElementById('pipeline-footer-count');

    // Drawer Elements
    const dName = document.getElementById('drawer-name');
    const dTitleCompany = document.getElementById('drawer-title-company');
    const dScore = document.getElementById('drawer-score');
    const dScoreTier = document.getElementById('drawer-score-tier');
    const dNeed = document.getElementById('drawer-need');
    const dSignals = document.getElementById('drawer-signals');
    const dQualification = document.getElementById('drawer-qualification');
    const dExternalLink = document.getElementById('drawer-external-link');

    // Public Lead Enrichment Elements
    const btnEnrichLead = document.getElementById('btn-enrich-lead');
    const btnEnrichLeadText = document.getElementById('btn-enrich-lead-text');
    const enrichNamedEmail = document.getElementById('enrich-named-email');
    const enrichGenericContact = document.getElementById('enrich-generic-contact');
    const enrichMxStatus = document.getElementById('enrich-mx-status');
    const enrichSourceWrapper = document.getElementById('enrich-source-wrapper');
    const enrichStatusLabel = document.getElementById('enrich-status-label');
    const enrichSourceLink = document.getElementById('enrich-source-link');

    let currentSelectedProspect = null;

    const getCsrfToken = () => document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';

    let currentOpportunities = [];
    let activePollTimeout = null;
    let activePollJobId = null;

    // ====================================================================
    // 1. LOAD SAVED GTM CONTEXT & SESSION STATUS
    // ====================================================================
    async function loadGtmContext() {
        try {
            const res = await fetch('/api/gtm-context', {
                headers: { 'Accept': 'application/json' }
            });
            const result = await res.json();

            if (result.success && result.data) {
                const ctx = result.data;
                if (icpBanner) {
                    const desc = ctx.company_name ? `${ctx.company_name} • ${ctx.target_icp || 'B2B SaaS'}` : (ctx.target_icp || 'Active Model');
                    icpBanner.textContent = `Based on ICP: ${desc}`;
                }

                if (sessionAlert) {
                    // LinkedIn session is optional since AI lead discovery operates via Claude + Global Directory
                    sessionAlert.classList.add('hidden');
                }

                // Restore active job display and resume polling on page reload
                if (ctx.active_job && (ctx.active_job.status === 'QUEUED' || ctx.active_job.status === 'RUNNING')) {
                    const job = ctx.active_job;
                    const progress = job.progress || {};
                    const pct = progress.pct || 15;
                    const message = progress.message || 'Processing research...';
                    const step = progress.step || job.status;

                    if (progressContainer) {
                        progressContainer.classList.remove('hidden');
                    }
                    updateProgress(pct, step, message, job.results_count || 0, job.status);

                    if (btnStartResearch) {
                        const actualBtn = btnStartResearch.closest('button') || btnStartResearch;
                        actualBtn.disabled = true;
                        const originalText = '<span class="material-symbols-outlined text-[20px]">travel_explore</span><span id="btn-start-research">Start Research</span>';
                        actualBtn.innerHTML = '<span class="material-symbols-outlined animate-spin text-[20px]">progress_activity</span><span>Researching...</span>';
                        startPollingJob(job.job_id, actualBtn, originalText);
                    }
                }
            } else if (result.error && icpBanner) {
                icpBanner.textContent = result.error;
            }
        } catch (err) {
            console.error('[GTM UI] Error fetching context:', err);
        }
    }

    // ====================================================================
    // 2. LOAD SAVED OPPORTUNITIES
    // ====================================================================
    async function loadOpportunities() {
        try {
            const res = await fetch('/api/gtm-opportunities', {
                headers: { 'Accept': 'application/json' }
            });
            const result = await res.json();

            if (result.success && Array.isArray(result.opportunities)) {
                currentOpportunities = result.opportunities;
                renderOpportunities(currentOpportunities);
            }
        } catch (err) {
            console.error('[GTM UI] Error fetching opportunities:', err);
        }
    }

    // ====================================================================
    // 3. RENDER OPPORTUNITIES IN TABLE
    // ====================================================================
    function renderOpportunities(opportunities) {
        if (!tableBody) return;

        const count = opportunities.length;
        if (pipelineCountBadge) pipelineCountBadge.textContent = `${count} Leads`;
        if (pipelineFooterCount) pipelineFooterCount.textContent = `Showing ${count} qualified prospects`;

        if (count === 0) {
            tableBody.innerHTML = `
                <tr id="prospects-empty-row">
                    <td colspan="6" class="py-12 text-center text-on-surface-variant font-body-md">
                        <div class="flex flex-col items-center justify-center gap-2">
                            <span class="material-symbols-outlined text-outline text-[36px]">travel_explore</span>
                            <span>No prospects discovered yet. Select your criteria above and click 'Start Research'.</span>
                        </div>
                    </td>
                </tr>
            `;
            resetDrawer();
            return;
        }

        tableBody.innerHTML = '';
        opportunities.forEach((item, index) => {
            const tr = document.createElement('tr');
            tr.id = `row-${item.id}`;
            tr.className = `prospect-row hover:bg-surface-container/60 transition-colors cursor-pointer group ${index === 0 ? 'bg-surface-container-high/60' : ''}`;
            tr.onclick = () => selectProspect(item);

            const score = item.score || 70;
            const scoreBadgeClass = score >= 85
                ? 'bg-tertiary-fixed text-on-tertiary-fixed'
                : 'bg-surface-container-high text-on-surface';

            tr.innerHTML = `
                <td class="py-3 px-space-md whitespace-nowrap">
                    <div class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full ${scoreBadgeClass} font-code-sm text-code-sm font-bold">
                        ${score >= 85 ? '<span class="material-symbols-outlined text-[14px]">stars</span>' : ''}
                        ${score}%
                    </div>
                </td>
                <td class="py-3 px-space-md whitespace-nowrap">
                    <div class="flex items-center gap-2.5">
                        <div class="w-8 h-8 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold text-xs uppercase">
                            ${(item.name || 'L').slice(0, 2)}
                        </div>
                        <div class="flex flex-col min-w-0">
                            <span class="font-label-md text-label-md text-on-surface font-semibold truncate">${escapeHtml(item.name || 'LinkedIn Member')}</span>
                            <span class="font-body-sm text-body-sm text-on-surface-variant truncate">${escapeHtml(item.role || 'Executive')}</span>
                        </div>
                    </div>
                </td>
                <td class="py-3 px-space-md whitespace-nowrap">
                    <div class="flex flex-col">
                        <span class="font-label-md text-label-md text-on-surface truncate">${escapeHtml(item.company || 'Target Organization')}</span>
                        <span class="font-body-sm text-body-sm text-outline truncate">${escapeHtml(item.location || 'Verified Market')}</span>
                    </div>
                </td>
                <td class="py-3 px-space-md whitespace-nowrap">
                    <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-surface-container-highest text-on-surface-variant font-label-sm text-label-sm font-medium">
                        ${escapeHtml(item.signals || 'Active Market Intent')}
                    </span>
                </td>
                <td class="py-3 px-space-md whitespace-nowrap">
                    <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-tertiary/10 text-tertiary font-label-sm text-label-sm font-medium">
                        ${escapeHtml(item.status || 'Qualified')}
                    </span>
                </td>
                <td class="py-3 px-space-md text-right whitespace-nowrap">
                    <button class="px-2.5 py-1 rounded bg-surface-container-lowest text-primary hover:bg-primary-container hover:text-on-primary font-label-sm text-label-sm transition-all shadow-sm">
                        Open
                    </button>
                </td>
            `;
            tableBody.appendChild(tr);
        });

        // Select the first prospect by default
        if (opportunities.length > 0) {
            selectProspect(opportunities[0]);
        }
    }

    // ====================================================================
    // 4. DRAWER SELECTION CONTROLLER
    // ====================================================================
    window.selectProspect = function(item) {
        if (!item) return;
        currentSelectedProspect = item;

        if (dName) dName.textContent = item.name || 'Unknown Prospect';
        if (dTitleCompany) dTitleCompany.textContent = `${item.role || 'Executive'} @ ${item.company || 'Organization'}`;
        if (dScore) dScore.textContent = `${item.score || 0}%`;
        if (dScoreTier) dScoreTier.textContent = item.tier || 'Strategic Match';
        if (dNeed) dNeed.textContent = item.need || 'Identified alignment with core offering.';
        if (dSignals) dSignals.textContent = item.signals || 'Active leadership signals detected.';
        if (dQualification) dQualification.textContent = item.qualification || 'Meets target role and ICP specifications.';

        if (dExternalLink) {
            if (item.profile_url) {
                dExternalLink.href = item.profile_url;
                dExternalLink.classList.remove('hidden');
            } else {
                dExternalLink.classList.add('hidden');
            }
        }

        // Render enrichment findings if present
        renderEnrichmentDetails(item.enrichment);

        // Highlight active row
        document.querySelectorAll('.prospect-row').forEach(r => r.classList.remove('bg-surface-container-high/60'));
        const activeRow = document.getElementById(`row-${item.id}`);
        if (activeRow) activeRow.classList.add('bg-surface-container-high/60');
    };

    function renderEnrichmentDetails(enrichment) {
        if (!enrichment) {
            if (enrichNamedEmail) {
                enrichNamedEmail.textContent = 'Not checked';
                enrichNamedEmail.className = 'font-mono text-on-surface-variant font-normal text-right truncate max-w-[200px]';
            }
            if (enrichGenericContact) enrichGenericContact.textContent = '-';
            if (enrichMxStatus) enrichMxStatus.textContent = '-';
            if (enrichSourceWrapper) enrichSourceWrapper.classList.add('hidden');
            if (btnEnrichLeadText) btnEnrichLeadText.textContent = 'Enrich Lead';
            return;
        }

        // Named Business Email
        if (enrichNamedEmail) {
            if (enrichment.business_email) {
                enrichNamedEmail.textContent = enrichment.business_email;
                enrichNamedEmail.className = 'font-mono text-emerald-400 font-semibold text-right truncate max-w-[200px]';
                enrichNamedEmail.title = `Source: ${enrichment.source_url || 'Public Website'}`;
            } else {
                enrichNamedEmail.textContent = 'None published';
                enrichNamedEmail.className = 'font-mono text-on-surface-variant font-normal text-right truncate max-w-[200px]';
            }
        }

        // Generic email or phone
        if (enrichGenericContact) {
            const genericParts = [];
            if (enrichment.generic_email) genericParts.push(enrichment.generic_email);
            if (enrichment.phone) genericParts.push(enrichment.phone);

            if (genericParts.length > 0) {
                enrichGenericContact.textContent = genericParts.join(' | ');
                enrichGenericContact.className = 'font-mono text-on-surface text-right truncate max-w-[200px]';
            } else {
                enrichGenericContact.textContent = 'None published';
                enrichGenericContact.className = 'font-mono text-on-surface-variant text-right truncate max-w-[200px]';
            }
        }

        // Domain & MX status
        if (enrichMxStatus) {
            if (enrichment.official_domain) {
                const mxNote = enrichment.mx_configured ? 'MX: Configured' : 'MX: Not configured';
                enrichMxStatus.textContent = `${enrichment.official_domain} (${mxNote})`;
                enrichMxStatus.className = enrichment.mx_configured ? 'font-mono text-emerald-400 text-[11px] text-right truncate max-w-[200px]' : 'font-mono text-amber-400 text-[11px] text-right truncate max-w-[200px]';
            } else {
                enrichMxStatus.textContent = 'Domain unresolved';
                enrichMxStatus.className = 'font-mono text-on-surface-variant text-[11px] text-right truncate max-w-[200px]';
            }
        }

        // Source and verification metadata
        if (enrichSourceWrapper) {
            if (enrichment.source_url || enrichment.verification_status) {
                enrichSourceWrapper.classList.remove('hidden');
                if (enrichStatusLabel) {
                    enrichStatusLabel.textContent = `Status: ${enrichment.verification_status || 'CHECKED'}`;
                }
                if (enrichSourceLink) {
                    if (enrichment.source_url) {
                        enrichSourceLink.href = enrichment.source_url;
                        enrichSourceLink.classList.remove('hidden');
                    } else {
                        enrichSourceLink.classList.add('hidden');
                    }
                }
            } else {
                enrichSourceWrapper.classList.add('hidden');
            }
        }

        if (btnEnrichLeadText) {
            btnEnrichLeadText.textContent = 'Re-Enrich';
        }
    }

    // Lead enrichment trigger handler
    if (btnEnrichLead) {
        btnEnrichLead.addEventListener('click', async (e) => {
            e.preventDefault();
            if (!currentSelectedProspect || !currentSelectedProspect.id) {
                alert('Please select a prospect to enrich.');
                return;
            }

            btnEnrichLead.disabled = true;
            const originalText = btnEnrichLeadText ? btnEnrichLeadText.textContent : 'Enrich Lead';
            if (btnEnrichLeadText) btnEnrichLeadText.textContent = 'Enriching...';

            try {
                const resp = await fetch(`/api/gtm-opportunities/${currentSelectedProspect.id}/enrich`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    }
                });

                let data = null;
                try {
                    data = await resp.json();
                } catch (parseErr) {
                    console.error('[Enrichment] Failed to parse JSON response:', parseErr);
                }

                if (resp.ok && data && data.success && data.enrichment) {
                    currentSelectedProspect.enrichment = data.enrichment;
                    // Also update in currentOpportunities array
                    const found = currentOpportunities.find(o => o.id === currentSelectedProspect.id);
                    if (found) {
                        found.enrichment = data.enrichment;
                    }
                    renderEnrichmentDetails(data.enrichment);
                } else {
                    const serverMsg = data ? (data.message || data.error || data.description) : null;
                    const errorDetail = serverMsg || `Server responded with HTTP ${resp.status} (${resp.statusText || 'Error'})`;
                    alert(`Enrichment failed: ${errorDetail}`);
                }
            } catch (networkErr) {
                console.error('[Enrichment] Network/Connection error:', networkErr);
                alert(`Network connection failure: Unable to reach the server. Please check your connection.`);
            } finally {
                btnEnrichLead.disabled = false;
                if (btnEnrichLeadText) btnEnrichLeadText.textContent = originalText === 'Enriching...' ? 'Re-Enrich' : originalText;
            }
        });
    }

    function resetDrawer() {
        currentSelectedProspect = null;
        if (dName) dName.textContent = 'Select a Prospect';
        if (dTitleCompany) dTitleCompany.textContent = '-';
        if (dScore) dScore.textContent = '0%';
        if (dScoreTier) dScoreTier.textContent = 'Awaiting Selection';
        if (dNeed) dNeed.textContent = 'Select a qualified prospect to view detailed intent analysis.';
        if (dSignals) dSignals.textContent = '-';
        if (dQualification) dQualification.textContent = '-';
        if (dExternalLink) dExternalLink.classList.add('hidden');
        renderEnrichmentDetails(null);
    }

    // ====================================================================
    // Credit estimation
    const creditEstimateSpan = document.getElementById('credit-cost-estimate');
    const updateCreditEstimate = () => {
        if (!creditEstimateSpan || !inputTargetLeads) return;
        const qty = parseInt(inputTargetLeads.value, 10) || 15;
        // Default GTM_RESEARCH_LEAD is 2 credits per lead
        const est = qty * 2;
        creditEstimateSpan.textContent = `~${est} credits`;
    };
    if (inputTargetLeads) {
        inputTargetLeads.addEventListener('input', updateCreditEstimate);
        updateCreditEstimate();
    }

    const btnStopResearchJob = document.getElementById('btn-stop-research-job');

    // 5. ASYNCHRONOUS RESEARCH JOB EXECUTION & POLLING
    // ====================================================================
    if (btnStartResearch) {
        const actualBtn = btnStartResearch.closest('button') || btnStartResearch;

        actualBtn.addEventListener('click', async () => {
            const targetLeads = inputTargetLeads ? parseInt(inputTargetLeads.value, 10) || 15 : 15;
            const personaFilter = selectPersonaFilter ? selectPersonaFilter.value : '';

            actualBtn.disabled = true;
            const originalText = actualBtn.innerHTML;
            actualBtn.innerHTML = '<span class="material-symbols-outlined animate-spin text-[20px]">progress_activity</span><span>Prospecting...</span>';

            if (btnStopResearchJob) {
                btnStopResearchJob.classList.remove('hidden');
                btnStopResearchJob.disabled = false;
            }

            if (progressContainer) {
                progressContainer.classList.remove('hidden');
            }
            updateProgress(5, 'STARTING', 'Initiating continuous prospecting loop...', 0, 'QUEUED');

            try {
                const res = await fetch('/api/gtm-opportunities/find', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: JSON.stringify({
                        target_leads: targetLeads,
                        persona_filter: personaFilter
                    })
                });

                const data = await res.json();
                if (!res.ok || !data.success) {
                    const errMsg = data.message || data.error || 'Failed to start research job.';
                    if (res.status === 402 || data.error === 'INSUFFICIENT_CREDITS') {
                        throw new Error(`Insufficient Credits: ${errMsg}`);
                    }
                    throw new Error(errMsg);
                }

                const jobId = data.job_id;
                startPollingJob(jobId, actualBtn, originalText);

            } catch (err) {
                alert(err.message);
                if (progressContainer) progressContainer.classList.add('hidden');
                if (btnStopResearchJob) btnStopResearchJob.classList.add('hidden');
                actualBtn.disabled = false;
                actualBtn.innerHTML = originalText;
            }
        });
    }

    if (btnStopResearchJob) {
        btnStopResearchJob.addEventListener('click', async () => {
            if (!activePollJobId) return;
            btnStopResearchJob.disabled = true;
            btnStopResearchJob.innerHTML = '<span class="material-symbols-outlined animate-spin text-[18px]">progress_activity</span><span>Stopping...</span>';

            try {
                const res = await fetch(`/api/gtm/jobs/${activePollJobId}/stop`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    }
                });
                const data = await res.json();
                if (data.success) {
                    updateProgress(100, 'STOPPING', 'Stop requested. Finalizing active queries and saving leads...', null, 'CANCELLING');
                }
            } catch (err) {
                console.error('[GTM Stop] Failed to signal job stop:', err);
            }
        });
    }

    function stopPollingJob() {
        if (activePollTimeout) {
            clearTimeout(activePollTimeout);
            activePollTimeout = null;
        }
        activePollJobId = null;
        if (btnStopResearchJob) {
            btnStopResearchJob.classList.add('hidden');
            btnStopResearchJob.disabled = false;
            btnStopResearchJob.innerHTML = '<span class="material-symbols-outlined text-[20px] text-rose-400">stop_circle</span><span>Stop Discovery</span>';
        }
    }

    function startPollingJob(jobId, button, originalButtonHtml) {
        stopPollingJob();
        activePollJobId = jobId;
        if (btnStopResearchJob) {
            btnStopResearchJob.classList.remove('hidden');
            btnStopResearchJob.disabled = false;
        }

        let pollDelayMs = 3000;
        const maxPollDelayMs = 8000;

        async function poll() {
            // Guard against duplicate / stale polling loops
            if (activePollJobId !== jobId) return;

            try {
                const res = await fetch(`/api/gtm/jobs/${jobId}/status`, {
                    headers: { 'Accept': 'application/json' }
                });

                if (res.status === 429) {
                    const retryHeader = res.headers.get('Retry-After');
                    const retrySec = retryHeader ? parseInt(retryHeader, 10) : 5;
                    const backoffMs = Math.min(Math.max(pollDelayMs * 1.5, (retrySec || 5) * 1000), 15000);
                    if (activePollJobId === jobId) {
                        activePollTimeout = setTimeout(poll, backoffMs);
                    }
                    return;
                }

                if (!res.ok && res.status !== 404) {
                    pollDelayMs = Math.min(pollDelayMs * 1.5, 12000);
                    if (activePollJobId === jobId) {
                        activePollTimeout = setTimeout(poll, pollDelayMs);
                    }
                    return;
                }

                const data = await res.json();

                if (!data.success) {
                    stopPollingJob();
                    if (button) {
                        button.disabled = false;
                        button.innerHTML = originalButtonHtml;
                    }
                    alert('Job status check failed: ' + (data.error || 'Unknown error'));
                    return;
                }

                const progress = data.progress || {};
                const pct = progress.pct || 15;
                const message = progress.message || 'Processing research...';
                const step = progress.step || 'RUNNING';

                updateProgress(pct, step, message, data.results_count || 0, data.status);

                // Auto-refresh main dashboard opportunities table on incremental lead arrivals
                if (data.results_count && data.results_count > currentOpportunities.length) {
                    loadOpportunities();
                }

                if (data.status === 'COMPLETED') {
                    stopPollingJob();
                    if (button) {
                        button.disabled = false;
                        button.innerHTML = originalButtonHtml;
                    }
                    const leadsFound = data.results_count || 0;
                    const completionMsg = progress.message || `Successfully discovered and qualified ${leadsFound} prospects!`;
                    updateProgress(100, 'COMPLETED', completionMsg, leadsFound, 'COMPLETED');
                    await loadOpportunities();
                } else if (data.status === 'FAILED') {
                    stopPollingJob();
                    if (button) {
                        button.disabled = false;
                        button.innerHTML = originalButtonHtml;
                    }
                    const errMsg = data.error || progress.message || 'Pipeline failure';
                    updateProgress(100, 'FAILED', `Research failed: ${errMsg}`, 0, 'FAILED');
                    alert(`Research pipeline error: ${errMsg}`);
                } else if (data.status === 'CANCELLED') {
                    stopPollingJob();
                    if (button) {
                        button.disabled = false;
                        button.innerHTML = originalButtonHtml;
                    }
                    updateProgress(100, 'CANCELLED', 'Prospecting was stopped.', data.results_count || 0, 'CANCELLED');
                    await loadOpportunities();
                } else {
                    // Job is still running (QUEUED or RUNNING) - apply bounded backoff
                    pollDelayMs = Math.min(Math.round(pollDelayMs * 1.1), maxPollDelayMs);
                    if (activePollJobId === jobId) {
                        activePollTimeout = setTimeout(poll, pollDelayMs);
                    }
                }
            } catch (err) {
                console.error('[GTM Polling] Error checking job status:', err);
                pollDelayMs = Math.min(pollDelayMs * 1.5, 12000);
                if (activePollJobId === jobId) {
                    activePollTimeout = setTimeout(poll, pollDelayMs);
                }
            }
        }

        // Schedule first poll after initial delay (3000ms)
        activePollTimeout = setTimeout(poll, pollDelayMs);
    }

    function updateProgress(pct, step, message, count, status) {
        if (progressBarFill) progressBarFill.style.width = `${pct}%`;
        if (progressPercentageLabel) progressPercentageLabel.textContent = `${pct}% COMPLETED`;
        if (progressStatusTitle) progressStatusTitle.textContent = message;
        if (telemetryStep) telemetryStep.textContent = step;
        if (telemetryCandidates) telemetryCandidates.textContent = count;
        if (telemetryStatus) telemetryStatus.textContent = status;
    }

    // Secondary Actions
    if (btnSaveLead) {
        btnSaveLead.addEventListener('click', () => {
            alert('Lead saved successfully to your History.');
        });
    }

    if (btnDraftOutreach) {
        btnDraftOutreach.addEventListener('click', () => {
            window.location.href = '/emails';
        });
    }

    if (btnExportCsv) {
        btnExportCsv.addEventListener('click', () => {
            window.location.href = '/api/gtm-opportunities/export';
        });
    }

    function escapeHtml(text) {
        if (!text) return '';
        const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
        return String(text).replace(/[&<>"']/g, m => map[m]);
    }

    // =========================================================================
    // LINKEDIN SEARCH & DISCOVERY WORKFLOW (PHASE 1)
    // =========================================================================
    const btnFindLeadsLinkedIn = document.getElementById('btn-find-leads-linkedin');
    const modalDiscovery = document.getElementById('modal-linkedin-discovery');
    const btnCloseDiscovery = document.getElementById('btn-close-discovery-modal');
    const btnCancelDiscovery = document.getElementById('btn-cancel-discovery');
    const btnRefreshQueries = document.getElementById('btn-refresh-queries');

    const discoverySpinner = document.getElementById('discovery-spinner');
    const discoveryStatusTitle = document.getElementById('discovery-status-title');
    const discoveryStatusDesc = document.getElementById('discovery-status-desc');

    const discoveryQueriesSection = document.getElementById('discovery-queries-section');
    const discoveryQueriesList = document.getElementById('discovery-queries-list');
    const discoveryQueryCount = document.getElementById('discovery-query-count');
    const selectNetworkScope = document.getElementById('select-network-scope');
    const btnPublicSearchDiscovery = document.getElementById('btn-public-search-discovery');
    const openSerpStatusBanner = document.getElementById('openserp-status-banner');
    const openSerpStatusIcon = document.getElementById('openserp-status-icon');
    const openSerpStatusText = document.getElementById('openserp-status-text');
    const openSerpStatusBadge = document.getElementById('openserp-status-badge');

    const discoveryResultsSection = document.getElementById('discovery-results-section');
    const discoveryResultsBody = document.getElementById('discovery-results-body');
    const discoveryResultsSummary = document.getElementById('discovery-results-summary');

    // Market Intelligence elements
    const discoveryMarketIntelSection = document.getElementById('discovery-market-intelligence-section');
    const marketSignalsBadge = document.getElementById('market-signals-badge');
    const intelTopTitles = document.getElementById('intel-top-titles');
    const intelTopLocations = document.getElementById('intel-top-locations');
    const intelTopCompanies = document.getElementById('intel-top-companies');
    const intelSampleSnippets = document.getElementById('intel-sample-snippets');

    const btnSelectAllProspects = document.getElementById('btn-select-all-prospects');
    const btnDeselectAllProspects = document.getElementById('btn-deselect-all-prospects');
    const btnProceedReview = document.getElementById('btn-proceed-review');
    const btnProceedReviewText = document.getElementById('btn-proceed-review-text');

    const discoveryQualSummary = document.getElementById('discovery-qualification-summary');
    const qualBadgeTotal = document.getElementById('qualification-badge-total');
    const qualStatQualified = document.getElementById('qual-stat-qualified');
    const qualStatPersisted = document.getElementById('qual-stat-persisted');
    const qualStatDuplicates = document.getElementById('qual-stat-duplicates');
    const qualStatBilled = document.getElementById('qual-stat-billed');
    const qualFeedbackText = document.getElementById('qualification-feedback-text');

    let currentSearchPlan = null;
    let discoveredProspects = []; // Array of { name, role, headline, company, location, profile_url, source_query_id, selected }
    let unverifiedMarketSignals = []; // Array of { headline, location, experience_snippet, company_mentions, source_query }
    let isExecutingSearch = false;

    function openDiscoveryModal() {
        if (!modalDiscovery) return;
        modalDiscovery.classList.remove('hidden');
        if (!currentSearchPlan) {
            fetchSearchPlan();
        }
    }

    function closeDiscoveryModal() {
        if (!modalDiscovery) return;
        modalDiscovery.classList.add('hidden');
    }

    if (btnFindLeadsLinkedIn) {
        btnFindLeadsLinkedIn.addEventListener('click', openDiscoveryModal);
    }
    if (btnCloseDiscovery) {
        btnCloseDiscovery.addEventListener('click', closeDiscoveryModal);
    }
    if (btnCancelDiscovery) {
        btnCancelDiscovery.addEventListener('click', closeDiscoveryModal);
    }
    if (btnRefreshQueries) {
        btnRefreshQueries.addEventListener('click', () => fetchSearchPlan(true));
    }

    async function fetchSearchPlan(force = false) {
        if (discoverySpinner) discoverySpinner.classList.remove('hidden');
        if (btnRefreshQueries) btnRefreshQueries.classList.add('hidden');
        discoveryStatusTitle.innerText = 'Generating Gemini Search Queries...';
        discoveryStatusDesc.innerText = 'Translating your ICP and company offering into focused LinkedIn queries.';
        discoveryQueriesSection.classList.add('hidden');

        try {
            const personaVal = selectPersonaFilter ? selectPersonaFilter.value : '';
            const res = await fetch('/api/gtm/search-plan', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({
                    persona_filter: personaVal || null,
                    max_queries: 6
                })
            });

            const result = await res.json();
            if (discoverySpinner) discoverySpinner.classList.add('hidden');

            if (!result.success || !result.data) {
                discoveryStatusTitle.innerText = 'Failed to generate queries';
                discoveryStatusDesc.innerText = result.error || 'Could not contact Gemini search planner.';
                if (btnRefreshQueries) btnRefreshQueries.classList.remove('hidden');
                return;
            }

            currentSearchPlan = result.data;
            renderSearchQueries(currentSearchPlan.queries || []);
            discoveryStatusTitle.innerText = 'Search Queries Ready';
            discoveryStatusDesc.innerText = 'Click "Search on LinkedIn" on any query below to discover visible prospects in your browser.';
            if (btnRefreshQueries) btnRefreshQueries.classList.remove('hidden');
        } catch (err) {
            if (discoverySpinner) discoverySpinner.classList.add('hidden');
            discoveryStatusTitle.innerText = 'Network error generating queries';
            discoveryStatusDesc.innerText = err.message;
            if (btnRefreshQueries) btnRefreshQueries.classList.remove('hidden');
        }
    }

    // Helper to generate search URL respecting the active network scope selection
    function buildLinkedInSearchUrl(queryKeywords, scopeValue) {
        const searchParams = new URLSearchParams();
        searchParams.set('keywords', queryKeywords);
        searchParams.set('origin', 'GLOBAL_SEARCH_HEADER');

        const scope = scopeValue || (selectNetworkScope ? selectNetworkScope.value : 'S');
        if (scope === 'F') {
            searchParams.set('network', JSON.stringify(['F']));
        } else if (scope === 'S') {
            searchParams.set('network', JSON.stringify(['S']));
        } else if (scope === 'F_S') {
            searchParams.set('network', JSON.stringify(['F', 'S']));
        } else if (scope === 'ALL') {
            searchParams.set('network', JSON.stringify(['F', 'S', 'O']));
        } else {
            // Default to 2nd Degree
            searchParams.set('network', JSON.stringify(['S']));
        }

        return `https://www.linkedin.com/search/results/people/?${searchParams.toString()}`;
    }

    function renderSearchQueries(queries) {
        if (!discoveryQueriesList) return;
        discoveryQueriesList.innerHTML = '';
        discoveryQueryCount.innerText = `${queries.length} queries`;

        if (queries.length === 0) {
            discoveryQueriesList.innerHTML = `<div class="col-span-2 text-sm text-on-surface-variant p-4 text-center">No queries generated. Click Regenerate.</div>`;
            discoveryQueriesSection.classList.remove('hidden');
            return;
        }

        const currentScope = selectNetworkScope ? selectNetworkScope.value : 'S';

        queries.forEach((q) => {
            const card = document.createElement('div');
            card.className = 'p-3.5 rounded-xl bg-surface-container-low border border-outline/10 flex flex-col justify-between gap-2.5 hover:border-outline/30 transition-all';

            const queryKeywords = q.keywords ? `${q.title} ${q.keywords}` : q.title;
            const searchUrl = buildLinkedInSearchUrl(queryKeywords, currentScope);

            card.innerHTML = `
                <div class="flex flex-col gap-1">
                    <div class="flex items-center justify-between">
                        <span class="font-label-md text-label-md font-bold text-on-surface">${escapeHtml(q.title)}</span>
                        <span class="font-code-sm text-[10px] px-1.5 py-0.5 rounded bg-surface-container text-on-surface-variant">${escapeHtml(q.id)}</span>
                    </div>
                    <p class="font-body-xs text-xs text-on-surface-variant line-clamp-2">${escapeHtml(q.rationale || `Focus: ${q.keywords || q.industry || 'ICP alignment'}`)}</p>
                    <div class="flex items-center gap-2 mt-1 text-[11px] text-on-surface-variant">
                        <span>Keywords: <strong class="text-on-surface">${escapeHtml(q.keywords || 'N/A')}</strong></span>
                        ${q.location ? `&bull; <span>${escapeHtml(q.location)}</span>` : ''}
                    </div>
                </div>
                <div class="pt-2 border-t border-outline/10 flex items-center justify-between">
                    <a href="${escapeHtml(searchUrl)}" target="_blank" rel="noopener" class="link-open-manually text-xs text-primary hover:underline flex items-center gap-1">
                        <span>Open manually</span>
                        <span class="material-symbols-outlined text-[14px]">open_in_new</span>
                    </a>
                    <button type="button" class="btn-execute-search px-3 py-1.5 rounded-lg bg-primary-container text-on-primary hover:bg-secondary font-label-sm text-label-sm font-semibold flex items-center gap-1.5 transition-all shadow-sm active:scale-95"
                            data-query-id="${escapeHtml(q.id)}"
                            data-query-text="${escapeHtml(queryKeywords)}">
                        <span class="material-symbols-outlined text-[16px]">travel_explore</span>
                        <span>Search Tab</span>
                    </button>
                </div>
            `;
            discoveryQueriesList.appendChild(card);
        });

        discoveryQueriesSection.classList.remove('hidden');

        // Bind execute search buttons — generates URL dynamically from latest selected scope
        discoveryQueriesList.querySelectorAll('.btn-execute-search').forEach((btn) => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                const qId = btn.getAttribute('data-query-id');
                const qText = btn.getAttribute('data-query-text');
                const dynamicSearchUrl = buildLinkedInSearchUrl(qText);
                executeLinkedInSearch(qId, qText, dynamicSearchUrl, btn);
            });
        });
    }

    // Re-render query card links if user changes network scope
    if (selectNetworkScope) {
        selectNetworkScope.addEventListener('change', () => {
            if (currentSearchPlan && currentSearchPlan.queries) {
                renderSearchQueries(currentSearchPlan.queries);
            }
        });
    }

    // Public Search Discovery via local OpenSERP
    let openSerpCooldownTimer = null;

    function formatCooldownTime(seconds) {
        const m = Math.floor(seconds / 60);
        const s = Math.floor(seconds % 60);
        return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    }

    function startCooldownCountdown(totalSeconds) {
        if (openSerpCooldownTimer) {
            clearInterval(openSerpCooldownTimer);
            openSerpCooldownTimer = null;
        }

        let remaining = Math.max(0, Math.ceil(totalSeconds));
        if (remaining <= 0) {
            renderCooldownExpiredBanner();
            return;
        }

        if (openSerpStatusBanner) {
            openSerpStatusBanner.className = 'p-3 rounded-xl border text-xs flex items-center justify-between bg-amber-500/10 border-amber-500/20 text-amber-300';
            openSerpStatusIcon.innerText = 'schedule';
            openSerpStatusIcon.className = 'material-symbols-outlined text-[18px] text-amber-400';
            openSerpStatusText.innerText = `Google search temporarily unavailable. Retry available in ${formatCooldownTime(remaining)}.`;
            openSerpStatusBanner.classList.remove('hidden');
        }

        openSerpCooldownTimer = setInterval(() => {
            remaining -= 1;
            if (remaining <= 0) {
                clearInterval(openSerpCooldownTimer);
                openSerpCooldownTimer = null;
                renderCooldownExpiredBanner();
            } else if (openSerpStatusText) {
                openSerpStatusText.innerText = `Google search temporarily unavailable. Retry available in ${formatCooldownTime(remaining)}.`;
            }
        }, 1000);
    }

    function renderCooldownExpiredBanner() {
        if (!openSerpStatusBanner) return;
        openSerpStatusBanner.className = 'p-3 rounded-xl border text-xs flex items-center justify-between bg-surface-container-low border-outline/20 text-on-surface';
        openSerpStatusIcon.innerText = 'check_circle';
        openSerpStatusIcon.className = 'material-symbols-outlined text-[18px] text-primary';
        openSerpStatusText.innerText = 'Cooldown expired. Google public discovery is ready for a fresh search.';
    }

    if (btnPublicSearchDiscovery) {
        btnPublicSearchDiscovery.addEventListener('click', async (e) => {
            e.preventDefault();
            if (isExecutingSearch) return;

            if (!currentSearchPlan || !currentSearchPlan.queries || currentSearchPlan.queries.length === 0) {
                alert('Please wait for the search plan to finish generating, or click Regenerate.');
                return;
            }

            const federatedEngineGrid = document.getElementById('federated-engine-grid');
            const btnStopDiscovery = document.getElementById('btn-stop-discovery');
            let progressPollInterval = null;

            if (btnStopDiscovery) {
                btnStopDiscovery.onclick = async () => {
                    btnStopDiscovery.disabled = true;
                    btnStopDiscovery.innerHTML = `<span class="material-symbols-outlined text-[16px] animate-spin">progress_activity</span><span>Stopping...</span>`;
                    try {
                        await fetch('/api/gtm/federated/stop', {
                            method: 'POST',
                            headers: { 'X-CSRFToken': getCsrfToken(), 'Accept': 'application/json' }
                        });
                        openSerpStatusText.innerText = 'Stopping discovery: finishing active query...';
                    } catch (e) {
                        console.error('Stop request failed', e);
                    }
                };
            }

            // 1. Check local OpenSERP health status
            if (openSerpStatusBanner) {
                openSerpStatusBanner.className = 'p-3 rounded-xl border text-xs flex items-center justify-between bg-surface-container-low border-outline/20 text-on-surface';
                openSerpStatusIcon.innerText = 'progress_activity';
                openSerpStatusIcon.className = 'material-symbols-outlined text-[18px] text-primary animate-spin';
                openSerpStatusText.innerText = 'Checking local discovery providers...';
                openSerpStatusBanner.classList.remove('hidden');
            }

            if (federatedEngineGrid) {
                federatedEngineGrid.classList.remove('hidden');
            }

            let openSerpAvailable = true;
            try {
                const statusRes = await fetch('/api/gtm/openserp/status', {
                    headers: { 'Accept': 'application/json' }
                });
                const statusData = await statusRes.json();
                openSerpAvailable = statusData.available;

                if (!openSerpAvailable) {
                    // Mark OpenSERP engines (Google, Bing, Yandex) as UNAVAILABLE in grid
                    ['google', 'bing', 'yandex'].forEach(eng => {
                        const pill = document.querySelector(`#badge-engine-${eng} .engine-status-pill`);
                        if (pill) {
                            pill.innerText = 'OFFLINE';
                            pill.className = 'engine-status-pill text-[10px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 font-mono';
                        }
                    });
                    openSerpStatusText.innerText = 'OpenSERP (port 7000) offline. Running DuckDuckGo only...';
                }
            } catch (err) {
                openSerpAvailable = false;
            }

            // 2. Execute federated discovery across queries (DuckDuckGo operates even if OpenSERP is offline)
            if (openSerpCooldownTimer) { clearInterval(openSerpCooldownTimer); openSerpCooldownTimer = null; }
            isExecutingSearch = true;
            btnPublicSearchDiscovery.disabled = true;
            if (btnStopDiscovery) btnStopDiscovery.classList.remove('hidden');

            const currentSessionId = 'fed_' + Date.now();
            const origPublicBtnText = btnPublicSearchDiscovery.innerHTML;
            btnPublicSearchDiscovery.innerHTML = `<span class="material-symbols-outlined text-[16px] animate-spin">progress_activity</span><span>Federated Searching...</span>`;

            openSerpStatusBanner.className = 'p-3 rounded-xl border text-xs flex items-center justify-between bg-primary/10 border-primary/20 text-on-surface';
            openSerpStatusIcon.innerText = 'travel_explore';
            openSerpStatusIcon.className = 'material-symbols-outlined text-[18px] text-primary animate-spin';
            const enginesNote = openSerpAvailable ? 'Google, Bing, DDG, Yandex' : 'DuckDuckGo (OpenSERP offline)';
            openSerpStatusText.innerText = `Executing federated discovery across ${currentSearchPlan.queries.length} queries (${enginesNote})...`;

            // Update active engine badges to SEARCHING
            const activeEngines = openSerpAvailable ? ['google', 'bing', 'duckduckgo', 'yandex'] : ['duckduckgo'];
            activeEngines.forEach(eng => {
                const pill = document.querySelector(`#badge-engine-${eng} .engine-status-pill`);
                if (pill) {
                    pill.innerText = 'SEARCHING';
                    pill.className = 'engine-status-pill text-[10px] px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400 font-mono font-semibold';
                }
            });

            // Poll live progress every 1.5 seconds for this specific session
            progressPollInterval = setInterval(async () => {
                try {
                    const pRes = await fetch(`/api/gtm/federated/progress?session_id=${encodeURIComponent(currentSessionId)}`, { headers: { 'Accept': 'application/json' } });
                    const pData = await pRes.json();
                    if (pData.success && pData.state) {
                        const st = pData.state;
                        if (st.current_query_index) {
                            openSerpStatusText.innerText = `Query ${st.current_query_index}/${st.total_queries}: ${st.current_provider ? '[' + st.current_provider + '] ' : ''}${st.prospects_count || 0} unique prospects collected`;
                        }
                        if (st.provider_telemetry) {
                            Object.keys(st.provider_telemetry).forEach(engKey => {
                                const pill = document.querySelector(`#badge-engine-${engKey} .engine-status-pill`);
                                if (pill) {
                                    const engStat = st.provider_telemetry[engKey].status || 'UNKNOWN';
                                    pill.innerText = engStat;
                                    if (engStat === 'SUCCESS') {
                                        pill.className = 'engine-status-pill text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 font-mono font-semibold';
                                    } else if (engStat === 'CAPTCHA_DETECTED' || engStat === 'RATE_LIMITED' || engStat === 'BOT_CHALLENGE') {
                                        pill.className = 'engine-status-pill text-[10px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 font-mono font-semibold';
                                    } else if (engStat === 'SEARCHING') {
                                        pill.className = 'engine-status-pill text-[10px] px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400 font-mono font-semibold';
                                    }
                                }
                            });
                        }
                        if (st.latest_candidates && st.latest_candidates.length > 0) {
                            appendDiscoveredProspects(st.latest_candidates, 'federated_live', 'Live Multi-Engine');
                        }
                    }
                } catch (pe) {
                    // Suppress background poll errors
                }
            }, 1500);

            try {
                const discoverRes = await fetch('/api/gtm/openserp/discover', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: JSON.stringify({
                        queries: currentSearchPlan.queries,
                        limit: 20,
                        session_id: currentSessionId
                    })
                });

                const discoverData = await discoverRes.json();
                if (progressPollInterval) { clearInterval(progressPollInterval); progressPollInterval = null; }
                isExecutingSearch = false;
                btnPublicSearchDiscovery.disabled = false;
                btnPublicSearchDiscovery.innerHTML = origPublicBtnText;
                if (btnStopDiscovery) {
                    btnStopDiscovery.classList.add('hidden');
                    btnStopDiscovery.disabled = false;
                    btnStopDiscovery.innerHTML = `<span class="material-symbols-outlined text-[16px] text-rose-400">stop_circle</span><span>Stop Discovery</span>`;
                }

                // Update provider badges from telemetry
                const telem = discoverData.provider_telemetry || {};
                Object.keys(telem).forEach(engKey => {
                    const pill = document.querySelector(`#badge-engine-${engKey} .engine-status-pill`);
                    if (pill) {
                        const engStat = telem[engKey].status || 'UNKNOWN';
                        pill.innerText = engStat;
                        if (engStat === 'SUCCESS') {
                            pill.className = 'engine-status-pill text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 font-mono font-semibold';
                        } else if (engStat === 'CAPTCHA_DETECTED' || engStat === 'RATE_LIMITED') {
                            pill.className = 'engine-status-pill text-[10px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 font-mono font-semibold';
                        } else if (engStat === 'EMPTY_RESPONSE') {
                            pill.className = 'engine-status-pill text-[10px] px-1.5 py-0.5 rounded bg-surface-container text-on-surface-variant font-mono';
                        } else {
                            pill.className = 'engine-status-pill text-[10px] px-1.5 py-0.5 rounded bg-rose-500/10 text-rose-400 font-mono';
                        }
                    }
                });

                if (discoverData.count > 0) {
                    openSerpStatusBanner.className = 'p-3 rounded-xl border text-xs flex items-center justify-between bg-emerald-500/10 border-emerald-500/20 text-emerald-300';
                    openSerpStatusIcon.innerText = 'check_circle';
                    openSerpStatusIcon.className = 'material-symbols-outlined text-[18px] text-emerald-400';
                    openSerpStatusText.innerText = `Discovered ${discoverData.count} unique prospects (${discoverData.duplicates_count || 0} duplicates merged across engines).`;
                    
                    // Route to discoveredProspects table
                    appendDiscoveredProspects(discoverData.results, 'federated_public', 'Multi-Engine Public Index');
                } else {
                    openSerpStatusBanner.className = 'p-3 rounded-xl border text-xs flex items-center justify-between bg-surface-container-low border-outline/20 text-on-surface-variant';
                    openSerpStatusIcon.innerText = 'search_off';
                    openSerpStatusIcon.className = 'material-symbols-outlined text-[18px] text-on-surface-variant';
                    openSerpStatusText.innerText = discoverData.message || 'No public profiles found across enabled search providers.';
                }
            } catch (err) {
                if (progressPollInterval) { clearInterval(progressPollInterval); progressPollInterval = null; }
                isExecutingSearch = false;
                btnPublicSearchDiscovery.disabled = false;
                if (btnStopDiscovery) {
                    btnStopDiscovery.classList.add('hidden');
                    btnStopDiscovery.disabled = false;
                    btnStopDiscovery.innerHTML = `<span class="material-symbols-outlined text-[16px] text-rose-400">stop_circle</span><span>Stop Discovery</span>`;
                }
                if (openSerpStatusBanner) {
                    openSerpStatusBanner.className = 'p-3 rounded-xl border text-xs flex items-center justify-between bg-rose-500/10 border-rose-500/20 text-rose-300';
                    openSerpStatusIcon.innerText = 'error';
                    openSerpStatusIcon.className = 'material-symbols-outlined text-[18px] text-rose-400';
                    openSerpStatusText.innerText = `Error contacting discovery API: ${err.message}`;
                }
            }
        });
    }

    function executeLinkedInSearch(queryId, queryText, searchUrl, buttonEl) {
        if (isExecutingSearch) return;
        isExecutingSearch = true;

        const originalText = buttonEl.innerHTML;
        buttonEl.disabled = true;
        buttonEl.innerHTML = `<span class="material-symbols-outlined text-[16px] animate-spin">progress_activity</span><span>Searching...</span>`;

        discoveryStatusTitle.innerText = `Searching LinkedIn for: "${queryText}"`;
        discoveryStatusDesc.innerText = 'The extension is navigating your authenticated LinkedIn tab and reading visible results.';
        if (discoverySpinner) discoverySpinner.classList.remove('hidden');

        const reqId = 'search_' + Date.now();
        console.log(`[GTM Search] Dispatched search request ${reqId} for query ${queryId}`);

        let timeoutTimer = null;

        const responseHandler = (event) => {
            if (event.source !== window || !event.data || typeof event.data !== 'object') return;
            if (event.data.type === 'FAMEWEB_EXT_SEARCH_RESPONSE' && event.data.requestId === reqId) {
                if (timeoutTimer) clearTimeout(timeoutTimer);
                window.removeEventListener('message', responseHandler);
                isExecutingSearch = false;
                buttonEl.disabled = false;
                buttonEl.innerHTML = originalText;
                if (discoverySpinner) discoverySpinner.classList.add('hidden');

                const response = event.data;
                console.log(`[GTM Search] Received response for ${reqId}:`, response);

                const unverifiedSignals = response.unverified_signals || [];
                if (unverifiedSignals.length > 0) {
                    appendUnverifiedMarketSignals(unverifiedSignals, queryId, queryText);
                }

                if (!response.success || (response.count === 0 && (!response.results || response.results.length === 0))) {
                    const status = response.status || response.error || 'ZERO_RESULTS';
                    const diag = response.diagnostic || {};
                    const diagTelem = diag.telemetry || {};
                    console.warn(`[GTM Search Diagnostic] status: ${status}`, {
                        tabId: response.tabId,
                        tabUrl: response.tabUrl,
                        tabTitle: response.tabTitle,
                        navigationStatus: response.navigationStatus,
                        diagnostic: diag
                    });

                    if (status === 'WRONG_TAB') {
                        discoveryStatusTitle.innerText = 'Wrong tab navigated';
                        discoveryStatusDesc.innerText = `Extension navigated tab (${response.tabTitle || 'Unknown'}). Please ensure your LinkedIn tab is active.`;
                    } else if (status === 'LOGIN_REQUIRED' || status === 'NOT_LOGGED_IN' || status === 'SESSION_EXPIRED') {
                        discoveryStatusTitle.innerText = 'LinkedIn login required';
                        discoveryStatusDesc.innerText = 'Please sign in to LinkedIn in your browser tab, then retry search.';
                    } else if (status === 'CHECKPOINT_DETECTED' || status === 'CHALLENGE_DETECTED') {
                        discoveryStatusTitle.innerText = 'Security verification checkpoint';
                        discoveryStatusDesc.innerText = 'LinkedIn requires interactive verification in your LinkedIn tab. Please complete it and retry.';
                    } else if (status === 'SEARCH_PAGE_NOT_LOADED') {
                        discoveryStatusTitle.innerText = 'Search page not loaded';
                        discoveryStatusDesc.innerText = `Current page URL is ${diagTelem.pathname || response.tabUrl || 'not a search page'}. Please wait for search navigation.`;
                    } else if (status === 'SEARCH_RESULTS_NOT_RENDERED') {
                        discoveryStatusTitle.innerText = 'Search results did not render';
                        discoveryStatusDesc.innerText = `LinkedIn search loaded (body: ${diagTelem.bodyTextLength || 0} chars) but cards were not rendered within the timeout.`;
                    } else if (status === 'RESULTS_PRESENT_SELECTOR_MISMATCH') {
                        discoveryStatusTitle.innerText = 'DOM Selector mismatch detected';
                        discoveryStatusDesc.innerText = `Found ${diagTelem.counts?.all_in_anchors || 0} profile links on page, but card containers did not match selectors. Inspecting DOM telemetry.`;
                    } else if (status === 'RESULTS_PRESENT_BUT_EXTRACTION_FAILED') {
                        discoveryStatusTitle.innerText = 'Card extraction failed';
                        discoveryStatusDesc.innerText = `Found ${diag.raw_items_found || 0} candidate cards, but failed to extract valid name/profile URLs.`;
                    } else if (status === 'ANONYMOUS_OUT_OF_NETWORK_RESULTS') {
                        const anonCount = diag.anonymous_cards_count || response.anonymous_count || unverifiedSignals.length || 'several';
                        const titleText = 'LinkedIn hid the identities of the search results.';
                        const descText = `LinkedIn displayed ${anonCount} results, but their individual identities are unavailable. FameWeb captured their visible professional details in the Market Intelligence section below.`;

                        // 1. Update top status card in modal
                        discoveryStatusTitle.innerText = titleText;
                        discoveryStatusDesc.innerText = descText;

                        // 2. Render notice in the verified-prospects review area if empty
                        if (discoveryResultsSection && discoveryResultsBody && discoveredProspects.length === 0) {
                            discoveryResultsSection.classList.remove('hidden');
                            if (discoveryResultsSummary) {
                                discoveryResultsSummary.innerText = `0 verified prospects imported (${anonCount} masked market signals detected)`;
                            }
                            discoveryResultsBody.innerHTML = `
                                <tr>
                                    <td colspan="5" class="py-8 px-4 text-center">
                                        <div class="flex flex-col items-center justify-center gap-2 max-w-lg mx-auto">
                                            <span class="material-symbols-outlined text-amber-400 text-[36px]">visibility_off</span>
                                            <div class="font-label-md text-label-md font-bold text-on-surface">
                                                ${escapeHtml(titleText)}
                                            </div>
                                            <p class="font-body-sm text-body-sm text-on-surface-variant leading-relaxed">
                                                ${escapeHtml(descText)}
                                            </p>
                                            <div class="mt-2 text-xs text-on-surface-variant/80 bg-surface-container-low px-3 py-1.5 rounded-lg border border-outline/10">
                                                Zero leads imported &bull; Safe ICP compliance preserved &bull; Zero credits billed
                                            </div>
                                        </div>
                                    </td>
                                </tr>
                            `;
                            updateProceedButton();
                        }
                    } else if (status === 'VERIFIED_EMPTY_RESULTS' || status === 'NO_MATCHING_PROSPECTS') {
                        discoveryStatusTitle.innerText = 'Verified zero matching prospects';
                        discoveryStatusDesc.innerText = `LinkedIn confirmed zero matching results for "${queryText}". Try a broader query title or keywords.`;
                    } else {
                        discoveryStatusTitle.innerText = `Extraction status: ${status}`;
                        discoveryStatusDesc.innerText = response.message || `No visible prospects found for "${queryText}".`;
                    }
                    return;
                }

                const newResults = response.results || [];
                appendDiscoveredProspects(newResults, queryId, queryText);
            }
        };

        window.addEventListener('message', responseHandler);

        // Send request to extension bridge
        window.postMessage({
            type: 'FAMEWEB_EXT_SEARCH_REQUEST',
            requestId: reqId,
            searchUrl: searchUrl,
            queryContext: {
                queryId: queryId,
                queryText: queryText
            }
        }, '*');

        timeoutTimer = setTimeout(() => {
            window.removeEventListener('message', responseHandler);
            isExecutingSearch = false;
            buttonEl.disabled = false;
            buttonEl.innerHTML = originalText;
            if (discoverySpinner) discoverySpinner.classList.add('hidden');
            discoveryStatusTitle.innerText = 'Search timed out';
            discoveryStatusDesc.innerText = 'Extension did not respond in time. Please check your open LinkedIn tab.';
        }, 25000);
    }

    function appendUnverifiedMarketSignals(newSignals, queryId, queryText) {
        if (!newSignals || newSignals.length === 0) return;

        let addedCount = 0;
        newSignals.forEach((sig) => {
            const h = (sig.headline || '').trim();
            const l = (sig.location || '').trim();
            const exp = (sig.experience_snippet || '').trim();
            if (!h && !l && !exp) return;

            // Deduplicate across signals by headline + location
            const dedupeKey = `${h.toLowerCase()}|${l.toLowerCase()}|${exp.toLowerCase()}`;
            const existing = unverifiedMarketSignals.some(s => `${(s.headline || '').toLowerCase()}|${(s.location || '').toLowerCase()}|${(s.experience_snippet || '').toLowerCase()}` === dedupeKey);
            if (!existing) {
                unverifiedMarketSignals.push({
                    headline: h || '-',
                    location: l || '-',
                    experience_snippet: exp || '-',
                    company_mentions: Array.isArray(sig.company_mentions) ? sig.company_mentions : [],
                    source_query: queryText || sig.source_query || queryId
                });
                addedCount++;
            }
        });

        renderMarketIntelligenceSection();
    }

    function renderMarketIntelligenceSection() {
        if (!discoveryMarketIntelSection) return;

        if (unverifiedMarketSignals.length === 0) {
            discoveryMarketIntelSection.classList.add('hidden');
            return;
        }

        discoveryMarketIntelSection.classList.remove('hidden');
        if (marketSignalsBadge) {
            marketSignalsBadge.innerText = `${unverifiedMarketSignals.length} Market Signals`;
        }

        // 1. Title frequency aggregation
        const titleCounts = {};
        unverifiedMarketSignals.forEach(s => {
            if (!s.headline || s.headline === '-') return;
            // Clean headline of noise and pipe separators to find primary role
            const primaryRole = s.headline.split(/[|·•\n]/)[0].trim();
            if (primaryRole && primaryRole.length > 2 && primaryRole.length < 50) {
                const norm = primaryRole.toLowerCase();
                titleCounts[norm] = titleCounts[norm] || { label: primaryRole, count: 0 };
                titleCounts[norm].count++;
            }
        });
        const sortedTitles = Object.values(titleCounts).sort((a, b) => b.count - a.count).slice(0, 4);

        if (intelTopTitles) {
            if (sortedTitles.length === 0) {
                intelTopTitles.innerHTML = `<span class="text-on-surface-variant/70">No distinct titles</span>`;
            } else {
                intelTopTitles.innerHTML = sortedTitles.map(t => `
                    <div class="flex items-center justify-between">
                        <span class="truncate max-w-[150px] font-medium text-on-surface" title="${escapeHtml(t.label)}">${escapeHtml(t.label)}</span>
                        <span class="font-code-sm text-[10px] px-1.5 py-0.2 rounded bg-surface-container font-semibold">${t.count}</span>
                    </div>
                `).join('');
            }
        }

        // 2. Location frequency aggregation
        const locationCounts = {};
        unverifiedMarketSignals.forEach(s => {
            if (!s.location || s.location === '-') return;
            const norm = s.location.trim().toLowerCase();
            locationCounts[norm] = locationCounts[norm] || { label: s.location.trim(), count: 0 };
            locationCounts[norm].count++;
        });
        const sortedLocations = Object.values(locationCounts).sort((a, b) => b.count - a.count).slice(0, 4);

        if (intelTopLocations) {
            if (sortedLocations.length === 0) {
                intelTopLocations.innerHTML = `<span class="text-on-surface-variant/70">No distinct locations</span>`;
            } else {
                intelTopLocations.innerHTML = sortedLocations.map(l => `
                    <div class="flex items-center justify-between">
                        <span class="truncate max-w-[150px] font-medium text-on-surface" title="${escapeHtml(l.label)}">${escapeHtml(l.label)}</span>
                        <span class="font-code-sm text-[10px] px-1.5 py-0.2 rounded bg-surface-container font-semibold">${l.count}</span>
                    </div>
                `).join('');
            }
        }

        // 3. Company mentions aggregation
        const companyCounts = {};
        unverifiedMarketSignals.forEach(s => {
            (s.company_mentions || []).forEach(comp => {
                if (!comp || comp.length < 2) return;
                const norm = comp.trim().toLowerCase();
                companyCounts[norm] = companyCounts[norm] || { label: comp.trim(), count: 0 };
                companyCounts[norm].count++;
            });
        });
        const sortedCompanies = Object.values(companyCounts).sort((a, b) => b.count - a.count).slice(0, 4);

        if (intelTopCompanies) {
            if (sortedCompanies.length === 0) {
                intelTopCompanies.innerHTML = `<span class="text-on-surface-variant/70">None explicitly named</span>`;
            } else {
                intelTopCompanies.innerHTML = sortedCompanies.map(c => `
                    <div class="flex items-center justify-between">
                        <span class="truncate max-w-[150px] font-medium text-on-surface" title="${escapeHtml(c.label)}">${escapeHtml(c.label)}</span>
                        <span class="font-code-sm text-[10px] px-1.5 py-0.2 rounded bg-surface-container font-semibold">${c.count}</span>
                    </div>
                `).join('');
            }
        }

        // 4. Representative Snippets
        if (intelSampleSnippets) {
            intelSampleSnippets.innerHTML = unverifiedMarketSignals.slice(0, 5).map(sig => `
                <div class="p-2 rounded bg-surface-container-lowest border border-outline/10 text-[11px] flex flex-col gap-0.5">
                    <div class="font-semibold text-on-surface flex items-center justify-between">
                        <span class="truncate max-w-[320px]">${escapeHtml(sig.headline)}</span>
                        <span class="text-[10px] text-on-surface-variant font-normal shrink-0">${escapeHtml(sig.location)}</span>
                    </div>
                    ${sig.experience_snippet && sig.experience_snippet !== '-' ? `
                        <div class="text-[10px] text-on-surface-variant/90 italic truncate">${escapeHtml(sig.experience_snippet)}</div>
                    ` : ''}
                </div>
            `).join('');
        }
    }

    function appendDiscoveredProspects(newItems, queryId, queryText) {
        if (!newItems || newItems.length === 0) {
            discoveryStatusTitle.innerText = 'Zero visible results returned';
            discoveryStatusDesc.innerText = `LinkedIn search for "${queryText}" returned 0 visible profiles. Try another query.`;
            return;
        }

        // Deduplicate against already discovered prospects by normalized profile URL
        let addedCount = 0;
        newItems.forEach((item) => {
            const cleanUrl = (item.profile_url || '').split('?')[0].replace(/\/+$/, '');
            if (!cleanUrl) return;

            const existingIdx = discoveredProspects.findIndex(p => (p.profile_url || '').split('?')[0].replace(/\/+$/, '') === cleanUrl);
            if (existingIdx === -1) {
                discoveredProspects.push({
                    name: item.name || 'LinkedIn Prospect',
                    role: item.role || item.headline || '-',
                    headline: item.headline || item.role || '-',
                    company: item.company || '-',
                    location: item.location || '-',
                    connection_degree: item.connection_degree || 'Unknown',
                    profile_url: cleanUrl,
                    source_query_id: queryId,
                    source_query_text: queryText,
                    sources: Array.isArray(item.sources) ? [...item.sources] : (item.provider ? [item.provider] : []),
                    selected: false // User must intentionally select
                });
                addedCount++;
            } else {
                // Profile already exists: merge new sources without duplicating row
                const existing = discoveredProspects[existingIdx];
                if (Array.isArray(item.sources)) {
                    existing.sources = existing.sources || [];
                    item.sources.forEach(s => {
                        if (!existing.sources.includes(s)) existing.sources.push(s);
                    });
                }
                if ((!existing.company || existing.company === '-') && item.company && item.company !== '-') {
                    existing.company = item.company;
                }
                if ((!existing.location || existing.location === '-') && item.location && item.location !== '-') {
                    existing.location = item.location;
                }
            }
        });

        if (addedCount > 0) {
            discoveryStatusTitle.innerText = `Discovered ${newItems.length} prospects (${addedCount} new)`;
            discoveryStatusDesc.innerText = 'Select the prospects you want to review and qualify against your ICP.';
            renderDiscoveredProspectsTable();
        }
    }

    function renderDiscoveredProspectsTable() {
        if (!discoveryResultsBody || !discoveryResultsSection) return;
        discoveryResultsSection.classList.remove('hidden');

        discoveryResultsSummary.innerText = `${discoveredProspects.length} total prospects discovered across queries`;
        discoveryResultsBody.innerHTML = '';

        if (discoveredProspects.length === 0) {
            discoveryResultsBody.innerHTML = `<tr><td colspan="5" class="py-6 text-center text-sm text-on-surface-variant">No prospects discovered yet. Run a query above.</td></tr>`;
            updateProceedButton();
            return;
        }

        discoveredProspects.forEach((p, index) => {
            const tr = document.createElement('tr');
            tr.className = 'hover:bg-surface-container-low transition-colors text-sm';
            const degreeBadgeClass = p.connection_degree === '1st' 
                ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' 
                : (p.connection_degree === '2nd' 
                    ? 'bg-primary/10 text-primary border border-primary/20' 
                    : (p.connection_degree === '3rd+' 
                        ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' 
                        : 'bg-surface-container text-on-surface-variant/70 border border-outline/10'));

            tr.innerHTML = `
                <td class="py-2.5 px-3 text-center">
                    <input type="checkbox" class="prospect-select-checkbox rounded text-primary focus:ring-primary h-4 w-4 cursor-pointer" data-index="${index}" ${p.selected ? 'checked' : ''}/>
                </td>
                <td class="py-2.5 px-3">
                    <div class="font-bold text-on-surface">${escapeHtml(p.name)}</div>
                    <div class="text-xs text-on-surface-variant truncate max-w-xs" title="${escapeHtml(p.headline)}">${escapeHtml(p.headline)}</div>
                </td>
                <td class="py-2.5 px-3 text-center">
                    <span class="inline-block px-2 py-0.5 rounded text-[10px] font-semibold ${degreeBadgeClass}">
                        ${escapeHtml(p.connection_degree || 'Unknown')}
                    </span>
                </td>
                <td class="py-2.5 px-3 text-on-surface-variant font-medium text-xs">
                    ${escapeHtml(p.company || '-')}
                </td>
                <td class="py-2.5 px-3 text-on-surface-variant text-xs">
                    ${escapeHtml(p.location || '-')}
                </td>
                <td class="py-2.5 px-3 text-right">
                    <a href="${escapeHtml(p.profile_url)}" target="_blank" rel="noopener" class="text-xs text-primary hover:underline inline-flex items-center gap-0.5">
                        <span>Profile</span>
                        <span class="material-symbols-outlined text-[13px]">open_in_new</span>
                    </a>
                </td>
            `;
            discoveryResultsBody.appendChild(tr);
        });

        // Bind checkboxes
        discoveryResultsBody.querySelectorAll('.prospect-select-checkbox').forEach((cb) => {
            cb.addEventListener('change', (e) => {
                const idx = parseInt(cb.getAttribute('data-index'), 10);
                if (discoveredProspects[idx]) {
                    discoveredProspects[idx].selected = cb.checked;
                    updateProceedButton();
                }
            });
        });

        updateProceedButton();
    }

    function updateProceedButton() {
        if (!btnProceedReview || !btnProceedReviewText) return;
        const selectedCount = discoveredProspects.filter(p => p.selected).length;
        btnProceedReviewText.innerText = `Review Selected Leads (${selectedCount})`;
        if (selectedCount > 0) {
            btnProceedReview.classList.remove('hidden');
        } else {
            btnProceedReview.classList.add('hidden');
        }
    }

    if (btnSelectAllProspects) {
        btnSelectAllProspects.addEventListener('click', () => {
            discoveredProspects.forEach(p => p.selected = true);
            renderDiscoveredProspectsTable();
        });
    }

    if (btnDeselectAllProspects) {
        btnDeselectAllProspects.addEventListener('click', () => {
            discoveredProspects.forEach(p => p.selected = false);
            renderDiscoveredProspectsTable();
        });
    }

    if (btnProceedReview) {
        btnProceedReview.addEventListener('click', async () => {
            const selectedLeads = discoveredProspects.filter(p => p.selected);
            if (selectedLeads.length === 0) {
                alert('Please select at least one prospect to qualify.');
                return;
            }

            const originalBtnHtml = btnProceedReview.innerHTML;
            btnProceedReview.disabled = true;
            btnProceedReview.innerHTML = `
                <span class="material-symbols-outlined text-[18px] animate-spin">progress_activity</span>
                <span>Qualifying with Gemini...</span>
            `;

            if (discoverySpinner) discoverySpinner.classList.remove('hidden');
            if (discoveryStatusTitle) discoveryStatusTitle.innerText = `Evaluating ${selectedLeads.length} leads against ICP...`;
            if (discoveryStatusDesc) discoveryStatusDesc.innerText = 'Gemini is analyzing roles, intent signals, and company fit.';

            try {
                // Determine source query context from the first selected lead, or fallback to current search plan
                const firstSelected = selectedLeads[0];
                const queryId = firstSelected.source_query_id || 'q1';
                const queryText = firstSelected.source_query_text || 'LinkedIn Search Discovery';

                const response = await fetch('/api/gtm/import-search-results', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: JSON.stringify({
                        query_id: queryId,
                        query: queryText,
                        candidates: selectedLeads
                    })
                });

                const data = await response.json();

                if (!response.ok || !data.success) {
                    const err = data.message || data.error || 'Failed to qualify leads';
                    alert(`Qualification error: ${err}`);
                    if (discoveryStatusTitle) discoveryStatusTitle.innerText = 'Qualification Error';
                    if (discoveryStatusDesc) discoveryStatusDesc.innerText = err;
                    return;
                }

                // Show qualification summary container
                if (discoveryQualSummary) {
                    discoveryQualSummary.classList.remove('hidden');
                    if (qualBadgeTotal) qualBadgeTotal.innerText = `${data.processed || selectedLeads.length} Processed`;
                    if (qualStatQualified) qualStatQualified.innerText = data.qualified_count || 0;
                    if (qualStatPersisted) qualStatPersisted.innerText = data.persisted_count || 0;
                    if (qualStatDuplicates) qualStatDuplicates.innerText = (data.duplicates || []).length;
                    if (qualStatBilled) qualStatBilled.innerText = data.billed_leads || 0;
                    if (qualFeedbackText) {
                        qualFeedbackText.innerText = data.message || `Evaluation finished: ${data.persisted_count || 0} opportunities added to your pipeline.`;
                    }
                }

                if (discoveryStatusTitle) discoveryStatusTitle.innerText = 'Qualification Complete';
                if (discoveryStatusDesc) discoveryStatusDesc.innerText = `${data.persisted_count || 0} leads saved to your GTM opportunities pipeline.`;

                // Remove the qualified leads from the active discovered list or uncheck them
                discoveredProspects = discoveredProspects.filter(p => !p.selected);
                renderDiscoveredProspectsTable();

                // Refresh opportunities table in the background
                await loadOpportunities();

            } catch (err) {
                console.error('[GTM Lead Import] Network error:', err);
                alert(`Network error during lead qualification: ${err.message}`);
                if (discoveryStatusTitle) discoveryStatusTitle.innerText = 'Network Error';
                if (discoveryStatusDesc) discoveryStatusDesc.innerText = err.message;
            } finally {
                btnProceedReview.disabled = false;
                btnProceedReview.innerHTML = originalBtnHtml;
                if (discoverySpinner) discoverySpinner.classList.add('hidden');
                updateProceedButton();
            }
        });
    }

    // Initial Load
    loadGtmContext();
    loadOpportunities();
});
