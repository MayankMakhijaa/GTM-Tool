import re

with open("templates/home.html", "r", encoding="utf-8") as f:
    content = f.read()

# Replace header login/signup
content = content.replace('data-path="login" href="#"', 'data-path="login" href="/login"')
content = content.replace('data-path="signup" href="#"', 'data-path="signup" href="/signup"')

# Replace "Start Free / Try Fameweb" which has href="#demo-preview"
# Let's change the CTA button to point to signup.
content = content.replace('href="#demo-preview"', 'href="/signup"')

with open("templates/home.html", "w", encoding="utf-8") as f:
    f.write(content)

print("Wired home.html")
