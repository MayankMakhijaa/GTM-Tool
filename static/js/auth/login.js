document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('loginForm');
    const identifierInput = document.getElementById('identifier');
    const passwordInput = document.getElementById('password');
    const togglePasswordBtn = document.getElementById('togglePassword');
    const pwdIcon = document.getElementById('pwdIcon');
    const signInBtn = document.getElementById('signInBtn');

    // CSRF token
    const getCsrfToken = () => document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';

    // Show/Hide password
    if (togglePasswordBtn && passwordInput && pwdIcon) {
        togglePasswordBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            if (passwordInput.type === 'password') {
                passwordInput.type = 'text';
                pwdIcon.textContent = 'visibility_off';
            } else {
                passwordInput.type = 'password';
                pwdIcon.textContent = 'visibility';
            }
        });
    }

    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const identifier = identifierInput?.value || '';
            const password = passwordInput?.value || '';

            if (!identifier || !password) return;

            // Loading state
            const originalBtnText = signInBtn.innerHTML;
            signInBtn.disabled = true;
            signInBtn.innerHTML = '<span class="material-symbols-outlined animate-spin text-[18px]">progress_activity</span><span>Signing In...</span>';

            try {
                const res = await fetch('/api/auth/login', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: JSON.stringify({ identifier, password })
                });

                let data;
                const contentType = res.headers.get("content-type");
                if (contentType && contentType.includes("application/json")) {
                    data = await res.json();
                } else {
                    const text = await res.text();
                    console.error("Non-JSON Auth API error:", res.status, text);
                    throw new Error(`Unexpected server response (${res.status})`);
                }
                
                if (res.ok && data.success) {
                    sessionStorage.removeItem('fameweb_csrf_retry');
                    window.location.href = data.redirect || '/dashboard';
                } else if (data && data.error === 'CSRF_ERROR') {
                    // Recover from expired or invalid CSRF token without treating as credential error
                    signInBtn.disabled = false;
                    signInBtn.innerHTML = originalBtnText;

                    const hasRetried = sessionStorage.getItem('fameweb_csrf_retry');
                    if (!hasRetried) {
                        sessionStorage.setItem('fameweb_csrf_retry', '1');
                        alert('Your security session has expired. The page will reload with a fresh security token.');
                        window.location.reload();
                    } else {
                        sessionStorage.removeItem('fameweb_csrf_retry');
                        alert('Security session verification failed. Please refresh the page and try again.');
                    }
                    return;
                } else if (data && data.error === 'EMAIL_NOT_VERIFIED') {
                    sessionStorage.removeItem('fameweb_csrf_retry');
                    const emailForVerify = data.email || (identifier.includes('@') ? identifier.trim().toLowerCase() : '');
                    if (emailForVerify) {
                        sessionStorage.setItem('fameweb_pending_verification_email', emailForVerify);
                    }
                    alert(data.message || 'Please verify your business email to continue.');
                    window.location.href = data.redirect ? `${data.redirect}?email=${encodeURIComponent(emailForVerify)}` : '/verify-email';
                    return;
                } else {
                    sessionStorage.removeItem('fameweb_csrf_retry');
                    throw new Error(data.message || 'Invalid credentials');
                }
            } catch (err) {
                alert(err.message || 'A network error occurred. Please try again.');
                signInBtn.disabled = false;
                signInBtn.innerHTML = originalBtnText;
            }
        });
    }
});
