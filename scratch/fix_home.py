import sys

with open("templates/home.html", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace("{{Account.Primary_Need}}", "[Account.Primary_Need]")
content = content.replace("{{Company.Name}}", "[Company.Name]")

with open("templates/home.html", "w", encoding="utf-8") as f:
    f.write(content)

print("Fixed home.html templates")
