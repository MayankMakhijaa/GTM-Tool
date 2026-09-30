import re

with open("templates/profileoptimization.html", "r", encoding="utf-8") as f:
    content = f.read()

# The script block starts at <script> and ends at </script>
content = re.sub(r'<script>.*?</script>', '', content, flags=re.DOTALL)

with open("templates/profileoptimization.html", "w", encoding="utf-8") as f:
    f.write(content)

print("Removed fake script block from profileoptimization.html")
