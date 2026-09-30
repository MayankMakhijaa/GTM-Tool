document.addEventListener('DOMContentLoaded', () => {
    // Determine active tab based on current URL path
    const path = window.location.pathname;
    const links = document.querySelectorAll('aside nav a');
    
    links.forEach(link => {
        // Clear active classes
        link.className = 'flex items-center gap-space-md px-space-md py-space-sm rounded-lg text-on-surface-variant font-label-md text-label-md hover:bg-surface-container hover:text-on-surface transition-colors';
        
        if (link.getAttribute('href') === path) {
            // Set active class
            link.className = 'flex items-center gap-space-md px-space-md py-space-sm transition-colors bg-primary-container text-on-primary font-label-md text-label-md rounded-lg';
            link.setAttribute('aria-current', 'page');
        } else {
            link.removeAttribute('aria-current');
        }
    
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

});

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

});
