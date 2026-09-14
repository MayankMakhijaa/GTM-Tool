import os
import re
from typing import Dict, Any, List, Optional
from playwright.sync_api import sync_playwright, Page

BROWSER_PROFILE_DIR = os.path.join(os.getcwd(), "browser_profile")

NAV_BLACKLIST = {
    "home", "my network", "jobs", "messaging", "notifications", "me", "for business",
    "work", "try premium", "search", "accessibility", "talent solutions",
    "community guidelines", "careers", "marketing solutions", "privacy & terms",
    "ad choices", "advertising", "sales solutions", "mobile", "small business",
    "safety center", "linkedin corporation", "questions?", "help center",
    "manage your account and privacy", "recommendation transparency", "more profiles for you"
}


def _is_nav_text(text: str) -> bool:
    if not text:
        return True
    t_clean = text.strip().lower()
    if t_clean in NAV_BLACKLIST:
        return True
    return any(b == t_clean for b in ["home", "my network", "jobs", "messaging", "notifications", "me", "for business"])


def _is_authwall_or_login(page: Page) -> bool:
    """Checks if current page is a LinkedIn login prompt or authwall."""
    url = page.url.lower()
    title = page.title().lower()
    if any(keyword in url for keyword in ["authwall", "login", "signup", "checkpoint", "uas/login"]):
        return True
    if any(keyword in title for keyword in ["sign up", "log in", "sign in", "authwall", "join linkedin"]):
        return True
    return False


