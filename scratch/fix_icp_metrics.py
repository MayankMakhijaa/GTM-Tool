import re

with open("templates/icp.html", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace('>4,820<', '>--<')
content = content.replace('88% (Tier 1 Fit)', '--')
content = content.replace('style="width: 88%"', 'style="width: 0%"')
content = content.replace('>14,290<', '>--<')

with open("templates/icp.html", "w", encoding="utf-8") as f:
    f.write(content)

print("Replaced ICP fabricated metrics with empty states")
