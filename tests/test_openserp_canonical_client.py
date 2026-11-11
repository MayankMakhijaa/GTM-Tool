import io
import json
import urllib.request
import urllib.error
import pytest
from unittest.mock import patch, MagicMock

from app.services.openserp_service import (
    OpenSerpClient,
    SUPPORTED_ENGINES,
    ENGINE_ENDPOINTS
)
from app.services.discovery.providers import (
    OpenSerpGoogleProvider,
    OpenSerpBingProvider,
    OpenSerpYandexProvider,
    OpenSerpBaiduProvider,
    OpenSerpEcosiaProvider,
    OpenSerpDuckDuckGoProvider,
    NativeDuckDuckGoProvider
)


class DummyHTTPResponse:
    def __init__(self, body_bytes: bytes, status: int = 200):
        self.body_bytes = body_bytes
        self.status = status

    def read(self):
        return self.body_bytes

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


def test_supported_engines_and_endpoints():
    client = OpenSerpClient(base_url="http://127.0.0.1:7000")
    assert len(SUPPORTED_ENGINES) == 6
    assert set(SUPPORTED_ENGINES) == {"google", "bing", "yandex", "baidu", "duckduckgo", "ecosia"}
    for eng in SUPPORTED_ENGINES:
        assert eng in ENGINE_ENDPOINTS
        st = client.get_engine_status(eng)
        assert st["supported"] is True
        assert st["is_in_cooldown"] is False


def test_health_check_success():
    client = OpenSerpClient(base_url="http://127.0.0.1:7000")
    dummy_resp = DummyHTTPResponse(b"OK", status=200)

    with patch("urllib.request.urlopen", return_value=dummy_resp):
        res = client.health_check(timeout=2.0)
        assert res["healthy"] is True
        assert res["status_code"] == 200
        assert res["message"] == "OK"


def test_health_check_failure():
    client = OpenSerpClient(base_url="http://127.0.0.1:7000")

    with patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
        res = client.health_check(timeout=2.0)
        assert res["healthy"] is False
        assert "Connection refused" in res["error"]


def test_normalization_with_both_snippet_and_description():
    # Item with snippet
    item_snippet = {
        "title": "Jane Doe - VP Marketing",
        "url": "https://www.linkedin.com/in/jane-doe",
        "snippet": "Experienced VP Marketing at TechCorp"
    }
    norm1 = OpenSerpClient.normalize_result_item(item_snippet, "google", rank=1)
    assert norm1["title"] == "Jane Doe - VP Marketing"
    assert norm1["url"] == "https://www.linkedin.com/in/jane-doe"
    assert norm1["snippet"] == "Experienced VP Marketing at TechCorp"
    assert norm1["description"] == "Experienced VP Marketing at TechCorp"
    assert norm1["domain"] == "www.linkedin.com"
    assert norm1["engine"] == "google"
    assert norm1["rank"] == 1

    # Item with description
    item_desc = {
        "title": "John Smith - CTO",
        "url": "https://de.linkedin.com/in/john-smith",
        "description": "CTO based in Berlin"
    }
    norm2 = OpenSerpClient.normalize_result_item(item_desc, "bing", rank=2)
    assert norm2["title"] == "John Smith - CTO"
    assert norm2["snippet"] == "CTO based in Berlin"
    assert norm2["description"] == "CTO based in Berlin"
    assert norm2["domain"] == "de.linkedin.com"
    assert norm2["engine"] == "bing"
    assert norm2["rank"] == 2


@pytest.mark.parametrize("engine,endpoint", [
    ("google", "/google/search"),
    ("bing", "/bing/search"),
    ("yandex", "/yandex/search"),
    ("baidu", "/baidu/search"),
    ("duckduckgo", "/duckduckgo/search"),
    ("ecosia", "/ecosia/search")
])
def test_all_six_engine_endpoints_dispatched(engine, endpoint):
    client = OpenSerpClient(base_url="http://127.0.0.1:7000")
    dummy_payload = json.dumps({
        "results": [
            {
                "title": f"Candidate from {engine}",
                "url": f"https://www.linkedin.com/in/candidate-{engine}",
                "snippet": f"Summary from {engine}"
            }
        ]
    }).encode("utf-8")

    captured_url = []

    def mock_urlopen(req, timeout):
        captured_url.append(req.full_url)
        return DummyHTTPResponse(dummy_payload, status=200)

    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        res = client.search(engine=engine, query="site:linkedin.com/in VP Sales", limit=5)
        assert res["status"] == "SUCCESS"
        assert res["count"] == 1
        assert res["engine"] == engine
        assert res["items"][0]["title"] == f"Candidate from {engine}"
        assert f"http://127.0.0.1:7000{endpoint}?text=" in captured_url[0]


