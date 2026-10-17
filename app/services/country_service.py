import difflib
import re
from typing import Optional, List, Tuple, Dict

# Standard ISO 3166-1 Canonical Country Names (all 195 UN member/observer states + key territories)
CANONICAL_COUNTRIES: List[str] = [
    "Afghanistan", "Albania", "Algeria", "Andorra", "Angola", "Antigua and Barbuda",
    "Argentina", "Armenia", "Australia", "Austria", "Azerbaijan", "Bahamas",
    "Bahrain", "Bangladesh", "Barbados", "Belarus", "Belgium", "Belize",
    "Benin", "Bhutan", "Bolivia", "Bosnia and Herzegovina", "Botswana", "Brazil",
    "Brunei", "Bulgaria", "Burkina Faso", "Burundi", "Cabo Verde", "Cambodia",
    "Cameroon", "Canada", "Central African Republic", "Chad", "Chile", "China",
    "Colombia", "Comoros", "Congo (Congo-Brazzaville)", "Costa Rica", "Croatia",
    "Cuba", "Cyprus", "Czech Republic", "Democratic Republic of the Congo",
    "Denmark", "Djibouti", "Dominica", "Dominican Republic", "Ecuador", "Egypt",
    "El Salvador", "Equatorial Guinea", "Eritrea", "Estonia", "Eswatini", "Ethiopia",
    "Fiji", "Finland", "France", "Gabon", "Gambia", "Georgia", "Germany", "Ghana",
    "Greece", "Grenada", "Guatemala", "Guinea", "Guinea-Bissau", "Guyana", "Haiti",
    "Honduras", "Hungary", "Iceland", "India", "Indonesia", "Iran", "Iraq", "Ireland",
    "Israel", "Italy", "Ivory Coast", "Jamaica", "Japan", "Jordan", "Kazakhstan",
    "Kenya", "Kiribati", "Kuwait", "Kyrgyzstan", "Laos", "Latvia", "Lebanon",
    "Lesotho", "Liberia", "Libya", "Liechtenstein", "Lithuania", "Luxembourg",
    "Madagascar", "Malawi", "Malaysia", "Maldives", "Mali", "Malta",
    "Marshall Islands", "Mauritania", "Mauritius", "Mexico", "Micronesia", "Moldova",
    "Monaco", "Mongolia", "Montenegro", "Morocco", "Mozambique", "Myanmar", "Namibia",
    "Nauru", "Nepal", "Netherlands", "New Zealand", "Nicaragua", "Niger", "Nigeria",
    "North Korea", "North Macedonia", "Norway", "Oman", "Pakistan", "Palau",
    "Palestine", "Panama", "Papua New Guinea", "Paraguay", "Peru", "Philippines",
    "Poland", "Portugal", "Qatar", "Romania", "Russia", "Rwanda",
    "Saint Kitts and Nevis", "Saint Lucia", "Saint Vincent and the Grenadines",
    "Samoa", "San Marino", "Sao Tome and Principe", "Saudi Arabia", "Senegal",
    "Serbia", "Seychelles", "Sierra Leone", "Singapore", "Slovakia", "Slovenia",
    "Solomon Islands", "Somalia", "South Africa", "South Korea", "South Sudan",
    "Spain", "Sri Lanka", "Sudan", "Suriname", "Sweden", "Switzerland", "Syria",
    "Taiwan", "Tajikistan", "Tanzania", "Thailand", "Timor-Leste", "Togo", "Tonga",
    "Trinidad and Tobago", "Tunisia", "Turkey", "Turkmenistan", "Tuvalu", "Uganda",
    "Ukraine", "United Arab Emirates", "United Kingdom", "United States", "Uruguay",
    "Uzbekistan", "Vanuatu", "Vatican City", "Venezuela", "Vietnam", "Yemen",
    "Zambia", "Zimbabwe"
]

CANONICAL_COUNTRY_MAP: Dict[str, str] = {
    c.lower(): c for c in CANONICAL_COUNTRIES
}

