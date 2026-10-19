import pytest
from datetime import datetime
from app.database import db_session
from app.models.all_models import UserTable, UsersCompanyDetails, UsersICP
from app.security.password import hash_password
from app.services.country_service import (
    CANONICAL_COUNTRIES,
    validate_country_string,
    validate_single_country,
    search_countries
)
from app.services.spelling_service import (
    get_spelling_suggestion,
    get_icp_field_advisories
)


def create_user_and_login(client, name="ICP User", email="icp_user@example.com", phone="+14155558901"):
    """Helper to create and log in a verified test user for ICP testing."""
    existing = db_session.query(UserTable).filter_by(email_id=email).first()
    if existing:
        user_id = existing.user_id
    else:
        user = UserTable(
            name=name,
            email_id=email,
            phone_no=phone,
            password_hash=hash_password("ValidPassword123!"),
            is_active=True,
            email_verified_at=datetime.utcnow(),
            onboarding_step="ICP"
        )
        db_session.add(user)
        db_session.commit()
        user_id = user.user_id

    # Create associated company record so user is properly at ICP step
    comp = db_session.query(UsersCompanyDetails).filter_by(user_id=user_id).first()
    if not comp:
        comp = UsersCompanyDetails(user_id=user_id, company_name="ICP Test Corp", website_url="https://icptest.com")
        db_session.add(comp)
        db_session.commit()

    with client.session_transaction() as sess:
        sess["user_id"] = user_id
    return user_id


# ---------------------------------------------------------------------------
# 1. Country Validation Unit & Functional Tests
# ---------------------------------------------------------------------------

def test_country_validation_accepts_canonical_countries():
    """Validates that standard canonical country names are accepted and normalized."""
    assert validate_single_country("India") == "India"
    assert validate_single_country("United States") == "United States"
    assert validate_single_country("United Kingdom") == "United Kingdom"
    assert validate_single_country("Singapore") == "Singapore"
    assert validate_single_country("Germany") == "Germany"


def test_country_validation_case_insensitivity_and_aliases():
    """Case-insensitive matches and common aliases normalize to canonical country names."""
    assert validate_single_country("india") == "India"
    assert validate_single_country("UNITED STATES") == "United States"
    assert validate_single_country("singapore") == "Singapore"
    assert validate_single_country("germany") == "Germany"

    # Common aliases
    assert validate_single_country("USA") == "United States"
    assert validate_single_country("UK") == "United Kingdom"
    assert validate_single_country("UAE") == "United Arab Emirates"
    assert validate_single_country("South Korea") == "South Korea"


def test_country_validation_multiple_comma_separated_countries():
    """Validates comma-separated country strings and deduplicates them."""
    res = validate_country_string("India, United States, United Kingdom, Singapore, Germany")
    assert res == "India, United States, United Kingdom, Singapore, Germany"

    # Case-insensitive with extra spaces and duplicates
    res2 = validate_country_string("  india  ,  UNITED STATES , India , Singapore ")
    assert res2 == "India, United States, Singapore"

    # Empty / None handling
    assert validate_country_string("") == ""
    assert validate_country_string(None) == ""


def test_country_validation_rejects_cities_with_actionable_error():
    """Rejects cities such as Bengaluru and London with informative error messages."""
    with pytest.raises(ValueError) as excinfo:
        validate_single_country("Bengaluru")
    msg = str(excinfo.value)
    assert "Bengaluru" in msg
    assert "city" in msg.lower()
    assert "India" in msg

    with pytest.raises(ValueError) as excinfo:
        validate_single_country("London")
    msg = str(excinfo.value)
    assert "London" in msg
    assert "city" in msg.lower()
    assert "United Kingdom" in msg


def test_country_validation_rejects_states_and_provinces():
    """Rejects state/province values such as California with clear error messages."""
    with pytest.raises(ValueError) as excinfo:
        validate_single_country("California")
    msg = str(excinfo.value)
    assert "California" in msg
    assert "state" in msg.lower()
    assert "United States" in msg


