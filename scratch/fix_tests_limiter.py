import glob

for filename in glob.glob("tests/integration/test_*.py"):
    with open(filename, "r", encoding="utf-8") as f:
        content = f.read()

    if "limiter.enabled = False" not in content:
        content = content.replace("app.config['RATELIMIT_ENABLED'] = False", "app.config['RATELIMIT_ENABLED'] = False\n    from app.security.limiter import limiter\n    limiter.enabled = False")
        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)

print("Patched tests to disable limiter")
