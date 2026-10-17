document.addEventListener('DOMContentLoaded', () => {
    const btnGenerate = document.getElementById('generate-suggestions-btn');
    const toast = document.getElementById('toast-notification');
    const toastMessage = document.getElementById('toast-message');

    const getCsrfToken = () => document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';

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

    function showSessionExpiredNotice(message, originalGenerateBtnHtml) {
        let reconnectContainer = document.getElementById('session-reconnect-container');
        if (!reconnectContainer && btnGenerate && btnGenerate.parentNode) {
            reconnectContainer = document.createElement('div');
            reconnectContainer.id = 'session-reconnect-container';
            btnGenerate.parentNode.insertBefore(reconnectContainer, btnGenerate);
        }
        if (!reconnectContainer) return;

        reconnectContainer.className = 'flex flex-col gap-2 p-3 bg-amber-50 border border-amber-200 rounded-lg text-sm mb-2';
        reconnectContainer.innerHTML = `
            <div class="flex items-start gap-2 text-amber-900">
                <span class="material-symbols-outlined text-[18px] shrink-0 mt-0.5 text-amber-700">warning</span>
                <div class="flex-1 font-medium leading-snug">
                    ${message || 'LinkedIn session expired. Please reconnect your account to continue.'}
                </div>
            </div>
            <button id="reconnect-linkedin-btn" type="button" class="mt-1 w-full flex items-center justify-center gap-2 px-3 py-2 bg-[#0a66c2] hover:bg-[#004182] text-white rounded-md text-xs font-semibold transition-all shadow-sm cursor-pointer">
                <span class="material-symbols-outlined text-[16px]">sync</span>
                <span id="reconnect-btn-text">Reconnect LinkedIn</span>
            </button>
        `;
        reconnectContainer.classList.remove('hidden');

        const reconnectBtn = document.getElementById('reconnect-linkedin-btn');
        if (reconnectBtn) {
            reconnectBtn.addEventListener('click', async () => {
                const btnText = document.getElementById('reconnect-btn-text');
                reconnectBtn.disabled = true;
                reconnectBtn.classList.add('opacity-75', 'cursor-not-allowed');
                if (btnText) {
                    btnText.innerHTML = '<span class="inline-flex items-center gap-1.5"><span class="material-symbols-outlined text-[14px] animate-spin">refresh</span> Waiting for LinkedIn login...</span>';
                }

                try {
                    const res = await fetch('/api/auth/linkedin/reconnect', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': getCsrfToken()
                        }
                    });
                    const resData = await res.json();
                    if (res.ok && resData.success) {
                        showToast('LinkedIn reconnected successfully!');
                        reconnectContainer.className = 'flex flex-col gap-2 p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-sm mb-2';
                        reconnectContainer.innerHTML = `
                            <div class="flex items-center gap-2 text-emerald-800 font-medium">
                                <span class="material-symbols-outlined text-[18px] text-emerald-600">check_circle</span>
                                <span>LinkedIn reconnected! You can now analyze your profile.</span>
                            </div>
                        `;
                        setTimeout(() => {
                            reconnectContainer.classList.add('hidden');
                        }, 5000);
                    } else {
                        const failMsg = resData.message || resData.error || 'Reconnection failed. Please try again.';
                        showSessionExpiredNotice(failMsg, originalGenerateBtnHtml);
                    }
                } catch (netErr) {
                    showSessionExpiredNotice('Connection error during LinkedIn reconnect. Please try again.', originalGenerateBtnHtml);
                } finally {
                    if (btnGenerate && originalGenerateBtnHtml) {
                        btnGenerate.disabled = false;
                        btnGenerate.innerHTML = originalGenerateBtnHtml;
                    }
                }
            });
        }
    }

    if (btnGenerate) {
        btnGenerate.addEventListener('click', async () => {
            const original = btnGenerate.innerHTML;
            btnGenerate.innerHTML = '<span class="material-symbols-outlined text-[18px] animate-spin">refresh</span><span>Analyzing your profile...</span>';
            btnGenerate.disabled = true;

            // Hide any previous reconnect notice while retrying
            const existingNotice = document.getElementById('session-reconnect-container');
            if (existingNotice) existingNotice.classList.add('hidden');

            try {
                const res = await fetch('/api/optimize-profile', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: JSON.stringify({}) // Backend pulls data from DB
                });

                const data = await res.json();
                if (data.success) {
                    showToast('Analysis complete');
                    setTimeout(() => {
                        window.location.reload();
                    }, 1000);
                } else if (data.error === 'SESSION_EXPIRED' || data.error === 'SESSION_INVALID') {
                    showSessionExpiredNotice(data.message || 'LinkedIn session expired. Please reconnect.', original);
                    btnGenerate.disabled = false;
                    btnGenerate.innerHTML = original;
                } else {
                    const errMsg = data.message || data.error || 'Failed to analyze profile';
                    alert('Unable to analyze profile: ' + errMsg);
                    btnGenerate.disabled = false;
                    btnGenerate.innerHTML = original;
                }
            } catch (err) {
                alert('Unable to analyze profile: ' + err.message);
                btnGenerate.disabled = false;
                btnGenerate.innerHTML = original;
            }
        });
    }

    const exportBtn = document.getElementById('export-summary-btn');
    if (exportBtn) {
        exportBtn.addEventListener('click', () => {
            showToast('Generating executive brief summary...');
        });
    }
});