# Aliases and acronyms mapped to their canonical country
COUNTRY_ALIASES: Dict[str, str] = {
    "usa": "United States",
    "us": "United States",
    "u.s.": "United States",
    "u.s.a.": "United States",
    "united states of america": "United States",
    "uk": "United Kingdom",
    "u.k.": "United Kingdom",
    "great britain": "United Kingdom",
    "britain": "United Kingdom",
    "uae": "United Arab Emirates",
    "u.a.e.": "United Arab Emirates",
    "emirates": "United Arab Emirates",
    "south korea": "South Korea",
    "korea, republic of": "South Korea",
    "republic of korea": "South Korea",
    "rok": "South Korea",
    "north korea": "North Korea",
    "dprk": "North Korea",
    "russia": "Russia",
    "russian federation": "Russia",
    "vietnam": "Vietnam",
    "viet nam": "Vietnam",
    "czech republic": "Czech Republic",
    "czechia": "Czech Republic",
    "taiwan": "Taiwan",
    "taiwan, province of china": "Taiwan",
    "holland": "Netherlands",
    "the netherlands": "Netherlands",
    "ivory coast": "Ivory Coast",
    "côte d'ivoire": "Ivory Coast",
    "cote d'ivoire": "Ivory Coast",
    "myanmar": "Myanmar",
    "burma": "Myanmar"
}

# Known non-country entities mapped to (entity_type, suggested_country_or_recommendation)
NON_COUNTRY_GEOGRAPHIES: Dict[str, Tuple[str, Optional[str]]] = {
    # Cities
    "bengaluru": ("city", "India"),
    "bangalore": ("city", "India"),
    "mumbai": ("city", "India"),
    "bombay": ("city", "India"),
    "delhi": ("city", "India"),
    "new delhi": ("city", "India"),
    "hyderabad": ("city", "India"),
    "chennai": ("city", "India"),
    "madras": ("city", "India"),
    "pune": ("city", "India"),
    "kolkata": ("city", "India"),
    "calcutta": ("city", "India"),
    "london": ("city", "United Kingdom"),
    "manchester": ("city", "United Kingdom"),
    "birmingham": ("city", "United Kingdom"),
    "edinburgh": ("city", "United Kingdom"),
    "new york": ("city", "United States"),
    "nyc": ("city", "United States"),
    "new york city": ("city", "United States"),
    "san francisco": ("city", "United States"),
    "sf": ("city", "United States"),
    "los angeles": ("city", "United States"),
    "la": ("city", "United States"),
    "chicago": ("city", "United States"),
    "seattle": ("city", "United States"),
    "austin": ("city", "United States"),
    "boston": ("city", "United States"),
    "toronto": ("city", "Canada"),
    "vancouver": ("city", "Canada"),
    "montreal": ("city", "Canada"),
    "sydney": ("city", "Australia"),
    "melbourne": ("city", "Australia"),
    "brisbane": ("city", "Australia"),
    "berlin": ("city", "Germany"),
    "munich": ("city", "Germany"),
    "frankfurt": ("city", "Germany"),
    "paris": ("city", "France"),
    "tokyo": ("city", "Japan"),
    "dubai": ("city", "United Arab Emirates"),
    "abu dhabi": ("city", "United Arab Emirates"),
    "dublin": ("city", "Ireland"),
    "amsterdam": ("city", "Netherlands"),

    # States / Provinces / Territories
    "california": ("state", "United States"),
    "texas": ("state", "United States"),
    "new york state": ("state", "United States"),
    "florida": ("state", "United States"),
    "washington": ("state", "United States"),
    "illinois": ("state", "United States"),
    "ontario": ("province", "Canada"),
    "quebec": ("province", "Canada"),
    "british columbia": ("province", "Canada"),
    "karnataka": ("state", "India"),
    "maharashtra": ("state", "India"),
    "tamil nadu": ("state", "India"),
    "delhi ncr": ("region/state", "India"),
    "gujarat": ("state", "India"),
    "haryana": ("state", "India"),
    "bavaria": ("state", "Germany"),
    "new south wales": ("state", "Australia"),
    "victoria": ("state", "Australia"),
    "scotland": ("constituent country", "United Kingdom"),
    "england": ("constituent country", "United Kingdom"),
    "wales": ("constituent country", "United Kingdom"),
    "northern ireland": ("constituent country", "United Kingdom"),

    # Continents & Macro-Regions
    "apac": ("macro-region", "Singapore, India, Japan, or Australia"),
    "asia-pacific": ("macro-region", "Singapore, India, Japan, or Australia"),
    "emea": ("macro-region", "United Kingdom, Germany, or United Arab Emirates"),
    "latam": ("macro-region", "Brazil, Mexico, or Colombia"),
    "latin america": ("macro-region", "Brazil, Mexico, or Colombia"),
    "north america": ("continent", "United States or Canada"),
    "na": ("continent/acronym", "United States or Canada"),
    "south america": ("continent", "Brazil, Argentina, or Chile"),
    "europe": ("continent", "United Kingdom, Germany, or France"),
    "eu": ("trade union/region", "Germany, France, or Netherlands"),
    "european union": ("trade union/region", "Germany, France, or Netherlands"),
    "western europe": ("macro-region", "United Kingdom, Germany, or France"),
    "eastern europe": ("macro-region", "Poland, Romania, or Czech Republic"),
    "asia": ("continent", "India, Singapore, or Japan"),
    "africa": ("continent", "South Africa, Nigeria, or Kenya"),
    "middle east": ("macro-region", "United Arab Emirates or Saudi Arabia"),
    "mena": ("macro-region", "United Arab Emirates or Saudi Arabia"),
    "gcc": ("macro-region", "United Arab Emirates or Saudi Arabia"),
    "asean": ("macro-region", "Singapore, Indonesia, or Malaysia"),
    "southeast asia": ("macro-region", "Singapore, Indonesia, or Malaysia"),
    "nordics": ("macro-region", "Sweden, Norway, or Denmark"),
    "scandinavia": ("macro-region", "Sweden, Norway, or Denmark"),
    "benelux": ("macro-region", "Belgium, Netherlands, or Luxembourg"),
    "dach": ("macro-region", "Germany, Austria, or Switzerland"),
    "global": ("global scope", "individual target countries"),
    "worldwide": ("global scope", "individual target countries")
}

