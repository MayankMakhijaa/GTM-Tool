with open("tests/integration/test_onboarding.py", "r") as f:
    content = f.read()

content = content.replace('assert data["onboarding_step"] == "COMPANY"', 'assert data["onboarding_step"] == "LINKEDIN"')
content = content.replace('assert data["onboarding_step"] == "ICP"', 'assert data["onboarding_step"] == "LINKEDIN"')

with open("tests/integration/test_onboarding.py", "w") as f:
    f.write(content)
