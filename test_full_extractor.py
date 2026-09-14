import json
from profile_extractor import extract_linkedin_profile

def test_extractor():
    url = "https://www.linkedin.com/in/mohamed-kaashif-73361030a/"
    print("Testing extraction on:", url)
    res = extract_linkedin_profile(url)
    profile = res.get("profile", {})
    
    print("\n--- RESULTS ---")
    print("Name:", profile.get("name"))
    print("Headline:", profile.get("headline"))
    print("About length:", len(profile.get("about") or ""))
    print("Top Skills count:", len(profile.get("top_skills") or []))
    print("Experience count:", len(profile.get("experience") or []))
    print("Education count:", len(profile.get("education") or []))
    print("Skills count:", len(profile.get("skills") or []))
    print("Certifications count:", len(profile.get("certifications") or []))
    
    print("\nExperience items:")
    for idx, exp in enumerate(profile.get("experience") or []):
        print(f"  [{idx+1}] {exp.get('title')} @ {exp.get('company')} ({exp.get('start_date')})")

    print("\nEducation items:")
    for idx, edu in enumerate(profile.get("education") or []):
        print(f"  [{idx+1}] {edu.get('institution')} - {edu.get('degree')} ({edu.get('start_date')})")

    print("\nCertifications items:")
    for idx, cert in enumerate(profile.get("certifications") or []):
        print(f"  [{idx+1}] {cert.get('name')} - {cert.get('issuing_organization')} ({cert.get('issue_date')})")

    print("\nSkills sample (first 10 of", len(profile.get("skills") or []), "):")
    for s in (profile.get("skills") or [])[:10]:
        print("  -", s if isinstance(s, str) else s.get("name"))

if __name__ == "__main__":
    test_extractor()