# Legitimate B2B / GTM regional target markets supported for ICP definition
LEGITIMATE_REGIONAL_MARKETS: Dict[str, str] = {
    # North America
    "north america (us & canada)": "North America (US & Canada)",
    "north america (us and canada)": "North America (US & Canada)",
    "north america": "North America",
    "na": "North America",

    # Europe
    "western europe": "Western Europe",
    "eastern europe": "Eastern Europe",
    "central & eastern europe": "Central & Eastern Europe",
    "central and eastern europe": "Central & Eastern Europe",
    "europe": "Europe",
    "european union": "European Union",
    "eu": "European Union",
    "nordics": "Nordics",
    "scandinavia": "Scandinavia",
    "benelux": "Benelux",
    "dach": "DACH",
    "uk & ireland": "UK & Ireland",
    "uk and ireland": "UK & Ireland",
    "united kingdom & ireland": "UK & Ireland",
    "united kingdom and ireland": "UK & Ireland",

    # Asia-Pacific
    "apac": "APAC",
    "asia-pacific": "Asia-Pacific",
    "asia pacific": "Asia-Pacific",
    "asean": "ASEAN",
    "southeast asia": "Southeast Asia",
    "anz": "ANZ",
    "australia & new zealand": "ANZ",
    "australia and new zealand": "ANZ",

    # Middle East & Africa
    "emea": "EMEA",
    "middle east": "Middle East",
    "mena": "MENA",
    "gcc": "GCC",

    # Latin America
    "latam": "LATAM",
    "latin america": "Latin America",
    "south america": "South America",

    # Global
    "global": "Global",
    "worldwide": "Worldwide"
}

LEGITIMATE_REGIONS: List[str] = list(dict.fromkeys(LEGITIMATE_REGIONAL_MARKETS.values()))


def resolve_canonical_country(raw_text: str) -> Optional[str]:
    """
    Resolves raw_text to its canonical country name case-insensitively,
    including exact aliases (e.g. 'USA' -> 'United States', 'india' -> 'India').
    Returns None if raw_text is not a direct canonical country or recognized alias.
    """
    if not raw_text:
        return None
    cleaned = raw_text.strip()
    key = cleaned.lower()
    if key in CANONICAL_COUNTRY_MAP:
        return CANONICAL_COUNTRY_MAP[key]
    if key in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[key]
    return None


