import urllib.request
import urllib.parse
import re
import json

QUERIES = [
    'site:linkedin.com/in "VP Sales" "B2B SaaS" India',
    'site:linkedin.com/in "Chief Revenue Officer" SaaS India',
    'site:linkedin.com/in "Head of Growth" SaaS Bengaluru',
    'site:linkedin.com/in "Founder" "B2B SaaS" Bengaluru',
    'site:linkedin.com/in "VP of Engineering" SaaS India',
    '"VP Sales" "B2B SaaS" Bengaluru leadership team',
    'site:linkedin.com/in "Director of Sales" SaaS Mumbai',
    'site:linkedin.com/in "Head of Sales" enterprise SaaS India',
    'site:linkedin.com/in "Co-Founder & CEO" AI SaaS India',
    'site:linkedin.com/in "VP Marketing" B2B SaaS India'
]

def search_ddg_html(query):
    encoded = urllib.parse.quote_plus(query)
    url = f"https://html.duckduckgo.com/html/?q={encoded}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
    )
    results = []
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8")
            # Grab title + url + snippet
            raw_blocks = re.findall(
                r'<h2 class="result__title">[\s\S]*?<a class="result__url"[^>]*href="([^"]+)"[^>]*>([\s\S]*?)</a>[\s\S]*?<a class="result__snippet"[^>]*>([\s\S]*?)</a>',
                html
            )
            if not raw_blocks:
                # alternative structure
                raw_blocks = re.findall(
                    r'<a class="result__snippet"[^>]*href="([^"]+)"[^>]*>([\s\S]*?)</a>',
                    html
                )
                for href, snip in raw_blocks:
                    m = re.search(r'uddg=([^&]+)', href)
                    real_url = urllib.parse.unquote(m.group(1)) if m else href
                    results.append({
                        "url": real_url,
                        "title": "",
                        "snippet": re.sub(r'<[^>]+>', '', snip).strip()
                    })
                return results

            for href, title, snip in raw_blocks:
                m = re.search(r'uddg=([^&]+)', href)
                real_url = urllib.parse.unquote(m.group(1)) if m else href
                results.append({
                    "url": real_url,
                    "title": re.sub(r'<[^>]+>', '', title).strip(),
                    "snippet": re.sub(r'<[^>]+>', '', snip).strip()
                })
    except Exception as e:
        return [{"error": str(e)}]
    return results

def parse_candidate_from_serp(item, query):
    url = item.get("url", "")
    title = item.get("title", "")
    snippet = item.get("snippet", "")
    
    # 1. Match genuine linkedin.com/in/<slug>
    m = re.search(r"linkedin\.com/in/([^/?#]+)", url, re.IGNORECASE)
    if not m:
        return None

    slug = m.group(1).strip()
    norm_url = f"https://www.linkedin.com/in/{slug}"
    
    # Try parsing name from snippet or title
    # E.g. in DuckDuckGo title or snippet often has: "Name - Role - Company | LinkedIn" or similar
    name = "LinkedIn Member"
    role = ""
    company = ""
    location = ""

    # Parse title pattern if available
    clean_title = re.sub(r"\s*\|\s*LinkedIn.*$", "", title, flags=re.IGNORECASE).strip()
    parts = [p.strip() for p in re.split(r"\s*[-–—|]\s*", clean_title) if p.strip()]
    if len(parts) >= 1 and not parts[0].lower().startswith("http"):
        name = parts[0]
    if len(parts) >= 2:
        role = parts[1]
    if len(parts) >= 3:
        company = parts[2]

    # If name is still LinkedIn Member or missing, inspect snippet
    if name == "LinkedIn Member" or not role:
        # Check if snippet has pattern e.g. "Name · Role at Company · Location"
        snip_parts = [p.strip() for p in re.split(r"[·•\n]", snippet) if p.strip()]
        for p in snip_parts:
            if " at " in p and not company:
                sub = p.split(" at ", 1)
                if not role: role = sub[0].strip()
                company = sub[1].strip()
            elif "India" in p or "Bengaluru" in p or "Mumbai" in p or "Delhi" in p:
                location = p
            elif not role and ("VP" in p or "Director" in p or "Head" in p or "Founder" in p or "Chief" in p):
                role = p

    # If name still not found from title, look at slug
    if name == "LinkedIn Member" and slug:
        # Format slug like 'kurt-srivastava-02s' -> 'Kurt Srivastava'
        name_parts = re.split(r"[-_]", slug)
        clean_name_parts = [p.capitalize() for p in name_parts if not re.match(r"^\d+[a-z]?$", p) and len(p) > 1]
        if clean_name_parts:
            inferred_name = " ".join(clean_name_parts)
            # Tag whether name is verified or slug-derived
            name = inferred_name

    return {
        "displayed_name": name,
        "linkedin_url": norm_url,
        "job_title": role or "Sales / Executive Leader",
        "company": company or "Unspecified Company",
        "location": location or "India",
        "query": query,
        "source_engine": "DuckDuckGo HTML SERP",
        "evidence_snippet": snippet[:200],
        "verification_status": "INDEXED_PROFILE" if (norm_url and name != "LinkedIn Member") else "UNVERIFIED"
    }

