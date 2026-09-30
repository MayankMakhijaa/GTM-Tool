import sys

with open('static/js/core/navigation.js', 'r', encoding='utf-8') as f:
    js = f.read()

logout_js = """
    // Handle Logout
    const logoutBtn = document.querySelector('[data-path="login"]');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', async (e) => {
            e.preventDefault();
            const getCsrfToken = () => document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
            try {
                const res = await fetch('/api/auth/logout', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    }
                });
                if (res.ok) {
                    window.location.href = '/login';
                }
            } catch (err) {
                console.error('Logout failed', err);
            }
        });
    }
"""

if 'Handle Logout' not in js:
    js = js.replace('});', logout_js + '\n});')
    with open('static/js/core/navigation.js', 'w', encoding='utf-8') as f:
        f.write(js)

print("Updated navigation.js with logout logic")
