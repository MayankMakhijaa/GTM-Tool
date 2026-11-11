import unittest
from unittest.mock import patch, MagicMock
from decimal import Decimal
from datetime import datetime

from app.services.gtm_pipeline_service import (
    generate_search_plan,
    qualify_candidates_with_gemini,
    persist_qualified_opportunities,
    _execute_gtm_pipeline_worker
)
from app.models.all_models import (
    ResearchJobStatus,
    LeadStatus,
    ReservationStatus,
    FeaturePricing,
    CreditReservation,
    ResearchJobs,
    UsersProfiles,
    GlobalProfiles
)


class TestContinuousDiscoveryPipeline(unittest.TestCase):

    def test_search_plan_uses_authentic_user_icp_no_hardcoding(self):
        user_context = {
            "user_id": 101,
            "company_name": "CyberShield AI",
            "offer": "Automated penetration testing and attack surface monitoring",
            "target_icp": "CISO, Head of Information Security, VP SecOps at financial institutions and fintechs in North America",
            "icp_raw": {
                "ideal_customer_profile": "CISO at Fintech",
                "target_titles": ["CISO", "Head of Information Security"],
                "target_industries": ["Fintech", "Banking"],
                "target_geographies": ["North America", "United States"],
                "version": 2
            }
        }

        mock_gemini_response = """{
            "strategy": "Target CISOs at fintech companies in North America",
            "queries": [
                {
                    "title": "CISO",
                    "keywords": "Fintech penetration testing attack surface",
                    "geography": "United States",
                    "industry": "Fintech",
                    "reasoning": "High-intent security leaders"
                }
            ]
        }"""

        with patch("app.services.gtm_pipeline_service._call_gemini_with_fallback", return_value=mock_gemini_response):
            plan = generate_search_plan(user_context=user_context, max_queries=1)
            self.assertIn("queries", plan)
            self.assertEqual(len(plan["queries"]), 1)
            q = plan["queries"][0]
            self.assertEqual(q["title"], "CISO")
            self.assertEqual(q["industry"], "Fintech")
            self.assertNotEqual(q["title"], "VP Sales")
            self.assertNotEqual(q["industry"], "B2B SaaS")

    def test_search_plan_respects_previous_queries_and_history(self):
        user_context = {
            "user_id": 102,
            "company_name": "HealthSync",
            "offer": "HIPAA-compliant EHR integration pipeline",
            "target_icp": "VP Engineering, Chief Medical Officer at regional hospital networks",
            "icp_raw": {"version": 1}
        }
        previous_queries = ['site:linkedin.com/in ("VP Engineering") ("EHR")']
        discovered_companies = ["Kaiser Permanente", "Mayo Clinic"]

        mock_gemini_response = """{
            "strategy": "Pivot to Chief Medical Officers to diversify angle",
            "queries": [
                {
                    "title": "Chief Medical Officer",
                    "keywords": "EHR integration hospital health network",
                    "geography": "United States",
                    "industry": "Hospital & Health Care",
                    "reasoning": "New angle avoiding previous VP Engineering query"
                }
            ]
        }"""

        with patch("app.services.gtm_pipeline_service._call_gemini_with_fallback", return_value=mock_gemini_response) as mock_gemini:
            plan = generate_search_plan(
                user_context=user_context,
                max_queries=2,
                previous_queries=previous_queries,
                discovered_companies=discovered_companies
            )
            call_prompt = mock_gemini.call_args[0][0]
            self.assertIn("site:linkedin.com/in", call_prompt)
            self.assertIn("Kaiser Permanente", call_prompt)
            self.assertEqual(plan["queries"][0]["title"], "Chief Medical Officer")

    def test_search_plan_raises_on_incomplete_icp(self):
        user_context = {
            "user_id": 103,
            "company_name": "",
            "offer": "",
            "target_icp": ""
        }
        with self.assertRaises(ValueError):
            generate_search_plan(user_context=user_context)

    def test_qualify_candidates_with_gemini_evidence_grounding(self):
        user_context = {
            "user_id": 104,
            "company_name": "LogiRoute",
            "offer": "Fleet route optimization for 3PL freight providers",
            "target_icp": "VP Logistics, Chief Operating Officer at freight carriers"
        }

        candidates = [
            {
                "urn_id": "marcus-vance",
                "name": "Marcus Vance",
                "role": "VP Logistics & Operations",
                "company": "Midwest Freight Lines",
                "location": "Chicago, IL",
                "profile_url": "https://www.linkedin.com/in/marcus-vance"
            },
            {
                "urn_id": "student-dave",
                "name": "Dave Miller",
                "role": "Student Intern",
                "company": "Staffing Co",
                "location": "Chicago, IL",
                "profile_url": "https://www.linkedin.com/in/student-dave"
            }
        ]

        mock_qual_response = """[
            {
                "urn_id": "marcus-vance",
                "fit_score": 94,
                "tier": "Tier 1 Priority Match",
                "qualification_reason": "Role VP Logistics directly matches target decision-maker at freight carrier.",
                "intent_signals": "Active supply chain expansion in Midwest.",
                "recommended_angle": "Discuss route optimization ROI."
            }
        ]"""

        with patch("app.services.gtm_pipeline_service._call_gemini_with_fallback", return_value=mock_qual_response):
            results = qualify_candidates_with_gemini(candidates, user_context, {})
            self.assertEqual(len(results), 2)
            marcus = next(r for r in results if r["urn_id"] == "marcus-vance")
            self.assertEqual(marcus["fit_score"], 94)
            self.assertEqual(marcus["tier"], "Tier 1 Priority Match")

            dave = next(r for r in results if r["urn_id"] == "student-dave")
            self.assertTrue(dave["is_excluded"])
            self.assertLess(dave["fit_score"], 50)

    def test_worker_cancellation_lifecycle(self):
        """Verify that worker breaks out cleanly when job is marked CANCELLED."""
        mock_app = MagicMock()
        mock_app.app_context.return_value.__enter__ = MagicMock()
        mock_app.app_context.return_value.__exit__ = MagicMock()

        mock_job = MagicMock()
        mock_job.id = 999
        mock_job.budget = {"reservation_id": 123}
        mock_job.status = ResearchJobStatus.CANCELLED.value
        mock_job.progress = {}

        mock_db = MagicMock()
        mock_db.query.return_value.filter_by.return_value.first.return_value = mock_job

        with patch("app.services.gtm_pipeline_service.db_session", mock_db), \
             patch("app.services.gtm_pipeline_service.CreditService") as mock_credit:

            _execute_gtm_pipeline_worker(
                app=mock_app,
                user_id=42,
                job_id=999,
                target_leads=10,
                persona_filter=None
            )

            self.assertEqual(mock_job.status, ResearchJobStatus.CANCELLED.value)

    def test_worker_credit_exhaustion_lifecycle(self):
        """Verify worker stops gracefully and settles collected leads when wallet has zero available credits."""
        mock_app = MagicMock()
        mock_app.app_context.return_value.__enter__ = MagicMock()
        mock_app.app_context.return_value.__exit__ = MagicMock()

        mock_job = MagicMock()
        mock_job.id = 1001
        mock_job.budget = {"reservation_id": 456}
        mock_job.status = ResearchJobStatus.QUEUED.value
        mock_job.progress = {}

        mock_pricing = MagicMock()
        mock_pricing.credit_cost = Decimal("2.00")

        mock_res = MagicMock(status=ReservationStatus.RESERVED.value)

        mock_db = MagicMock()

        def query_mock(model):
            m = MagicMock()
            if model is ResearchJobs:
                m.filter_by.return_value.first.return_value = mock_job
            elif model is FeaturePricing:
                m.filter_by.return_value.first.return_value = mock_pricing
            elif model is CreditReservation:
                m.filter_by.return_value.first.return_value = mock_res
            else:
                m.filter_by.return_value.first.return_value = None
                m.filter.return_value.count.return_value = 3
                m.join.return_value.filter.return_value.all.return_value = []
            return m

        mock_db.query.side_effect = query_mock

        with patch("app.services.gtm_pipeline_service.db_session", mock_db), \
             patch("app.services.gtm_pipeline_service.get_user_gtm_context", return_value={"onboarding_completed": True, "icp_raw": {"version": 1}}), \
             patch("app.services.gtm_pipeline_service.find_existing_global_candidates", return_value=[]), \
             patch("app.services.gtm_pipeline_service.CreditService") as mock_credit:

            mock_credit.get_wallet_balance.return_value = {"available_balance": Decimal("0.00")}

            _execute_gtm_pipeline_worker(
                app=mock_app,
                user_id=42,
                job_id=1001,
                target_leads=0,
                persona_filter=None
            )

            self.assertEqual(mock_job.status, ResearchJobStatus.COMPLETED.value)
            mock_credit.settle_reservation.assert_called_once()

    def test_incremental_qualification_and_persistence_before_completion(self):
        """
        Stage 9.2 Section 3 & 8.B:
        Demonstrates that when a rolling batch produces verified candidates,
        Gemini qualifies them and they are durably committed to the database IMMEDIATELY,
        updating the job progress, prior to any subsequent query batch or job completion.
        """
        mock_app = MagicMock()
        mock_app.app_context.return_value.__enter__ = MagicMock()
        mock_app.app_context.return_value.__exit__ = MagicMock()

        mock_job = MagicMock()
        mock_job.id = 777
        mock_job.budget = {"reservation_id": 789}
        mock_job.status = ResearchJobStatus.QUEUED.value
        mock_job.progress = {}

        mock_pricing = MagicMock()
        mock_pricing.credit_cost = Decimal("2.00")

        mock_db = MagicMock()

        def query_mock(model):
            m = MagicMock()
            if model is ResearchJobs:
                m.filter_by.return_value.first.return_value = mock_job
            elif model is FeaturePricing:
                m.filter_by.return_value.first.return_value = mock_pricing
            elif model is CreditReservation:
                m.filter_by.return_value.first.return_value = MagicMock(status=ReservationStatus.RESERVED.value)
            else:
                m.filter_by.return_value.first.return_value = None
                m.filter.return_value.count.return_value = 1
                m.join.return_value.filter.return_value.all.return_value = []
            return m

        mock_db.query.side_effect = query_mock

        persisted_calls = []

        def mock_persist(user_id, job_id, qualified_candidates, icp_version):
            # Assert that the job is still RUNNING when candidates are persisted
            self.assertEqual(mock_job.status, ResearchJobStatus.RUNNING.value)
            persisted_calls.append(len(qualified_candidates))
            return len(qualified_candidates)

        candidate_batch = [{
            "urn_id": "jennifer-lawrence-vp",
            "name": "Jennifer Lawrence",
            "role": "VP Revenue",
            "company": "ScaleFin",
            "location": "New York, NY",
            "profile_url": "https://www.linkedin.com/in/jennifer-lawrence-vp"
        }]

        with patch("app.services.gtm_pipeline_service.db_session", mock_db), \
             patch("app.services.gtm_pipeline_service.get_user_gtm_context", return_value={"onboarding_completed": True, "icp_raw": {"version": 1}}), \
             patch("app.services.gtm_pipeline_service.find_existing_global_candidates", return_value=[]), \
             patch("app.services.gtm_pipeline_service.CreditService") as mock_credit, \
             patch("app.services.gtm_pipeline_service.generate_search_plan", side_effect=[
                 {"queries": [{"title": "VP Revenue", "keywords": "ScaleFin fintech", "industry": "FinTech"}]},
                 {"queries": []} # Terminate rolling loop after batch 1
             ]), \
             patch("app.services.discovery.orchestrator.FederatedDiscoveryOrchestrator.execute_federated_discovery", return_value={
                 "results": candidate_batch,
                 "raw_results_count": 1
             }), \
             patch("app.services.gtm_pipeline_service.validate_and_classify_candidate", return_value=("VERIFIED", candidate_batch[0], None)), \
             patch("app.services.gtm_pipeline_service.qualify_candidates_with_gemini", return_value=[{**candidate_batch[0], "fit_score": 92}]), \
             patch("app.services.gtm_pipeline_service.persist_qualified_opportunities", side_effect=mock_persist):

            mock_credit.get_wallet_balance.return_value = {"available_balance": Decimal("50.00")}

            _execute_gtm_pipeline_worker(
                app=mock_app,
                user_id=42,
                job_id=777,
                target_leads=5,
                persona_filter=None
            )

            # Verification:
            # 1. persist_qualified_opportunities was called during the loop while RUNNING
            self.assertEqual(persisted_calls, [1])
            # 2. Database committed incremental progress
            self.assertGreaterEqual(mock_db.commit.call_count, 3)
            # 3. Final status finalized as COMPLETED
            self.assertEqual(mock_job.status, ResearchJobStatus.COMPLETED.value)
            self.assertEqual(mock_job.results_count, 1)


if __name__ == "__main__":
    unittest.main()
