import re

with open("templates/dashboard.html", "r", encoding="utf-8") as f:
    content = f.read()

# Replace hardcoded numbers in font-headline-xl
content = content.replace('text-on-surface">42<', 'text-on-surface">--<')
content = content.replace('text-on-surface">16<', 'text-on-surface">--<')
content = content.replace('text-on-surface">128<', 'text-on-surface">--<')
content = content.replace('text-on-surface">84<', 'text-on-surface">--<')
# Also there might be a percentage like 84%
content = content.replace('text-on-surface">84%<', 'text-on-surface">--%<')

with open("templates/dashboard.html", "w", encoding="utf-8") as f:
    f.write(content)

print("Replaced hardcoded metrics with empty states")
