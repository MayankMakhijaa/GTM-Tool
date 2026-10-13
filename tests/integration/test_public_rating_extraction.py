import pytest
import time
from unittest.mock import patch, MagicMock
from app.services.scraping_service import (
    extract_trustpilot_rating_direct,
    research_public_company_ratings,
    enrich_company_with_multi_source_research,
    perform_public_web_search,
    SearchEngineUnavailableError,
    SEARCH_QUERY_DELAY,
    RATING_CACHE
)

@pytest.fixture(autouse=True)
def clear_rating_cache():
    """Clear in-memory rating cache before each test."""
    RATING_CACHE.clear()
    yield
    RATING_CACHE.clear()


@pytest.fixture(autouse=True)
def zero_search_query_delay(monkeypatch):
    """Keep tests fast by default; delay-specific test overrides this."""
    monkeypatch.setattr("app.services.scraping_service.SEARCH_QUERY_DELAY", 0.0)


def test_extract_trustpilot_rating_direct_success():
    mock_html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@type": "Organization",
          "name": "Acme Software",
          "aggregateRating": {
            "@type": "AggregateRating",
            "ratingValue": "4.7",
            "reviewCount": 1250,
            "bestRating": 5
          }
        }
        </script>
      </head>
    </html>
    """
    with patch("app.services.scraping_service.fetch_url_safely") as mock_fetch:
        mock_fetch.return_value = {"success": True, "html": mock_html}
        result = extract_trustpilot_rating_direct("acme.com")
        
        assert result is not None
        assert result["score"] == 4.7
        assert result["review_count"] == 1250
        assert result["source_name"] == "Trustpilot"
        assert result["verification_status"] == "VERIFIED"
        assert "4.7 / 5 (1,250 reviews on Trustpilot)" in result["value"]


def test_extract_trustpilot_rating_direct_not_found():
    with patch("app.services.scraping_service.fetch_url_safely") as mock_fetch:
        mock_fetch.return_value = {"success": False, "html": ""}
        result = extract_trustpilot_rating_direct("nonexistentdomain12345.com")
        assert result is None


def test_research_public_company_ratings_trustpilot_match():
    mock_html = """
    <html>
      <script type="application/ld+json">
      {
        "@type": "AggregateRating",
        "ratingValue": "4.9",
        "ratingCount": 320,
        "bestRating": 5
      }
      </script>
    </html>
    """
    def mock_fetch(url, timeout=4.0, headers=None, **kwargs):
        if "trustpilot.com" in url:
            return {"success": True, "html": mock_html}
        return {"success": False, "html": ""}

    with patch("app.services.scraping_service.fetch_url_safely", side_effect=mock_fetch), \
         patch("app.services.scraping_service.perform_public_web_search", return_value=[]):
        res_map, telemetry = research_public_company_ratings("Star Corp", "https://starcorp.io")
        
        assert res_map is not None
        assert "rating" in res_map
        rating_item = res_map["rating"]
        assert rating_item["source_name"] == "Trustpilot"
        assert rating_item["verification_status"] == "VERIFIED"
        assert "4.9 / 5 (320 reviews on Trustpilot)" in rating_item["value"]
        assert telemetry["status"] == "SUCCESS_TRUSTPILOT"


def test_research_public_company_ratings_ttl_caching():
    mock_html = """
    <html>
      <script type="application/ld+json">
      {
        "@type": "AggregateRating",
        "ratingValue": "4.5",
        "reviewCount": 100
      }
      </script>
    </html>
    """
    with patch("app.services.scraping_service.fetch_url_safely") as mock_fetch, \
         patch("app.services.scraping_service.perform_public_web_search", return_value=[]):
        mock_fetch.return_value = {"success": True, "html": mock_html}
        
        # First call - cache miss
        res1, telemetry1 = research_public_company_ratings("Cache Test", "https://cachetest.com")
        assert mock_fetch.call_count == 1
        assert telemetry1["status"] in ("SUCCESS_AMBITIONBOX", "SUCCESS_TRUSTPILOT")
        
        # Second call - cache hit
        res2, telemetry2 = research_public_company_ratings("Cache Test", "https://cachetest.com")
        assert mock_fetch.call_count == 1  # No additional network calls
        assert telemetry2["status"] == "CACHE_HIT"
        assert res1 == res2



def test_research_public_company_ratings_fallback_not_found():
    with patch("app.services.scraping_service.fetch_url_safely") as mock_fetch, \
         patch("app.services.scraping_service.perform_public_web_search") as mock_search:
        mock_fetch.return_value = {"success": False, "html": ""}
        mock_search.return_value = []
        
        res_map, telemetry = research_public_company_ratings("Unknown Corp", "https://unknowncorp.xyz")
        
        assert res_map["rating"]["value"] == "Not available"
        assert res_map["rating"]["verification_status"] == "NOT_FOUND"


def test_research_public_company_ratings_justdial_primary():
    """Requirement 1: Justdial rating is prioritized and correctly extracted."""
    mock_leads = [
        {
            "title": "Fameweb, Faridabad Sector 16, Faridabad - Justdial",
            "snippet": "Fameweb in Faridabad Sector 16, Faridabad listed under Consultants. Rated 4.6 based on 5 Customer Reviews and 10 Ratings.",
            "url": "https://www.justdial.com/Faridabad/Fameweb-Faridabad-Sector-16/011PXX11-XX11-250523204236-J2Y9_BZDET"
        }
    ]
    with patch("app.services.scraping_service.perform_public_web_search") as mock_search:
        mock_search.return_value = mock_leads
        res_map, telemetry = research_public_company_ratings("Fameweb", "https://fameweb.in", location="Faridabad")

        assert res_map is not None
        assert "rating" in res_map
        item = res_map["rating"]
        assert item["source_name"] == "Justdial"
        assert item["verification_status"] == "VERIFIED"
        assert item["score"] == 4.6
        assert item["review_count"] == 5
        assert "4.6 / 5 (5 reviews on Justdial)" in item["value"]
        assert telemetry["status"] == "SUCCESS_JUSTDIAL"


def test_research_public_company_ratings_justdial_unavailable_ambitionbox_fallback():
    """Requirement 2: Justdial has no rating -> falls back to AmbitionBox."""
    def mock_search_side_effect(query, max_results=3):
        if "site:justdial.com" in query:
            return []  # Justdial not found
        if "site:ambitionbox.com" in query:
            return [
                {
                    "title": "Fameweb Reviews by 2 Employees | Rated 5.0/5 | AmbitionBox",
                    "snippet": "Fameweb is rated 5.0 out of 5, based on 2 reviews by employees on AmbitionBox. Fameweb is known for Company culture.",
                    "url": "https://www.ambitionbox.com/reviews/fameweb-reviews"
                }
            ]
        return []

    with patch("app.services.scraping_service.fetch_url_safely", return_value={"success": False, "html": ""}), \
         patch("app.services.scraping_service.perform_public_web_search", side_effect=mock_search_side_effect):
        res_map, telemetry = research_public_company_ratings("Fameweb", "https://fameweb.in")

        assert res_map is not None
        item = res_map["rating"]
        assert item["source_name"] == "AmbitionBox"
        assert item["score"] == 5.0
        assert item["review_count"] == 2
        assert "5.0 / 5 (2 reviews on AmbitionBox)" in item["value"]
        assert telemetry["status"] == "SUCCESS_AMBITIONBOX"


def test_research_public_company_ratings_goodfirms_sulekha_fallback():
    """Requirement 3: Justdial & AmbitionBox unavailable -> GoodFirms & Sulekha fallback."""
    def mock_search_side_effect(query, max_results=3):
        if "site:goodfirms.co" in query:
            return [
                {
                    "title": "CloudScale Solutions - Reviews & Ratings | GoodFirms",
                    "snippet": "CloudScale Solutions has a 4.8 out of 5 rating based on 32 reviews from verified clients.",
                    "url": "https://www.goodfirms.co/company/cloudscale-solutions"
                }
            ]
        return []

    with patch("app.services.scraping_service.perform_public_web_search", side_effect=mock_search_side_effect):
        res_map, telemetry = research_public_company_ratings("CloudScale Solutions", "https://cloudscale.io")

        assert res_map is not None
        item = res_map["rating"]
        assert item["source_name"] == "GoodFirms"
        assert item["score"] == 4.8
        assert item["review_count"] == 32
        assert "4.8 / 5 (32 reviews on GoodFirms)" in item["value"]
        assert telemetry["status"] == "SUCCESS_GOODFIRMS"


def test_entity_matching_correct_and_wrong_company():
    """Requirements 4 & 5: Entity matching validates correct company and rejects unrelated entities."""
    from app.services.scraping_service import match_candidate_entity

    # Exact brand name match
    assert match_candidate_entity(
        title="Fameweb, Sector 16, Faridabad - Justdial",
        snippet="Consultants. Rated 4.6 based on 5 reviews",
        url="https://www.justdial.com/Faridabad/Fameweb",
        company_name="Fameweb",
        website_url="https://fameweb.in"
    ) is True

    # Multi-token company name match with domain
    assert match_candidate_entity(
        title="Wipro Enterprises Pvt Ltd - Justdial",
        snippet="Software solutions in Bangalore",
        url="https://www.justdial.com/Bangalore/Wipro-Enterprises",
        company_name="Wipro Enterprises",
        website_url="https://wipro.com"
    ) is True

    # Rejection of unrelated company with common substring
    assert match_candidate_entity(
        title="Fame Dance Academy - Dance Classes in Delhi - Justdial",
        snippet="Dance classes and choreography. Rated 4.9 based on 100 reviews",
        url="https://www.justdial.com/Delhi/Fame-Dance-Academy",
        company_name="Fameweb",
        website_url="https://fameweb.in"
    ) is False

    # Rejection of totally different company
    assert match_candidate_entity(
        title="Apex Global Solutions - Justdial",
        snippet="Manufacturing and exports",
        url="https://www.justdial.com/Mumbai/Apex-Global",
        company_name="Stark Industries",
        website_url="https://starkindustries.com"
    ) is False


def test_rating_extraction_deterministic_parsing():
    """Requirement 6: Parsing deterministic ratings from various review snippet text formats."""
    from app.services.scraping_service import extract_rating_from_text

    # Justdial standard format
    jd = extract_rating_from_text("Rated 4.6 based on 5 Customer Reviews and 10 Ratings", "Justdial")
    assert jd is not None
    assert jd["score"] == 4.6
    assert jd["review_count"] == 5
    assert jd["value"] == "4.6 / 5 (5 reviews on Justdial)"

    # Ambitionbox format
    ab = extract_rating_from_text("Rated 5.0/5 | AmbitionBox - based on 12 reviews", "AmbitionBox")
    assert ab is not None
    assert ab["score"] == 5.0
    assert ab["review_count"] == 12
    assert ab["value"] == "5.0 / 5 (12 reviews on AmbitionBox)"

    # GoodFirms format
    gf = extract_rating_from_text("Accenture has an overall rating of 4.8 out of 5", "GoodFirms")
    assert gf is not None
    assert gf["score"] == 4.8
    assert gf["value"] == "4.8 / 5 (GoodFirms)"

    # Sulekha format
    su = extract_rating_from_text("Rated 4.5 based on 25 votes on Sulekha", "Sulekha")
    assert su is not None
    assert su["score"] == 4.5
    assert su["review_count"] == 25

    # Out-of-bounds rating rejection (e.g. 0.0 or 7.5 or non-ratings)
    invalid = extract_rating_from_text("Rated 9.5 out of 10", "Justdial")
    assert invalid is None


def test_no_llm_called_for_rating_extraction():
    """Requirement 7: Rating research does not call Gemini/LLM."""
    mock_leads = [
        {
            "title": "Fameweb, Faridabad - Justdial",
            "snippet": "Rated 4.6 based on 5 Customer Reviews",
            "url": "https://www.justdial.com/Faridabad/Fameweb"
        }
    ]
    with patch("app.services.scraping_service.perform_public_web_search", return_value=mock_leads), \
         patch("app.services.scraping_service.validate_search_evidence_with_gemini") as mock_gemini:
        res_map, telemetry = research_public_company_ratings("Fameweb", "https://fameweb.in")

        # LLM must NOT be called for rating extraction
        assert mock_gemini.call_count == 0
        assert res_map["rating"]["score"] == 4.6


def test_all_sources_unavailable_clear_failure_no_fabrication():
    """Requirement 8: All sources exhausted -> clear NOT_FOUND status, no fabricated rating."""
    with patch("app.services.scraping_service.perform_public_web_search", return_value=[]), \
         patch("app.services.scraping_service.fetch_url_safely", return_value={"success": False, "html": ""}):
        res_map, telemetry = research_public_company_ratings("Invisible Corp", "https://invisiblecorp123.com")

        assert res_map["rating"]["value"] == "Not available"
        assert res_map["rating"]["verification_status"] == "NOT_FOUND"
        assert telemetry["status"] == "NO_RATING_FOUND"


def test_rating_persistence_in_database(client):
    """Requirement 10: Discovered rating properly persists into users_company_details.rating in DB."""
    from app.services.onboarding_service import save_company, get_company
    from app.models.all_models import UserTable, UsersCompanyDetails
    from app.database import db_session

    # Create test user in test DB
    user = UserTable(
        name="Rating Test User",
        email_id="rating_test@acme.com",
        password_hash="test_hash"
    )
    db_session.add(user)
    db_session.commit()

    company_payload = {
        "company_name": "Acme Technologies",
        "website_url": "https://acme.com",
        "description": "Enterprise cloud platform",
        "what_company_sells": "Cloud SaaS",
        "industry": "Software & SaaS",
        "location": "Bangalore, India",
        "rating": "4.6 / 5 (5 reviews on Justdial)"
    }

    # Save company
    saved = save_company(user.user_id, company_payload)
    assert saved["rating"] == "4.6 / 5 (5 reviews on Justdial)"

    # Retrieve company and verify DB persistence
    retrieved = get_company(user.user_id)
    assert retrieved is not None
    assert retrieved["rating"] == "4.6 / 5 (5 reviews on Justdial)"

    # Verify directly from UsersCompanyDetails model
    db_row = db_session.query(UsersCompanyDetails).filter_by(user_id=user.user_id).first()
    assert db_row is not None
    assert db_row.rating == "4.6 / 5 (5 reviews on Justdial)"


def test_enrich_company_with_multi_source_research_rating_integration():
    """Requirement 9a: enrich_company_with_multi_source_research integrates public rating."""
    scraped_data = {
        "company_name": "Acme Inc",
        "website_url": "https://acme.com",
        "location": "San Francisco, CA",
        "company_size": "51–200 employees",
        "revenue": "$10M–$20M annual revenue",
        "rating": None,
        "provenance": {}
    }

    jd_item = {
        "score": 4.6,
        "max_rating": 5.0,
        "review_count": 5,
        "value": "4.6 / 5 (5 reviews on Justdial)",
        "source_name": "Justdial",
        "source_url": "https://www.justdial.com/San-Francisco/Acme-Inc",
        "evidence": "Justdial verified public rating: 4.6/5 across 5 reviews",
        "retrieval_timestamp": "2026-10-07T00:00:00Z",
        "verification_status": "VERIFIED"
    }

    with patch("app.services.scraping_service.research_public_company_ratings") as mock_rating:
        mock_rating.return_value = ({"rating": jd_item}, {"status": "SUCCESS_JUSTDIAL", "sources_checked": ["Justdial"]})

        enriched_data, diag = enrich_company_with_multi_source_research(scraped_data, "Acme Inc", "https://acme.com")

        assert enriched_data["rating"] == "4.6 / 5 (5 reviews on Justdial)"
        assert enriched_data["provenance"]["rating"]["source_name"] == "Justdial"
        assert enriched_data["provenance"]["rating"]["verification_status"] == "VERIFIED"
        assert "rating" in diag["fields_enriched"]


def test_company_scraping_workflow_with_rating():
    """Requirement 9b: scrape_official_company_website end-to-end integration with rating."""
    from app.services.scraping_service import scrape_official_company_website

    mock_home_html = """
    <html>
      <head><title>Acme Software - Enterprise Cloud</title></head>
      <body>
        <h1>Welcome to Acme Software</h1>
        <p>We provide enterprise cloud solutions for growing companies.</p>
        <p>Location: Bangalore, India</p>
      </body>
    </html>
    """
    mock_jd_leads = [
        {
            "title": "Acme Software, Bangalore - Justdial",
            "snippet": "Enterprise cloud provider. Rated 4.8 based on 15 Customer Reviews.",
            "url": "https://www.justdial.com/Bangalore/Acme-Software"
        }
    ]

    with patch("app.services.scraping_service.resolve_and_validate_hostname", return_value=(True, "93.184.216.34")), \
         patch("app.services.scraping_service.crawl_with_crawl4ai", return_value=[]), \
         patch("app.services.scraping_service.fetch_url_safely") as mock_fetch, \
         patch("app.services.scraping_service.perform_public_web_search") as mock_search, \
         patch("app.services.scraping_service.extract_company_data_with_gemini") as mock_gemini:

        mock_fetch.return_value = {"success": True, "html": mock_home_html, "status_code": 200, "final_url": "https://acmesoft.io"}
        mock_search.return_value = mock_jd_leads
        mock_gemini.return_value = (
            {
                "company_name": "Acme Software",
                "website_url": "https://acmesoft.io",
                "description": "Enterprise cloud solutions",
                "what_company_sells": "Cloud SaaS",
                "products_services": ["Cloud SaaS"],
                "industry": "Software & SaaS",
                "company_size": "51–200 employees",
                "revenue": None,
                "location": "Bangalore, India",
                "rating": None,
                "other_details": None,
                "provenance": {}
            },
            None,
            {"gemini_configured": True, "gemini_request_successful": True, "extraction_engine_used": "gemini"}
        )

        result = scrape_official_company_website("https://acmesoft.io")
        assert result["status"] in ("SUCCESS", "PARTIAL")
        assert result["scraped_data"]["rating"] == "4.8 / 5 (15 reviews on Justdial)"
        assert result["scraped_data"]["provenance"]["rating"]["source_name"] == "Justdial"


def test_research_public_company_ratings_search_unavailable_when_engine_fails():
    """When external search engines fail/timeout, return SEARCH_UNAVAILABLE and do NOT cache."""
    with patch("app.services.scraping_service.fetch_url_safely") as mock_fetch, \
         patch("app.services.scraping_service.perform_public_web_search") as mock_search:
        mock_fetch.return_value = {"success": False, "html": ""}
        mock_search.side_effect = SearchEngineUnavailableError("DuckDuckGo timed out or returned HTTP 202")

        res_map, telemetry = research_public_company_ratings("Unavailable Corp", "https://unavailcorp.com")

        assert res_map is not None
        item = res_map["rating"]
        assert item["value"] == "Search unavailable"
        assert item["verification_status"] == "SEARCH_UNAVAILABLE"
        assert telemetry["status"] == "SEARCH_UNAVAILABLE"
        assert len(telemetry["search_engine_errors"]) > 0

        # Must NOT be cached
        assert "unavailable corp_unavailcorp.com" not in RATING_CACHE


def test_research_public_company_ratings_not_found_not_cached():
    """When searches succeed with 200 OK but find no ratings, return NOT_FOUND and do NOT cache false negatives."""
    with patch("app.services.scraping_service.fetch_url_safely") as mock_fetch, \
         patch("app.services.scraping_service.perform_public_web_search") as mock_search:
        mock_fetch.return_value = {"success": False, "html": ""}
        mock_search.return_value = []  # Succeeded with 0 results

        res_map, telemetry = research_public_company_ratings("NotFound Corp", "https://notfoundcorp.com")

        assert res_map is not None
        item = res_map["rating"]
        assert item["value"] == "Not available"
        assert item["verification_status"] == "NOT_FOUND"
        assert telemetry["status"] == "NO_RATING_FOUND"

        # Must NOT be cached
        assert "notfound corp_notfoundcorp.com" not in RATING_CACHE


def test_perform_public_web_search_raises_search_engine_unavailable_on_bot_or_timeout():
    """perform_public_web_search raises SearchEngineUnavailableError immediately when search engines return anti-bot or error."""
    mock_post_resp = MagicMock()
    mock_post_resp.status_code = 202  # DuckDuckGo Lite anti-bot challenge

    mock_get_resp = MagicMock()
    mock_get_resp.status_code = 202   # DuckDuckGo HTML anti-bot challenge

    with patch("requests.post", return_value=mock_post_resp), \
         patch("requests.get", return_value=mock_get_resp):
        with pytest.raises(SearchEngineUnavailableError) as exc_info:
            perform_public_web_search("Test Corp site:ambitionbox.com")

        assert "External public search engines unavailable" in str(exc_info.value)


def test_perform_public_web_search_never_invokes_crawl4ai():
    """Verify that perform_public_web_search NEVER invokes Crawl4AI headless browser even on complete failure."""
    mock_post_resp = MagicMock()
    mock_post_resp.status_code = 202

    mock_get_resp = MagicMock()
    mock_get_resp.status_code = 202

    with patch("requests.post", return_value=mock_post_resp), \
         patch("requests.get", return_value=mock_get_resp), \
         patch("app.services.scraping_service.crawl_with_crawl4ai", create=True) as mock_crawl:
        with pytest.raises(SearchEngineUnavailableError):
            perform_public_web_search("site:ambitionbox.com Fameweb reviews")

        mock_crawl.assert_not_called()


def test_perform_public_web_search_lite_success_parses_leads():
    """When DDG Lite succeeds, leads are parsed directly and quickly via HTTP."""
    mock_post_resp = MagicMock()
    mock_post_resp.status_code = 200
    mock_post_resp.text = """
    <html><body><table>
      <tr><td><a class="result-link" href="https://www.ambitionbox.com/reviews/fameweb-reviews">Fameweb Reviews</a></td></tr>
      <tr><td>Great company culture</td></tr>
    </table></body></html>
    """

    with patch("requests.post", return_value=mock_post_resp):
        leads = perform_public_web_search("site:ambitionbox.com Fameweb reviews", max_results=3)

        assert len(leads) == 1
        assert leads[0]["url"] == "https://www.ambitionbox.com/reviews/fameweb-reviews"
        assert leads[0]["title"] == "Fameweb Reviews"


def test_extract_ambitionbox_direct_json_ld_success():
    """Verify AmbitionBox EmployerAggregateRating JSON-LD microdata extraction."""
    from app.services.scraping_service import extract_ambitionbox_rating_direct
    mock_html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@type": "EmployerAggregateRating",
          "ratingValue": "5.0",
          "ratingCount": 3,
          "bestRating": "5",
          "itemReviewed": {
            "@type": "Organization",
            "name": "Fameweb"
          }
        }
        </script>
      </head>
    </html>
    """
    with patch("app.services.scraping_service.fetch_url_safely", return_value={"success": True, "html": mock_html}):
        rating_res = extract_ambitionbox_rating_direct("https://www.ambitionbox.com/reviews/fameweb-reviews")
        assert rating_res is not None
        assert rating_res["score"] == 5.0
        assert rating_res["review_count"] == 3
        assert rating_res["source_name"] == "AmbitionBox"
        assert rating_res["verification_status"] == "VERIFIED"
        assert "5.0 / 5 (3 reviews on AmbitionBox)" in rating_res["value"]