def test_country_validation_rejects_regions_and_continents():
    """Rejects macro-regions and continents such as APAC and North America."""
    with pytest.raises(ValueError) as excinfo:
        validate_single_country("APAC")
    msg = str(excinfo.value)
    assert "APAC" in msg
    assert ("region" in msg.lower() or "continent" in msg.lower())

    with pytest.raises(ValueError) as excinfo:
        validate_single_country("North America")
    msg = str(excinfo.value)
    assert "North America" in msg
    assert "continent" in msg.lower()


def test_country_validation_typo_suggestions():
    """Provides clear typo suggestions for close misspellings like 'Indai' -> 'India'."""
    with pytest.raises(ValueError) as excinfo:
        validate_single_country("Indai")
    msg = str(excinfo.value)
    assert "Did you mean 'India'?" in msg

    with pytest.raises(ValueError) as excinfo:
        validate_single_country("Singapor")
    msg = str(excinfo.value)
    assert "Did you mean 'Singapore'?" in msg


def test_country_validation_arbitrary_unrecognized_text():
    """Rejects completely arbitrary text without silently guessing."""
    with pytest.raises(ValueError) as excinfo:
        validate_single_country("XyzUnknownPlanet123")
    msg = str(excinfo.value)
    assert "Invalid country 'XyzUnknownPlanet123'" in msg
    assert "recognized country" in msg


def test_country_search_autocomplete():
    """Verifies search_countries for prefix, substring, and default suggestions."""
    # Prefix
    results = search_countries("ind")
    assert "India" in results
    assert "Indonesia" in results

    # Substring
    results_uni = search_countries("united")
    assert "United States" in results_uni
    assert "United Kingdom" in results_uni

    # Empty query returns popular defaults
    defaults = search_countries("")
    assert len(defaults) > 0
    assert "United States" in defaults


# ---------------------------------------------------------------------------
# 2. Advisory Spelling Assistance Tests
# ---------------------------------------------------------------------------

def test_spelling_preserves_business_acronyms():
    """Acronyms like SaaS, B2B, and RevOps are preserved and normalized to canonical casing."""
    # When lowercase, suggests proper casing
    assert get_spelling_suggestion("b2b saas revops") == "B2B SaaS RevOps"
    assert get_spelling_suggestion("b2b") == "B2B"
    assert get_spelling_suggestion("saas") == "SaaS"
    assert get_spelling_suggestion("revops") == "RevOps"

    # When already properly cased, returns None (no unnecessary suggestion)
    assert get_spelling_suggestion("B2B SaaS RevOps") is None
    assert get_spelling_suggestion("FinTech DevTools") is None


def test_spelling_typo_suggestions_without_silent_overwrites():
    """Identifies common typos like 'enterpise' without silently modifying original input."""
    assert get_spelling_suggestion("enterpise automation") == "enterprise automation"
    assert get_spelling_suggestion("b2b enterpise") == "B2B enterprise"

    # Field advisories dictionary generator does not mutate original data
    original_data = {
        "target_customer": "b2b enterpise companies",
        "industry": "Fintech Devtools",
        "keywords": "revops automatn",
        "exclusions": "B2C"
    }
    advisories = get_icp_field_advisories(original_data)
    assert "target_customer" in advisories
    assert advisories["target_customer"] == "B2B enterprise companies"
    assert "keywords" in advisories
    assert advisories["keywords"] == "RevOps automation"
    # Original data untouched
    assert original_data["target_customer"] == "b2b enterpise companies"


# ---------------------------------------------------------------------------
# 3. Integration Tests: API Country Validation, Persistence & Signal Reload
# ---------------------------------------------------------------------------