def resolve_legitimate_region(raw_text: str) -> Optional[str]:
    """
    Resolves raw_text to a recognized legitimate regional target market (case-insensitively).
    Returns canonical display string, or None if not recognized.
    """
    if not raw_text:
        return None
    cleaned = raw_text.strip()
    return LEGITIMATE_REGIONAL_MARKETS.get(cleaned.lower())


def get_country_typo_suggestion(raw_text: str) -> Optional[str]:
    """
    Finds close matching canonical country for typos (e.g. 'Indai' -> 'India', 'Unted States' -> 'United States').
    Uses difflib with a 0.6 similarity threshold.
    """
    if not raw_text or len(raw_text.strip()) < 3:
        return None
    cleaned = raw_text.strip()
    # Check against canonical country names
    matches = difflib.get_close_matches(cleaned, CANONICAL_COUNTRIES, n=1, cutoff=0.6)
    if matches:
        return matches[0]

    # Also check case-insensitive match against lower list
    lower_map = {c.lower(): c for c in CANONICAL_COUNTRIES}
    lower_matches = difflib.get_close_matches(cleaned.lower(), list(lower_map.keys()), n=1, cutoff=0.6)
    if lower_matches:
        return lower_map[lower_matches[0]]

    return None


def validate_single_country(raw_name: str) -> str:
    """
    Validates a single country token strictly:
    1. Direct match / alias -> returns canonical country name.
    2. Known city, state, or region -> raises actionable ValueError explaining the entity type.
    3. Typo with high similarity -> raises actionable ValueError with suggestion.
    4. Arbitrary unrecognized text -> raises actionable ValueError.
    """
    if not raw_name or not raw_name.strip():
        raise ValueError("Location country name cannot be empty.")

    cleaned = raw_name.strip()
    key = cleaned.lower()

    # 1. Direct canonical or alias match
    canonical = resolve_canonical_country(cleaned)
    if canonical:
        return canonical

    # 2. Known non-country entity check
    if key in NON_COUNTRY_GEOGRAPHIES:
        entity_type, rec = NON_COUNTRY_GEOGRAPHIES[key]
        rec_str = f" (e.g., {rec})" if rec else ""
        raise ValueError(
            f"Invalid location '{cleaned}': '{cleaned}' is a {entity_type}, not a country. "
            f"Please specify a recognized country{rec_str}."
        )

    # 3. Check for typo suggestion
    suggestion = get_country_typo_suggestion(cleaned)
    if suggestion:
        raise ValueError(
            f"Invalid country '{cleaned}'. Did you mean '{suggestion}'?"
        )

    # 4. Fallback generic rejection
    raise ValueError(
        f"Invalid country '{cleaned}'. Please specify a recognized country name "
        f"(e.g., India, United States, United Kingdom, Singapore, Germany). "
        f"Cities, states, regions, and continents are not accepted."
    )


