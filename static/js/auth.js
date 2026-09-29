document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('login-form-wrapper');
    const signupForm = document.getElementById('signup-form-wrapper');
    const showSignupBtn = document.getElementById('show-signup-btn');
    const showLoginBtn = document.getElementById('show-login-btn');
    const authLoginBtn = document.getElementById('auth-login-btn');
    const authSignupBtn = document.getElementById('auth-signup-btn');
    
    // CSRF Setup
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
    const defaultHeaders = {
        'Content-Type': 'application/json'
    };
    if (csrfToken) {
        defaultHeaders['X-CSRFToken'] = csrfToken;
    }

    if (showSignupBtn) {
        showSignupBtn.addEventListener('click', () => {
            loginForm.classList.add('hidden');
            signupForm.classList.remove('hidden');
        });
    }

    if (showLoginBtn) {
        showLoginBtn.addEventListener('click', () => {
            signupForm.classList.add('hidden');
            loginForm.classList.remove('hidden');
        });
    }

    if (authLoginBtn) {
        authLoginBtn.addEventListener('click', async () => {
            const identifier = document.getElementById('login-identifier').value;
            const password = document.getElementById('login-password').value;
            const errorDiv = document.getElementById('login-error');
            errorDiv.classList.add('hidden');

            try {
                const res = await fetch('/api/auth/login', {
                    method: 'POST',
                    headers: defaultHeaders,
                    body: JSON.stringify({ identifier, password })
                });
                const data = await res.json();
                if (!res.ok || !data.success) {
                    errorDiv.textContent = data.message || 'Login failed';
                    errorDiv.classList.remove('hidden');
                } else {
                    window.location.reload();
                }
            } catch (err) {
                errorDiv.textContent = 'A network error occurred';
                errorDiv.classList.remove('hidden');
            }
        });
    }

    if (authSignupBtn) {
        authSignupBtn.addEventListener('click', async () => {
            const name = document.getElementById('signup-name').value;
            const email = document.getElementById('signup-email').value;
            const phone = document.getElementById('signup-phone').value;
            const password = document.getElementById('signup-password').value;
            const errorDiv = document.getElementById('signup-error');
            errorDiv.classList.add('hidden');

            try {
                const res = await fetch('/api/auth/signup', {
                    method: 'POST',
                    headers: defaultHeaders,
                    body: JSON.stringify({ name, email, phone, password })
                });
                const data = await res.json();
                if (!res.ok || !data.success) {
                    errorDiv.textContent = data.message || 'Signup failed';
                    errorDiv.classList.remove('hidden');
                } else {
                    window.location.reload();
                }
            } catch (err) {
                errorDiv.textContent = 'A network error occurred';
                errorDiv.classList.remove('hidden');
            }
        });
    }

    // Replace the app.js login check with our new auth/me check if needed
    // (We will patch app.js instead to use /api/auth/me)
});
