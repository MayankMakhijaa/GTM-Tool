import os

# Create auth folder if it doesn't exist
os.makedirs("static/js/auth", exist_ok=True)

login_js = """document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('loginForm');
    
    // CSRF Setup
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
    const defaultHeaders = {
        'Content-Type': 'application/json'
    };
    if (csrfToken) {
        defaultHeaders['X-CSRFToken'] = csrfToken;
    }

    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const identifier = document.getElementById('identifier').value;
            const password = document.getElementById('password').value;
            // The stitch ui might not have a dedicated login-error div by default.
            // Let's create an alert or inject if needed, or see if one exists.
            let errorDiv = document.getElementById('login-error');
            if (!errorDiv) {
                errorDiv = document.createElement('div');
                errorDiv.id = 'login-error';
                errorDiv.className = 'text-error font-medium text-sm hidden mt-2';
                loginForm.prepend(errorDiv);
            }
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
                    window.location.href = '/dashboard';
                }
            } catch (err) {
                errorDiv.textContent = 'A network error occurred';
                errorDiv.classList.remove('hidden');
            }
        });
    }
});
"""

signup_js = """document.addEventListener('DOMContentLoaded', () => {
    const signupForm = document.getElementById('signup-form');
    
    // CSRF Setup
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
    const defaultHeaders = {
        'Content-Type': 'application/json'
    };
    if (csrfToken) {
        defaultHeaders['X-CSRFToken'] = csrfToken;
    }

    if (signupForm) {
        signupForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const name = document.getElementById('fullName').value;
            const email = document.getElementById('businessEmail').value;
            const code = document.getElementById('selectedCode').innerText;
            const phone = document.getElementById('phoneNumber').value;
            const password = document.getElementById('passwordField').value;
            
            let errorDiv = document.getElementById('signup-error');
            if (!errorDiv) {
                errorDiv = document.createElement('div');
                errorDiv.id = 'signup-error';
                errorDiv.className = 'text-error font-medium text-sm hidden mt-2';
                signupForm.prepend(errorDiv);
            }
            errorDiv.classList.add('hidden');

            try {
                const res = await fetch('/api/auth/signup', {
                    method: 'POST',
                    headers: defaultHeaders,
                    body: JSON.stringify({ name, email, phone: code + phone, password })
                });
                const data = await res.json();
                if (!res.ok || !data.success) {
                    errorDiv.textContent = data.message || 'Signup failed';
                    errorDiv.classList.remove('hidden');
                } else {
                    window.location.href = '/company';
                }
            } catch (err) {
                errorDiv.textContent = 'A network error occurred';
                errorDiv.classList.remove('hidden');
            }
        });
    }
});
"""

with open("static/js/auth/login.js", "w", encoding="utf-8") as f:
    f.write(login_js)

with open("static/js/auth/signup.js", "w", encoding="utf-8") as f:
    f.write(signup_js)
    
print("Created login.js and signup.js")
