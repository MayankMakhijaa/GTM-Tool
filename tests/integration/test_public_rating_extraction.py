import pytest
import time
from unittest.mock import patch, MagicMock
from app.services.scraping_service import (
    extract_trustpilot_rating_direct,
    research_public_company_ratings,
    enrich_company_with_multi_source_research,
    RATING_CACHE
)

@pytest.fixture(autouse=True)
def clear_rating_cache():
    """Clear in-memory rating cache before each test."""
    RATING_CACHE.clear()
    yield
    RATING_CACHE.clear()


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
    with patch("app.services.scraping_service.fetch_url_safely") as mock_fetch:
        mock_fetch.return_value = {"success": True, "html": mock_html}
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
    with patch("app.services.scraping_service.fetch_url_safely") as mock_fetch:
        mock_fetch.return_value = {"success": True, "html": mock_html}
        
        # First call - cache miss
        res1, telemetry1 = research_public_company_ratings("Cache Test", "https://cachetest.com")
        assert mock_fetch.call_count == 1
        assert telemetry1["status"] == "SUCCESS_TRUSTPILOT"
        
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


def test_enrich_company_with_multi_source_research_rating_integration():
    scraped_data = {
        "company_name": "Acme Inc",
        "website_url": "https://acme.com",
        "location": "San Francisco, CA",
        "company_size": "51–200 employees",
        "revenue": "$10M–$20M annual revenue",
        "rating": None,
        "provenance": {}
    }
    
    tp_item = {
        "score": 4.8,
        "max_rating": 5.0,
        "review_count": 850,
        "value": "4.8 / 5 (850 reviews on Trustpilot)",
        "source_name": "Trustpilot",
        "source_url": "https://www.trustpilot.com/review/acme.com",
        "evidence": "Trustpilot AggregateRating schema: 4.8/5 across 850 reviews",
        "retrieval_timestamp": "2026-10-02T20:00:00Z",
        "verification_status": "VERIFIED"
    }
    
    with patch("app.services.scraping_service.research_public_company_ratings") as mock_rating:
        mock_rating.return_value = ({"rating": tp_item}, {"status": "SUCCESS_TRUSTPILOT", "sources_checked": ["Trustpilot Direct"]})
        
        enriched_data, diag = enrich_company_with_multi_source_research(scraped_data, "Acme Inc", "https://acme.com")
        
        assert enriched_data["rating"] == "4.8 / 5 (850 reviews on Trustpilot)"
        assert enriched_data["provenance"]["rating"]["source_name"] == "Trustpilot"
        assert enriched_data["provenance"]["rating"]["verification_status"] == "VERIFIED"
        assert "rating" in diag["fields_enriched"]
