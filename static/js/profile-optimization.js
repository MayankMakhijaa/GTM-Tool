document.addEventListener('DOMContentLoaded', async () => {
    const btnGenerate = document.getElementById('generate-suggestions-btn');
    const btnRefresh = document.getElementById('refresh-data-btn');
    const recHeadline = document.getElementById('rec-headline-text');
    const recAbout = document.getElementById('rec-about-text');
    const recExp = document.getElementById('rec-exp-text');
    
    // Toast notification elements
    const toast = document.getElementById('toast-notification');
    const toastMessage = document.getElementById('toast-message');
    
    // Settings Modal elements
    const settingsModal = document.getElementById('settings-modal');
    const closeSettingsBtn = document.getElementById('close-settings-modal');
    const cancelSettingsBtn = document.getElementById('cancel-settings-btn');
    const saveSettingsBtn = document.getElementById('save-settings-btn');
    const settingOptStatus = document.getElementById('setting-opt-status');
    const settingPriorityFilter = document.getElementById('setting-priority-filter');
    const settingAutosave = document.getElementById('setting-autosave');
    
    const getCsrfToken = () => document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
    
    let currentExtractedData = null;
    let savedSettings = {
        priority_filter: 'all',
        skill_ordering: ["Pipeline Velocity", "RevOps Architecture", "Outbound Intelligence"],
        auto_save: true
    };
    let appliedSuggestions = [];

    window.showToast = function(message) {
        if (!toast || !toastMessage) return alert(message);
        toastMessage.innerText = message;
        toast.classList.remove('translate-y-20', 'opacity-0', 'pointer-events-none');
        setTimeout(() => {
            toast.classList.add('translate-y-20', 'opacity-0', 'pointer-events-none');
        }, 3200);
    };

    window.copyToClipboard = function(elementId, btn) {
        const el = document.getElementById(elementId);
        if (!el) return;
        const textToCopy = el.innerText.replace(/^"|"$/g, '');
        navigator.clipboard.writeText(textToCopy).then(() => {
            showToast('Copied to clipboard');
            const originalContent = btn.innerHTML;
            btn.innerHTML = '<span class="material-symbols-outlined text-[16px] text-tertiary">done</span><span>Copied</span>';
            setTimeout(() => {
                btn.innerHTML = originalContent;
            }, 2000);
        }).catch(() => {
            showToast('Failed to copy');
        });
    };

    const markAppliedUI = (btn, message) => {
        if (!btn) return;
        btn.innerHTML = '<span class="material-symbols-outlined text-[16px]">check</span><span>Applied</span>';
        btn.classList.remove('bg-primary-container', 'hover:bg-secondary');
        btn.classList.add('bg-tertiary-container', 'text-on-tertiary');
        btn.disabled = true;
    };

    window.applyToDraft = async function(btn, message) {
        const original = btn.innerHTML;
        btn.innerHTML = '<span class="material-symbols-outlined text-[16px] animate-spin">refresh</span><span>Applying...</span>';
        
        try {
            const res = await fetch('/api/onboarding/optimization', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({
                    applied_suggestion: message,
                    optimization_status: 'ACCEPTED'
                })
            });
            const data = await res.json();
            if (res.ok && data.success) {
                markAppliedUI(btn, message);
                showToast(message || 'Applied to draft workspace');
                if (!appliedSuggestions.includes(message)) {
                    appliedSuggestions.push(message);
                }
            } else {
                throw new Error(data.message || 'Failed to persist application');
            }
        } catch (err) {
            console.error(err);
            btn.innerHTML = original;
            alert('Unable to apply suggestion: ' + err.message);
        }
    };

    // Load optimization settings on page load
    const loadOptimizationSettings = async () => {
        try {
            const res = await fetch('/api/onboarding/optimization');
            if (!res.ok) return;
            const data = await res.json();
            if (data.success) {
                appliedSuggestions = data.applied_suggestions || [];
                if (data.settings) {
                    savedSettings = { ...savedSettings, ...data.settings };
                }
                
                // Restore applied suggestion buttons
                const applyButtons = document.querySelectorAll('button[onclick*="applyToDraft"]');
                applyButtons.forEach(btn => {
                    const onclickAttr = btn.getAttribute('onclick') || '';
                    if (onclickAttr.includes('Headline updated in draft') && appliedSuggestions.includes('Headline updated in draft')) {
                        markAppliedUI(btn, 'Headline updated in draft');
                    } else if (onclickAttr.includes('Summary hook applied to draft') && appliedSuggestions.includes('Summary hook applied to draft')) {
                        markAppliedUI(btn, 'Summary hook applied to draft');
                    }
                });

                if (settingOptStatus && data.optimization_status) {
                    settingOptStatus.value = data.optimization_status;
                }
                if (settingPriorityFilter && savedSettings.priority_filter) {
                    settingPriorityFilter.value = savedSettings.priority_filter;
                }
                if (settingAutosave && typeof savedSettings.auto_save === 'boolean') {
                    settingAutosave.checked = savedSettings.auto_save;
                }
                
                // Apply active filter visual state
                applyPriorityFilter(savedSettings.priority_filter || 'all');
            }
        } catch (err) {
            console.error('Error loading optimization settings:', err);
        }
    };

    // Priority filter handling
    const filterButtons = document.querySelectorAll('.lg\\:col-span-8 .flex.items-center.gap-space-xs button');
    const suggestionCards = document.querySelectorAll('.lg\\:col-span-8 .flex.flex-col.gap-space-lg > .bg-surface-container-lowest');

    const applyPriorityFilter = (filterType) => {
        filterButtons.forEach(btn => {
            const txt = btn.textContent.trim().toLowerCase();
            if ((filterType === 'all' && txt.includes('all')) ||
                (filterType === 'high' && txt.includes('high impact')) ||
                (filterType === 'draft' && txt.includes('draft stage'))) {
                btn.className = 'px-3 py-1 bg-surface-container-high text-on-surface font-label-sm text-label-sm rounded-lg font-semibold';
            } else {
                btn.className = 'px-3 py-1 bg-surface-container-lowest text-on-surface-variant hover:text-on-surface font-label-sm text-label-sm rounded-lg';
            }
        });

        suggestionCards.forEach(card => {
            if (filterType === 'all') {
                card.style.display = 'flex';
            } else if (filterType === 'high') {
                const isHigh = card.querySelector('.bg-amber-100');
                card.style.display = isHigh ? 'flex' : 'none';
            } else if (filterType === 'draft') {
                const hasApplied = card.querySelector('button[disabled]') || card.textContent.includes('Applied');
                card.style.display = hasApplied ? 'flex' : 'none';
            }
        });
    };

    filterButtons.forEach(btn => {
        btn.addEventListener('click', async () => {
            const txt = btn.textContent.trim().toLowerCase();
            let filterType = 'all';
            if (txt.includes('high impact')) filterType = 'high';
            else if (txt.includes('draft stage')) filterType = 'draft';

            savedSettings.priority_filter = filterType;
            applyPriorityFilter(filterType);

            try {
                await fetch('/api/onboarding/optimization', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: JSON.stringify({ settings: savedSettings })
                });
            } catch (e) {
                console.error('Failed saving priority filter:', e);
            }
        });
    });

    if (btnRefresh) {
        btnRefresh.addEventListener('click', async () => {
            const url = prompt("Enter LinkedIn URL to analyze:");
            if (!url) return;
            
            const original = btnRefresh.innerHTML;
            btnRefresh.innerHTML = '<span class="material-symbols-outlined text-[18px] animate-spin">refresh</span><span>Syncing...</span>';
            btnRefresh.disabled = true;
            
            try {
                const res = await fetch('/api/extract-profile', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: JSON.stringify({ linkedin_url: url })
                });
                
                const data = await res.json();
                if (data.success) {
                    currentExtractedData = data.profile;
                    showToast('Profile sync complete');
                } else {
                    throw new Error(data.error || 'Failed to extract profile');
                }
            } catch (err) {
                alert(err.message);
            } finally {
                btnRefresh.disabled = false;
                btnRefresh.innerHTML = original;
            }
        });
    }

    if (btnGenerate) {
        btnGenerate.addEventListener('click', async () => {
            const original = btnGenerate.innerHTML;
            btnGenerate.innerHTML = '<span class="material-symbols-outlined text-[18px] animate-spin">refresh</span><span>Synthesizing ICP Data...</span>';
            btnGenerate.disabled = true;
            
            try {
                const res = await fetch('/api/optimize-profile', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: JSON.stringify({ 
                        profile_data: currentExtractedData || {},
                        icp_context: "Generate improvements for my profile based on my ICP."
                    })
                });
                
                const data = await res.json();
                if (data.success && data.optimization) {
                    if (recHeadline) recHeadline.textContent = '"' + data.optimization.headline + '"';
                    if (recAbout) recAbout.textContent = '"' + data.optimization.about + '"';
                    showToast('Generated fresh optimizations');
                } else {
                    throw new Error(data.error || 'Failed to optimize profile');
                }
            } catch (err) {
                alert(err.message);
            } finally {
                btnGenerate.disabled = false;
                btnGenerate.innerHTML = original;
            }
        });
    }

    const reorderBtn = document.getElementById('reorder-skills-btn');
    if (reorderBtn) {
        reorderBtn.addEventListener('click', async () => {
            try {
                await fetch('/api/onboarding/optimization', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: JSON.stringify({
                        settings: {
                            skill_ordering: ["Pipeline Velocity", "RevOps Architecture", "Outbound Intelligence"]
                        }
                    })
                });
                showToast('Skill priorities updated for GTM discoverability');
                reorderBtn.innerHTML = '<span class="material-symbols-outlined text-[16px] text-tertiary">check</span><span>Prioritized</span>';
            } catch (e) {
                alert('Unable to save skill ordering.');
            }
        });
    }

    const exportBtn = document.getElementById('export-summary-btn');
    if (exportBtn) {
        exportBtn.addEventListener('click', () => {
            showToast('Generating profile optimization brief (PDF)...');
        });
    }

    // Settings Modal behavior
    const openSettings = () => {
        if (settingsModal) {
            settingsModal.classList.remove('hidden');
        }
    };

    const closeSettings = () => {
        if (settingsModal) {
            settingsModal.classList.add('hidden');
        }
    };

    if (closeSettingsBtn) closeSettingsBtn.addEventListener('click', closeSettings);
    if (cancelSettingsBtn) cancelSettingsBtn.addEventListener('click', closeSettings);

    if (saveSettingsBtn) {
        saveSettingsBtn.addEventListener('click', async () => {
            const statusVal = settingOptStatus ? settingOptStatus.value : 'ACCEPTED';
            const filterVal = settingPriorityFilter ? settingPriorityFilter.value : 'all';
            const autosaveVal = settingAutosave ? settingAutosave.checked : true;

            savedSettings.priority_filter = filterVal;
            savedSettings.auto_save = autosaveVal;

            saveSettingsBtn.disabled = true;
            saveSettingsBtn.textContent = 'Saving...';

            try {
                const res = await fetch('/api/onboarding/optimization', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: JSON.stringify({
                        optimization_status: statusVal,
                        settings: savedSettings
                    })
                });

                const data = await res.json();
                if (res.ok && data.success) {
                    closeSettings();
                    applyPriorityFilter(filterVal);
                    showToast('Settings saved successfully!');
                } else {
                    throw new Error(data.message || 'Failed to save settings');
                }
            } catch (err) {
                alert('Error saving settings: ' + err.message);
            } finally {
                saveSettingsBtn.disabled = false;
                saveSettingsBtn.textContent = 'Save Settings';
            }
        });
    }

    // Connect Settings link in sidebar/header
    const settingsLinks = document.querySelectorAll('a[data-path="settings"]');
    settingsLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            openSettings();
        });
    });

    loadOptimizationSettings();
});

