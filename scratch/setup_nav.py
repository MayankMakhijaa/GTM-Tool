import os

# 1. Patch base.html hrefs
with open('templates/base.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Replace href="#" with actual URLs based on data-path
html = html.replace('data-path="dashboard" href="#"', 'data-path="dashboard" href="/dashboard"')
html = html.replace('data-path="profile-optimization" href="#"', 'data-path="profile-optimization" href="/profile-optimization"')
html = html.replace('data-path="gtm-research" href="#"', 'data-path="gtm-research" href="/gtm"')
html = html.replace('data-path="emails" href="#"', 'data-path="emails" href="/emails"')
html = html.replace('data-path="history" href="#"', 'data-path="history" href="/history"')
html = html.replace('data-path="login" href="#"', 'data-path="login" href="/api/auth/logout"')

# Inject core/navigation.js
if 'static/js/core/navigation.js' not in html:
    html = html.replace('{% block scripts %}{% endblock %}', '<script src="/static/js/core/navigation.js"></script>\n    {% block scripts %}{% endblock %}')

with open('templates/base.html', 'w', encoding='utf-8') as f:
    f.write(html)

# 2. Create core/navigation.js
nav_js = """document.addEventListener('DOMContentLoaded', () => {
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
    });
});
"""

os.makedirs('static/js/core', exist_ok=True)
with open('static/js/core/navigation.js', 'w', encoding='utf-8') as f:
    f.write(nav_js)

print("Setup navigation.js and patched base.html")
