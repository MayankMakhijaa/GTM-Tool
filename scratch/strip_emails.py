import re

with open("templates/emails.html", "r", encoding="utf-8") as f:
    content = f.read()

# Remove the script block at the end (from let leadsData to the end)
content = re.sub(r'<script>\s*const leadsData = \{.*?</script>', '', content, flags=re.DOTALL)

# Empty the lead-list-container but keep the container itself
content = re.sub(r'(<div class="flex flex-col gap-space-xs" id="lead-list-container">).*?(<div class="p-space-md rounded-xl bg-surface-container flex flex-col gap-space-sm mt-space-xs">)', r'\1\n          </div>\n          \2', content, flags=re.DOTALL)

with open("templates/emails.html", "w", encoding="utf-8") as f:
    f.write(content)

print("Stripped emails.html")
