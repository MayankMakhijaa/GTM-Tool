import os
import re

# 1. Update base.html
with open('templates/base.html', 'r', encoding='utf-8') as f:
    html = f.read()

html = html.replace('>Sarah Jenkins<', '>{{ user.name if user else \'Sarah Jenkins\' }}<')
html = html.replace('>sarah@fameweb.ai<', '>{{ user.email_id if user else \'sarah@fameweb.ai\' }}<')

with open('templates/base.html', 'w', encoding='utf-8') as f:
    f.write(html)

# 2. Update dashboard.html
with open('templates/dashboard.html', 'r', encoding='utf-8') as f:
    dash = f.read()
    
# Replace "Good morning, Sarah"
dash = dash.replace('>Good morning, Sarah<', '>Good morning, {{ user.name.split(" ")[0] if user else \'Sarah\' }}<')
# Wait, jinja might throw error on split if user.name is none, but 'if user' should protect it, wait no, jinja needs `user.name.split(' ')[0] if user and user.name else 'Sarah'`

dash = dash.replace('>Good morning, Sarah<', '>Good morning, {{ user.name.split(" ")[0] if user and user.name else \'Sarah\' }}<')

with open('templates/dashboard.html', 'w', encoding='utf-8') as f:
    f.write(dash)

print("Injected user details placeholders")
