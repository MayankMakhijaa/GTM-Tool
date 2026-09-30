import glob

templates = glob.glob("templates/*.html")

for filepath in templates:
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Replace header login/signup
    content = content.replace('data-path="login" href="#"', 'data-path="login" href="/login"')
    content = content.replace('data-path="signup" href="#"', 'data-path="signup" href="/signup"')
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

print("Wired headers in all templates")
