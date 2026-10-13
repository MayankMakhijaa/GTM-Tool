// Onboarding Step 1 — LinkedIn Connection State Machine & Controller
document.addEventListener('DOMContentLoaded', () => {
    const connectBtn = document.getElementById('connect-linkedin-btn');
    const checkStatusBtn = document.getElementById('check-status-btn');
    const btnLabel = document.getElementById('btn-label');
    const btnContinue = document.getElementById('btn-continue');
    const statusBadge = document.getElementById('status-badge');
    const statusText = document.getElementById('status-text');
    const statusIcon = document.getElementById('status-icon');
    const statusHeadline = document.getElementById('status-headline');
    const statusDescription = document.getElementById('status-description');
    const statusMessageBox = document.getElementById('status-message-box');
    const connectingProgress = document.getElementById('connecting-progress');
    const progressText = document.getElementById('progress-text');
    const profileName = document.getElementById('profile-name');
    const profileSubtext = document.getElementById('profile-subtext');

    let isConnecting = false;
    let pollInterval = null;

    const getCsrfToken = () => document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';

    // State Machine Renderer
    function applyState(state, data = {}) {
        console.log(`[LinkedIn Onboarding] State transition: ${state}`, data);

        // Clear poll if terminal state reached
        if (state === 'CONNECTED' || state === 'ERROR' || state === 'DISCONNECTED') {
            if (pollInterval) {
                clearInterval(pollInterval);
                pollInterval = null;
            }
            isConnecting = false;
        }

        switch (state) {
            case 'DISCONNECTED':
                statusBadge.className = 'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-surface-container-high text-on-surface-variant';
                statusBadge.innerHTML = '<span class="w-2 h-2 rounded-full bg-outline"></span><span>Not Connected</span>';
                
                statusMessageBox.className = 'bg-surface-container-low rounded-xl p-4 sm:p-5 flex items-start gap-3.5 transition-all border border-transparent';
                statusIcon.textContent = 'info';
                statusIcon.className = 'material-symbols-outlined text-primary text-[22px] shrink-0 mt-0.5';
                statusHeadline.textContent = 'Authentication Instructions';
                statusDescription.textContent = 'Click "Connect LinkedIn" below. A browser window will open for you to log into your account. Fameweb will detect your session once you reach your feed, encrypt the cookies, and save them.';
                
                connectingProgress.classList.add('hidden');
                connectingProgress.classList.remove('flex');

                connectBtn.disabled = false;
                connectBtn.className = 'px-6 py-3.5 bg-[#0a66c2] hover:bg-[#004182] text-white text-sm font-semibold rounded-xl flex items-center justify-center gap-2.5 transition-all shadow-md active:scale-95 cursor-pointer';
                btnLabel.textContent = 'Connect LinkedIn';

                // Lock Continue button
                btnContinue.className = 'px-6 py-2.5 bg-surface-container-high text-outline text-sm font-semibold rounded-xl flex items-center gap-2 cursor-not-allowed opacity-60 pointer-events-none transition-all shadow-sm';
                break;

            case 'CONNECTING':
            case 'WAITING_FOR_LOGIN':
                isConnecting = true;
                statusBadge.className = 'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-primary-fixed text-primary animate-pulse';
                statusBadge.innerHTML = '<span class="w-2 h-2 rounded-full bg-primary animate-ping"></span><span>Connecting...</span>';

                statusMessageBox.className = 'bg-primary-fixed/20 rounded-xl p-4 sm:p-5 flex items-start gap-3.5 transition-all border border-primary/20';
                statusIcon.textContent = 'open_in_browser';
                statusIcon.className = 'material-symbols-outlined text-primary text-[22px] shrink-0 mt-0.5 animate-bounce';
                statusHeadline.textContent = 'Browser Window Open — Action Required';
                statusDescription.textContent = 'A dedicated browser window has opened. Please log in with your LinkedIn account and navigate to your home feed. Fameweb will automatically capture your session.';

                connectingProgress.classList.remove('hidden');
                connectingProgress.classList.add('flex');
                progressText.textContent = 'Waiting for LinkedIn login & feed navigation...';

                connectBtn.disabled = true;
                connectBtn.className = 'px-6 py-3.5 bg-surface-container-high text-outline text-sm font-semibold rounded-xl flex items-center justify-center gap-2.5 transition-all cursor-not-allowed opacity-75';
                btnLabel.textContent = 'Waiting for Login in Browser...';

                btnContinue.className = 'px-6 py-2.5 bg-surface-container-high text-outline text-sm font-semibold rounded-xl flex items-center gap-2 cursor-not-allowed opacity-60 pointer-events-none transition-all shadow-sm';
                break;

            case 'VALIDATING':
                statusBadge.className = 'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-tertiary-fixed text-tertiary';
                statusBadge.innerHTML = '<span class="material-symbols-outlined animate-spin text-[14px]">progress_activity</span><span>Validating Session...</span>';

                statusMessageBox.className = 'bg-tertiary-fixed/20 rounded-xl p-4 sm:p-5 flex items-start gap-3.5 transition-all';
                statusIcon.textContent = 'verified_user';
                statusIcon.className = 'material-symbols-outlined text-tertiary text-[22px] shrink-0 mt-0.5';
                statusHeadline.textContent = 'Encrypting & Validating Cookies';
                statusDescription.textContent = 'Extracting li_at and JSESSIONID, encrypting credentials via AES-256 Fernet, and verifying active session with LinkedIn Voyager REST API...';

                progressText.textContent = 'Validating and persisting encrypted session...';
                break;

            case 'CONNECTED':
                statusBadge.className = 'inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-semibold bg-tertiary-fixed text-tertiary border border-tertiary/20';
                statusBadge.innerHTML = '<span class="material-symbols-outlined text-[16px] text-tertiary">check_circle</span><span>Connected & Verified ✓</span>';

                statusMessageBox.className = 'bg-tertiary-fixed/25 rounded-xl p-4 sm:p-5 flex items-start gap-3.5 transition-all border border-tertiary/30';
                statusIcon.textContent = 'task_alt';
                statusIcon.className = 'material-symbols-outlined text-tertiary text-[22px] shrink-0 mt-0.5';
                statusHeadline.textContent = 'LinkedIn Connected Successfully';
                statusDescription.textContent = 'Your LinkedIn session is securely encrypted and validated. You are ready to proceed to company details and ICP configuration.';

                connectingProgress.classList.add('hidden');
                connectingProgress.classList.remove('flex');

                if (data.profile && data.profile.name) {
                    profileName.textContent = data.profile.name;
                    profileSubtext.textContent = data.profile.headline || 'Connected LinkedIn Account';
                }

                connectBtn.disabled = true;
                connectBtn.className = 'px-6 py-3.5 bg-surface-container text-tertiary text-sm font-semibold rounded-xl flex items-center justify-center gap-2.5 transition-all border border-tertiary/20 cursor-default';
                btnLabel.textContent = 'Connected ✓';

                // Unlock Continue button with prominent primary styling
                btnContinue.className = 'px-7 py-3 bg-primary hover:bg-secondary text-on-primary text-sm font-semibold rounded-xl flex items-center gap-2 cursor-pointer transition-all shadow-md active:scale-95';
                break;

            case 'EXPIRED':
            case 'ERROR':
                statusBadge.className = 'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-error-container text-error';
                statusBadge.innerHTML = '<span class="material-symbols-outlined text-[16px] text-error">error</span><span>Connection Failed</span>';

                statusMessageBox.className = 'bg-error-container/40 rounded-xl p-4 sm:p-5 flex items-start gap-3.5 transition-all border border-error/20';
                statusIcon.textContent = 'warning';
                statusIcon.className = 'material-symbols-outlined text-error text-[22px] shrink-0 mt-0.5';
                statusHeadline.textContent = 'Authentication Incomplete or Expired';
                statusDescription.textContent = data.message || 'LinkedIn login was cancelled, closed prematurely, or required credentials were missing. Please click Retry to open the browser again.';

                connectingProgress.classList.add('hidden');
                connectingProgress.classList.remove('flex');

                connectBtn.disabled = false;
                connectBtn.className = 'px-6 py-3.5 bg-[#0a66c2] hover:bg-[#004182] text-white text-sm font-semibold rounded-xl flex items-center justify-center gap-2.5 transition-all shadow-md active:scale-95 cursor-pointer';
                btnLabel.textContent = 'Retry Connection';

                btnContinue.className = 'px-6 py-2.5 bg-surface-container-high text-outline text-sm font-semibold rounded-xl flex items-center gap-2 cursor-not-allowed opacity-60 pointer-events-none transition-all shadow-sm';
                break;
        }
    }

    // Hydrate current status from backend
    async function checkStatus() {
        try {
            const res = await fetch('/api/auth/linkedin/status');
            if (!res.ok) return;
            const data = await res.json();
            if (data.success && data.connected) {
                applyState('CONNECTED', data);
            } else if (data.status === 'expired') {
                applyState('EXPIRED', { message: 'Existing LinkedIn session has expired. Please reconnect.' });
            } else {
                if (!isConnecting) {
                    applyState('DISCONNECTED');
                }
            }
        } catch (e) {
            console.error('Error fetching LinkedIn status:', e);
            if (!isConnecting) {
                applyState('DISCONNECTED');
            }
        }
    }

    // Connect handler
    async function handleConnect() {
        if (isConnecting) return;

        applyState('CONNECTING');

        // Start background polling in case connection finishes before POST returns
        pollInterval = setInterval(async () => {
            try {
                const res = await fetch('/api/auth/linkedin/status');
                if (res.ok) {
                    const data = await res.json();
                    if (data.success && data.connected) {
                        applyState('CONNECTED', data);
                    }
                }
            } catch (err) {
                console.warn('Poll error:', err);
            }
        }, 3000);

        try {
            const res = await fetch('/api/auth/linkedin/reconnect', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                }
            });

            const data = await res.json();
            if (res.ok && data.success && data.connected) {
                applyState('CONNECTED', data);
            } else {
                applyState('ERROR', {
                    message: data.message || 'Failed to authenticate LinkedIn session. Please ensure you reach the LinkedIn home feed.'
                });
            }
        } catch (err) {
            console.error('Connection request error:', err);
            applyState('ERROR', {
                message: 'A network error occurred while launching browser login. Please try again.'
            });
        }
    }

    connectBtn?.addEventListener('click', handleConnect);
    checkStatusBtn?.addEventListener('click', checkStatus);

    // Initial hydration
    checkStatus();
});