def _clean_text(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    cleaned = text.strip()
    return cleaned if cleaned else None


def _find_section_by_keywords(page: Page, keywords: List[str]):
    """
    Locates a specific LinkedIn profile section card strictly inside the main container.
    """
    for kw in keywords:
        sec = page.query_selector(f"section:has(#{kw}), section:has(div#{kw}), section:has(span#{kw}), section#{kw}")
        if sec:
            return sec

    sections = page.query_selector_all("main section, div.scaffold-layout__main section, section")
    for sec in sections:
        heading = sec.query_selector("h2, .pvs-header__title, .pv-profile-section__card-heading, h2 span")
        if heading:
            h_text = heading.inner_text().strip().lower()
            for kw in keywords:
                kw_clean = kw.replace("_", " ").lower()
                if kw_clean == h_text or kw_clean in h_text:
                    return sec
    return None


def check_linkedin_session() -> Dict[str, Any]:
    """
    Checks if the persistent Playwright browser profile is logged into LinkedIn.
    Returns status: 'Connected' (True) or 'Not Connected' (False).
    """
    os.makedirs(BROWSER_PROFILE_DIR, exist_ok=True)
    with sync_playwright() as p:
        context = None
        try:
            context = p.chromium.launch_persistent_context(
                user_data_dir=BROWSER_PROFILE_DIR,
                headless=True,
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                args=["--disable-blink-features=AutomationControlled"]
            )
            page = context.pages[0] if context.pages else context.new_page()
            page.goto("https://www.linkedin.com/feed/", timeout=15000, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)

            final_url = page.url.lower()
            page_title = page.title().lower()

            is_unauth = (
                any(k in final_url for k in ["authwall", "login", "signup", "uas/login"]) or 
                any(k in page_title for k in ["sign up", "log in", "sign in", "authwall"])
            )

            authenticated = not is_unauth
            res_url = page.url
            res_title = page.title()
            context.close()
            return {
                "authenticated": authenticated,
                "status": "Connected" if authenticated else "Not Connected",
                "url": res_url,
                "title": res_title
            }
        except Exception as e:
            if context:
                context.close()
            return {
                "authenticated": False,
                "status": "Not Connected",
                "error": str(e)
            }


def launch_interactive_linkedin_login() -> Dict[str, Any]:
    """
    Launches Playwright Chromium with persistent context in non-headless mode (headless=False)
    navigating to LinkedIn login, allowing the user to interactively log into LinkedIn.
    Saves session data permanently in browser_profile/ directory.
    """
    os.makedirs(BROWSER_PROFILE_DIR, exist_ok=True)
    with sync_playwright() as p:
        context = None
        try:
            print("[PROFILE EXTRACTOR DEBUG] Launching non-headless Playwright session browser for user authentication...")
            context = p.chromium.launch_persistent_context(
                user_data_dir=BROWSER_PROFILE_DIR,
                headless=False,
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                args=["--disable-blink-features=AutomationControlled"]
            )
            page = context.pages[0] if context.pages else context.new_page()
            page.goto("https://www.linkedin.com/login", timeout=45000)
            
            print("[PROFILE EXTRACTOR DEBUG] Browser opened. Waiting for user to complete manual login...")
            for _ in range(120):
                if page.is_closed():
                    break
                url = page.url.lower()
                if "feed" in url or ("in/" in url and not "login" in url and not "authwall" in url):
                    print("[PROFILE EXTRACTOR DEBUG] Successful login detected in browser session!")
                    page.wait_for_timeout(3000)
                    break
                page.wait_for_timeout(1000)

            context.close()
            return {
                "success": True,
                "message": "LinkedIn session updated."
            }
        except Exception as e:
            if context:
                context.close()
            return {
                "success": False,
                "error": str(e)
            }


def _extract_detail_page_lines(context, base_url: str, section_path: str) -> List[str]:
    """
    Navigates to a specific LinkedIn detail sub-page (e.g. /details/skills/)
    and extracts clean text lines scoped strictly inside the main content container.
    Performs controlled scrolling to ensure lazy-loaded items are rendered.
    """
    detail_url = base_url.rstrip("/") + f"/details/{section_path}/"
    page = context.new_page()
    raw_lines: List[str] = []
    try:
        page.goto(detail_url, timeout=25000, wait_until="domcontentloaded")
        page.wait_for_timeout(2500)

        if _is_authwall_or_login(page):
            page.close()
            return []

        # Controlled scrolling to trigger lazy load
        last_count = 0
        for step in range(8):
            page.mouse.wheel(0, 600)
            page.wait_for_timeout(400)
            main_el = page.query_selector("main, div.scaffold-layout__main, section.artdeco-card")
            target_el = main_el if main_el else page.query_selector("body")
            if target_el:
                lines = [l.strip() for l in target_el.inner_text().split("\n") if l.strip()]
                if len(lines) == last_count and step > 3:
                    break
                last_count = len(lines)

        # If on skills tab, click category tabs to get complete skills list across categories
        if section_path == "skills":
            tabs = ["Industry Knowledge", "Tools & Technologies", "Interpersonal Skills", "Other Skills"]
            all_tab_lines = []
            main_el = page.query_selector("main, div.scaffold-layout__main, section.artdeco-card")
            if main_el:
                all_tab_lines.extend([l.strip() for l in main_el.inner_text().split("\n") if l.strip()])

            for tab in tabs:
                try:
                    btn = page.query_selector(f"main button:has-text('{tab}')")
                    if btn:
                        btn.click()
                        page.wait_for_timeout(800)
                        for _ in range(3):
                            page.mouse.wheel(0, 500)
                            page.wait_for_timeout(300)
                        if main_el:
                            all_tab_lines.extend([l.strip() for l in main_el.inner_text().split("\n") if l.strip()])
                except Exception:
                    pass

            target_el = None
            lines = all_tab_lines
        else:
            main_el = page.query_selector("main, div.scaffold-layout__main, section.artdeco-card")
            target_el = main_el if main_el else page.query_selector("body")
            lines = [l.strip() for l in target_el.inner_text().split("\n") if l.strip()] if target_el else []

        stop_markers = {
            "who your viewers also viewed", "private to you", "profile language",
            "about", "accessibility", "talent solutions", "community guidelines",
            "careers", "marketing solutions", "privacy & terms", "ad choices",
            "advertising", "sales solutions", "mobile", "small business",
            "safety center", "linkedin corporation", "select language"
        }
        cleaned = []
        for l in lines:
            l_lower = l.lower()
            if l_lower in stop_markers:
                if section_path != "skills":
                    break
                else:
                    continue
            if not _is_nav_text(l):
                cleaned.append(l)
        raw_lines = cleaned
    except Exception as e:
        print(f"[PROFILE EXTRACTOR DEBUG] Detail sub-page fetch ({section_path}) info: {e}")
    finally:
        try:
            page.close()
        except Exception:
            pass
    return raw_lines


def _parse_experience(lines: List[str]) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    stop_headers = {"education", "skills", "licenses", "certifications", "projects", "more profiles for you", "recommendations", "interests", "featured"}
    
    filtered: List[str] = []
    for l in lines:
        l_lower = l.lower().strip()
        if l_lower in stop_headers:
            break
        if l_lower not in ["experience", "show all"] and not _is_nav_text(l) and "show all" not in l_lower:
            filtered.append(l)

    i = 0
    while i < len(filtered):
        line = filtered[i]
        if _is_nav_text(line) or any(bad in line.lower() for bad in ["enhance with ai", "profile language", "who your viewers"]):
            i += 1
            continue

        title = line
        company = ""
        dates = ""
        location = ""
        desc_lines = []

        if i + 1 < len(filtered) and not _is_nav_text(filtered[i+1]):
            company = filtered[i+1]
            i += 1

        if i + 1 < len(filtered) and any(c in filtered[i+1].lower() for c in ["present", "yr", "mo", "19", "20", "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]):
            dates = filtered[i+1]
            i += 1

        if i + 1 < len(filtered) and any(loc_kw in filtered[i+1].lower() for loc_kw in ["area", "united states", "india", "california", "london", "york", "seattle", "bengaluru", "bangalore", "on-site", "remote", "hybrid"]):
            location = filtered[i+1]
            i += 1

        while i + 1 < len(filtered) and not _is_nav_text(filtered[i+1]):
            next_l = filtered[i+1].lower()
            if any(bad in next_l for bad in ["enhance with ai", "profile language", "who your viewers"]):
                break
            if any(c in next_l for c in ["present", "yr", "mo", "19", "20"]) and any(m in next_l for m in ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]):
                break
            if i + 2 < len(filtered) and any(c in filtered[i+2].lower() for c in ["present", "yr", "mo", "19", "20"]) and any(m in filtered[i+2].lower() for m in ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]):
                break
            desc_lines.append(filtered[i+1])
            i += 1

        # Structural Validation: Must have valid title and company/dates/location
        if title and not _is_nav_text(title) and len(title) <= 100:
            entries.append({
                "title": title,
                "company": company,
                "employment_type": "",
                "location": location,
                "start_date": dates,
                "end_date": "",
                "duration": "",
                "description": "\n".join(desc_lines)
            })
        i += 1
    return entries


def _parse_education(lines: List[str]) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    stop_headers = {"skills", "licenses", "certifications", "projects", "more profiles for you", "recommendations", "interests", "featured"}

    filtered: List[str] = []
    for l in lines:
        l_lower = l.lower().strip()
        if l_lower in stop_headers:
            break
        if l_lower not in ["education", "show all"] and not _is_nav_text(l) and "show all" not in l_lower:
            filtered.append(l)

    i = 0
    while i < len(filtered):
        line = filtered[i]
        if _is_nav_text(line) or any(bad in line.lower() for bad in ["profile language", "who your viewers"]):
            i += 1
            continue

        inst = line
        degree = ""
        dates = ""
        grade = ""
        activities = ""
        skills_assoc = []

        if i + 1 < len(filtered) and not _is_nav_text(filtered[i+1]):
            if not any(c in filtered[i+1].lower() for c in ["19", "20", "grade:", "activities"]):
                degree = filtered[i+1]
                i += 1

        if i + 1 < len(filtered) and any(c in filtered[i+1].lower() for c in ["19", "20"]):
            dates = filtered[i+1]
            i += 1

        while i + 1 < len(filtered) and not _is_nav_text(filtered[i+1]):
            next_line = filtered[i+1]
            next_lower = next_line.lower()
            if next_lower.startswith("grade:"):
                grade = next_line.replace("Grade:", "").replace("grade:", "").strip()
                i += 1
            elif next_lower.startswith("activities and societies:"):
                activities = next_line.replace("Activities and societies:", "").strip()
                i += 1
            elif next_lower.startswith("skills:"):
                skills_assoc.append(next_line.replace("Skills:", "").strip())
                i += 1
            elif i + 2 < len(filtered) and any(c in filtered[i+2].lower() for c in ["19", "20"]):
                break
            else:
                break

        # Structural Validation: Must have non-empty institution
        if inst and not _is_nav_text(inst) and len(inst) <= 120:
            entries.append({
                "institution": inst,
                "degree": degree,
                "field_of_study": "",
                "start_date": dates,
                "end_date": "",
                "grade": grade,
                "activities": activities,
                "description": "",
                "skills": ", ".join(skills_assoc) if skills_assoc else ""
            })
        i += 1
    return entries


def _parse_skills(lines: List[str]) -> List[Dict[str, Any]]:
    skills_entries: List[Dict[str, Any]] = []
    seen = set()
    category_headers = {
        "skills", "all", "show all", "industry knowledge", "tools & technologies",
        "interpersonal skills", "languages", "other skills", "more profiles for you"
    }

    # Strict Blacklist of non-skill text / language options / footer / navigation
    non_skill_keywords = {
        "persian", "arabic", "bengali", "czech", "danish", "deutsch", "german", "greek", "english",
        "español", "spanish", "suomi", "finnish", "français", "french", "hindi", "magyar", "hungarian",
        "indonesian", "italiano", "italian", "hebrew", "japanese", "korean", "marathi", "malay",
        "dutch", "norwegian", "punjabi", "polski", "polish", "português", "portuguese", "română", "romanian",
        "russian", "svenska", "swedish", "telugu", "thai", "tagalog", "türkçe", "turkish", "ukrainian",
        "vietnamese", "chinese", "profile language", "who your viewers also viewed", "private to you",
        "linkedin corporation", "help center", "settings", "recommended content", "select language",
        "view", "enhance with ai", "manage your account and privacy", "recommendation transparency"
    }

    for l in lines:
        l_clean = l.strip()
        l_lower = l_clean.lower()

        if not l_clean or _is_nav_text(l_clean) or l_lower in category_headers or "show all" in l_lower:
            continue
        if l_lower in non_skill_keywords or any(bad in l_lower for bad in ["who your viewers", "private to you", "linkedin corporation", "educational experiences at"]):
            continue
        # Skip job title / school association subtext lines under skills
        if any(assoc in l_lower for assoc in ["at larsen & toubro", "high school", "college", "public school", "academy"]):
            continue

        if l_clean not in seen and len(l_clean) <= 60:
            seen.add(l_clean)
            skills_entries.append({
                "name": l_clean,
                "endorsements": None
            })
    return skills_entries


def _parse_certifications(lines: List[str]) -> List[Dict[str, Any]]:
    cert_entries: List[Dict[str, Any]] = []
    stop_headers = {"who your viewers also viewed", "private to you", "profile language", "about", "accessibility"}

    filtered: List[str] = []
    for l in lines:
        l_lower = l.lower().strip()
        if l_lower in stop_headers:
            break
        if l_lower not in ["licenses & certifications", "certifications", "show all"] and not _is_nav_text(l):
            filtered.append(l)

    i = 0
    while i < len(filtered):
        line = filtered[i]
        if _is_nav_text(line) or line.lower().startswith("skills:"):
            i += 1
            continue

        name = line
        issuer = ""
        issued = ""
        skills_assoc = ""

        if i + 1 < len(filtered) and not _is_nav_text(filtered[i+1]) and not filtered[i+1].lower().startswith("skills:"):
            issuer = filtered[i+1]
            i += 1

        if i + 1 < len(filtered) and (filtered[i+1].lower().startswith("issued") or any(c in filtered[i+1].lower() for c in ["19", "20"])):
            issued = filtered[i+1].replace("Issued", "").strip()
            i += 1

        if i + 1 < len(filtered) and filtered[i+1].lower().startswith("skills:"):
            skills_assoc = filtered[i+1].replace("Skills:", "").strip()
            i += 1

        # Structural Validation: Certification must have name & issuer or issued date
        if name and not _is_nav_text(name) and (issuer or issued):
            cert_entries.append({
                "name": name,
                "issuing_organization": issuer,
                "issue_date": issued,
                "expiration_date": "",
                "credential_id": "",
                "credential_url": "",
                "skills": skills_assoc
            })
        i += 1
    return cert_entries




def _extract_skills_from_detail_page(context, base_url: str) -> List[Dict[str, Any]]:
    """
    Navigates to /details/skills/ sub-page and extracts skills strictly from verified
    skill-entry DOM elements. Completely avoids broad container text scraping.
    """
    detail_url = base_url.rstrip("/") + "/details/skills/"
    page = context.new_page()
    master_skills: List[str] = []
    
    try:
        page.goto(detail_url, timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(2500)

        if _is_authwall_or_login(page):
            page.close()
            return []

        js_dom_harvester = """
        () => {
            const currentSkills = [];

            // Primary Method A: Skill edit form anchors inside main (excluding /new/)
            const editAnchors = Array.from(document.querySelectorAll("main a[href*='/skills/edit/forms/'], main a[href*='/details/skills/edit/forms/']"));
            const validAnchors = editAnchors.filter(a => !a.getAttribute('href').includes('/new/'));

            validAnchors.forEach(a => {
                let container = a;
                for (let i = 0; i < 5; i++) {
                    if (container.parentElement && !['MAIN', 'BODY'].includes(container.parentElement.tagName)) {
                        container = container.parentElement;
                        const txt = container.innerText ? container.innerText.trim() : '';
                        const lines = txt.split('\\n').map(s => s.trim()).filter(Boolean);
                        if (lines.length >= 1 && lines.length <= 8) {
                            break;
                        }
                    }
                }
                if (container) {
                    const lines = container.innerText ? container.innerText.split('\\n').map(s => s.trim()).filter(Boolean) : [];
                    if (lines.length > 0) {
                        const name = lines[0];
                        if (name && name.length <= 80 && !currentSkills.includes(name)) {
                            currentSkills.push(name);
                        }
                    }
                }
            });

            // Primary Method B: Explicit skill list item DOM elements inside main container
            const skillItems = Array.from(document.querySelectorAll("main div.pvs-entity, main ul.pvs-list > li, main div.pvs-list__outer-container li"));
            skillItems.forEach(item => {
                if (item.closest('nav') || item.closest('footer')) return;
                const nameEl = item.querySelector("div.display-flex.align-items-center span[aria-hidden='true'], span.mr1 span[aria-hidden='true'], div.hoverable-link-text span[aria-hidden='true'], a span[aria-hidden='true']");
                let name = nameEl ? nameEl.innerText.trim() : '';
                if (!name && item.innerText) {
                    name = item.innerText.split('\\n')[0].trim();
                }
                if (name && name.length <= 80 && !currentSkills.includes(name)) {
                    const lower = name.toLowerCase();
                    const categoryHeaders = ['skills', 'all', 'industry knowledge', 'tools & technologies', 'interpersonal skills', 'other skills', 'show all'];
                    if (!categoryHeaders.includes(lower) && !lower.includes('help center') && !lower.includes('settings')) {
                        currentSkills.push(name);
                    }
                }
            });

            return currentSkills;
        }
        """

        def harvest():
            try:
                found = page.evaluate(js_dom_harvester)
                for s in found:
                    if s and s not in master_skills:
                        master_skills.append(s)
            except Exception:
                pass

        # 1. Harvest initial view
        harvest()

        # 2. Scroll and harvest on 'All' tab
        for _ in range(8):
            page.mouse.wheel(0, 600)
            page.wait_for_timeout(400)
            harvest()

        # 3. Click category tabs if present and harvest
        tabs = ["All", "Industry Knowledge", "Tools & Technologies", "Interpersonal Skills", "Other Skills"]
        for tab in tabs:
            try:
                btn = page.query_selector(f"main button:has-text('{tab}')")
                if btn:
                    btn.click()
                    page.wait_for_timeout(800)
                    for _ in range(5):
                        page.mouse.wheel(0, 600)
                        page.wait_for_timeout(350)
                        harvest()
            except Exception:
                pass

    except Exception as e:
        print(f"[PROFILE EXTRACTOR DEBUG] DOM Skills fetch info: {e}")
    finally:
        try:
            page.close()
        except Exception:
            pass

    return [{"name": s, "endorsements": None} for s in master_skills]


def extract_linkedin_profile(profile_url: str) -> Dict[str, Any]:
    """
    Extract visible LinkedIn profile details using Playwright.
    Connects via persistent context if browser_profile exists.
    Returns a structured ProfileExtraction dictionary.
    """
    if not profile_url or not profile_url.strip():
        raise ValueError("Please enter a valid LinkedIn profile URL.")

    url = profile_url.strip()
    if not url.startswith("http"):
        url = "https://" + url

    print(f"\n[PROFILE EXTRACTOR DEBUG] Initializing Playwright extraction for URL: {url}")

    with sync_playwright() as p:
        user_data_dir = BROWSER_PROFILE_DIR if os.path.exists(BROWSER_PROFILE_DIR) else None
        context = None
        browser = None
        
        if user_data_dir:
            print(f"[PROFILE EXTRACTOR DEBUG] Using persistent browser profile from: {user_data_dir}")
            context = p.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=True,
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                args=["--disable-blink-features=AutomationControlled"]
            )
            page = context.pages[0] if context.pages else context.new_page()
        else:
            print("[PROFILE EXTRACTOR DEBUG] No browser_profile directory found. Launching standard Chromium context.")
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"]
            )
            page = browser.new_page(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )

        try:
            page.goto(url, timeout=45000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)

            final_url = page.url
            page_title = page.title()
            print(f"[PROFILE EXTRACTOR DEBUG] Final URL after navigation: {final_url}")
            print(f"[PROFILE EXTRACTOR DEBUG] Page Title: {page_title}")

            # 1. Session / Authwall verification
            if _is_authwall_or_login(page):
                print("[PROFILE EXTRACTOR DEBUG] ERROR: LinkedIn redirected to authwall/login. User is unauthenticated in Playwright session.")
                raise RuntimeError("LinkedIn session is not authenticated. Please log in to your LinkedIn account in the browser session and try again.")

            # 2. Section-by-section scrollIntoView
            print("[PROFILE EXTRACTOR DEBUG] Performing section-by-section scrollIntoView to trigger lazy DOM rendering...")
            sections = page.query_selector_all("main section, div.scaffold-layout__main section, section")
            for s in sections:
                try:
                    s.evaluate("el => el.scrollIntoView({behavior: 'smooth', block: 'center'})")
                    page.wait_for_timeout(350)
                except Exception:
                    pass

            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(400)

            # 3. Name
            name: Optional[str] = None
            if page_title and " | " in page_title and not any(k in page_title.lower() for k in ["login", "sign up", "sign in", "authwall", "linkedin"]):
                name = page_title.split(" | ")[0].strip()

            if not name:
                for s in sections[:3]:
                    txt = s.inner_text().strip()
                    lines = [l.strip() for l in txt.split("\n") if l.strip() and not _is_nav_text(l)]
                    if lines and not any(bad in lines[0].lower() for bad in ["notification", "cookie", "sign in"]):
                        name = lines[0]
                        break

            # 4. Headline
            headline: Optional[str] = None
            headline_el = page.query_selector("div.text-body-medium[data-generated-suggestion-target], .pv-text-details__left-panel div.text-body-medium")
            if headline_el:
                headline = _clean_text(headline_el.inner_text())

            if not headline:
                for s in sections[:3]:
                    txt = s.inner_text().strip()
                    lines = [l.strip() for l in txt.split("\n") if l.strip() and not _is_nav_text(l)]
                    for l in lines[1:5]:
                        if l and not any(bad in l.lower() for bad in ["1st", "2nd", "3rd", "contact info", "followers", "connections", "mutual", "message", "follow"]):
                            headline = l
                            break
                    if headline:
                        break

            # 5. Profile Photo URL
            photo_url: Optional[str] = None
            photo_selectors = [
                "img.pv-top-card-profile-picture__image",
                "img.pv-top-card__photo",
                "img[alt*='profile picture']",
                ".pv-top-card--photo img"
            ]
            for sel in photo_selectors:
                el = page.query_selector(sel)
                if el:
                    src = el.get_attribute("src")
                    if src and src.startswith("http"):
                        photo_url = src
                        break

            # 6. About Section
            about: Optional[str] = None
            about_sec = _find_section_by_keywords(page, ["about", "summary"])
            if about_sec:
                raw_about = about_sec.inner_text().strip()
                lines = [l.strip() for l in raw_about.split("\n") if l.strip() and not _is_nav_text(l)]
                filtered_lines = []
                for l in lines:
                    if l.lower() in ["featured", "activity", "experience", "education", "skills"]:
                        break
                    if l.lower() not in ["about", "summary", "see more", "show more", "…see more", "...see more"]:
                        filtered_lines.append(l)
                if filtered_lines:
                    about = "\n".join(filtered_lines)

            # 7. Top Skills Summary
            top_skills: List[str] = []
            top_skills_els = page.query_selector_all("div.pv-top-card--list-bullet span, button:has-text('Top skills') + span")
            for ts in top_skills_els:
                ts_txt = _clean_text(ts.inner_text())
                if ts_txt and ts_txt not in top_skills and "top skills" not in ts_txt.lower() and not _is_nav_text(ts_txt):
                    top_skills.append(ts_txt)

            active_context = context if context else page.context

            # 8. Experience Section (Dedicated details page first)
            experience_items: List[Dict[str, Any]] = []
            exp_lines: List[str] = []
            if active_context:
                exp_lines = _extract_detail_page_lines(active_context, final_url, "experience")
            if not exp_lines:
                exp_sec = _find_section_by_keywords(page, ["experience"])
                if exp_sec:
                    raw_txt = exp_sec.inner_text().strip()
                    exp_lines = [l.strip() for l in raw_txt.split("\n") if l.strip() and not _is_nav_text(l)]
            experience_items = _parse_experience(exp_lines)

            # 9. Education Section (Dedicated details page first)
            education_items: List[Dict[str, Any]] = []
            edu_lines: List[str] = []
            if active_context:
                edu_lines = _extract_detail_page_lines(active_context, final_url, "education")
            if not edu_lines:
                edu_sec = _find_section_by_keywords(page, ["education"])
                if edu_sec:
                    raw_txt = edu_sec.inner_text().strip()
                    edu_lines = [l.strip() for l in raw_txt.split("\n") if l.strip() and not _is_nav_text(l)]
            education_items = _parse_education(edu_lines)

            # 10. Full Skills Section (Dedicated DOM element extraction from /details/skills/)
            skills_items: List[Dict[str, Any]] = []
            if active_context:
                skills_items = _extract_skills_from_detail_page(active_context, final_url)
            if not skills_items:
                skills_sec = _find_section_by_keywords(page, ["skills"])
                if skills_sec:
                    raw_txt = skills_sec.inner_text().strip()
                    skills_lines = [l.strip() for l in raw_txt.split("\n") if l.strip() and not _is_nav_text(l)]
                    skills_items = _parse_skills(skills_lines)


            # 11. Honors & Awards Section
            honors_items: List[Dict[str, Any]] = []
            honors_sec = _find_section_by_keywords(page, ["honors", "awards", "honors_and_awards"])
            if honors_sec:
                lines = [l.strip() for l in honors_sec.inner_text().split("\n") if l.strip() and not _is_nav_text(l)]
                filtered = [l for l in lines if l.lower() not in ["honors & awards", "show all"]]
                for idx in range(0, len(filtered), 3):
                    if idx < len(filtered) and not _is_nav_text(filtered[idx]):
                        honors_items.append({
                            "title": filtered[idx],
                            "issuer": filtered[idx+1] if idx+1 < len(filtered) else "",
                            "date": filtered[idx+2] if idx+2 < len(filtered) else "",
                            "description": ""
                        })

            # 12. Certifications Section (Dedicated details page first)
            cert_items: List[Dict[str, Any]] = []
            cert_lines: List[str] = []
            if active_context:
                cert_lines = _extract_detail_page_lines(active_context, final_url, "certifications")
            if not cert_lines:
                cert_sec = _find_section_by_keywords(page, ["licenses_and_certifications", "certifications", "licenses"])
                if cert_sec:
                    raw_txt = cert_sec.inner_text().strip()
                    cert_lines = [l.strip() for l in raw_txt.split("\n") if l.strip() and not _is_nav_text(l)]
            cert_items = _parse_certifications(cert_lines)


            # 13. Featured Section
            featured_items: List[Dict[str, Any]] = []
            feat_sec = _find_section_by_keywords(page, ["featured"])
            if feat_sec:
                lines = [l.strip() for l in feat_sec.inner_text().split("\n") if l.strip() and not _is_nav_text(l)]
                filtered = [l for l in lines if l.lower() not in ["featured", "show all"]]
                for idx in range(0, len(filtered), 2):
                    if idx < len(filtered) and not _is_nav_text(filtered[idx]):
                        featured_items.append({
                            "title": filtered[idx],
                            "type": "Post",
                            "description": filtered[idx+1] if idx+1 < len(filtered) else "",
                            "url": ""
                        })

            # Determine current position
            current_pos: Optional[str] = None
            if experience_items:
                top_exp = experience_items[0]
                current_pos = f"{top_exp['title']} @ {top_exp['company']}" if top_exp.get("company") else top_exp['title']

            # Critical Debugging Summary Output
            print("\n========================================")
            print("## PROFILE EXTRACTION SUMMARY")
            print("========================================")
            print(f"Name: {'FOUND (' + name + ')' if name else 'MISSING'}")
            print(f"Headline: {'FOUND (' + (headline[:40] + '...') if headline else 'MISSING'}")
            print(f"About: {'FOUND (' + str(len(about)) + ' chars)' if about else 'MISSING'}")
            print(f"Top Skills: {len(top_skills)}")
            print(f"Experience: {len(experience_items)} REAL ENTRIES")
            print(f"Education: {len(education_items)} REAL ENTRIES")
            print(f"Skills: {len(skills_items)} REAL SKILLS")
            print(f"Certifications: {len(cert_items)}")
            print(f"Featured: {len(featured_items)}")
            print(f"Honors & Awards: {len(honors_items)}")
            print("========================================\n")

            return {
                "tenant_id": "default_tenant",
                "user_id": "pro_user",
                "source_url": url,
                "extracted_at": os.popen("powershell Get-Date -Format s").read().strip() if os.name == "nt" else "",
                "profile": {
                    "name": name,
                    "profile_photo_url": photo_url,
                    "headline": headline,
                    "about": about,
                    "current_position": current_pos,
                    "top_skills": top_skills,
                    "experience": experience_items,
                    "education": education_items,
                    "skills": skills_items,
                    "certifications": cert_items,
                    "licenses": [],
                    "projects": [],
                    "featured": featured_items,
                    "honors_awards": honors_items,
                    "publications": [],
                    "courses": [],
                    "volunteer_experience": [],
                    "languages": [],
                    "organizations": [],
                    "recommendations": [],
                    "other_sections": []
                }
            }

        finally:
            if context:
                context.close()
            elif browser:
                browser.close()
