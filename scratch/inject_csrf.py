import os

for filename in ['templates/login.html', 'templates/signup.html']:
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find </head> and insert the meta tag before it
    if '<meta name="csrf-token"' not in content:
        content = content.replace('</head>', '\n<meta name="csrf-token" content="{{ csrf_token() }}">\n</head>')
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Injected CSRF token into {filename}")
    else:
        print(f"CSRF token already in {filename}")
