import re

with open("templates/history.html", "r", encoding="utf-8") as f:
    content = f.read()

# Add ID to tbody and remove trs
content = re.sub(
    r'(<tbody class="divide-y divide-surface-container-low font-body-md text-body-md").*?(</tbody>)',
    r'\1 id="history-table-body">\n</tbody>',
    content,
    flags=re.DOTALL
)

# Add IDs to pagination texts
content = content.replace(
    '<span class="font-label-md text-label-md text-on-surface font-semibold">1 to 7</span>',
    '<span class="font-label-md text-label-md text-on-surface font-semibold" id="pagination-range">0 to 0</span>'
)
content = content.replace(
    '<span class="font-body-sm text-body-sm text-on-surface-variant">of 148 historical prospects</span>',
    '<span class="font-body-sm text-body-sm text-on-surface-variant" id="pagination-total">of 0 historical prospects</span>'
)
content = content.replace(
    '<div class="inline-flex items-center gap-1">',
    '<div class="inline-flex items-center gap-1" id="pagination-controls">'
)

# And empty the pagination controls because we'll render them via JS
content = re.sub(
    r'(<div class="inline-flex items-center gap-1" id="pagination-controls">).*?(</div>\s*<div class="inline-flex items-center gap-space-xs)',
    r'\1\n</div>\n<div class="inline-flex items-center gap-space-xs',
    content,
    flags=re.DOTALL
)

# Include history.js
content = content.replace(
    '{% endblock %}',
    '{% endblock %}\n{% block scripts %}\n<script src="/static/js/history.js"></script>\n{% endblock %}',
    1
)

with open("templates/history.html", "w", encoding="utf-8") as f:
    f.write(content)

print("Cleaned history.html")
