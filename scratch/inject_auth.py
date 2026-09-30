import sys

def inject_script(filepath, script_path):
    with open(filepath, 'r', encoding='utf-8') as f:
        html = f.read()
    
    script_tag = f'<script src="{script_path}"></script>'
    if script_tag not in html:
        html = html.replace('</body>', f'{script_tag}\n</body>')
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html)

inject_script('templates/login.html', '/static/js/auth/login.js')
inject_script('templates/signup.html', '/static/js/auth/signup.js')
print("Injected auth scripts")
