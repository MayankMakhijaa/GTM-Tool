import pytest
from unittest.mock import patch, MagicMock
from decimal import Decimal

from app.services.lead_validator import (
    is_safe_external_url,
    normalize_lead_identifier,
    validate_and_classify_candidate
)
from app.services.claude_service import discover_candidates_with_claude


# ====================================================================
# 1. Lead Evidence and URL Security Validator Tests
# ====================================================================

def test_url_ssrf_protection():
    """Verify SSRF blockers for internal, private, loopback and metadata addresses."""
    # Forbidden / SSRF
    assert is_safe_external_url("http://127.0.0.1/admin")[0] is False
    assert is_safe_external_url("http://localhost:8000/api")[0] is False
    assert is_safe_external_url("http://169.254.169.254/latest/meta-data/")[0] is False
    assert is_safe_external_url("http://metadata.google.internal/computeMetadata/v1/")[0] is False
    assert is_safe_external_url("ftp://example.com/file")[0] is False
    assert is_safe_external_url("javascript:alert(1)")[0] is False

    # Generic search roots without path
    assert is_safe_external_url("https://www.google.com/")[0] is False
    assert is_safe_external_url("https://bing.com/search")[0] is False

    # Valid external URLs
    assert is_safe_external_url("https://acme-saas.com/team/jane-doe")[0] is True
    assert is_safe_external_url("https://www.linkedin.com/in/janedoe")[0] is True
    assert is_safe_external_url("https://techcrunch.com/2026/10/acme-appoints-cro/")[0] is True


def test_normalize_lead_identifier():
    """Verify canonical identifier generation for deduplication."""
    # LinkedIn URL vanity extraction
    slug1 = normalize_lead_identifier("Jane Doe", "Acme Corp", "https://www.linkedin.com/in/janedoe?ref=trk")
    assert slug1 == "janedoe"

    # Non-LinkedIn web slug
    slug2 = normalize_lead_identifier("Jane Doe", "Acme Corp", "https://acme.com/team/jane")
    assert slug2 == "web:acme-corp:jane-doe"


def test_validate_and_classify_candidate_valid():
    """Verify that a complete candidate with evidence and valid URL is VERIFIED."""
    candidate = {
        "full_name": "Alice Smith",
        "job_title": "VP of Engineering",
        "company_name": "CloudScale Inc",
        "location": "Austin, TX",
        "industry": "Cloud Infrastructure",
        "source_url": "https://cloudscale.com/leadership/alice-smith",
        "source_evidence": "Alice Smith leads cloud architecture and engineering as VP of Engineering at CloudScale Inc."
    }

    status, sanitized, reason = validate_and_classify_candidate(candidate)
    assert status == "VERIFIED"
    assert reason is None
    assert sanitized["name"] == "Alice Smith"
    assert sanitized["role"] == "VP of Engineering"
    assert sanitized["company"] == "CloudScale Inc"
    assert sanitized["email"] is None  # Zero hallucination
    assert sanitized["phone"] is None  # Zero hallucination
    assert sanitized["verification_status"] == "VERIFIED"


def test_validate_and_classify_candidate_unverified_or_rejected():
    """Verify that empty evidence, missing names, or unsafe URLs are UNVERIFIED / REJECTED."""
    # Missing name
    c_no_name = {
        "job_title": "VP of Engineering",
        "company_name": "CloudScale Inc",
        "source_url": "https://cloudscale.com/leadership",
        "source_evidence": "Valid quote about the engineering department here."
    }
    status, _, reason = validate_and_classify_candidate(c_no_name)
    assert status == "REJECTED"
    assert "name" in reason.lower()

    # SSRF URL
    c_ssrf = {
        "full_name": "Bob Jones",
        "job_title": "CTO",
        "company_name": "Evil Corp",
        "source_url": "http://169.254.169.254/secret",
        "source_evidence": "Bob Jones is CTO at Evil Corp."
    }
    status, _, reason = validate_and_classify_candidate(c_ssrf)
    assert status == "REJECTED"
    assert "verification" in reason.lower()

    # Trivial / short evidence
    c_short_evidence = {
        "full_name": "Bob Jones",
        "job_title": "CTO",
        "company_name": "Acme",
        "source_url": "https://acme.com/about",
        "source_evidence": "CTO"  # < 15 chars
    }
    status, _, reason = validate_and_classify_candidate(c_short_evidence)
    assert status == "UNVERIFIED"
    assert "insufficient evidence" in reason.lower()


# ====================================================================
# 2. Claude Candidate Discovery Tests
# ====================================================================

@patch("app.services.claude_service.get_active_claude_api_key")
def test_claude_discovery_unconfigured(mock_key):
    """When Claude is unconfigured, discovery returns NOT_CONFIGURED without crashing."""
    mock_key.return_value = None
    res = discover_candidates_with_claude(
        structured_icp={"keyword_title": "VP Sales"},
        user_company={"company_name": "FameWeb"},
        count_needed=5
    )
    assert res["success"] is False
    assert res["status"] == "NOT_CONFIGURED"
    assert res["candidates"] == []


@patch("app.services.claude_service.get_active_claude_api_key")
@patch("app.services.claude_service.requests.post")
def test_claude_discovery_insufficient_credits(mock_post, mock_key):
    """When Anthropic returns 402 or 400 spend limit, discovery returns INSUFFICIENT_CREDITS."""
    mock_key.return_value = "sk-ant-api03-test-mock-key-valid-length-1234567890"

    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.headers = {"request-id": "req_mock_spend_limit"}
    mock_resp.json.return_value = {
        "type": "error",
        "error": {
            "type": "invalid_request_error",
            "message": "Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits."
        }
    }
    mock_post.return_value = mock_resp

    res = discover_candidates_with_claude(
        structured_icp={"keyword_title": "VP Sales"},
        user_company={"company_name": "FameWeb"},
        count_needed=5
    )
    assert res["success"] is False
    assert res["status"] == "INSUFFICIENT_CREDITS"
    assert res["error_category"] == "CREDIT_BALANCE_EXHAUSTED"
    assert res["candidates"] == []


@patch("app.services.claude_service.get_active_claude_api_key")
@patch("app.services.claude_service.requests.post")
def test_claude_discovery_success_payload(mock_post, mock_key):
    """When Anthropic returns valid candidate JSON, candidates are correctly extracted."""
    mock_key.return_value = "sk-ant-api03-test-mock-key-valid-length-1234567890"

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"request-id": "req_mock_success"}
    mock_resp.json.return_value = {
        "id": "msg_01mock",
        "type": "message",
        "role": "assistant",
        "model": "claude-sonnet-5-5",
        "usage": {"input_tokens": 150, "output_tokens": 120},
        "content": [
            {
                "type": "text",
                "text": """[
                    {
                        "full_name": "Sarah Connor",
                        "job_title": "Head of Revenue Operations",
                        "company_name": "Cyberdyne SaaS",
                        "location": "Los Angeles, CA",
                        "industry": "Software",
                        "source_url": "https://cyberdyne-saas.com/team/sarah",
                        "source_title": "Cyberdyne Leadership",
                        "source_evidence": "Sarah Connor serves as Head of Revenue Operations driving go-to-market architecture."
                    }
                ]"""
            }
        ]
    }
    mock_post.return_value = mock_resp

    res = discover_candidates_with_claude(
        structured_icp={"keyword_title": "Head of RevOps"},
        user_company={"company_name": "FameWeb"},
        count_needed=1
    )
    assert res["success"] is True
    assert res["status"] == "SUCCESS"
    assert len(res["candidates"]) == 1
    assert res["candidates"][0]["full_name"] == "Sarah Connor"