def test_independent_engine_cooldown_isolation():
    client = OpenSerpClient(base_url="http://127.0.0.1:7000", cooldown_duration=300.0)

    # Trigger a 429 rate limit on Google
    http_429 = urllib.error.HTTPError(
        url="http://127.0.0.1:7000/google/search",
        code=429,
        msg="Too Many Requests",
        hdrs={},
        fp=io.BytesIO(b"rate limit exceeded")
    )

    with patch("urllib.request.urlopen", side_effect=http_429):
        res_google = client.search(engine="google", query="test query")
        assert res_google["status"] == "HTTP_429"
        assert res_google["cooldown_seconds"] > 0

    # Google should now be in cooldown
    google_st = client.get_engine_status("google")
    assert google_st["is_in_cooldown"] is True
    assert google_st["cooldown_remaining_seconds"] > 200

    # Next immediate Google search should be blocked by cooldown without making HTTP call
    res_google_blocked = client.search(engine="google", query="test query 2")
    assert res_google_blocked["status"] == "RATE_LIMITED"
    assert "in active cooldown" in res_google_blocked["error_message"]

    # CRITICAL: Bing, Yandex, Baidu, DuckDuckGo, and Ecosia must NOT be affected!
    for other_engine in ["bing", "yandex", "baidu", "duckduckgo", "ecosia"]:
        st = client.get_engine_status(other_engine)
        assert st["is_in_cooldown"] is False, f"Engine {other_engine} was falsely put in cooldown!"

    # Test that Bing search succeeds even while Google is in cooldown
    dummy_payload = json.dumps({"results": [{"title": "Bing Candidate", "url": "https://linkedin.com/in/b", "snippet": "ok"}]}).encode("utf-8")
    with patch("urllib.request.urlopen", return_value=DummyHTTPResponse(dummy_payload)):
        res_bing = client.search(engine="bing", query="test bing")
        assert res_bing["status"] == "SUCCESS"
        assert res_bing["count"] == 1


def test_error_classification():
    client = OpenSerpClient(base_url="http://127.0.0.1:7000")

    # 1. CAPTCHA error
    http_captcha = urllib.error.HTTPError(
        url="http://127.0.0.1:7000/yandex/search",
        code=403,
        msg="Forbidden",
        hdrs={},
        fp=io.BytesIO(b"captcha challenge required")
    )
    with patch("urllib.request.urlopen", side_effect=http_captcha):
        res = client.search(engine="yandex", query="test")
        assert res["status"] == "CAPTCHA_DETECTED"
        assert client.get_engine_status("yandex")["is_in_cooldown"] is True

    # 2. Timeout error
    timeout_err = urllib.error.URLError("operation timed out")
    with patch("urllib.request.urlopen", side_effect=timeout_err):
        res = client.search(engine="duckduckgo", query="test")
        assert res["status"] == "TIMEOUT"

    # 3. Connection error
    conn_err = urllib.error.URLError("Connection refused")
    with patch("urllib.request.urlopen", side_effect=conn_err):
        res = client.search(engine="ecosia", query="test")
        assert res["status"] == "CONNECTION_ERROR"

    # 4. Invalid JSON
    invalid_json = DummyHTTPResponse(b"<html>502 Bad Gateway</html>", status=200)
    with patch("urllib.request.urlopen", return_value=invalid_json):
        res = client.search(engine="baidu", query="test")
        assert res["status"] == "INVALID_RESPONSE"


def test_provider_adapters_delegation():
    client = OpenSerpClient(base_url="http://127.0.0.1:7000")
    dummy_payload = json.dumps({
        "results": [{"title": "Prov Candidate", "url": "https://linkedin.com/in/p", "snippet": "ok"}]
    }).encode("utf-8")

    providers = [
        OpenSerpGoogleProvider(client=client),
        OpenSerpBingProvider(client=client),
        OpenSerpYandexProvider(client=client),
        OpenSerpBaiduProvider(client=client),
        OpenSerpEcosiaProvider(client=client),
        OpenSerpDuckDuckGoProvider(client=client),
        NativeDuckDuckGoProvider(client=client)  # Backward compat alias
    ]

    with patch("urllib.request.urlopen", return_value=DummyHTTPResponse(dummy_payload)):
        for prov in providers:
            res = prov.search("VP Marketing", limit=5)
            assert res.status == "SUCCESS"
            assert len(res.items) == 1
            assert res.items[0]["title"] == "Prov Candidate"
            assert res.items[0]["url"] == "https://linkedin.com/in/p"
            assert res.items[0]["engine"] == prov.engine

