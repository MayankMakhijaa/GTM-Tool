import unittest
from unittest.mock import patch, MagicMock
from app.services.discovery.providers import (
    BaseSearchProvider,
    OpenSerpGoogleProvider,
    OpenSerpBingProvider,
    NativeDuckDuckGoProvider,
    OpenSerpYandexProvider,
    SearchProviderResult
)
from app.services.discovery.orchestrator import (
    FederatedDiscoveryOrchestrator,
    get_federated_session_state,
    request_federated_stop,
    clear_federated_session_state
)

class TestStage72Stability(unittest.TestCase):
    def setUp(self):
        clear_federated_session_state(user_id=888)

    def tearDown(self):
        clear_federated_session_state(user_id=888)

    def test_openserp_offline_does_not_block_duckduckgo(self):
        # OpenSERP engines on dead port
        p_google = OpenSerpGoogleProvider(base_url="http://127.0.0.1:9999")
        p_bing = OpenSerpBingProvider(base_url="http://127.0.0.1:9999")
        
        # DDG mock operational
        mock_ddg = MagicMock(spec=BaseSearchProvider)
        mock_ddg.name = "DuckDuckGo (Native)"
        mock_ddg.engine = "duckduckgo"
        mock_ddg.is_in_cooldown.return_value = (False, 0.0)
        mock_ddg.search.return_value = SearchProviderResult(
            provider_name="DuckDuckGo (Native)",
            engine="duckduckgo",
            status="SUCCESS",
            items=[{"title": "Priya Sharma - VP Sales | LinkedIn", "url": "https://in.linkedin.com/in/priya-sharma"}]
        )

        orch = FederatedDiscoveryOrchestrator(providers=[p_google, p_bing, mock_ddg])
        orch.INTER_QUERY_INTERVAL = 0.0

        res = orch.execute_federated_discovery([{"title": "VP Sales"}], limit=10, user_id=888)
        self.assertTrue(res["success"])
        self.assertEqual(res["count"], 1)
        self.assertEqual(res["results"][0]["name"], "Priya Sharma")
        self.assertEqual(res["provider_telemetry"]["google"]["status"], "ERROR")
        self.assertEqual(res["provider_telemetry"]["bing"]["status"], "ERROR")
        self.assertEqual(res["provider_telemetry"]["duckduckgo"]["status"], "SUCCESS")

    def test_concurrent_discovery_session_blocked_gracefully(self):
        user_id = 888
        mock_p = MagicMock(spec=BaseSearchProvider)
        mock_p.name = "Bing"
        mock_p.engine = "bing"
        mock_p.is_in_cooldown.return_value = (False, 0.0)
        mock_p.search.return_value = SearchProviderResult(provider_name="Bing", engine="bing", status="SUCCESS", items=[])

        orch = FederatedDiscoveryOrchestrator(providers=[mock_p])

        # Simulate Session 1 starting
        orch.execute_federated_discovery(queries=[], limit=10, user_id=user_id, session_id="sess_1")
        
        # Manually verify that trying to start Session 2 while Session 1 is active returns CONCURRENT_DISCOVERY_BLOCKED
        from app.services.discovery.orchestrator import _active_federated_sessions, _federated_lock
        with _federated_lock:
            _active_federated_sessions[user_id]["is_running"] = True

        res2 = orch.execute_federated_discovery(queries=[{"title": "Q"}], limit=10, user_id=user_id, session_id="sess_2")
        self.assertFalse(res2["success"])
        self.assertEqual(res2["status"], "CONCURRENT_DISCOVERY_BLOCKED")

    def test_session_id_isolation_for_stop_and_polling(self):
        user_id = 888
        orch = FederatedDiscoveryOrchestrator(providers=[])
        # Start sess_A
        orch.execute_federated_discovery(queries=[], limit=10, user_id=user_id, session_id="sess_A")

        # Polling with wrong session_id returns None
        st_wrong = get_federated_session_state(user_id, session_id="sess_B")
        self.assertIsNone(st_wrong)

        # Polling with correct session_id returns dict
        st_correct = get_federated_session_state(user_id, session_id="sess_A")
        self.assertIsNotNone(st_correct)

        # Stop with wrong session_id is ignored
        stopped_wrong = request_federated_stop(user_id, session_id="sess_B")
        self.assertFalse(stopped_wrong)

        # Stop with correct session_id succeeds
        stopped_correct = request_federated_stop(user_id, session_id="sess_A")
        self.assertTrue(stopped_correct)

if __name__ == "__main__":
    unittest.main()

