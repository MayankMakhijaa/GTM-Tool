"""
Federated Multi-Engine Search Providers.
Defines isolated provider adapters for:
- Google (via OpenSerpClient /google/search)
- Bing (via OpenSerpClient /bing/search)
- Yandex (via OpenSerpClient /yandex/search)
- Baidu (via OpenSerpClient /baidu/search)
- DuckDuckGo (via OpenSerpClient /duckduckgo/search)
- Ecosia (via OpenSerpClient /ecosia/search)

Each provider is a thin adapter delegating to the canonical OpenSerpClient,
maintaining engine-isolated failure states, cooldowns, and normalized responses.
"""

import time
import logging
from typing import Dict, Any, List, Optional, Tuple
from abc import ABC, abstractmethod

from app.services.openserp_service import OpenSerpClient, default_openserp_client

logger = logging.getLogger(__name__)


class SearchProviderResult:
    def __init__(
        self,
        provider_name: str,
        engine: str,
        status: str,  # READY, SUCCESS, EMPTY_RESPONSE, RATE_LIMITED, CAPTCHA_DETECTED, TEMPORARILY_UNAVAILABLE, ERROR, etc.
        items: List[Dict[str, Any]],
        latency_ms: float = 0.0,
        error_message: Optional[str] = None,
        cooldown_seconds: float = 0.0
    ):
        self.provider_name = provider_name
        self.engine = engine
        self.status = status
        self.items = items
        self.latency_ms = latency_ms
        self.error_message = error_message
        self.cooldown_seconds = cooldown_seconds

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider_name": self.provider_name,
            "engine": self.engine,
            "status": self.status,
            "count": len(self.items),
            "items": self.items,
            "latency_ms": self.latency_ms,
            "error_message": self.error_message,
            "cooldown_seconds": self.cooldown_seconds
        }


class BaseSearchProvider(ABC):
    def __init__(
        self,
        name: str,
        engine: str,
        client: Optional[OpenSerpClient] = None,
        min_interval: float = 0.0
    ):
        self.name = name
        self.engine = engine.lower()
        self.client = client or default_openserp_client
        self.min_interval = min_interval
        self._last_request_time = 0.0

    def is_in_cooldown(self) -> Tuple[bool, float]:
        st = self.client.get_engine_status(self.engine)
        return st.get("is_in_cooldown", False), st.get("cooldown_remaining_seconds", 0.0)

    def set_cooldown(self, seconds: float):
        self.client.set_engine_cooldown(self.engine, seconds=seconds)

    def clear_cooldown(self):
        self.client.clear_engine_cooldown(self.engine)

    def enforce_pacing(self):
        if self.min_interval <= 0:
            return
        now = time.monotonic()
        elapsed = now - self._last_request_time
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_request_time = time.monotonic()

    def search(self, raw_query: str, limit: int = 10) -> SearchProviderResult:
        in_cd, rem = self.is_in_cooldown()
        if in_cd:
            return SearchProviderResult(
                provider_name=self.name,
                engine=self.engine,
                status="RATE_LIMITED" if "CAPTCHA" not in self.engine.upper() else "CAPTCHA_DETECTED",
                items=[],
                latency_ms=0.0,
                error_message=f"{self.name} cooldown active ({rem}s remaining)",
                cooldown_seconds=rem
            )

        self.enforce_pacing()

        res = self.client.search(
            engine=self.engine,
            query=raw_query,
            limit=limit
        )

        return SearchProviderResult(
            provider_name=self.name,
            engine=self.engine,
            status=res["status"],
            items=res["items"],
            latency_ms=res["latency_ms"],
            error_message=res["error_message"],
            cooldown_seconds=res["cooldown_seconds"]
        )


class OpenSerpGoogleProvider(BaseSearchProvider):
    def __init__(self, base_url: Optional[str] = None, client: Optional[OpenSerpClient] = None):
        c = client or (OpenSerpClient(base_url=base_url) if base_url else default_openserp_client)
        super().__init__(name="Google (OpenSERP)", engine="google", client=c, min_interval=0.0)
        self.base_url = c.base_url


class OpenSerpBingProvider(BaseSearchProvider):
    def __init__(self, base_url: Optional[str] = None, client: Optional[OpenSerpClient] = None):
        c = client or (OpenSerpClient(base_url=base_url) if base_url else default_openserp_client)
        super().__init__(name="Bing (OpenSERP)", engine="bing", client=c, min_interval=0.0)
        self.base_url = c.base_url


class OpenSerpYandexProvider(BaseSearchProvider):
    def __init__(self, base_url: Optional[str] = None, client: Optional[OpenSerpClient] = None):
        c = client or (OpenSerpClient(base_url=base_url) if base_url else default_openserp_client)
        super().__init__(name="Yandex (OpenSERP)", engine="yandex", client=c, min_interval=0.0)
        self.base_url = c.base_url


class OpenSerpBaiduProvider(BaseSearchProvider):
    def __init__(self, base_url: Optional[str] = None, client: Optional[OpenSerpClient] = None):
        c = client or (OpenSerpClient(base_url=base_url) if base_url else default_openserp_client)
        super().__init__(name="Baidu (OpenSERP)", engine="baidu", client=c, min_interval=0.0)
        self.base_url = c.base_url


class OpenSerpEcosiaProvider(BaseSearchProvider):
    def __init__(self, base_url: Optional[str] = None, client: Optional[OpenSerpClient] = None):
        c = client or (OpenSerpClient(base_url=base_url) if base_url else default_openserp_client)
        super().__init__(name="Ecosia (OpenSERP)", engine="ecosia", client=c, min_interval=0.0)
        self.base_url = c.base_url


class OpenSerpDuckDuckGoProvider(BaseSearchProvider):
    def __init__(self, base_url: Optional[str] = None, client: Optional[OpenSerpClient] = None):
        c = client or (OpenSerpClient(base_url=base_url) if base_url else default_openserp_client)
        super().__init__(name="DuckDuckGo (OpenSERP)", engine="duckduckgo", client=c, min_interval=0.0)
        self.base_url = c.base_url


# Backward-compatibility alias so any existing imports of NativeDuckDuckGoProvider continue to function cleanly
class NativeDuckDuckGoProvider(OpenSerpDuckDuckGoProvider):
    def __init__(self, base_url: Optional[str] = None, client: Optional[OpenSerpClient] = None):
        super().__init__(base_url=base_url, client=client)
        self.name = "DuckDuckGo (OpenSERP)"
