import sys

with open("templates/index.html", "r", encoding="utf-8") as f:
    index_html = f.read()

head_start = index_html.find('<head>')
head_end = index_html.find('</head>')

# Ensure we inject the block head inside the <head>
head_content = index_html[head_start:head_end] + "\n    {% block head %}{% endblock %}\n</head>"

with open("templates/base.html", "r", encoding="utf-8") as f:
    base_html = f.read()

# Let's see if base_html has an <html> tag at the start
if "<html" not in base_html:
    base_html = "<!DOCTYPE html>\n<html lang=\"en\">\n" + head_content + "\n" + base_html
else:
    # Remove existing <head> if it exists and replace
    if "<head>" in base_html:
        base_head_start = base_html.find('<head>')
        base_head_end = base_html.find('</head>') + 7
        base_html = base_html[:base_head_start] + head_content + base_html[base_head_end:]
    else:
        html_end = base_html.find('>') + 1
        base_html = base_html[:html_end] + "\n" + head_content + "\n" + base_html[html_end:]

with open("templates/base.html", "w", encoding="utf-8") as f:
    f.write(base_html)

print("Patched base.html")

# Let's also patch the standalone files to have the correct <head>!
standalone_files = ["login.html", "signup.html", "companydetails.html", "icp.html", "icp_review.html", "home.html"]
for file in standalone_files:
    filepath = f"templates/{file}"
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            
        if "<head>" not in content:
            if "<html" not in content:
                content = "<!DOCTYPE html>\n<html lang=\"en\">\n" + head_content + "\n" + content
            else:
                html_end = content.find('>') + 1
                content = content[:html_end] + "\n" + head_content + "\n" + content[html_end:]
                
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Patched head of {file}")
    except Exception as e:
        print(f"Error patching {file}: {e}")

