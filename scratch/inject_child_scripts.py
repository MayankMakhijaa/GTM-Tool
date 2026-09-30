import os

scripts_map = {
    'gtm.html': '/static/js/gtm.js',
    'emails.html': '/static/js/email-outreach.js',
    'profileoptimization.html': '/static/js/profile-optimization.js',
    'dashboard.html': '/static/js/leads.js'
}

for template, script_src in scripts_map.items():
    filepath = f"templates/{template}"
    with open(filepath, 'r', encoding='utf-8') as f:
        html = f.read()
    
    # The child templates end with {% endblock %} because they only have block content.
    # We should add {% block scripts %}<script src="..."></script>{% endblock %}
    if 'block scripts' not in html:
        injection = f"\n{{% block scripts %}}\n<script src=\"{script_src}\"></script>\n{{% endblock %}}\n"
        with open(filepath, 'a', encoding='utf-8') as f:
            f.write(injection)
        print(f"Injected {script_src} into {template}")