def test_research_public_company_ratings_ambitionbox_direct_match():
    """Direct AmbitionBox profile lookup finds verified rating and stops immediately before search."""
    mock_html = """
    <html>
      <script type="application/ld+json">
      {
        "@type": "EmployerAggregateRating",
        "ratingValue": "5.0",
        "ratingCount": 3,
        "itemReviewed": {
          "@type": "Organization",
          "name": "Fameweb"
        }
      }
      </script>
    </html>
    """
    with patch("app.services.scraping_service.fetch_url_safely", return_value={"success": True, "html": mock_html}), \
         patch("app.services.scraping_service.perform_public_web_search") as mock_search:
        # Justdial search returns nothing, AmbitionBox direct succeeds
        mock_search.return_value = []
        res_map, telemetry = research_public_company_ratings("Fameweb", "https://fameweb.in")

        assert res_map is not None
        item = res_map["rating"]
        assert item["source_name"] == "AmbitionBox"
        assert item["score"] == 5.0
        assert item["verification_status"] == "VERIFIED"
        assert telemetry["status"] == "SUCCESS_AMBITIONBOX"
        # Since AmbitionBox direct succeeded, GoodFirms, Sulekha, Clutch, Trustpilot searches must not be called!
        assert "AmbitionBox Direct" in telemetry["sources_checked"]


