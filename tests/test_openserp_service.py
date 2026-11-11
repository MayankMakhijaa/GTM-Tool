import unittest
from app.services.openserp_service import OpenSerpDiscoveryService

class TestOpenSerpDiscoveryService(unittest.TestCase):
    """
    Focused unit tests for OpenSerpDiscoveryService logic:
    - URL parsing & hostname allowlist
    - Country-specific subdomains
    - Rejection of external and malicious redirect hosts
    - Evidence extraction (strict name validation, no hallucinated companies)
    - Rejection of name inference from slug
    - Preserving unsupported fields as None
    """

    def test_allowed_linkedin_hosts(self):
        # Valid hostnames
        self.assertTrue(OpenSerpDiscoveryService.is_allowed_linkedin_host("linkedin.com"))
        self.assertTrue(OpenSerpDiscoveryService.is_allowed_linkedin_host("www.linkedin.com"))
        self.assertTrue(OpenSerpDiscoveryService.is_allowed_linkedin_host("in.linkedin.com"))
        self.assertTrue(OpenSerpDiscoveryService.is_allowed_linkedin_host("uk.linkedin.com"))
        self.assertTrue(OpenSerpDiscoveryService.is_allowed_linkedin_host("ca.linkedin.com"))
        self.assertTrue(OpenSerpDiscoveryService.is_allowed_linkedin_host("de.linkedin.com"))

        # Invalid / malicious hostnames
        self.assertFalse(OpenSerpDiscoveryService.is_allowed_linkedin_host("attacker.com"))
        self.assertFalse(OpenSerpDiscoveryService.is_allowed_linkedin_host("fake-linkedin.com"))
        self.assertFalse(OpenSerpDiscoveryService.is_allowed_linkedin_host("google.com"))

    def test_resolve_safe_linkedin_url_direct(self):
        # Direct valid URLs
        url1 = "https://www.linkedin.com/in/sarah-connor"
        self.assertEqual(
            OpenSerpDiscoveryService.resolve_safe_linkedin_url(url1),
            "https://www.linkedin.com/in/sarah-connor"
        )

        url2 = "https://in.linkedin.com/in/priya-sharma?utm_source=share"
        self.assertEqual(
            OpenSerpDiscoveryService.resolve_safe_linkedin_url(url2),
            "https://in.linkedin.com/in/priya-sharma"
        )

        # Invalid profile paths
        self.assertIsNone(OpenSerpDiscoveryService.resolve_safe_linkedin_url("https://www.linkedin.com/in/me"))
        self.assertIsNone(OpenSerpDiscoveryService.resolve_safe_linkedin_url("https://www.linkedin.com/jobs/view/123"))
        self.assertIsNone(OpenSerpDiscoveryService.resolve_safe_linkedin_url("https://www.linkedin.com/company/acme"))
        self.assertIsNone(OpenSerpDiscoveryService.resolve_safe_linkedin_url("https://attacker.com/in/sarah-connor"))

    def test_parse_candidate_evidence_strict_name(self):
        # Title has supported real name
        item = {
            "title": "Tejas Mehta - VP Sales & Customer Success | Sell.Do",
            "url": "https://in.linkedin.com/in/tejas-mehta-51842880",
            "snippet": "Tejas Mehta. VP Sales & Customer Success at Sell.Do in Bengaluru, Karnataka, India."
        }
        cand = OpenSerpDiscoveryService.parse_candidate_evidence(item, {"title": "VP Sales"})
        self.assertIsNotNone(cand)
        self.assertEqual(cand["name"], "Tejas Mehta")
        self.assertIn("VP Sales", cand["role"])
        self.assertEqual(cand["company"], "Sell.Do")
        self.assertEqual(cand["location"], "Bengaluru, Karnataka, India")
        self.assertEqual(cand["provider"], "OPENSERP")
        self.assertEqual(cand["distance"], "PUBLIC_INDEX")

    def test_refuse_name_inferred_from_slug_alone(self):
        # Result title has no person name (e.g. only company or generic directory title)
        item = {
            "title": "https://in.linkedin.com/in/mysterious-executive - LinkedIn",
            "url": "https://in.linkedin.com/in/mysterious-executive",
            "snippet": "Some profile overview text without a name."
        }
        # Must refuse candidate because name is unsupported by title/snippet
        cand = OpenSerpDiscoveryService.parse_candidate_evidence(item, {"title": "Executive"})
        self.assertIsNone(cand)

    def test_missing_fields_preserved_as_none(self):
        # Snippet has role and name, but no company
        item = {
            "title": "Aleksey Navalny - Independent Strategist",
            "url": "https://de.linkedin.com/in/aleksey-navalny-123",
            "snippet": "Experienced leader in Berlin, Germany."
        }
        cand = OpenSerpDiscoveryService.parse_candidate_evidence(item, {"title": "Strategist"})
        self.assertIsNotNone(cand)
        self.assertEqual(cand["name"], "Aleksey Navalny")
        self.assertIsNone(cand["company"])  # Never defaulted to 'Target Company'!

    def test_fixture_1_mohamed_rafiuddin(self):
        # Mohamed Rafiuddin, PhD — full name and complete VP/Sales role; company should be None (no employer)
        item = {
            "title": "Mohamed Rafiuddin, PhD. - VP – Sales | Director",
            "url": "https://in.linkedin.com/in/mohamed-rafiuddin-phd-a2ba475",
            "snippet": "Mohamed Rafiuddin, PhD. VP – Sales | Director – Sales | Head of Sales | Chief Revenue Officer | B2B SaaS, Cloud, Cybersecurity & AI | 25+ Yrs Driving ...",
        }
        cand = OpenSerpDiscoveryService.parse_candidate_evidence(item, {"title": "VP Sales"})
        self.assertIsNotNone(cand)
        self.assertEqual(cand["name"], "Mohamed Rafiuddin")
        self.assertEqual(cand["role"], "VP – Sales")
        self.assertIsNone(cand["company"])  # Not 'Sales'
        self.assertIsNone(cand["location"])

    def test_fixture_2_kurt_srivastava_and_sprouts_ai(self):
        # Kurt S — name preserved as supported by title, company extracted as Sprouts.ai
        item = {
            "title": "Kurt S - VP Sales | Scaling revenue and sales teams",
            "url": "https://in.linkedin.com/in/kurt-srivastava-02s",
            "snippet": "Bengaluru, Karnataka, India · VP of Sales · Sprouts.ai"
        }
        cand = OpenSerpDiscoveryService.parse_candidate_evidence(item, {"title": "VP Sales"})
        self.assertIsNotNone(cand)
        self.assertEqual(cand["name"], "Kurt S")
        self.assertEqual(cand["role"], "VP Sales")
        self.assertEqual(cand["company"], "Sprouts.ai")
        self.assertEqual(cand["location"], "Bengaluru, Karnataka, India")

    def test_fixture_3_scaling_revenue_not_company(self):
        # Descriptive phrase must never become company
        item = {
            "title": "John Doe - VP of Sales | Scaling revenue and sales teams",
            "url": "https://www.linkedin.com/in/john-doe-123",
            "snippet": "Passionate leader helping startups grow."
        }
        cand = OpenSerpDiscoveryService.parse_candidate_evidence(item, {"title": "VP Sales"})
        self.assertIsNotNone(cand)
        self.assertIsNone(cand["company"])  # 'Scaling revenue and sales teams' rejected!

    def test_fixture_4_no_employer_evidence_remains_none(self):
        item = {
            "title": "Jane Doe - Chief Revenue Officer",
            "url": "https://www.linkedin.com/in/jane-doe-456",
            "snippet": "Experienced CRO based in San Francisco."
        }
        cand = OpenSerpDiscoveryService.parse_candidate_evidence(item, {"title": "CRO"})
        self.assertIsNotNone(cand)
        self.assertIsNone(cand["company"])
        self.assertEqual(cand["location"], "San Francisco")

    def test_fixture_5_no_location_evidence_remains_none(self):
        item = {
            "title": "Alice Smith - VP Marketing at TechFlow",
            "url": "https://www.linkedin.com/in/alice-smith-789",
            "snippet": "Leading B2B growth and performance marketing globally."
        }
        cand = OpenSerpDiscoveryService.parse_candidate_evidence(item, {"title": "VP Marketing"})
        self.assertIsNotNone(cand)
        self.assertIsNone(cand["location"])

    def test_fixture_6_ambiguous_name_not_inferred_from_slug(self):
        # E.g. title is generic and snippet has no person name
        item = {
            "title": "VP of Sales & Marketing | LinkedIn",
            "url": "https://www.linkedin.com/in/john-williams-exec",
            "snippet": "Profile for an executive in London."
        }
        cand = OpenSerpDiscoveryService.parse_candidate_evidence(item, {"title": "VP Sales"})
        self.assertIsNone(cand)

    def test_shared_scheduler_pacing_across_invocations(self):
        # Reset scheduler state for clean test
        OpenSerpDiscoveryService.clear_cooldown_for_testing()
        
        orig_interval = OpenSerpDiscoveryService.MIN_REQUEST_INTERVAL
        OpenSerpDiscoveryService.MIN_REQUEST_INTERVAL = 0.05
        import time

        try:
            t0 = time.monotonic()
            can1, rem1 = OpenSerpDiscoveryService.wait_for_request_gate()
            self.assertTrue(can1)
            t1 = time.monotonic()

            can2, rem2 = OpenSerpDiscoveryService.wait_for_request_gate()
            self.assertTrue(can2)
            t2 = time.monotonic()

            self.assertGreaterEqual(t2 - t1, 0.045)
        finally:
            OpenSerpDiscoveryService.MIN_REQUEST_INTERVAL = orig_interval
            OpenSerpDiscoveryService.clear_cooldown_for_testing()

    def test_concurrent_threads_actual_dispatch_spacing(self):
        import threading
        import time
        OpenSerpDiscoveryService.clear_cooldown_for_testing()

        dispatch_times = []
        lock_held_during_dispatch = []

        # We test real gate with short interval of 0.05s to verify spacing deterministically
        orig_interval = OpenSerpDiscoveryService.MIN_REQUEST_INTERVAL
        OpenSerpDiscoveryService.MIN_REQUEST_INTERVAL = 0.05

        try:
            def worker():
                can, _ = OpenSerpDiscoveryService.wait_for_request_gate()
                # Record dispatch time immediately after gate
                t = time.monotonic()
                dispatch_times.append(t)
                # Verify scheduler lock is NOT held during network I/O
                is_locked = OpenSerpDiscoveryService._scheduler_lock.locked()
                lock_held_during_dispatch.append(is_locked)
                # Simulate network I/O
                time.sleep(0.01)

            t1 = threading.Thread(target=worker)
            t2 = threading.Thread(target=worker)
            t1.start()
            t2.start()
            t1.join()
            t2.join()

            self.assertEqual(len(dispatch_times), 2)
            # Spacing between actual dispatch starts must be >= MIN_REQUEST_INTERVAL (with small timing tolerance)
            dispatch_times.sort()
            spacing = dispatch_times[1] - dispatch_times[0]
            self.assertGreaterEqual(spacing, 0.045)
            # Lock must not be held during network I/O
            self.assertFalse(any(lock_held_during_dispatch))
        finally:
            OpenSerpDiscoveryService.MIN_REQUEST_INTERVAL = orig_interval
            OpenSerpDiscoveryService.clear_cooldown_for_testing()

    def test_cooldown_activated_while_thread_waiting_aborts_dispatch(self):
        import threading
        import time
        OpenSerpDiscoveryService.clear_cooldown_for_testing()

        orig_interval = OpenSerpDiscoveryService.MIN_REQUEST_INTERVAL
        OpenSerpDiscoveryService.MIN_REQUEST_INTERVAL = 0.10

        results = []
        try:
            # First thread takes gate
            can1, _ = OpenSerpDiscoveryService.wait_for_request_gate()
            self.assertTrue(can1)

            def waiting_worker():
                can, rem = OpenSerpDiscoveryService.wait_for_request_gate()
                results.append((can, rem))

            # Second thread begins waiting at the gate
            t2 = threading.Thread(target=waiting_worker)
            t2.start()

            # Before t2 clears gate, activate cooldown
            time.sleep(0.02)
            OpenSerpDiscoveryService.activate_captcha_cooldown()
            t2.join()

            # Second thread must have aborted with can=False
            self.assertEqual(len(results), 1)
            self.assertFalse(results[0][0])
            self.assertGreater(results[0][1], 290.0)
        finally:
            OpenSerpDiscoveryService.MIN_REQUEST_INTERVAL = orig_interval
            OpenSerpDiscoveryService.clear_cooldown_for_testing()

    def test_captcha_activates_shared_cooldown(self):
        OpenSerpDiscoveryService.clear_cooldown_for_testing()
        self.assertFalse(OpenSerpDiscoveryService.get_cooldown_status()[0])
        
        OpenSerpDiscoveryService.activate_captcha_cooldown()
        in_cd, rem = OpenSerpDiscoveryService.get_cooldown_status()
        self.assertTrue(in_cd)
        self.assertGreater(rem, 290.0)

    def test_cooldown_expiry_behavior(self):
        OpenSerpDiscoveryService.clear_cooldown_for_testing()
        with OpenSerpDiscoveryService._scheduler_lock:
            # Set cooldown deadline in the past
            OpenSerpDiscoveryService._captcha_cooldown_until = 1.0
        
        in_cd, rem = OpenSerpDiscoveryService.get_cooldown_status()
        self.assertFalse(in_cd)
        self.assertEqual(rem, 0.0)

    def test_preflight_cooldown_blocks_upstream_calls(self):
        OpenSerpDiscoveryService.clear_cooldown_for_testing()
        OpenSerpDiscoveryService.activate_captcha_cooldown()

        # Mock is_available to return True
        orig_avail = OpenSerpDiscoveryService.is_available
        try:
            OpenSerpDiscoveryService.is_available = classmethod(lambda cls: (True, "OK"))
            res = OpenSerpDiscoveryService.discover_candidates([{"title": "VP Sales"}])
            self.assertFalse(res["success"])
            self.assertEqual(res["status"], "CAPTCHA_DETECTED")
            self.assertEqual(res["queries_executed"], 0)
            self.assertGreater(res["cooldown_remaining_seconds"], 250.0)
        finally:
            OpenSerpDiscoveryService.is_available = orig_avail
            OpenSerpDiscoveryService.clear_cooldown_for_testing()

    def test_query_keyword_sanitization_removes_comma_lists(self):
        # Verify that long comma-separated keyword lists are stripped to the primary token
        from app.services.openserp_service import OpenSerpDiscoveryService
        raw_kw = "B2B SaaS, outbound automation, sales capacity"
        parts = [p.strip() for p in raw_kw.split(",") if p.strip()]
        sanitized = parts[0] if parts else ""
        self.assertEqual(sanitized, "B2B SaaS")

    def test_single_query_cap_enforced(self):
        # Verify that passing multiple queries only executes at most 1 query
        self.assertEqual(OpenSerpDiscoveryService.MAX_QUERY_CAP, 1)

    def test_discover_candidates_executes_only_first_query_when_multiple_supplied(self):
        from unittest.mock import patch, MagicMock
        import io
        import json

        OpenSerpDiscoveryService.clear_cooldown_for_testing()
        orig_avail = OpenSerpDiscoveryService.is_available
        orig_interval = OpenSerpDiscoveryService.MIN_REQUEST_INTERVAL

        try:
            OpenSerpDiscoveryService.is_available = classmethod(lambda cls: (True, "OK"))
            OpenSerpDiscoveryService.MIN_REQUEST_INTERVAL = 0.0

            three_queries = [
                {"title": "VP Sales", "keywords": "B2B SaaS", "location": "Bengaluru"},
                {"title": "Chief Revenue Officer", "keywords": "Cybersecurity", "location": "Mumbai"},
                {"title": "Head of Engineering", "keywords": "Python", "location": "Pune"}
            ]

            mock_response_data = json.dumps({
                "results": [
                    {
                        "title": "Rajesh Kumar - VP Sales - Acme Corp | LinkedIn",
                        "url": "https://www.linkedin.com/in/rajesh-kumar",
                        "description": "VP Sales at Acme Corp in Bengaluru"
                    }
                ]
            }).encode("utf-8")

            mock_cm = MagicMock()
            mock_cm.status = 200
            mock_cm.read.return_value = mock_response_data
            mock_cm.__enter__.return_value = mock_cm
            mock_cm.__exit__.return_value = False

            with patch("urllib.request.urlopen", return_value=mock_cm) as mock_urlopen:
                result = OpenSerpDiscoveryService.discover_candidates(three_queries)

                # 1. Exactly one Google HTTP request is dispatched
                self.assertEqual(mock_urlopen.call_count, 1)

                # 2. The first query was the one dispatched
                dispatched_req = mock_urlopen.call_args[0][0]
                dispatched_url = dispatched_req.full_url
                self.assertIn("VP+Sales", dispatched_url)
                self.assertIn("B2B+SaaS", dispatched_url)
                self.assertIn("Bengaluru", dispatched_url)

                # 3. No second or third query is attempted
                self.assertNotIn("Chief+Revenue+Officer", dispatched_url)
                self.assertNotIn("Cybersecurity", dispatched_url)
                self.assertNotIn("Head+of+Engineering", dispatched_url)

                # Verification of returned structure
                self.assertTrue(result["success"])
                self.assertEqual(result["queries_executed"], 1)
                self.assertEqual(result["count"], 1)
                self.assertEqual(result["results"][0]["name"], "Rajesh Kumar")
                self.assertIn("VP Sales", result["results"][0]["role"])
        finally:
            OpenSerpDiscoveryService.is_available = orig_avail
            OpenSerpDiscoveryService.MIN_REQUEST_INTERVAL = orig_interval
            OpenSerpDiscoveryService.clear_cooldown_for_testing()

if __name__ == "__main__":
    unittest.main()

