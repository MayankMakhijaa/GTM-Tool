"""
tests/integration/test_google_places_rating_fallback.py

Comprehensive test suite verifying the Google-First company rating resolution architecture:
1. Google finds verified rating -> Google called, public sources NOT called.
2. Google finds no confident match -> public sources called.
3. Google finds company but no rating -> public sources called.
4. Google API unavailable -> public sources called.
5. Google missing API key -> no crash, public sources called.
6. Public source finds rating after Google fails -> public rating returned.
7. Google and public sources both fail -> preserve correct NOT_FOUND / SEARCH_UNAVAILABLE semantics.
8. Existing non-empty rating -> Google NOT called.
9. Manually edited rating -> Google/public fallback must not overwrite it.
10. Similar company names -> conservative Google matching.
11. Successful Google rating -> verify no unnecessary public-search network calls occur.
"""
import pytest
from unittest.mock import patch, MagicMock
from app.services.google_places_service import (
    lookup_google_places_rating,
    match_google_place_candidate
)
from app.services.scraping_service import (
    research_public_company_ratings,
    enrich_company_with_multi_source_research,
    SearchEngineUnavailableError,
    RATING_CACHE
)


@pytest.fixture(autouse=True)
def clear_rating_cache():
    RATING_CACHE.clear()
    yield
    RATING_CACHE.clear()


