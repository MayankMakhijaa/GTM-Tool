with open('scratch/ddg_sample.html', 'r', encoding='utf-8') as f:
    text = f.read()

import re
print("Length:", len(text))
clean = re.sub(r'<[^>]+>', ' ', text)
lines = [l.strip() for l in clean.splitlines() if l.strip()]
print("\n--- SAMPLE TEXT LINES ---")
for l in lines[:30]:
    print(l)

