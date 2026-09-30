import sys

with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

# Add import for pages_bp
if "from app.routes.pages import pages_bp" not in content:
    content = content.replace("from app.routes.onboarding import onboarding_bp", "from app.routes.onboarding import onboarding_bp\nfrom app.routes.pages import pages_bp")

# Register blueprint
if "app.register_blueprint(pages_bp)" not in content:
    content = content.replace("app.register_blueprint(onboarding_bp)", "app.register_blueprint(onboarding_bp)\napp.register_blueprint(pages_bp)")

# Remove old @app.route("/")
old_route = """@app.route("/")
def index():
    return render_template("index.html")"""
content = content.replace(old_route, "")

with open("app.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Patched app.py")