def test_1_google_finds_verified_rating_public_sources_not_called(monkeypatch):
    """1. When Google Places finds a verified rating, Google is called and public sources are NOT called."""
    monkeypatch.setattr("config.Config.GOOGLE_MAPS_API_KEY", "test-maps-key")

    mock_google_resp = {
        "status": "OK",
        "results": [
            {
                "name": "Acme Tech Solutions",
                "formatted_address": "123 Market St, San Francisco, CA 94105",
                "rating": 4.8,
                "user_ratings_total": 45,
                "place_id": "ChIJ_acme_456"
            }
        ]
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_google_resp

    with patch("requests.get", return_value=mock_resp), \
         patch("app.services.scraping_service.perform_public_web_search") as mock_public_search, \
         patch("app.services.scraping_service.fetch_url_safely") as mock_fetch:

        res_map, telemetry = research_public_company_ratings("Acme Tech Solutions", "https://acmetech.com", location="San Francisco")

        assert res_map is not None
        item = res_map["rating"]
        assert item["source_name"] == "Google Places"
        assert item["score"] == 4.8
        assert item["review_count"] == 45
        assert "4.8 / 5 (45 reviews on Google Maps)" in item["value"]
        assert item["verification_status"] == "VERIFIED"
        assert telemetry["status"] == "SUCCESS_GOOGLE_PLACES"
        assert telemetry["sources_checked"] == ["Google Places API"]

        # Critical: Public search and fetch MUST NOT be called!
        mock_public_search.assert_not_called()
        mock_fetch.assert_not_called()


def test_2_google_finds_no_confident_match_public_sources_called(monkeypatch):
    """2. When Google finds no confident match, fallback public sources are called."""
    monkeypatch.setattr("config.Config.GOOGLE_MAPS_API_KEY", "test-maps-key")

    mock_google_resp = {
        "status": "OK",
        "results": [
            {
                "name": "Unrelated Bakery",
                "formatted_address": "Faridabad",
                "rating": 4.5,
                "user_ratings_total": 10,
                "place_id": "ChIJ_bakery"
            }
        ]
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_google_resp

    mock_jd_leads = [
        {
            "title": "Fameweb, Sector 16, Faridabad - Justdial",
            "snippet": "Rated 4.6 based on 5 Customer Reviews.",
            "url": "https://www.justdial.com/Faridabad/Fameweb"
        }
    ]

    with patch("requests.get", return_value=mock_resp), \
         patch("app.services.scraping_service.perform_public_web_search", return_value=mock_jd_leads) as mock_public_search:

        res_map, telemetry = research_public_company_ratings("Fameweb", "https://fameweb.in", location="Faridabad")

        assert res_map is not None
        assert res_map["rating"]["source_name"] == "Justdial"
        assert res_map["rating"]["verification_status"] == "VERIFIED"
        assert telemetry["status"] == "SUCCESS_JUSTDIAL"
        # Public search was indeed called as fallback
        assert mock_public_search.called


def test_3_google_finds_company_but_no_rating_public_sources_called(monkeypatch):
    """3. When Google finds the company but has no rating field, fall back to public sources."""
    monkeypatch.setattr("config.Config.GOOGLE_MAPS_API_KEY", "test-maps-key")

    mock_google_resp = {
        "status": "OK",
        "results": [
            {
                "name": "Fameweb",
                "formatted_address": "Sector 16, Faridabad",
                # no 'rating' field
                "place_id": "ChIJ_fameweb_norating"
            }
        ]
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_google_resp

    mock_ab_leads = [
        {
            "title": "Fameweb Reviews and Ratings - AmbitionBox",
            "snippet": "Fameweb is rated 5.0 out of 5 based on employee reviews.",
            "url": "https://www.ambitionbox.com/reviews/fameweb-reviews"
        }
    ]

    with patch("requests.get", return_value=mock_resp), \
         patch("app.services.scraping_service.perform_public_web_search", return_value=mock_ab_leads) as mock_public_search:

        res_map, telemetry = research_public_company_ratings("Fameweb", "https://fameweb.in")

        assert res_map is not None
        assert res_map["rating"]["source_name"] == "AmbitionBox"
        assert res_map["rating"]["verification_status"] == "VERIFIED"
        assert telemetry["status"] == "SUCCESS_AMBITIONBOX"
        assert mock_public_search.called


def test_4_google_api_unavailable_public_sources_called(monkeypatch):
    """4. When Google API is unavailable (e.g. REQUEST_DENIED or network error), fall back to public sources without crashing."""
    monkeypatch.setattr("config.Config.GOOGLE_MAPS_API_KEY", "test-maps-key")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "status": "REQUEST_DENIED",
        "error_message": "The provided API key is invalid."
    }

    mock_gf_leads = [
        {
            "title": "CloudScale Solutions Reviews - GoodFirms",
            "snippet": "Rated 4.8 out of 5.0 based on 12 client reviews on GoodFirms.",
            "url": "https://www.goodfirms.co/company/cloudscale-solutions"
        }
    ]

    with patch("requests.get", return_value=mock_resp), \
         patch("app.services.scraping_service.perform_public_web_search", return_value=mock_gf_leads) as mock_public_search:

        res_map, telemetry = research_public_company_ratings("CloudScale Solutions", "https://cloudscale.io")

        assert res_map is not None
        assert res_map["rating"]["source_name"] == "GoodFirms"
        assert res_map["rating"]["verification_status"] == "VERIFIED"
        assert telemetry["status"] == "SUCCESS_GOODFIRMS"
        assert mock_public_search.called


def test_5_google_missing_api_key_no_crash_public_sources_called(monkeypatch):
    """5. When Google API key is missing or placeholder, no crash occurs and public sources are called."""
    monkeypatch.setattr("config.Config.GOOGLE_MAPS_API_KEY", None)
    monkeypatch.setattr("config.Config.GOOGLE_PLACES_API_KEY", None)
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_PLACES_API_KEY", raising=False)

    mock_sul_leads = [
        {
            "title": "Alpha Corp, Delhi - Sulekha",
            "snippet": "Rated 4.4 out of 5 based on 20 ratings on Sulekha.",
            "url": "https://www.sulekha.com/alpha-corp-delhi"
        }
    ]

    with patch("app.services.scraping_service.perform_public_web_search", return_value=mock_sul_leads) as mock_public_search:
        res_map, telemetry = research_public_company_ratings("Alpha Corp", "https://alphacorp.in")

        assert res_map is not None
        assert res_map["rating"]["source_name"] == "Sulekha"
        assert res_map["rating"]["verification_status"] == "VERIFIED"
        assert telemetry["status"] == "SUCCESS_SULEKHA"
        assert mock_public_search.called


def test_6_public_source_finds_rating_after_google_fails(monkeypatch):
    """6. When Google returns no match, public directory snippet (e.g. Trustpilot snippet) returns VERIFIED rating."""
    monkeypatch.setattr("config.Config.GOOGLE_MAPS_API_KEY", "test-maps-key")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "ZERO_RESULTS", "results": []}

    mock_tp_leads = [
        {
            "title": "Star Corp Reviews | Read Customer Service Reviews of starcorp.io",
            "snippet": "Star Corp has a rating of 4.5 / 5 based on 80 reviews on Trustpilot.",
            "url": "https://www.trustpilot.com/review/starcorp.io"
        }
    ]

    with patch("requests.get", return_value=mock_resp), \
         patch("app.services.scraping_service.fetch_url_safely", return_value={"success": False, "html": ""}), \
         patch("app.services.scraping_service.perform_public_web_search", return_value=mock_tp_leads):

        res_map, telemetry = research_public_company_ratings("Star Corp", "https://starcorp.io")

        assert res_map is not None
        assert res_map["rating"]["source_name"] == "Trustpilot"
        assert res_map["rating"]["score"] == 4.5
        assert res_map["rating"]["verification_status"] == "VERIFIED"
        assert telemetry["status"] == "SUCCESS_TRUSTPILOT"


def test_7_google_and_public_sources_both_fail_semantics(monkeypatch):
    """7. When both Google and public sources fail, correct NOT_FOUND vs SEARCH_UNAVAILABLE semantics are preserved."""
    monkeypatch.setattr("config.Config.GOOGLE_MAPS_API_KEY", "test-maps-key")

    # Case A: Google has ZERO_RESULTS, public searches return empty (clean NOT_FOUND)
    mock_resp_zero = MagicMock()
    mock_resp_zero.status_code = 200
    mock_resp_zero.json.return_value = {"status": "ZERO_RESULTS", "results": []}

    with patch("requests.get", return_value=mock_resp_zero), \
         patch("app.services.scraping_service.perform_public_web_search", return_value=[]), \
         patch("app.services.scraping_service.fetch_url_safely", return_value={"success": False, "html": ""}):

        res_map, telemetry = research_public_company_ratings("Unknown Corp", "https://unknowncorp.xyz")

        assert res_map is not None
        assert res_map["rating"]["verification_status"] == "NOT_FOUND"
        assert res_map["rating"]["value"] == "Not available"
        assert telemetry["status"] == "NO_RATING_FOUND"

    RATING_CACHE.clear()

    # Case B: Google is REQUEST_DENIED, public searches fail with SearchEngineUnavailableError
    mock_resp_err = MagicMock()
    mock_resp_err.status_code = 200
    mock_resp_err.json.return_value = {"status": "REQUEST_DENIED", "error_message": "Invalid Key"}

    with patch("requests.get", return_value=mock_resp_err), \
         patch("app.services.scraping_service.perform_public_web_search", side_effect=SearchEngineUnavailableError("Timeout")), \
         patch("app.services.scraping_service.fetch_url_safely", return_value={"success": False, "html": ""}):

        res_map, telemetry = research_public_company_ratings("Down Corp", "https://downcorp.com")

        assert res_map is not None
        assert res_map["rating"]["verification_status"] == "SEARCH_UNAVAILABLE"
        assert res_map["rating"]["value"] == "Search unavailable"
        assert telemetry["status"] == "SEARCH_UNAVAILABLE"


def test_8_existing_non_empty_rating_google_not_called():
    """8. If an existing non-empty rating is already present, Google Places is never called during enrichment."""
    scraped_data = {
        "company_name": "Fameweb",
        "rating": "5.0 / 5 (AmbitionBox)",
        "location": "Faridabad",
        "company_size": "11-50",
        "revenue": "$1M-$5M",
        "provenance": {
            "rating": {
                "value": "5.0 / 5 (AmbitionBox)",
                "verification_status": "VERIFIED"
            }
        }
    }

    with patch("app.services.scraping_service.lookup_google_places_rating") as mock_google:
        enriched, diag = enrich_company_with_multi_source_research(
            scraped_data=scraped_data,
            website_url="https://fameweb.in",
            company_name="Fameweb"
        )

        assert enriched["rating"] == "5.0 / 5 (AmbitionBox)"
        mock_google.assert_not_called()
        assert diag.get("google_places_status") == "SKIPPED"


def test_9_manually_edited_rating_never_overwritten_by_backfill():
    """9. In backfill, a record whose rating was manually edited is protected and never touched."""
    from scripts.backfill_company_ratings import backfill_company_ratings

    mock_record = MagicMock()
    mock_record.id = 1
    mock_record.user_id = 99
    mock_record.company_name = "Manual Co"
    mock_record.website_url = "https://manualco.com"
    mock_record.location = "Mumbai"
    mock_record.rating = None
    mock_record.edited_fields = ["rating"]

    mock_query = MagicMock()
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = [mock_record]

    with patch("scripts.backfill_company_ratings.db_session") as mock_db, \
         patch("app.services.scraping_service.lookup_google_places_rating") as mock_google:
        mock_db.query.return_value = mock_query

        stats = backfill_company_ratings(dry_run=True)

        assert stats["skipped_manual_edit"] == 1
        assert stats["updated"] == 0
        mock_google.assert_not_called()


def test_10_similar_company_names_conservative_google_matching(monkeypatch):
    """10. When Google returns multiple similarly named companies, conservative matching picks only the exact company."""
    monkeypatch.setattr("config.Config.GOOGLE_MAPS_API_KEY", "test-maps-key")

    mock_google_resp = {
        "status": "OK",
        "results": [
            {
                "name": "Fame Unisex Salon",
                "formatted_address": "Faridabad, Haryana",
                "rating": 4.2,
                "user_ratings_total": 30,
                "place_id": "ChIJ_salon"
            },
            {
                "name": "Fame Dance Academy",
                "formatted_address": "Faridabad, Haryana",
                "rating": 4.9,
                "user_ratings_total": 80,
                "place_id": "ChIJ_dance"
            },
            {
                "name": "Fameweb",
                "formatted_address": "Sector 16, Faridabad, Haryana",
                "rating": 5.0,
                "user_ratings_total": 8,
                "place_id": "ChIJ_fameweb"
            }
        ]
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_google_resp

    with patch("requests.get", return_value=mock_resp), \
         patch("app.services.scraping_service.perform_public_web_search") as mock_public_search:

        res_map, telemetry = research_public_company_ratings("Fameweb", "https://fameweb.in", location="Faridabad")

        assert res_map is not None
        item = res_map["rating"]
        assert item["score"] == 5.0  # Selected exact company, rejected salon (4.2) and dance academy (4.9)
        assert item["review_count"] == 8
        assert "place_id:ChIJ_fameweb" in item["source_url"]
        mock_public_search.assert_not_called()


def test_11_successful_google_rating_skips_all_network_calls(monkeypatch):
    """11. Successful Google rating verifies zero public search network calls occur."""
    monkeypatch.setattr("config.Config.GOOGLE_MAPS_API_KEY", "test-maps-key")

    mock_google_resp = {
        "status": "OK",
        "results": [
            {
                "name": "Spotify Technology",
                "formatted_address": "Stockholm, Sweden",
                "rating": 4.4,
                "user_ratings_total": 5000,
                "place_id": "ChIJ_spotify"
            }
        ]
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_google_resp

    with patch("requests.get", return_value=mock_resp), \
         patch("app.services.scraping_service.perform_public_web_search") as mock_search, \
         patch("app.services.scraping_service.fetch_url_safely") as mock_fetch, \
         patch("app.services.scraping_service.extract_trustpilot_rating_direct") as mock_tp_direct:

        res_map, telemetry = research_public_company_ratings("Spotify", "https://open.spotify.com")

        assert res_map is not None
        assert res_map["rating"]["source_name"] == "Google Places"
        assert res_map["rating"]["score"] == 4.4
        assert res_map["rating"]["verification_status"] == "VERIFIED"

        mock_search.assert_not_called()
        mock_fetch.assert_not_called()
        mock_tp_direct.assert_not_called()
