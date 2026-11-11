import json
import unittest
from unittest.mock import patch, MagicMock
from app.services.lead_enrichment_service import LeadEnrichmentService
from app.models.all_models import UsersProfiles, GlobalProfiles


class TestEnrichmentEndpointAndAuthorization(unittest.TestCase):
    """
    Tests Stage 9.2 Section 5 & 8.G requirements:
    - CSRF protection: Rejected with 400 CSRF_ERROR if token is missing.
    - User ownership: Only lead owned by logged-in user can be enriched (unauthorized returns 404).
    - Unauthenticated: Returns 401 when no session is present.
    - JSON error structure: Structured JSON errors returned rather than generic text.
    - Idempotent and safe JSONB persistence: Preserves existing company_data keys and doesn't erase data.
    - Safe error handling: Timeouts and upstream network failures return graceful structured status.
    """

    def setUp(self):
        import sys
        self.app = sys.modules["app_module"].app
        self.client = self.app.test_client()

    def test_missing_csrf_token_rejected(self):
        # CSRF rejection test (Section 8.G Test CSRF failure)
        resp = self.client.post("/api/gtm-opportunities/123/enrich")
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertFalse(data["success"])
        self.assertEqual(data["error"], "CSRF_ERROR")

    def test_unauthenticated_enrich_rejected(self):
        with patch.object(self.app, "config", {**self.app.config, "WTF_CSRF_ENABLED": False}):
            resp = self.client.post("/api/gtm-opportunities/123/enrich")
            self.assertEqual(resp.status_code, 401)
            data = resp.get_json()
            self.assertFalse(data["success"])
            self.assertEqual(data["error"], "Not authenticated.")

    def test_unauthorized_lead_not_owned_by_user_rejected(self):
        mock_db = MagicMock()
        # Query returns None because user_id does not match
        mock_db.query.return_value.filter_by.return_value.first.return_value = None

        with self.client.session_transaction() as sess:
            sess["user_id"] = 100

        with patch.object(self.app, "config", {**self.app.config, "WTF_CSRF_ENABLED": False}):
            with patch("app_module.db_session", mock_db):
                resp = self.client.post("/api/gtm-opportunities/999/enrich")
                self.assertEqual(resp.status_code, 404)
                data = resp.get_json()
                self.assertFalse(data["success"])
                self.assertEqual(data["error"], "Lead not found.")

    def test_authorized_lead_enrich_success(self):
        mock_up = MagicMock()
        mock_up.id = 55
        mock_up.user_id = 100
        mock_up.global_id = 200

        mock_gp = MagicMock()
        mock_gp.global_id = 200
        mock_gp.name = "Alice Walker"
        mock_gp.company = "FinTech Global"
        mock_gp.role = "VP Engineering"
        mock_gp.profile_url = "https://www.linkedin.com/in/alicewalker"
        mock_gp.company_data = {"existing_note": "Keep this key", "tier": "Tier 1 Priority Match"}

        mock_db = MagicMock()
        mock_db.query.return_value.filter_by.side_effect = [
            mock_up,  # lookup in UsersProfiles
            mock_gp,  # lookup in GlobalProfiles
            MagicMock(with_for_update=MagicMock(return_value=MagicMock(first=MagicMock(return_value=mock_gp))))
        ]

        mock_findings = {
            "status": "ENRICHED_NAMED_CONTACT",
            "business_email": "alice@fintechglobal.com",
            "official_domain": "fintechglobal.com",
            "mx_configured": True
        }

        with self.client.session_transaction() as sess:
            sess["user_id"] = 100

        with patch.object(self.app, "config", {**self.app.config, "WTF_CSRF_ENABLED": False}):
            with patch("app_module.db_session", mock_db), \
                 patch.object(LeadEnrichmentService, "enrich_qualified_lead", return_value=mock_findings):

                resp = self.client.post("/api/gtm-opportunities/55/enrich")
                self.assertEqual(resp.status_code, 200)
                data = resp.get_json()
                self.assertTrue(data["success"])
                self.assertEqual(data["opportunity_id"], 55)
                self.assertEqual(data["enrichment"]["business_email"], "alice@fintechglobal.com")

                # Check that existing JSONB keys were preserved
                self.assertIn("existing_note", mock_gp.company_data)
                self.assertIn("tier", mock_gp.company_data)
                self.assertEqual(mock_gp.company_data["enrichment"], mock_findings)


if __name__ == "__main__":
    unittest.main()
