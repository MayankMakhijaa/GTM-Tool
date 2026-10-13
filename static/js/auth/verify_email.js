document.addEventListener('DOMContentLoaded', () => {
    const otpForm = document.getElementById('otp-form');
    const otpInput = document.getElementById('otp-input');
    const btnVerify = document.getElementById('btn-verify-otp');
    const btnResend = document.getElementById('btn-resend-otp');
    const resendText = document.getElementById('resend-text');
    const statusBanner = document.getElementById('status-banner');
    const statusBannerText = document.getElementById('status-banner-text');
    const statusBannerIcon = document.getElementById('status-banner-icon');
    const targetEmailDisplay = document.getElementById('target-email-display');
    const expiryTimerEl = document.getElementById('expiry-timer');

    const getCsrfToken = () => document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';

    // Determine target email
    const urlParams = new URLSearchParams(window.location.search);
    let targetEmail = urlParams.get('email') || sessionStorage.getItem('fameweb_pending_verification_email') || '';

    if (!targetEmail && targetEmailDisplay) {
        const text = targetEmailDisplay.textContent.trim();
        if (text && text.includes('@')) {
            targetEmail = text;
        }
    }

    if (targetEmail && targetEmailDisplay) {
        targetEmailDisplay.textContent = targetEmail;
        sessionStorage.setItem('fameweb_pending_verification_email', targetEmail);
    }

    const showBanner = (message, type = 'error') => {
        if (!statusBanner || !statusBannerText) return;
        statusBanner.classList.remove('hidden', 'bg-error-container', 'text-on-error-container', 'bg-tertiary/10', 'text-tertiary', 'bg-amber-100', 'text-amber-800');
        
        if (type === 'error') {
            statusBanner.classList.add('bg-error-container', 'text-on-error-container');
            if (statusBannerIcon) statusBannerIcon.textContent = 'error';
        } else if (type === 'success') {
            statusBanner.classList.add('bg-tertiary/10', 'text-tertiary');
            if (statusBannerIcon) statusBannerIcon.textContent = 'check_circle';
        } else {
            statusBanner.classList.add('bg-amber-100', 'text-amber-800');
            if (statusBannerIcon) statusBannerIcon.textContent = 'info';
        }

        statusBannerText.innerHTML = message;
    };

    // 10-Minute Expiry Countdown Timer
    let expirySeconds = 10 * 60;
    let expiryInterval = null;

    const startExpiryTimer = (seconds = 600) => {
        if (expiryInterval) clearInterval(expiryInterval);
        expirySeconds = seconds;

        const updateDisplay = () => {
            const m = Math.floor(expirySeconds / 60);
            const s = expirySeconds % 60;
            if (expiryTimerEl) {
                expiryTimerEl.textContent = `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
            }
            if (expirySeconds <= 0) {
                clearInterval(expiryInterval);
                showBanner('Verification code has expired. Please request a new code.', 'warning');
                if (btnVerify) btnVerify.disabled = true;
            }
            expirySeconds--;
        };

        updateDisplay();
        expiryInterval = setInterval(updateDisplay, 1000);
    };

    startExpiryTimer(600);

    // 60-Second Resend Cooldown
    let resendCooldown = 0;
    let resendInterval = null;

    const startResendCooldown = (seconds = 60) => {
        if (resendInterval) clearInterval(resendInterval);
        resendCooldown = seconds;
        if (btnResend) btnResend.disabled = true;

        const updateResend = () => {
            if (resendCooldown <= 0) {
                clearInterval(resendInterval);
                if (btnResend) btnResend.disabled = false;
                if (resendText) resendText.textContent = 'Resend Code';
                return;
            }
            if (resendText) resendText.textContent = `Resend in ${resendCooldown}s`;
            resendCooldown--;
        };

        updateResend();
        resendInterval = setInterval(updateResend, 1000);
    };

    // Form input formatting: numeric only
    if (otpInput) {
        otpInput.addEventListener('input', (e) => {
            e.target.value = e.target.value.replace(/[^0-9]/g, '').slice(0, 6);
            if (e.target.value.length === 6 && btnVerify) {
                btnVerify.focus();
            }
        });
    }

    // Submit Verification
    if (otpForm) {
        otpForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const code = otpInput?.value?.trim();
            if (!code || code.length !== 6) {
                showBanner('Please enter the complete 6-digit code.', 'error');
                otpInput?.focus();
                return;
            }

            if (!targetEmail) {
                showBanner('Email address missing. Please return to the signup page.', 'error');
                return;
            }

            const originalBtnHtml = btnVerify.innerHTML;
            btnVerify.disabled = true;
            btnVerify.innerHTML = '<span class="material-symbols-outlined animate-spin text-[18px]">progress_activity</span><span>Verifying...</span>';

            try {
                const res = await fetch('/api/auth/verify-otp', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: JSON.stringify({ email: targetEmail, otp: code })
                });

                const data = await res.json();
                if (res.ok && data.success) {
                    showBanner('Email verified! Redirecting to setup...', 'success');
                    sessionStorage.removeItem('fameweb_pending_verification_email');
                    setTimeout(() => {
                        window.location.href = data.redirect || '/connect-linkedin';
                    }, 800);
                } else {
                    showBanner(data.message || 'Invalid or expired verification code.', 'error');
                    btnVerify.disabled = false;
                    btnVerify.innerHTML = originalBtnHtml;
                    if (otpInput) {
                        otpInput.value = '';
                        otpInput.focus();
                    }
                }
            } catch (err) {
                showBanner('Network error occurred. Please try again.', 'error');
                btnVerify.disabled = false;
                btnVerify.innerHTML = originalBtnHtml;
            }
        });
    }

    // Resend Code Click Handler
    if (btnResend) {
        btnResend.addEventListener('click', async () => {
            if (resendCooldown > 0) return;

            if (!targetEmail) {
                showBanner('Email address missing. Please return to the signup page.', 'error');
                return;
            }

            btnResend.disabled = true;
            if (resendText) resendText.textContent = 'Sending...';

            try {
                const res = await fetch('/api/auth/resend-otp', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: JSON.stringify({ email: targetEmail })
                });

                const data = await res.json();
                if (res.ok && data.success) {
                    showBanner('A new verification code has been dispatched to your email.', 'success');
                    startResendCooldown(60);
                    startExpiryTimer(600);
                    if (btnVerify) btnVerify.disabled = false;
                    if (otpInput) {
                        otpInput.value = '';
                        otpInput.focus();
                    }
                } else if (res.status === 429 && data.retry_after) {
                    showBanner(data.message || 'Please wait before requesting another code.', 'warning');
                    startResendCooldown(data.retry_after);
                } else {
                    showBanner(data.message || 'Failed to resend code. Please try again.', 'error');
                    if (resendText) resendText.textContent = 'Resend Code';
                    btnResend.disabled = false;
                }
            } catch (err) {
                showBanner('Network error while requesting code. Please try again.', 'error');
                if (resendText) resendText.textContent = 'Resend Code';
                btnResend.disabled = false;
            }
        });
    }
});