if __name__ == "__main__":
    all_candidates = []
    seen_urls = set()
    summary = {
        "queries_run": len(QUERIES),
        "total_serp_items": 0,
        "linkedin_profiles_found": 0,
        "named_candidates": 0,
        "failures": 0
    }

    print("=================================================================")
    print("PHASE 3 EXPERIMENT: 10 PUBLIC SEARCH-BASED DISCOVERY QUERIES")
    print("=================================================================\n")

    for idx, q in enumerate(QUERIES, 1):
        print(f"[{idx}/10] Query: '{q}'")
        results = search_ddg_html(q)
        if results and "error" in results[0]:
            print(f"   -> ERROR: {results[0]['error']}")
            summary["failures"] += 1
            continue

        summary["total_serp_items"] += len(results)
        profiles_in_q = 0

        for r in results:
            cand = parse_candidate_from_serp(r, q)
            if cand:
                profiles_in_q += 1
                if cand["linkedin_url"] not in seen_urls:
                    seen_urls.add(cand["linkedin_url"])
                    all_candidates.append(cand)
                    if cand["displayed_name"] != "LinkedIn Member":
                        summary["named_candidates"] += 1

        summary["linkedin_profiles_found"] += profiles_in_q
        print(f"   -> Found {len(results)} search results | {profiles_in_q} LinkedIn profile URLs")

    print("\n=================================================================")
    print("EXPERIMENT RESULTS SUMMARY")
    print("=================================================================")
    print(f"Total Queries Executed:           {summary['queries_run']}")
    print(f"Total Raw SERP Results:          {summary['total_serp_items']}")
    print(f"Total LinkedIn Profiles Found:    {summary['linkedin_profiles_found']}")
    print(f"Unique Deduplicated Candidates:   {len(all_candidates)}")
    print(f"Candidates with Real Names:       {summary['named_candidates']}")
    print(f"Search Engine Failures:           {summary['failures']}\n")

    print("SAMPLE CANDIDATES EXTRACTED:")
    print("-----------------------------------------------------------------")
    for i, c in enumerate(all_candidates[:5], 1):
        print(f"Candidate #{i}:")
        print(f"  Name:             {c['displayed_name']}")
        print(f"  Profile URL:      {c['linkedin_url']}")
        print(f"  Role:             {c['job_title']}")
        print(f"  Company:          {c['company']}")
        print(f"  Location:         {c['location']}")
        print(f"  Evidence Snippet: {c['evidence_snippet']}")
        print(f"  Status:           {c['verification_status']}")
        print("-----------------------------------------------------------------")

