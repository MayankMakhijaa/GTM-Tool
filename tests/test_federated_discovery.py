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
from app.services.discovery.orchestrator import FederatedDiscoveryOrchestrator

class TestFederatedDiscovery(unittest.TestCase):
    def test_query_string_formatting(self):
        orch = FederatedDiscoveryOrchestrator(providers=[])
        q = {
            "title": "VP Sales",
            "keywords": "B2B SaaS, outbound marketing",
            "location": "Bengaluru"
        }
        query_str = orch.build_query_string(q)
        self.assertIn("site:linkedin.com/in", query_str)
        self.assertIn('"VP Sales"', query_str)
        self.assertIn('"B2B SaaS"', query_str)
        self.assertNotIn("outbound marketing", query_str)  # Sanitized comma list
        self.assertIn("Bengaluru", query_str)

    def test_federated_orchestration_merges_duplicates_across_engines(self):
        # Create mock providers returning overlapping results
        mock_google = MagicMock(spec=BaseSearchProvider)
        mock_google.name = "Google (OpenSERP)"
        mock_google.engine = "google"
        mock_google.is_in_cooldown.return_value = (False, 0.0)
        mock_google.search.return_value = SearchProviderResult(
            provider_name="Google",
            engine="google",
            status="SUCCESS",
            items=[
                {
                    "title": "Aarav Sharma - VP Sales - TechCorp | LinkedIn",
                    "url": "https://www.linkedin.com/in/aarav-sharma",
                    "description": "VP Sales at TechCorp in Bengaluru"
                }
            ]
        )

        mock_bing = MagicMock(spec=BaseSearchProvider)
        mock_bing.name = "Bing (OpenSERP)"
        mock_bing.engine = "bing"
        mock_bing.is_in_cooldown.return_value = (False, 0.0)
        mock_bing.search.return_value = SearchProviderResult(
            provider_name="Bing",
            engine="bing",
            status="SUCCESS",
            items=[
                {
                    "title": "Aarav Sharma - VP Sales | LinkedIn",
                    "url": "https://in.linkedin.com/in/aarav-sharma",  # Regional subdomain, same slug
                    "description": "VP Sales at TechCorp in Bengaluru, India"
                },
                {
                    "title": "Priya Nair - Head of Engineering - Sell.Do | LinkedIn",
                    "url": "https://www.linkedin.com/in/priya-nair-dev",
                    "description": "Head of Engineering at Sell.Do"
                }
            ]
        )

        orch = FederatedDiscoveryOrchestrator(providers=[mock_google, mock_bing])
        orch.INTER_QUERY_INTERVAL = 0.0  # Fast execution in test

        queries = [{"title": "VP Sales", "keywords": "B2B SaaS", "location": "Bengaluru"}]
        res = orch.execute_federated_discovery(queries, limit=10)

        self.assertTrue(res["success"])
        self.assertEqual(res["unique_profiles_count"], 2)
        self.assertEqual(res["duplicates_count"], 1)

        # Candidate Aarav Sharma should have merged sources
        aarav = next(c for c in res["results"] if c["urn_id"] == "aarav-sharma")
        self.assertIn("google", aarav["sources"])
        self.assertIn("bing", aarav["sources"])
        self.assertEqual(aarav["name"], "Aarav Sharma")

    def test_provider_in_cooldown_is_skipped_without_affecting_others(self):
        mock_google = MagicMock(spec=BaseSearchProvider)
        mock_google.name = "Google (OpenSERP)"
        mock_google.engine = "google"
        mock_google.is_in_cooldown.return_value = (True, 150.0)  # In CAPTCHA cooldown

        mock_bing = MagicMock(spec=BaseSearchProvider)
        mock_bing.name = "Bing (OpenSERP)"
        mock_bing.engine = "bing"
        mock_bing.is_in_cooldown.return_value = (False, 0.0)
        mock_bing.search.return_value = SearchProviderResult(
            provider_name="Bing",
            engine="bing",
            status="SUCCESS",
            items=[
                {
                    "title": "Devika Sen - Chief Revenue Officer | LinkedIn",
                    "url": "https://www.linkedin.com/in/devika-sen",
                    "description": "CRO in Mumbai"
                }
            ]
        )

        orch = FederatedDiscoveryOrchestrator(providers=[mock_google, mock_bing])
        orch.INTER_QUERY_INTERVAL = 0.0

        res = orch.execute_federated_discovery([{"title": "Chief Revenue Officer"}], limit=10)

        self.assertEqual(res["unique_profiles_count"], 1)
        self.assertEqual(res["results"][0]["name"], "Devika Sen")
        # Google should be marked in cooldown in telemetry
        self.assertEqual(res["provider_telemetry"]["google"]["status"], "CAPTCHA_DETECTED")
        self.assertEqual(res["provider_telemetry"]["bing"]["status"], "SUCCESS")

    def test_early_stop_honors_cancellation(self):
        mock_provider = MagicMock(spec=BaseSearchProvider)
        mock_provider.name = "Bing"
        mock_provider.engine = "bing"
        mock_provider.is_in_cooldown.return_value = (False, 0.0)
        
        sample_res = SearchProviderResult(
            provider_name="Bing",
            engine="bing",
            status="SUCCESS",
            items=[{"title": "User One | LinkedIn", "url": "https://www.linkedin.com/in/user-one"}]
        )

        should_stop = False
        def check_stop():
            nonlocal should_stop
            return should_stop

        # Simulate stop after first query
        queries = [{"title": "Q1"}, {"title": "Q2"}, {"title": "Q3"}]
        
        def mock_search(*args, **kwargs):
            nonlocal should_stop
            should_stop = True
            return sample_res

        mock_provider.search.side_effect = mock_search

        orch = FederatedDiscoveryOrchestrator(providers=[mock_provider])
        orch.INTER_QUERY_INTERVAL = 0.0

        res = orch.execute_federated_discovery(queries, limit=10, stop_check_fn=check_stop)
        # Should only execute Q1, then abort before Q2
        self.assertEqual(mock_provider.search.call_count, 1)
        self.assertEqual(res["unique_profiles_count"], 1)

if __name__ == "__main__":
    unittest.main()