def test_google_places_never_invoked_during_rating_research(monkeypatch):
    """Verify Google Places is NEVER called during research_public_company_ratings."""
    monkeypatch.setattr("config.Config.GOOGLE_MAPS_API_KEY", "dummy-key")
    with patch("app.services.scraping_service.perform_public_web_search", return_value=[]), \
         patch("app.services.scraping_service.fetch_url_safely", return_value={"success": False, "html": ""}), \
         patch("app.services.google_places_service.lookup_google_places_rating", create=True) as mock_google:

        res_map, telemetry = research_public_company_ratings("TestCorp", "https://testcorp.com")
        mock_google.assert_not_called()
        assert "Google Places API" not in telemetry.get("sources_checked", [])




def test_research_public_company_ratings_query_delay_applied(monkeypatch):
    """Delay of ~1.0s is applied between successive search queries."""
    monkeypatch.setattr("app.services.scraping_service.SEARCH_QUERY_DELAY", 1.0)

    sleep_calls = []
    def mock_sleep(seconds):
        sleep_calls.append(seconds)

    with patch("time.sleep", side_effect=mock_sleep), \
         patch("app.services.scraping_service.fetch_url_safely", return_value={"success": False, "html": ""}), \
         patch("app.services.scraping_service.perform_public_web_search", return_value=[]):

        res_map, telemetry = research_public_company_ratings("Delay Corp", "https://delaycorp.com")

        # First query runs immediately; subsequent queries must trigger sleep(1.0)
        assert len(sleep_calls) >= 1
        assert all(s == 1.0 for s in sleep_calls)
