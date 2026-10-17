import re
from typing import Optional, Dict, Any

# Canonical casing for high-value business terms and acronyms
CANONICAL_BUSINESS_TERMS: Dict[str, str] = {
    "saas": "SaaS",
    "b2b": "B2B",
    "b2c": "B2C",
    "revops": "RevOps",
    "devops": "DevOps",
    "fintech": "FinTech",
    "devtools": "DevTools",
    "crm": "CRM",
    "tam": "TAM",
    "arr": "ARR",
    "mrr": "MRR",
    "acv": "ACV",
    "sdr": "SDR",
    "sdrs": "SDRs",
    "bdr": "BDR",
    "bdrs": "BDRs",
    "ae": "AE",
    "aes": "AEs",
    "gtm": "GTM",
    "icp": "ICP",
    "ceo": "CEO",
    "cto": "CTO",
    "cro": "CRO",
    "cfo": "CFO",
    "coo": "COO",
    "vp": "VP",
    "smb": "SMB",
    "ai": "AI",
    "ml": "ML",
    "api": "API",
    "apis": "APIs",
    "paas": "PaaS",
    "iaas": "IaaS",
    "plg": "PLG",
    "cac": "CAC",
    "ltv": "LTV",
    "roi": "ROI",
    "qoq": "QoQ",
    "yoy": "YoY",
    "it": "IT",
    "hr": "HR"
}

# Common spelling typos in B2B/GTM domains mapped to correct form
TYPO_CORRECTIONS: Dict[str, str] = {
    "enterpise": "enterprise",
    "enterpirse": "enterprise",
    "enteprise": "enterprise",
    "midmarket": "Mid-Market",
    "mid-market": "Mid-Market",
    "stratgy": "strategy",
    "automatn": "automation",
    "automtion": "automation",
    "enricment": "enrichment",
    "enrichmnt": "enrichment",
    "managment": "management",
    "foudner": "founder",
    "fundr": "founder",
    "markting": "marketing",
    "oppurtunity": "opportunity",
    "prospectng": "prospecting",
    "outboud": "outbound",
    "inboud": "inbound"
}

ALL_SUGGESTIONS: Dict[str, str] = {
    **{k.lower(): v for k, v in CANONICAL_BUSINESS_TERMS.items()},
    **{k.lower(): v for k, v in TYPO_CORRECTIONS.items()}
}


def get_spelling_suggestion(text: Optional[str]) -> Optional[str]:
    """
    Analyzes text and returns an advisory suggestion string if any recognized business
    terms or common domain typos can be improved.
    Preserves acronyms like 'SaaS', 'B2B', 'RevOps'.
    Never silently modifies the original text.
    Returns None if no improvements are suggested or if text is already canonical.
    """
    if not text or not isinstance(text, str) or not text.strip():
        return None

    original = text.strip()

    # Tokenize word-by-word while preserving delimiters
    def replace_word(match):
        word = match.group(0)
        lower_word = word.lower()
        if lower_word in ALL_SUGGESTIONS:
            target = ALL_SUGGESTIONS[lower_word]
            # If word is already exactly matching the target, keep it
            return target
        return word

    suggested = re.sub(r'\b[A-Za-z0-9\'-]+\b', replace_word, original)

    if suggested != original:
        return suggested

    return None


def get_icp_field_advisories(data: Dict[str, Any]) -> Dict[str, str]:
    """
    Generates non-destructive advisory suggestions for relevant ICP text fields.
    Does not mutate data.
    """
    advisories: Dict[str, str] = {}
    check_fields = [
        "target_customer",
        "industry",
        "target_jobs_roles",
        "keywords",
        "exclusions"
    ]

    for field in check_fields:
        val = data.get(field)
        if isinstance(val, str) and val.strip():
            suggestion = get_spelling_suggestion(val)
            if suggestion:
                advisories[field] = suggestion

    return advisories
