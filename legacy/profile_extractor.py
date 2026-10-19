import os
import re
import time
from typing import Dict, Any, List, Optional, cast
from playwright.sync_api import sync_playwright, Page

from app.integrations.linkedin.voyager_client import get_browser_profile_dir
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


VERIFICATION_PATTERNS = [
    r"^verify\s+in\s+\d+\s+minutes?$",
    r"^verification\s+pending$",
    r"^verify\s+now$",
    r"^get\s+verified$",
    r"^verify\s+your\s+identity$",
    r"^identity\s+verified$",
]

VERIFICATION_EXACT_TEXTS = {
    "verify in 2 minutes",
    "verify in 1 minute",
    "verification pending",
    "get verified",
    "verify now",
    "verified",
    "verify your identity",
    "identity verified"
}


def _is_verification_text(text: Optional[str]) -> bool:
    if not text:
        return False
    t_clean = text.strip().lower()
    if t_clean in VERIFICATION_EXACT_TEXTS:
        return True
    for pat in VERIFICATION_PATTERNS:
        if re.match(pat, t_clean, re.IGNORECASE):
            return True
    return False


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


def check_linkedin_session(user_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Checks if the user has an authenticated LinkedIn session using the canonical DB record.
    Never launches Chromium for ordinary status checks.
    """
    if not user_id:
        return {
            "authenticated": False,
            "status": "Not Connected",
            "linkedin_id": None,
            "name": None,
            "profile_photo_url": None,
            "profile_url": None
        }

    from app.integrations.linkedin.voyager_client import validate_user_session
    from app.database import db_session
    from app.models.all_models import UsersLinkedinDetails

    try:
        details = db_session.query(UsersLinkedinDetails).filter_by(user_id=user_id).first()
        if not details or not details.auth_data_encrypted:
            return {
                "authenticated": False,
                "status": "Not Connected",
                "linkedin_id": None,
                "name": None,
                "profile_photo_url": None,
                "profile_url": None
            }

        validation = validate_user_session(user_id)
        is_auth = validation.get("valid", False)
        photo_url = details.profile_data.get("profile_photo_url") if details.profile_data else None

        return {
            "authenticated": is_auth,
            "status": "Connected" if is_auth else "Not Connected",
            "category": validation.get("category", "unknown"),
            "linkedin_id": details.linkedin_id,
            "name": details.name,
            "profile_photo_url": photo_url,
            "profile_url": details.profile_url
        }
    except Exception as e:
        return {
            "authenticated": False,
            "status": "Not Connected",
            "error": str(e)
        }


def logout_linkedin_session(user_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Clears the persistent browser profile directory and marks connection status DISCONNECTED.
    Preserves encrypted credentials non-destructively unless explicitly deleted.
    """
    if not user_id:
        return {"success": False, "error": "No user ID provided."}

    import shutil
    try:
        profile_dir = get_browser_profile_dir(user_id)
        if os.path.exists(profile_dir):
            shutil.rmtree(profile_dir, ignore_errors=True)

        from app.database import db_session
        from app.models.all_models import UsersLinkedinDetails
        record = db_session.query(UsersLinkedinDetails).filter_by(user_id=user_id).first()
        if record:
            record.connection_status = "DISCONNECTED"
            db_session.commit()

        return {"success": True, "message": "Session logged out successfully."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def launch_interactive_linkedin_login(user_id: int) -> Dict[str, Any]:
    """
    Launches Playwright Chromium with persistent context in non-headless mode (headless=False)
    navigating to LinkedIn login, allowing the user to interactively log into LinkedIn.
    Saves session data permanently in browser_profiles/{user_id}/ directory and encrypts
    cookies into UsersLinkedinDetails in PostgreSQL.
    """
    if not user_id:
        return {"success": False, "message": "Authenticated user_id is required.", "error": "NO_USER_ID"}

    profile_dir = get_browser_profile_dir(user_id)
    os.makedirs(profile_dir, exist_ok=True)
    with sync_playwright() as p:
        context = None
        try:
            print(f"[LinkedIn Connect] Starting browser for user {user_id}")
            context = p.chromium.launch_persistent_context(
                user_data_dir=profile_dir,
                headless=False,
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                args=["--disable-blink-features=AutomationControlled"]
            )
            page = context.pages[0] if context.pages else context.new_page()
            page.goto("https://www.linkedin.com/feed/", timeout=45000, wait_until="domcontentloaded")
            print(f"[LinkedIn Connect] Checking authentication state for user {user_id}...")
            page.wait_for_timeout(2000)

            # Check if already authenticated on feed
            current_url = page.url.lower() if not page.is_closed() else ""
            page_title = page.title().lower() if not page.is_closed() else ""

            is_unauth = (
                any(k in current_url for k in ["authwall", "login", "signup", "uas/login"]) or 
                any(k in page_title for k in ["sign up", "log in", "sign in", "authwall"])
            )

            if is_unauth and not page.is_closed():
                print(f"[LinkedIn Connect] Redirect detected: {current_url}. Clearing stale cookies and navigating to login...")
                try:
                    context.clear_cookies()
                except Exception:
                    pass
                page.goto("https://www.linkedin.com/login", timeout=45000)
                print("[LinkedIn Connect] Waiting for user authentication (up to 5 minutes for 2FA / verification)...")

            li_at = None
            jsessionid = None
            window_closed = False

            # Wait loop: poll context cookies and page status up to 300 seconds
            for _ in range(300):
                if page.is_closed():
                    window_closed = True
                    break

                url = page.url.lower()
                title = page.title().lower()

                # Guard: Must be on an authenticated destination page, not on root or intermediate redirect screens
                is_on_authenticated_destination = (
                    any(k in url for k in ["feed", "in/", "mynetwork", "messaging", "jobs"]) and
                    not any(k in url for k in ["authwall", "login", "signup", "uas/login", "checkpoint", "challenge"]) and
                    not any(k in title for k in ["sign up", "log in", "sign in", "authwall", "checkpoint", "security verification"])
                )

                if not is_on_authenticated_destination:
                    time.sleep(1)
                    continue

                # Verify that LinkedIn's authenticated DOM (navigation bar or feed container) is loaded
                try:
                    has_authenticated_dom = page.locator("nav, .global-nav, #global-nav, .feed-identity-module, header").count() > 0
                except Exception:
                    has_authenticated_dom = False

                if not has_authenticated_dom:
                    time.sleep(1)
                    continue

                # Once authenticated destination and DOM are confirmed:
                try:
                    cookies = context.cookies()
                except Exception:
                    cookies = []

                cur_li_at = None
                cur_jsessionid = None
                for c in cookies:
                    c_name = c.get("name")
                    c_val = (c.get("value") or "").strip()
                    if c_name == "li_at" and c_val:
                        cur_li_at = c_val
                    elif c_name == "JSESSIONID" and c_val:
                        cleaned = c_val.strip('"')
                        if cleaned and not cleaned.startswith("ajax:0000000000000000000"):
                            cur_jsessionid = cleaned

                if cur_li_at and cur_jsessionid:
                    li_at = cur_li_at
                    jsessionid = cur_jsessionid
                    print(f"[LinkedIn Connect] Fresh authentication confirmed on {url}. Both li_at and JSESSIONID captured.")
                    # Allow final cookies to flush to disk before exiting
                    page.wait_for_timeout(2000)
                    break

                if cur_li_at and not cur_jsessionid:
                    # User reached feed, but JSESSIONID hasn't updated from dummy yet. Nudge Voyager endpoint.
                    try:
                        page.evaluate("fetch('/voyager/api/me').catch(e => {})")
                    except Exception:
                        pass
                    time.sleep(1)
                    continue

                time.sleep(1)

            # Final cookie extraction check from context if page was authenticated before closing
            if not (li_at and jsessionid) and context and not window_closed:
                try:
                    cookies = context.cookies()
                    for c in cookies:
                        c_name = c.get("name")
                        c_val = (c.get("value") or "").strip()
                        if c_name == "li_at" and c_val:
                            li_at = c_val
                        elif c_name == "JSESSIONID" and c_val:
                            cleaned = c_val.strip('"')
                            if cleaned and not cleaned.startswith("ajax:0000000000000000000"):
                                jsessionid = cleaned
                except Exception as e:
                    print(f"[LinkedIn Connect] Error reading final cookies from context: {e}")

            capture_success = False
            error_code = None
            error_msg = None

            if li_at and jsessionid:
                try:
                    import json
                    session_cookie = json.dumps({"li_at": li_at, "JSESSIONID": jsessionid})
                    from app.services.onboarding_service import save_linkedin_connection
                    save_linkedin_connection(user_id, session_cookie)
                    capture_success = True
                    print(f"[LinkedIn Connect] Successfully extracted, encrypted, and saved cookies for user {user_id}")
                except Exception as e:
                    capture_success = False
                    error_code = "PERSISTENCE_FAILED"
                    error_msg = f"Failed to persist LinkedIn connection: {str(e)}"
                    print(f"[LinkedIn Connect] {error_msg}")
            else:
                if window_closed:
                    error_code = "WINDOW_CLOSED"
                    error_msg = "Browser window was closed before LinkedIn authentication completed."
                elif li_at and not jsessionid:
                    error_code = "EXTRACTION_FAILED"
                    error_msg = "Authentication succeeded, but the required security token (JSESSIONID) was not captured."
                else:
                    error_code = "NOT_AUTHENTICATED"
                    error_msg = "LinkedIn session was not authenticated. Please log in and reach your home feed."

            try:
                context.close()
            except Exception:
                pass
            time.sleep(0.5)

            if capture_success:
                return {
                    "success": True,
                    "message": "LinkedIn session connected and saved successfully."
                }
            else:
                return {
                    "success": False,
                    "message": error_msg or "LinkedIn session was not authenticated.",
                    "error": error_code or "NOT_AUTHENTICATED"
                }

        except Exception as e:
            print(f"[LinkedIn Connect] Exception occurred: {type(e).__name__} - {str(e)}")
            import traceback
            traceback.print_exc()
            if context:
                try:
                    print("[LinkedIn Connect] Browser cleanup on exception")
                    context.close()
                except Exception:
                    pass
                time.sleep(0.5)
            return {
                "success": False,
                "message": f"Error during LinkedIn login: {str(e)}",
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



def _parse_projects(lines: List[str]) -> List[Dict[str, Any]]:
    entries = []
    filtered = [l for l in lines if not _is_nav_text(l) and l.lower() not in ["projects", "show all", "other viewers"]]
    i = 0
    while i < len(filtered):
        title = filtered[i]
        i += 1
        desc_lines = []
        while i < len(filtered):
            # Heuristic: next project starts when we see a short title followed by a date line or another short line
            if len(filtered[i]) < 100 and i+1 < len(filtered) and any(m in filtered[i+1].lower() for m in ["19", "20", "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec", "associated with"]):
                break
            desc_lines.append(filtered[i])
            i += 1
        entries.append({"title": title, "description": "\n".join(desc_lines)})
    return entries

def _parse_publications(lines: List[str]) -> List[Dict[str, Any]]:
    entries = []
    filtered = [l for l in lines if not _is_nav_text(l) and l.lower() not in ["publications", "show all"]]
    i = 0
    while i < len(filtered):
        title = filtered[i]
        i += 1
        desc_lines = []
        while i < len(filtered):
            if len(filtered[i]) < 100 and i+1 < len(filtered) and any(m in filtered[i+1].lower() for m in ["19", "20", "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]):
                break
            desc_lines.append(filtered[i])
            i += 1
        entries.append({"title": title, "description": "\n".join(desc_lines)})
    return entries

def _parse_courses(lines: List[str]) -> List[Dict[str, Any]]:
    entries = []
    filtered = [l for l in lines if not _is_nav_text(l) and l.lower() not in ["courses", "show all"]]
    for l in filtered:
        entries.append({"title": l})
    return entries

def _parse_volunteer(lines: List[str]) -> List[Dict[str, Any]]:
    entries = []
    filtered = [l for l in lines if not _is_nav_text(l) and l.lower() not in ["volunteer experience", "show all"]]
    i = 0
    while i < len(filtered):
        role = filtered[i]
        i += 1
        org = filtered[i] if i < len(filtered) else ""
        i += 1
        desc_lines = []
        while i < len(filtered):
            if len(filtered[i]) < 100 and i+1 < len(filtered) and len(filtered[i+1]) < 100:
                # possible next volunteer role
                if any(m in filtered[i+1].lower() or (i+2 < len(filtered) and m in filtered[i+2].lower()) for m in ["19", "20", "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]):
                    break
            desc_lines.append(filtered[i])
            i += 1
        entries.append({"role": role, "organization": org, "description": "\n".join(desc_lines)})
    return entries

def _parse_languages(lines: List[str]) -> List[Dict[str, Any]]:
    entries = []
    filtered = [l for l in lines if not _is_nav_text(l) and l.lower() not in ["languages", "show all"]]
    i = 0
    while i < len(filtered):
        lang = filtered[i]
        i += 1
        prof = ""
        if i < len(filtered) and any(p in filtered[i].lower() for p in ["proficiency", "native", "bilingual", "professional", "elementary", "limited"]):
            prof = filtered[i]
            i += 1
        entries.append({"language": lang, "proficiency": prof})
    return entries

def _parse_recommendations(lines: List[str]) -> List[Dict[str, Any]]:
    entries = []
    filtered = [l for l in lines if not _is_nav_text(l) and l.lower() not in ["recommendations", "received", "given", "show all"]]
    i = 0
    while i < len(filtered):
        if "pending" in filtered[i].lower() or "ask for a recommendation" in filtered[i].lower():
            i += 1
            continue
        person = filtered[i]
        i += 1
        desc_lines = []
        while i < len(filtered):
            if len(filtered[i]) < 100 and i+1 < len(filtered) and " · " in filtered[i+1]:
                break
            desc_lines.append(filtered[i])
            i += 1
        if person and desc_lines:
            entries.append({"person": person, "text": "\n".join(desc_lines)})
    return entries
def extract_linkedin_profile_generator(profile_url: str, selected_sections: Optional[List[str]] = None, linkedin_details=None):
    """
    Generator that progressively extracts a LinkedIn profile section by section,
    yielding progress dictionaries for real-time streaming to the UI.
    If selected_sections is provided, only those sections are extracted and yielded.
    If linkedin_details is provided, it uses the decrypted session to authenticate Playwright.
    """
    if not profile_url or not profile_url.strip():
        yield {"event": "error", "error": "Please enter a valid LinkedIn profile URL."}
        return

    url = profile_url.strip()
    if not url.startswith("http"):
        url = "https://" + url

    sel_set = set(s.lower().strip() for s in selected_sections) if selected_sections else None

    yield {"event": "status", "message": "Connecting to LinkedIn..."}

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            from app.integrations.linkedin.voyager_client import decrypt_credential
            if linkedin_details and linkedin_details.auth_data_encrypted:
                decrypted = decrypt_credential(linkedin_details.auth_data_encrypted)
                
                import json
                try:
                    session_data = json.loads(decrypted)
                except json.JSONDecodeError:
                    session_data = {}
                    
                cookies = []
                for k, v in session_data.items():
                    if k in ["li_at", "JSESSIONID"]:
                        cookies.append({
                            "name": k,
                            "value": v.strip('"') if isinstance(v, str) else str(v),
                            "domain": ".linkedin.com",
                            "path": "/"
                        })
                if cookies and context:
                    context.add_cookies(cookies)
                    
            page.goto(url, timeout=45000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)

            final_url = page.url
            page_title = page.title()

            if _is_authwall_or_login(page):
                yield {"event": "error", "error": "LinkedIn session is not authenticated. Please log in to your LinkedIn account in the browser session and try again."}
                return
            
            print("[PROFILE EXTRACTOR] LinkedIn authentication verified")

            sections = page.query_selector_all("main section, div.scaffold-layout__main section, section")
            for s in sections:
                try:
                    s.evaluate("el => el.scrollIntoView({behavior: 'smooth', block: 'center'})")
                    page.wait_for_timeout(250)
                except Exception:
                    pass

            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(250)

            # --- 1. Name & Photo ---
            name: Optional[str] = None
            photo_url: Optional[str] = None
            if sel_set is None or "name" in sel_set:
                yield {"event": "section_start", "section": "name", "label": "Name"}
                if page_title and " | " in page_title and not any(k in page_title.lower() for k in ["login", "sign up", "sign in", "authwall", "linkedin"]):
                    name = page_title.split(" | ")[0].strip()

                if not name:
                    for s in sections[:3]:
                        txt = s.inner_text().strip()
                        lines = [l.strip() for l in txt.split("\n") if l.strip() and not _is_nav_text(l) and not _is_verification_text(l)]
                        if lines and not any(bad in lines[0].lower() for bad in ["notification", "cookie", "sign in"]):
                            name = lines[0]
                            break

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

                yield {"event": "section_complete", "section": "name", "label": "Name", "data": name, "photo_url": photo_url}

            # --- 2. Headline ---
            headline: Optional[str] = None
            if sel_set is None or "headline" in sel_set:
                yield {"event": "section_start", "section": "headline", "label": "Headline"}
                headline_els = page.query_selector_all("div.text-body-medium[data-generated-suggestion-target], .pv-text-details__left-panel div.text-body-medium, div.text-body-medium")
                for el in headline_els:
                    txt = _clean_text(el.inner_text())
                    if txt and not _is_nav_text(txt) and not _is_verification_text(txt):
                        headline = txt
                        break

                if not headline:
                    for s in sections[:3]:
                        txt = s.inner_text().strip()
                        lines = [l.strip() for l in txt.split("\n") if l.strip() and not _is_nav_text(l) and not _is_verification_text(l)]
                        for l in lines[1:5]:
                            if l and not any(bad in l.lower() for bad in ["1st", "2nd", "3rd", "contact info", "followers", "connections", "mutual", "message", "follow"]):
                                headline = l
                                break
                        if headline:
                            break

                yield {"event": "section_complete", "section": "headline", "label": "Headline", "data": headline}

            # --- 3. About & Top Skills ---
            about: Optional[str] = None
            top_skills: List[str] = []
            if sel_set is None or "about" in sel_set:
                yield {"event": "section_start", "section": "about", "label": "About"}
                about_sec = _find_section_by_keywords(page, ["about", "summary"])
                if about_sec:
                    raw_about = about_sec.inner_text().strip()
                    lines = [l.strip() for l in raw_about.split("\n") if l.strip() and not _is_nav_text(l) and not _is_verification_text(l)]
                    filtered_lines = []
                    for l in lines:
                        if l.lower() in ["featured", "activity", "experience", "education", "skills"]:
                            break
                        if l.lower() not in ["about", "summary", "see more", "show more", "…see more", "...see more"]:
                            filtered_lines.append(l)
                    if filtered_lines:
                        about = "\n".join(filtered_lines)

                top_skills_els = page.query_selector_all("div.pv-top-card--list-bullet span, button:has-text('Top skills') + span")
                for ts in top_skills_els:
                    ts_txt = _clean_text(ts.inner_text())
                    if ts_txt and ts_txt not in top_skills and "top skills" not in ts_txt.lower() and not _is_nav_text(ts_txt):
                        top_skills.append(ts_txt)

                yield {"event": "section_complete", "section": "about", "label": "About", "data": about, "top_skills": top_skills}

            active_context = context if context else page.context

            # --- 4. Experience ---
            experience_items: List[Dict[str, Any]] = []
            if sel_set is None or "experience" in sel_set:
                yield {"event": "section_start", "section": "experience", "label": "Experience"}
                exp_lines: List[str] = []
                if active_context:
                    exp_lines = _extract_detail_page_lines(active_context, final_url, "experience")
                if not exp_lines:
                    exp_sec = _find_section_by_keywords(page, ["experience"])
                    if exp_sec:
                        raw_txt = exp_sec.inner_text().strip()
                        exp_lines = [l.strip() for l in raw_txt.split("\n") if l.strip() and not _is_nav_text(l)]
                experience_items = _parse_experience(exp_lines)

                yield {"event": "section_complete", "section": "experience", "label": "Experience", "data": experience_items}

            # --- 5. Education ---
            education_items: List[Dict[str, Any]] = []
            if sel_set is None or "education" in sel_set:
                yield {"event": "section_start", "section": "education", "label": "Education"}
                edu_lines: List[str] = []
                if active_context:
                    edu_lines = _extract_detail_page_lines(active_context, final_url, "education")
                if not edu_lines:
                    edu_sec = _find_section_by_keywords(page, ["education"])
                    if edu_sec:
                        raw_txt = edu_sec.inner_text().strip()
                        edu_lines = [l.strip() for l in raw_txt.split("\n") if l.strip() and not _is_nav_text(l)]
                education_items = _parse_education(edu_lines)

                yield {"event": "section_complete", "section": "education", "label": "Education", "data": education_items}

            # --- 6. Skills ---
            skills_items: List[Dict[str, Any]] = []
            if sel_set is None or "skills" in sel_set:
                yield {"event": "section_start", "section": "skills", "label": "Skills"}
                if active_context:
                    skills_items = _extract_skills_from_detail_page(active_context, final_url)
                if not skills_items:
                    skills_sec = _find_section_by_keywords(page, ["skills"])
                    if skills_sec:
                        raw_txt = skills_sec.inner_text().strip()
                        skills_lines = [l.strip() for l in raw_txt.split("\n") if l.strip() and not _is_nav_text(l)]
                        skills_items = _parse_skills(skills_lines)

                yield {"event": "section_complete", "section": "skills", "label": "Skills", "data": skills_items}

            # --- 7. Certifications ---
            cert_items: List[Dict[str, Any]] = []
            if sel_set is None or "certifications" in sel_set:
                yield {"event": "section_start", "section": "certifications", "label": "Certifications"}
                cert_lines: List[str] = []
                if active_context:
                    cert_lines = _extract_detail_page_lines(active_context, final_url, "certifications")
                if not cert_lines:
                    cert_sec = _find_section_by_keywords(page, ["licenses_and_certifications", "certifications", "licenses"])
                    if cert_sec:
                        raw_txt = cert_sec.inner_text().strip()
                        cert_lines = [l.strip() for l in raw_txt.split("\n") if l.strip() and not _is_nav_text(l)]
                cert_items = _parse_certifications(cert_lines)

                yield {"event": "section_complete", "section": "certifications", "label": "Certifications", "data": cert_items}

            # --- 8. Honors & Featured (Original) ---
            featured_items: List[Dict[str, Any]] = []
            honors_items: List[Dict[str, Any]] = []
            try:
                honors_sec = _find_section_by_keywords(page, ["honors", "awards", "honors_and_awards"])
                if honors_sec:
                    lines = [l.strip() for l in honors_sec.inner_text().split("\\n") if l.strip() and not _is_nav_text(l)]
                    filtered = [l for l in lines if l.lower() not in ["honors & awards", "show all"]]
                    for idx in range(0, len(filtered), 3):
                        if idx < len(filtered) and not _is_nav_text(filtered[idx]):
                            honors_items.append({
                                "title": filtered[idx],
                                "issuer": filtered[idx+1] if idx+1 < len(filtered) else "",
                                "date": filtered[idx+2] if idx+2 < len(filtered) else "",
                                "description": ""
                            })

                feat_sec = _find_section_by_keywords(page, ["featured"])
                if feat_sec:
                    lines = [l.strip() for l in feat_sec.inner_text().split("\\n") if l.strip() and not _is_nav_text(l)]
                    filtered = [l for l in lines if l.lower() not in ["featured", "show all"]]
                    for idx in range(0, len(filtered), 2):
                        if idx < len(filtered) and not _is_nav_text(filtered[idx]):
                            featured_items.append({
                                "title": filtered[idx],
                                "type": "Post",
                                "description": filtered[idx+1] if idx+1 < len(filtered) else "",
                                "url": ""
                            })
            except Exception as e:
                print(f"Failed to extract honors/featured: {e}")

            # --- 9. Missing Sections (Projects, Publications, Courses, Volunteer, Languages, Recommendations) ---
            
            def safe_extract_section(name, detail_path, parse_fn):
                items = []
                yield_payload = {"event": "section_complete", "section": name, "label": name.capitalize(), "data": []}
                try:
                    if sel_set is None or name in sel_set:
                        yield {"event": "section_start", "section": name, "label": name.capitalize()}
                        lines = _extract_detail_page_lines(active_context, final_url, detail_path)
                        if lines:
                            items = parse_fn(lines)
                        yield_payload["data"] = items
                except Exception as e:
                    print(f"Failed to extract {name}: {e}")
                    yield_payload["error"] = str(e)
                finally:
                    if sel_set is None or name in sel_set:
                        yield yield_payload
                return items
                
            projects_items = yield from safe_extract_section("projects", "projects", _parse_projects)
            publications_items = yield from safe_extract_section("publications", "publications", _parse_publications)
            courses_items = yield from safe_extract_section("courses", "courses", _parse_courses)
            volunteer_items = yield from safe_extract_section("volunteer_experience", "volunteering-experiences", _parse_volunteer)
            languages_items = yield from safe_extract_section("languages", "languages", _parse_languages)
            recommendations_items = yield from safe_extract_section("recommendations", "recommendations", _parse_recommendations)


            current_pos: Optional[str] = None
            if experience_items:
                top_exp = experience_items[0]
                current_pos = f"{top_exp['title']} @ {top_exp['company']}" if top_exp.get("company") else top_exp['title']

            full_profile = {
                "tenant_id": "default_tenant",
                "user_id": "pro_user",
                "source_url": url,
                "selected_sections": list(sel_set) if sel_set is not None else None,
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
                    "projects": projects_items,
                    "featured": featured_items,
                    "honors_awards": honors_items,
                    "publications": publications_items,
                    "courses": courses_items,
                    "volunteer_experience": volunteer_items,
                    "languages": languages_items,
                    "organizations": [],
                    "recommendations": recommendations_items,
                    "other_sections": []
                }
            }

            yield {"event": "complete", "full_profile": full_profile}

        finally:
            if context:
                context.close()
            elif browser:
                browser.close()


def extract_linkedin_profile(profile_url: str, linkedin_details=None) -> Dict[str, Any]:
    """
    Extract visible LinkedIn profile details using Playwright.
    Wraps the generator for non-streaming callers.
    """
    full_data = None
    for event in extract_linkedin_profile_generator(profile_url, linkedin_details=linkedin_details):
        if event.get("event") == "error":
            # raise RuntimeError using stringified error to be safe
            raise RuntimeError(str(event.get("error")))
        elif event.get("event") == "complete":
            full_data = cast(Dict[str, Any], event.get("full_profile"))
    if not full_data:
        raise RuntimeError("Profile extraction completed without producing output data.")
    return full_data