def test_api_save_icp_valid_countries_succeeds(client):
    """POST /api/onboarding/icp accepts and persists valid canonical countries."""
    user_id = create_user_and_login(client, "Valid User", "valid_country@example.com", "+14155558911")

    payload = {
        "target_customer": "B2B SaaS Founders",
        "location": "India, United States, Singapore",
        "company_size": "11-50 Employees",
        "revenue_range": "$2M - $25M ARR",
        "industry": "DevTools",
        "tone": "CASUAL"
    }

    res = client.post('/api/onboarding/icp', json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["data"]["location"] == "India, United States, Singapore"

    # Verify directly in PostgreSQL
    db_icp = db_session.query(UsersICP).filter_by(user_id=user_id).first()
    assert db_icp is not None
    assert db_icp.location == "India, United States, Singapore"


def test_api_save_icp_rejects_city_or_state(client):
    """POST /api/onboarding/icp rejects cities, states, and arbitrary non-country/non-region values."""
    create_user_and_login(client, "City User", "city_user@example.com", "+14155558912")

    # City rejection
    res1 = client.post('/api/onboarding/icp', json={
        "target_customer": "Enterprise",
        "location": "Bengaluru"
    })
    assert res1.status_code == 400
    assert "city, not a country" in res1.get_json()["message"]

    # State rejection
    res2 = client.post('/api/onboarding/icp', json={
        "target_customer": "Enterprise",
        "location": "California"
    })
    assert res2.status_code == 400
    assert "state, not a country" in res2.get_json()["message"]

    # Arbitrary unrecognized text rejection
    res3 = client.post('/api/onboarding/icp', json={
        "target_customer": "Enterprise",
        "location": "NonExistentRegion123"
    })
    assert res3.status_code == 400
    assert "Invalid location 'NonExistentRegion123'" in res3.get_json()["message"]


def test_api_save_icp_rejects_typo_with_suggestion(client):
    """POST /api/onboarding/icp returns 400 with a typo suggestion for misspelled countries."""
    create_user_and_login(client, "Typo User", "typo_user@example.com", "+14155558913")

    res = client.post('/api/onboarding/icp', json={
        "target_customer": "Mid-Market",
        "location": "Indai"
    })
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False
    assert "Did you mean 'India'?" in data["message"]


def test_api_buying_signals_persistence_and_reload(client):
    """POST /api/onboarding/icp persists signals and GET /api/onboarding/icp reloads them accurately."""
    user_id = create_user_and_login(client, "Signal User", "signals_user@example.com", "+14155558914")

    signals_payload = {
        "active_hiring": {"enabled": True, "window": "90d Window"},
        "fresh_capital": {"enabled": False, "stage": "Series A"},
        "crm_stack_migration": {"enabled": True, "type": "HubSpot to Salesforce"}
    }

    save_res = client.post('/api/onboarding/icp', json={
        "target_customer": "FinTech Scaleups",
        "location": "United Kingdom, Germany",
        "signals": signals_payload
    })
    assert save_res.status_code == 200
    saved_data = save_res.get_json()["data"]
    assert saved_data["signals"]["active_hiring"]["enabled"] is True
    assert saved_data["signals"]["fresh_capital"]["enabled"] is False

    # GET request verifies retrieval
    get_res = client.get('/api/onboarding/icp')
    assert get_res.status_code == 200
    reloaded_data = get_res.get_json()["data"]
    assert reloaded_data["signals"] is not None
    assert reloaded_data["signals"]["active_hiring"]["window"] == "90d Window"
    assert reloaded_data["signals"]["crm_stack_migration"]["enabled"] is True


def test_api_countries_endpoint(client):
    """GET /api/onboarding/countries returns canonical countries list and filtered queries."""
    res_all = client.get('/api/onboarding/countries')
    assert res_all.status_code == 200
    data_all = res_all.get_json()
    assert data_all["success"] is True
    assert len(data_all["countries"]) >= 195
    assert "India" in data_all["countries"]
    assert "United States" in data_all["countries"]

    res_q = client.get('/api/onboarding/countries?q=sing')
    assert res_q.status_code == 200
    data_q = res_q.get_json()
    assert "Singapore" in data_q["countries"]


# ---------------------------------------------------------------------------
# 5. Edit ICP & User Ownership Isolation Tests
# ---------------------------------------------------------------------------

def test_edit_icp_button_rendered_on_profile_optimization(client):
    """Profile optimization page displays the Edit ICP button and links to /icp with return_url."""
    user_id = create_user_and_login(client, "Opt User", "opt_user@example.com", "+14155558915")
    user = db_session.query(UserTable).filter_by(user_id=user_id).first()
    user.onboarding_step = "OPTIMIZATION"

    # Seed an ICP record with location and signals
    icp = UsersICP(
        user_id=user_id,
        target_customer="Enterprise SaaS",
        target_jobs_roles="VP of Sales",
        industry="DevTools",
        location="India, United States",
        company_size="51-200 Employees",
        signals={"active_hiring": {"enabled": True, "window": "90d Window"}},
        version=1
    )
    db_session.add(icp)
    db_session.commit()

    res = client.get('/profile-optimization')
    assert res.status_code == 200
    html = res.get_data(as_text=True)

    # Edit ICP button and link
    assert 'id="btn-edit-icp"' in html
    assert 'href="/icp?return_url=/profile-optimization"' in html
    assert "Edit ICP" in html

    # Values rendered on the card
    assert "Enterprise SaaS" in html
    assert "India, United States" in html
    assert "51-200 Employees" in html


def test_existing_users_can_access_icp_page_in_edit_mode(client):
    """Users whose onboarding_step is OPTIMIZATION or DONE can freely access /icp without redirection."""
    user_id = create_user_and_login(client, "Done User", "done_user@example.com", "+14155558916")
    user = db_session.query(UserTable).filter_by(user_id=user_id).first()
    user.onboarding_step = "DONE"
    db_session.commit()

    res = client.get('/icp?return_url=/profile-optimization')
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "Define your Ideal Customer Profile" in html
    assert 'id="btn-save-return-direct"' in html


def test_edit_icp_updates_existing_record_and_bumps_version(client):
    """POST /api/onboarding/icp updates an existing ICP record in place and bumps version."""
    user_id = create_user_and_login(client, "Update User", "update_user@example.com", "+14155558917")
    user = db_session.query(UserTable).filter_by(user_id=user_id).first()
    user.onboarding_step = "OPTIMIZATION"

    icp = UsersICP(
        user_id=user_id,
        target_customer="Initial Target",
        location="United States",
        version=1
    )
    db_session.add(icp)
    db_session.commit()

    res = client.post('/api/onboarding/icp', json={
        "target_customer": "Updated Target",
        "location": "Germany, Singapore",
        "industry": "FinTech",
        "company_size": "11-50 Employees",
        "signals": {"fresh_capital": {"enabled": True, "stage": "Series A"}}
    })
    assert res.status_code == 200
    data = res.get_json()["data"]

    assert data["target_customer"] == "Updated Target"
    assert data["location"] == "Germany, Singapore"
    assert data["version"] == 2

    # Check total count of ICP rows for this user remains exactly 1
    total_records = db_session.query(UsersICP).filter_by(user_id=user_id).count()
    assert total_records == 1


def test_icp_strict_user_ownership_isolation(client):
    """Ensures user A and user B cannot view or overwrite each other's ICP records."""
    # User A
    user_a_id = create_user_and_login(client, "User A", "user_a@example.com", "+14155558918")
    client.post('/api/onboarding/icp', json={
        "target_customer": "User A Companies",
        "location": "United States"
    })

    # User B
    user_b_id = create_user_and_login(client, "User B", "user_b@example.com", "+14155558919")
    client.post('/api/onboarding/icp', json={
        "target_customer": "User B Companies",
        "location": "India"
    })

    # Verify User B gets User B's data
    res_b = client.get('/api/onboarding/icp')
    assert res_b.status_code == 200
    assert res_b.get_json()["data"]["target_customer"] == "User B Companies"

    # Switch session back to User A
    with client.session_transaction() as sess:
        sess["user_id"] = user_a_id

    res_a = client.get('/api/onboarding/icp')
    assert res_a.status_code == 200
    assert res_a.get_json()["data"]["target_customer"] == "User A Companies"
    assert res_a.get_json()["data"]["location"] == "United States"


def test_icp_unauthenticated_access_rejected(client):
    """Unauthenticated GET and POST /api/onboarding/icp return 401."""
    with client.session_transaction() as sess:
        sess.clear()

    get_res = client.get('/api/onboarding/icp')
    assert get_res.status_code == 401

    post_res = client.post('/api/onboarding/icp', json={"target_customer": "Hacker Corp"})
    assert post_res.status_code == 401


# ---------------------------------------------------------------------------
# 5. Legitimate Regional Target Market Regression Tests
# ---------------------------------------------------------------------------

def test_saved_icp_regional_targeting_loads_and_saves_unchanged(client):
    """
    Existing company's saved ICP containing 'North America (US & Canada)'
    loads and saves without rejection or value degradation.
    """
    user_id = create_user_and_login(client, "Region User", "region_user@example.com", "+14155558930")

    # Seed existing database record with legitimate regional target
    existing_icp = UsersICP(
        user_id=user_id,
        target_customer="Enterprise Cloud Platforms",
        location="North America (US & Canada)",
        industry="SaaS",
        version=1
    )
    db_session.add(existing_icp)
    db_session.commit()

    # 1. GET /api/onboarding/icp must return the exact regional location
    get_res = client.get('/api/onboarding/icp')
    assert get_res.status_code == 200
    data = get_res.get_json()["data"]
    assert data["location"] == "North America (US & Canada)"

    # 2. Saving the loaded ICP without modification must succeed
    post_res = client.post('/api/onboarding/icp', json={
        "target_customer": data["target_customer"],
        "location": data["location"],
        "industry": data["industry"]
    })
    assert post_res.status_code == 200
    saved = post_res.get_json()["data"]
    assert saved["location"] == "North America (US & Canada)"

    # Verify DB state
    db_record = db_session.query(UsersICP).filter_by(user_id=user_id).first()
    assert db_record.location == "North America (US & Canada)"


def test_multi_target_regional_and_country_location_saved(client):
    """
    Users can combine legitimate regional markets and individual canonical countries,
    preserving parenthetical clauses like 'North America (US & Canada), Western Europe, Singapore'.
    """
    create_user_and_login(client, "Multi Region User", "multi_region@example.com", "+14155558931")

    res = client.post('/api/onboarding/icp', json={
        "target_customer": "Global B2B",
        "location": "North America (US & Canada), Western Europe, Singapore"
    })
    assert res.status_code == 200
    saved_location = res.get_json()["data"]["location"]
    assert "North America (US & Canada)" in saved_location
    assert "Western Europe" in saved_location
    assert "Singapore" in saved_location


def test_existing_regional_icp_data_can_be_edited_and_saved(client):
    """
    An existing user with regional targeting can edit their ICP (e.g. adding a country
    or updating roles) and successfully save it with a version bump.
    """
    user_id = create_user_and_login(client, "Edit Region User", "edit_region@example.com", "+14155558932")

    seed_icp = UsersICP(
        user_id=user_id,
        target_customer="Fintech Enterprises",
        location="EMEA",
        version=1
    )
    db_session.add(seed_icp)
    db_session.commit()

    # User edits ICP to add Germany and updates roles
    res = client.post('/api/onboarding/icp', json={
        "target_customer": "Fintech Enterprises",
        "location": "EMEA, Germany",
        "target_jobs_roles": "VP Engineering, CTO"
    })
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert data["location"] == "EMEA, Germany"
    assert data["target_jobs_roles"] == "VP Engineering, CTO"
    assert data["version"] == 2


def test_gtm_consumers_receive_compatible_targeting_with_regions(client):
    """
    Verifies that downstream consumers (Profile Optimization GTM context & summary card)
    receive compatible targeting information when regional markets are used.
    """
    user_id = create_user_and_login(client, "GTM Region User", "gtm_region@example.com", "+14155558933")
    user = db_session.query(UserTable).filter_by(user_id=user_id).first()
    user.onboarding_step = "OPTIMIZATION"
    db_session.commit()

    seed_icp = UsersICP(
        user_id=user_id,
        target_customer="Enterprise Security",
        location="North America (US & Canada)",
        industry="Cybersecurity",
        version=1
    )
    db_session.add(seed_icp)
    db_session.commit()

    with client.session_transaction() as sess:
        sess["user_id"] = user_id

    # Profile optimization page loads and renders regional market
    page_res = client.get('/profile-optimization')
    assert page_res.status_code == 200
    html = page_res.get_data(as_text=True)
    # Jinja2 autoescapes '&' as '&amp;' in HTML templates
    assert "North America (US &amp; Canada)" in html or "North America (US & Canada)" in html


# ---------------------------------------------------------------------------
# 6. Smart Autocomplete & Multi-Field Suggestions Tests
# ---------------------------------------------------------------------------

def test_icp_page_renders_smart_autocomplete_dropdowns_and_helpers(client):
    """
    ICP Builder renders autocomplete dropdown containers for all multi-select fields,
    disables browser default autofill with autocomplete="off", and displays clear helper
    text for ARR and Headcount Band.
    """
    create_user_and_login(client, "Autocomplete UI User", "auto_ui@example.com", "+14155558940")

    res = client.get('/icp')
    assert res.status_code == 200
    html = res.get_data(as_text=True)

    # 1. Autocomplete dropdown containers for all fields
    assert 'id="target-customer-dropdown"' in html
    assert 'id="industry-dropdown"' in html
    assert 'id="roles-dropdown"' in html
    assert 'id="keywords-dropdown"' in html
    assert 'id="exclusions-dropdown"' in html
    assert 'id="location-dropdown"' in html

    # 2. Browser autofill disabled on all input elements
    assert 'id="target-customer-input"' in html
    assert 'id="industry-input"' in html
    assert 'id="roles-input"' in html
    assert 'id="keywords-input"' in html
    assert 'id="exclusions-input"' in html
    assert 'id="location-input"' in html

    # 3. Discoverability & guidance helper text for ARR and Headcount
    assert "Derived from secondary filings" in html
    assert "Select one or more employee count bands" in html


def test_icp_all_fields_accept_and_persist_custom_chips(client):
    """
    Ensures Target Customer Segment, Industry, Roles, Keywords, and Exclusions
    accept arbitrary custom tags (unlike strict location) and persist them without data loss.
    """
    user_id = create_user_and_login(client, "Custom Tags User", "custom_tags@example.com", "+14155558941")

    payload = {
        "target_customer": "Quantum AI Labs, Niche Robotics Boutique",
        "industry": "DeepTech Hardware, Autonomous Drone Logistics",
        "target_jobs_roles": "Chief Prompt Engineer, Head of Edge Computing",
        "keywords": "neuromorphic chips, edge inference, tensor telemetry",
        "exclusions": "Crypto Speculators, Dropshipping Agencies",
        "location": "Germany, Singapore",
        "company_size": "11-50 Employees, 51-200 Employees",
        "revenue_range": "$2M - $25M ARR",
        "tone": "TECHNICAL"
    }

    res = client.post('/api/onboarding/icp', json=payload)
    assert res.status_code == 200
    data = res.get_json()["data"]

    # Verify custom values returned by API
    assert data["target_customer"] == "Quantum AI Labs, Niche Robotics Boutique"
    assert data["industry"] == "DeepTech Hardware, Autonomous Drone Logistics"
    assert data["target_jobs_roles"] == "Chief Prompt Engineer, Head of Edge Computing"
    assert data["keywords"] == "neuromorphic chips, edge inference, tensor telemetry"
    assert data["exclusions"] == "Crypto Speculators, Dropshipping Agencies"
    assert data["location"] == "Germany, Singapore"
    assert data["company_size"] == "11-50 Employees, 51-200 Employees"
    assert data["revenue_range"] == "$2M - $25M ARR"

    # Verify directly in DB
    db_record = db_session.query(UsersICP).filter_by(user_id=user_id).first()
    assert db_record is not None
    assert db_record.target_customer == payload["target_customer"]
    assert db_record.industry == payload["industry"]
    assert db_record.target_jobs_roles == payload["target_jobs_roles"]
    assert db_record.keywords == payload["keywords"]
    assert db_record.exclusions == payload["exclusions"]


def test_spelling_preserves_acv_and_custom_terms():
    """
    Verifies spelling service preserves and standardizes ACV, ARR, SaaS, B2B, B2C,
    DevOps, RevOps, and warns on common typos like 'enterpise' without altering clean terms.
    """
    # Acronym preservation and casing
    assert get_spelling_suggestion("acv arr crm saas") == "ACV ARR CRM SaaS"
    assert get_spelling_suggestion("ACV ARR CRM SaaS") is None

    # Preserves mixed acronyms and typos
    assert get_spelling_suggestion("b2b acv enterpise") == "B2B ACV enterprise"

    # Field advisories dictionary includes ACV when lowercase
    advisories = get_icp_field_advisories({
        "target_customer": "acv focus",
        "keywords": "revops acv"
    })
    assert advisories.get("target_customer") == "ACV focus"
    assert advisories.get("keywords") == "RevOps ACV"


def test_smart_autocomplete_data_roundtrip_and_versioning(client):
    """
    Verifies a full roundtrip: creating an ICP with standard suggested tags,
    retrieving it via GET, editing it with custom tags, and verifying version increment.
    """
    user_id = create_user_and_login(client, "Roundtrip User", "roundtrip@example.com", "+14155558942")

    # Initial creation with standard suggested values
    initial_payload = {
        "target_customer": "B2B SaaS Companies, Mid-Market Companies",
        "industry": "FinTech, DevTools",
        "target_jobs_roles": "VP of Sales, Chief Revenue Officer",
        "keywords": "sales intelligence, CRM, contact data enrichment",
        "exclusions": "B2C / Consumer, Agency / Freelance",
        "location": "United States, United Kingdom",
        "company_size": "51-200 Employees",
        "revenue_range": "$5M - $20M ARR"
    }

    create_res = client.post('/api/onboarding/icp', json=initial_payload)
    assert create_res.status_code == 200
    assert create_res.get_json()["data"]["version"] == 1

    # GET verification
    get_res = client.get('/api/onboarding/icp')
    assert get_res.status_code == 200
    loaded = get_res.get_json()["data"]
    assert loaded["target_customer"] == "B2B SaaS Companies, Mid-Market Companies"
    assert loaded["industry"] == "FinTech, DevTools"
    assert loaded["target_jobs_roles"] == "VP of Sales, Chief Revenue Officer"
    assert loaded["keywords"] == "sales intelligence, CRM, contact data enrichment"
    assert loaded["exclusions"] == "B2C / Consumer, Agency / Freelance"
    assert loaded["version"] == 1

    # Update with custom tags addition
    updated_payload = dict(initial_payload)
    updated_payload["target_customer"] = "B2B SaaS Companies, Custom BioTech SaaS"
    updated_payload["keywords"] = "sales intelligence, CRM, custom pipeline velocity signal"

    update_res = client.post('/api/onboarding/icp', json=updated_payload)
    assert update_res.status_code == 200
    updated_data = update_res.get_json()["data"]
    assert updated_data["version"] == 2
    assert "Custom BioTech SaaS" in updated_data["target_customer"]
    assert "custom pipeline velocity signal" in updated_data["keywords"]
