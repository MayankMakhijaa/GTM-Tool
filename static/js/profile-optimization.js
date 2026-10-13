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

    window.showToast = function (message) {
        if (!toast || !toastMessage) return alert(message);
        toastMessage.innerText = message;
        toast.classList.remove('translate-y-20', 'opacity-0', 'pointer-events-none');
        setTimeout(() => {
            toast.classList.add('translate-y-20', 'opacity-0', 'pointer-events-none');
        }, 3200);
    };

    window.copyToClipboard = function (elementId, btn) {
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

    window.applyToDraft = function (btn, message) {
        const original = btn.innerHTML;
        btn.innerHTML = '<span class="material-symbols-outlined text-[16px] animate-spin">refresh</span><span>Applying...</span>';
        setTimeout(() => {
            btn.innerHTML = '<span class="material-symbols-outlined text-[16px]">check</span><span>Applied</span>';
            btn.classList.remove('bg-primary-container', 'hover:bg-secondary');
            btn.classList.add('bg-tertiary-container', 'text-on-tertiary');
            showToast(message || 'Applied to draft workspace');
        }, 800);
    };

    if (btnRefresh) {
        btnRefresh.addEventListener('click', async () => {
            const url = prompt("Enter LinkedIn URL to analyze:");
            if (!url) return;

            const original = btnRefresh.innerHTML;
            btnRefresh.innerHTML = '<span class="material-symbols-outlined text-[18px] animate-spin">refresh</span><span>Syncing...</span>';
            btnRefresh.disabled = true;

            try {
                // Since this uses SSE in the original implementation (/api/extract-profile-stream), 
                // we'll hit the fallback /api/extract-profile POST endpoint
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
                    // Data would be updated in the DOM here ideally
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
            btnGenerate.innerHTML = '<span class="material-symbols-outlined text-[18px] animate-spin">refresh</span><span>Analyzing your profile...</span>';
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
                        icp_context: "Generate improvements for my profile based on my ICP." // We pass dummy if needed
                    })
                });

                const data = await res.json();
                if (data.success) {
                    showToast('Analysis complete');
                    setTimeout(() => {
                        window.location.reload();
                    }, 1000);
                } else {
                    throw new Error(data.error || 'Failed to analyze profile');
                }
            } catch (err) {
                alert('Unable to analyze profile: ' + err.message);
                btnGenerate.disabled = false;
                btnGenerate.innerHTML = original;
            }
        });
    }

    const reorderBtn = document.getElementById('reorder-skills-btn');
    if (reorderBtn) {
        reorderBtn.addEventListener('click', () => {
            showToast('Skill priorities updated for GTM discoverability');
            reorderBtn.innerHTML = '<span class="material-symbols-outlined text-[16px] text-tertiary">check</span><span>Prioritized</span>';
        });
    }

    const exportBtn = document.getElementById('export-summary-btn');
    if (exportBtn) {
        exportBtn.addEventListener('click', () => {
            showToast('Generating profile optimization brief (PDF)...');
        });
    }
});
