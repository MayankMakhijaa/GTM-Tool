import re

with open("templates/gtm.html", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace('<span>Start Research</span>', '<span id="btn-start-research">Start Research</span>')
content = content.replace('<span>Save Lead</span>', '<span id="btn-save-lead">Save Lead</span>')
content = content.replace('<span>Draft Personalized Outreach</span>', '<span id="btn-draft-outreach">Draft Personalized Outreach</span>')

with open("templates/gtm.html", "w", encoding="utf-8") as f:
    f.write(content)

print("Added IDs to GTM buttons")
