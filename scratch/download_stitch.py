import json
import urllib.request
import os

with open(r'C:\Users\mdkaa\.gemini\antigravity-ide\brain\5c7e233a-ce20-48a2-ae19-48b611b49c7b\.system_generated\steps\2081\output.txt', 'r') as f:
    data = json.load(f)

os.makedirs('stitch_html', exist_ok=True)

mapping = {
    "Fameweb - Home (Landing Page)": "home.html",
    "Fameweb - Sign In": "login.html",
    "Fameweb - Sign Up": "signup.html",
    "Fameweb - Company Details (Onboarding Step 1)": "companydetails.html",
    "Fameweb - ICP Setup (State 1: Questionnaire)": "icp.html",
    "Fameweb - ICP Setup (State 2: Report Review)": "icp_review.html",
    "Fameweb - Dashboard": "dashboard.html",
    "Fameweb - Profile Optimization": "profileoptimization.html",
    "Fameweb - GTM Research": "gtm.html",
    "Fameweb - Email Outreach": "emails.html",
    "Fameweb - History": "history.html"
}

for screen in data.get('screens', []):
    title = screen.get('title')
    html_url = screen.get('htmlCode', {}).get('downloadUrl')
    
    if title in mapping and html_url:
        filename = mapping[title]
        filepath = os.path.join('stitch_html', filename)
        print(f"Downloading {title} to {filepath}...")
        try:
            req = urllib.request.Request(html_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                html_content = response.read().decode('utf-8')
            with open(filepath, 'w', encoding='utf-8') as out_f:
                out_f.write(html_content)
        except Exception as e:
            print(f"Failed to download {title}: {e}")

print("Done downloading stitch screens.")
