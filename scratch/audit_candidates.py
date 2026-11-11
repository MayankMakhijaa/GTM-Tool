import json
import urllib.request
import re
import os

OUTPUT_DIR = r"d:\Programming\FameWebs_Internship\linkedin_lead_generator\scratch\openserp_validation"

with open(os.path.join(OUTPUT_DIR, "raw_google.json"), "r", encoding="utf-8") as f:
    google_data = json.load(f)

results = google_data.get("raw_response", {}).get("results", [])

def resolve_url(raw_url):
    if "google.com/goto" in raw_url:
        try:
            req = urllib.request.Request(raw_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.geturl()
        except Exception as e:
            return raw_url
    return raw_url

validated_candidates = []

print("=================================================================")
print("OPENSERP GOOGLE CANDIDATE EVIDENCE AUDIT")
print("=================================================================\n")

for idx, r in enumerate(results, 1):
    raw_title = r.get("title", "")
    raw_url = r.get("url", "")
    snippet = r.get("snippet", "")
    
    # Resolve real destination URL
    final_url = resolve_url(raw_url)
    
    # Check if genuine LinkedIn profile
    m = re.search(r"linkedin\.com/in/([^/?#]+)", final_url, re.IGNORECASE)
    has_valid_url = bool(m)
    slug = m.group(1).strip() if m else None
    
    # Candidate Name Evaluation:
    # Google titles typically follow "Name - Title | Company" or "Name. Title"
    clean_title = re.sub(r"\s*\|\s*LinkedIn.*$", "", raw_title, flags=re.IGNORECASE).strip()
    parts = [p.strip() for p in re.split(r"\s*[-–—|]\s*", clean_title) if p.strip()]
    
    name_from_title = parts[0] if parts else ""
    # Remove degree credentials if attached
    clean_name = re.sub(r",\s*(PhD|MBA|MS|BTech|BE).*$", "", name_from_title, flags=re.IGNORECASE).strip()
    
    # Evaluation flags
    url_format_valid = has_valid_url
    name_supported = bool(clean_name and len(clean_name.split()) >= 2 and not clean_name.lower().startswith("http"))
    
    # Role Evaluation
    role = ""
    if len(parts) >= 2:
        role = parts[1]
    elif "VP" in snippet or "Director" in snippet:
        role_m = re.search(r"(VP\s+[^·•\n]+|Director\s+[^·•\n]+)", snippet)
        if role_m: role = role_m.group(1).strip()
    role_supported = bool("VP" in role or "Director" in role or "Sales" in role or "Head" in role or "CMO" in role)
    
    # Company Evaluation
    company = ""
    # Notice Google snippet often has: "Bengaluru, Karnataka, India · VP of Sales · Sprouts.ai"
    snip_parts = [p.strip() for p in snippet.split("·") if p.strip()]
    for p in snip_parts:
        if any(kw in p for kw in ["VP", "Director", "Sales", "Marketing", "CMO", "Chief"]):
            continue
        if any(kw in p for kw in ["Bengaluru", "Karnataka", "India", "Mumbai", "Delhi"]):
            continue
        if len(p) > 2 and len(p) < 40 and not p.startswith("..."):
            company = p.replace("...", "").strip()
    
    if not company and "Sell.Do" in snippet:
        company = "Sell.Do"
        
    company_supported = bool(company and company != "Target Company")
    
    # Location Evaluation
    location = "Unspecified"
    if "Bengaluru" in snippet or "Bengaluru" in raw_title:
        location = "Bengaluru, Karnataka, India"
    elif "India" in snippet or "India" in raw_title:
        location = "India"
    location_supported = location != "Unspecified"

    candidate_audit = {
        "candidate_index": idx,
        "raw_title": raw_title,
        "raw_url": raw_url,
        "resolved_url": final_url,
        "slug": slug,
        "extracted_name": clean_name,
        "extracted_role": role,
        "extracted_company": company or None,
        "extracted_location": location,
        "evidence_snippet": snippet,
        "validation_flags": {
            "URL_FORMAT_VALID": url_format_valid,
            "NAME_SUPPORTED_BY_TITLE_OR_SNIPPET": name_supported,
            "NAME_INFERRED_FROM_SLUG": False,
            "ROLE_SUPPORTED": role_supported,
            "COMPANY_SUPPORTED": company_supported,
            "LOCATION_SUPPORTED": location_supported,
            "GEOGRAPHY_MISMATCH": False,
            "IDENTITY_UNVERIFIED": not (url_format_valid and name_supported)
        }
    }
    validated_candidates.append(candidate_audit)

    print(f"Candidate #{idx}:")
    print(f"  Name:             {clean_name} (Supported: {name_supported})")
    print(f"  Resolved URL:     {final_url}")
    print(f"  Role:             {role} (Supported: {role_supported})")
    print(f"  Company:          {company or 'Not Found'} (Supported: {company_supported})")
    print(f"  Location:         {location} (Supported: {location_supported})")
    print(f"  Snippet:          {snippet}")
    print(f"  Validation Flags: {[k for k, v in candidate_audit['validation_flags'].items() if v]}")
    print("-----------------------------------------------------------------")

# Save detailed validation output
summary_path = os.path.join(OUTPUT_DIR, "validation_summary.json")
with open(summary_path, "w", encoding="utf-8") as f:
    json.dump({
        "engine": "google",
        "tested_endpoint": "http://127.0.0.1:7000/google/search",
        "total_results": len(results),
        "validated_candidates": validated_candidates
    }, f, indent=2)

print(f"\nSaved full validation report to {summary_path}")