def validate_single_location(raw_name: str) -> str:
    """
    Validates a single location target for ICP (country or legitimate regional market):
    1. Direct canonical country or country alias -> returns canonical country name.
    2. Recognized legitimate regional target market -> returns canonical region name.
    3. Known city, state, or province check -> raises actionable ValueError explaining the entity type.
    4. Typo in country or region -> raises actionable ValueError with suggestion.
    5. Arbitrary unrecognized text -> raises actionable ValueError.
    """
    if not raw_name or not raw_name.strip():
        raise ValueError("Location target entry cannot be empty.")

    cleaned = raw_name.strip()
    key = cleaned.lower()

    # 1. Canonical country or country alias
    country = resolve_canonical_country(cleaned)
    if country:
        return country

    # 2. Legitimate regional target market
    region = resolve_legitimate_region(cleaned)
    if region:
        return region

    # 3. Known city, state, or province check
    if key in NON_COUNTRY_GEOGRAPHIES:
        entity_type, rec = NON_COUNTRY_GEOGRAPHIES[key]
        if entity_type in ("city", "state", "province", "region/state", "constituent country"):
            rec_str = f" (e.g., {rec})" if rec else ""
            raise ValueError(
                f"Invalid location '{cleaned}': '{cleaned}' is a {entity_type}, not a country or regional market. "
                f"Please specify a recognized country{rec_str} or legitimate regional target market."
            )

    # 4. Check for typo suggestion in countries
    suggestion = get_country_typo_suggestion(cleaned)
    if suggestion:
        raise ValueError(
            f"Invalid country '{cleaned}'. Did you mean '{suggestion}'?"
        )

    # 5. Check for typo suggestion in regional markets
    reg_matches = difflib.get_close_matches(key, list(LEGITIMATE_REGIONAL_MARKETS.keys()), n=1, cutoff=0.7)
    if reg_matches:
        rec_reg = LEGITIMATE_REGIONAL_MARKETS[reg_matches[0]]
        raise ValueError(
            f"Invalid location '{cleaned}'. Did you mean '{rec_reg}'?"
        )

    # 6. Fallback rejection
    raise ValueError(
        f"Invalid location '{cleaned}'. Please specify a recognized country "
        f"(e.g., India, United States, United Kingdom, Singapore, Germany) "
        f"or legitimate regional target market (e.g., North America (US & Canada), Western Europe, EMEA, APAC)."
    )


def split_location_tokens(location_input: str) -> List[str]:
    """
    Splits location input string by commas, but preserves commas inside parentheses
    such as 'North America (US & Canada)' or 'North America (US, Canada)'.
    """
    if not location_input:
        return []
    tokens = re.split(r',\s*(?![^()]*\))', str(location_input).strip())
    return [t.strip() for t in tokens if t.strip()]


def validate_country_string(location_input: Optional[str]) -> str:
    """
    Validates location string for UsersICP.
    Accepts comma-separated sovereign countries and legitimate regional target markets.
    Returns canonical, deduplicated comma-separated string
    (e.g. 'North America (US & Canada), Western Europe, Singapore').
    Empty input returns empty string.
    """
    if location_input is None:
        return ""

    raw_str = str(location_input).strip()
    if not raw_str:
        return ""

    tokens = split_location_tokens(raw_str)
    if not tokens:
        return ""

    validated: List[str] = []
    seen = set()

    for token in tokens:
        canonical = validate_single_location(token)
        if canonical.lower() not in seen:
            seen.add(canonical.lower())
            validated.append(canonical)

    return ", ".join(validated)


# Backward-compatible alias
validate_location_string = validate_country_string


def search_countries(query: str, limit: int = 10) -> List[str]:
    """
    Searches canonical countries and regional markets for autocomplete suggestions.
    Matches prefix first, then substring.
    """
    combined_pool = CANONICAL_COUNTRIES + [
        "North America (US & Canada)", "Western Europe", "EMEA", "APAC", "LATAM", "DACH", "Nordics"
    ]
    seen_lower = set()
    deduped_pool = []
    for item in combined_pool:
        if item.lower() not in seen_lower:
            seen_lower.add(item.lower())
            deduped_pool.append(item)

    if not query or not query.strip():
        # Return popular default targets
        defaults = [
            "United States", "United Kingdom", "India", "Singapore", "Germany",
            "North America (US & Canada)", "Western Europe", "EMEA", "APAC", "Canada"
        ]
        return defaults[:limit]

    q = query.strip().lower()
    prefix_matches = [c for c in deduped_pool if c.lower().startswith(q)]
    contain_matches = [c for c in deduped_pool if q in c.lower() and c not in prefix_matches]

    results = prefix_matches + contain_matches
    if results:
        return results[:limit]

    # If no substring match, check for typo suggestion in countries
    suggestion = get_country_typo_suggestion(query)
    if suggestion:
        return [suggestion]

    reg_matches = difflib.get_close_matches(q, list(LEGITIMATE_REGIONAL_MARKETS.keys()), n=1, cutoff=0.7)
    if reg_matches:
        return [LEGITIMATE_REGIONAL_MARKETS[reg_matches[0]]]

    return []
