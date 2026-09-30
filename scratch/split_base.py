import re
import os

with open(r'stitch_html/dashboard.html', 'r', encoding='utf-8') as f:
    html = f.read()

# We want to find the <aside> tag and the top navigation.
# Usually it's:
# <body>
#   <div class="flex h-screen bg-surface text-on-surface font-body-md">
#     <!-- Sidebar (Desktop) -->
#     <aside ...> ... </aside>
#     <!-- Main Content Wrapper -->
#     <div class="flex-1 flex flex-col min-w-0">
#       <!-- Top Navigation -->
#       <header ...> ... </header>
#       <!-- Main Canvas Area -->
#       <main class="flex-1 overflow-y-auto">
#           ... content ...
#       </main>

# Let's use regex or just string splitting to extract these.
# First, let's find <main 
main_start = html.find('<main')
if main_start == -1:
    print("Could not find <main>")
    exit(1)

# Find where <main> ends and its content starts
main_content_start = html.find('>', main_start) + 1

# Find the matching </main>
main_end = html.rfind('</main>')

base_html = html[:main_content_start] + '\n        {% block content %}{% endblock %}\n      ' + html[main_end:]
dashboard_content = html[main_content_start:main_end]

# We should also replace the <head> links to be dynamic or add {% block head %} if needed.
# Let's add a {% block title %}
base_html = base_html.replace('<title>Fameweb - Dashboard</title>', '<title>{% block title %}Fameweb{% endblock %}</title>')

# We also need to include our base css and JS
# Inject {% block head %} and {% block scripts %}
head_end = base_html.find('</head>')
base_html = base_html[:head_end] + '\n    {% block head %}{% endblock %}\n' + base_html[head_end:]

body_end = base_html.find('</body>')
base_html = base_html[:body_end] + '\n    {% block scripts %}{% endblock %}\n' + base_html[body_end:]

# Create templates dir
os.makedirs('templates', exist_ok=True)

with open('templates/base.html', 'w', encoding='utf-8') as f:
    f.write(base_html)

dashboard_html = '{% extends "base.html" %}\n{% block title %}Fameweb - Dashboard{% endblock %}\n{% block content %}\n' + dashboard_content + '\n{% endblock %}\n'
with open('templates/dashboard.html', 'w', encoding='utf-8') as f:
    f.write(dashboard_html)

print("Created base.html and dashboard.html")
