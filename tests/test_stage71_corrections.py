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

class TestStage71AuditAndCorrections(unittest.TestCase):
    def setUp(self):
        clear_federated_session_state(user_id=999)

    def tearDown(self):
        clear_federated_session_state(user_id=999)

    def test_live_session_progress_and_cancellation(self):
        user_id = 999
        mock_provider = MagicMock(spec=BaseSearchProvider)
        mock_provider.name = "MockBing"
        mock_provider.engine = "bing"
        mock_provider.is_in_cooldown.return_value = (False, 0.0)
        
        # When search is called, verify that session state is active
        def search_impl(*args, **kwargs):
            st = get_federated_session_state(user_id)
            self.assertIsNotNone(st)
            self.assertTrue(st["is_running"])
            self.assertEqual(st["current_query_index"], 1)
            self.assertEqual(st["current_provider"], "MockBing")
            return SearchProviderResult(
                provider_name="MockBing",
                engine="bing",
                status="SUCCESS",
                items=[{"title": "Alice Smith | LinkedIn", "url": "https://www.linkedin.com/in/alice-smith"}]
            )

        mock_provider.search.side_effect = search_impl
        orch = FederatedDiscoveryOrchestrator(providers=[mock_provider])
        orch.INTER_QUERY_INTERVAL = 0.0

        res = orch.execute_federated_discovery([{"title": "CEO"}], limit=10, user_id=user_id)
        self.assertTrue(res["success"])
        self.assertEqual(res["count"], 1)

        # Session should be marked not running after completion
        final_st = get_federated_session_state(user_id)
        self.assertFalse(final_st["is_running"])

    def test_request_federated_stop_terminates_further_dispatches(self):
        user_id = 999
        mock_provider = MagicMock(spec=BaseSearchProvider)
        mock_provider.name = "MockBing"
        mock_provider.engine = "bing"
        mock_provider.is_in_cooldown.return_value = (False, 0.0)
        
        sample_res = SearchProviderResult(
            provider_name="MockBing",
            engine="bing",
            status="SUCCESS",
            items=[{"title": "User One | LinkedIn", "url": "https://www.linkedin.com/in/user-one"}]
        )

        def search_impl(*args, **kwargs):
            # Signal stop during query 1 execution
            request_federated_stop(user_id)
            return sample_res

        mock_provider.search.side_effect = search_impl
        orch = FederatedDiscoveryOrchestrator(providers=[mock_provider])
        orch.INTER_QUERY_INTERVAL = 0.0

        queries = [{"title": "Q1"}, {"title": "Q2"}, {"title": "Q3"}]
        res = orch.execute_federated_discovery(queries, limit=10, user_id=user_id)

        # Call count must be exactly 1 because stop was signaled
        self.assertEqual(mock_provider.search.call_count, 1)
        self.assertEqual(res["count"], 1)

    def test_openserp_offline_reports_gracefully_without_crashing(self):
        # Point to unreachable port
        p_google = OpenSerpGoogleProvider(base_url="http://127.0.0.1:9999")
        p_bing = OpenSerpBingProvider(base_url="http://127.0.0.1:9999")
        p_yandex = OpenSerpYandexProvider(base_url="http://127.0.0.1:9999")

        res_g = p_google.search("site:linkedin.com/in test")
        res_b = p_bing.search("site:linkedin.com/in test")
        res_y = p_yandex.search("site:linkedin.com/in test")

        self.assertEqual(res_g.status, "ERROR")
        self.assertEqual(res_b.status, "ERROR")
        self.assertEqual(res_y.status, "ERROR")
        self.assertIn("connection", res_g.error_message.lower())

if __name__ == "__main__":
    unittest.main()

