import os

template_dir = 'templates'
for filename in os.listdir(template_dir):
    if not filename.endswith('.html'):
        continue
        
    filepath = os.path.join(template_dir, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        
    if '<meta name="csrf-token"' not in content and '</head>' in content:
        content = content.replace('</head>', '\n<meta name="csrf-token" content="{{ csrf_token() }}">\n</head>')
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Injected CSRF token into {filename}")
    else:
        print(f"CSRF token already present or no </head> in {filename}")
