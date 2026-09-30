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
        togglePasswordBtn.addEventListener('click', () => {
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
                    window.location.href = '/dashboard';
                } else {
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
