import os

def extract_main(filepath, target_file):
    with open(filepath, 'r', encoding='utf-8') as f:
        html = f.read()

    main_start = html.find('<main')
    if main_start == -1:
        # If no <main>, just wrap the whole body content?
        # Actually for standalone ones like login.html, signup.html, we don't extend base.html
        print(f"Skipping extract for {filepath} - no <main> found")
        return False
        
    main_content_start = html.find('>', main_start) + 1
    main_end = html.rfind('</main>')

    dashboard_content = html[main_content_start:main_end]

    dashboard_html = '{% extends "base.html" %}\n{% block title %}Fameweb{% endblock %}\n{% block content %}\n' + dashboard_content + '\n{% endblock %}\n'
    
    with open(f'templates/{target_file}', 'w', encoding='utf-8') as f:
        f.write(dashboard_html)
    return True

# Ensure base.html exists, we already made it.
# Files that should extend base:
screens_to_extend = [
    ('dashboard.html', 'dashboard.html'),
    ('gtm.html', 'gtm.html'),
    ('emails.html', 'emails.html'),
    ('history.html', 'history.html'),
    ('profileoptimization.html', 'profileoptimization.html')
]

for src, target in screens_to_extend:
    if extract_main(f'stitch_html/{src}', target):
        print(f"Successfully generated templates/{target}")

# For screens that do not extend base.html (e.g. login, signup, companydetails, icp, home)
# we can just copy them directly into templates, but maybe inject Jinja tags for static files if needed.
import shutil

standalone_screens = [
    'login.html',
    'signup.html',
    'companydetails.html',
    'icp.html',
    'icp_review.html',
    'home.html'
]

for screen in standalone_screens:
    src = f'stitch_html/{screen}'
    if os.path.exists(src):
        # We might want to fix static paths here? We'll do it later or manually.
        shutil.copy(src, f'templates/{screen}')
        print(f"Copied standalone {screen}")

