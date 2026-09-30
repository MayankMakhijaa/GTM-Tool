import os
import glob

template_dir = 'templates'
for filepath in glob.glob(os.path.join(template_dir, '*.html')):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if 'href="#"' in content:
        content = content.replace('href="#"', 'href="javascript:void(0)"')
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Patched {filepath}")

print("Done patching hrefs")
