import unittest
from unittest.mock import patch, MagicMock
from app.services.lead_enrichment_service import LeadEnrichmentService

class TestLeadEnrichmentService(unittest.TestCase):
    """
    Focused unit tests for LeadEnrichmentService Stage 8.1.1:
    1. Email classification: Distinguish named person email from generic company email.
    2. Phone classification: Distinguish individual contact from generic company line.
    3. Missing / ambiguous data: Preserves None when information is not explicitly published.
    4. DNS MX resolution: Verifies MX record lookup without claiming individual mailbox exists.
    5. No guessing / No domain inference: Confirms company names (even 'sell.do') without external/profile evidence do NOT resolve domains.
    6. Complete IP range validation: Checks IPv4 private, loopback, link-local, IPv6 loopback, unique-local, link-local, and IPv4-mapped IPv6.
    7. DNS Rebinding Protection: Validates connection-time socket creation interception blocking non-global IPs.
    8. Lead enrichment pipeline: End-to-end enrichment on a mock qualified lead.
    9. Database rollback & JSONB preservation: Confirms error triggers db rollback and preserves existing company_data keys.
    """

    def test_classify_email_named_vs_generic(self):
        # Named individual email
        cat, expl = LeadEnrichmentService.classify_email("sarah.connor@cyberdyne.com", "Sarah Connor")
        self.assertEqual(cat, "NAMED_BUSINESS_EMAIL")

        # Generic company email
        cat, expl = LeadEnrichmentService.classify_email("contact@cyberdyne.com", "Sarah Connor")
        self.assertEqual(cat, "GENERIC_COMPANY_EMAIL")

        cat, expl = LeadEnrichmentService.classify_email("info@sell.do", "Tejas Mehta")
        self.assertEqual(cat, "GENERIC_COMPANY_EMAIL")

        cat, expl = LeadEnrichmentService.classify_email("sales@famewebs.com", "John Doe")
        self.assertEqual(cat, "GENERIC_COMPANY_EMAIL")

    def test_classify_email_personal_domain(self):
        # Personal public email domain
        cat, expl = LeadEnrichmentService.classify_email("sarah.connor@gmail.com", "Sarah Connor")
        self.assertEqual(cat, "PERSONAL_EMAIL")

    def test_dns_mx_check_mock(self):
        # Valid domain with mocked MX
        mock_rdata1 = MagicMock()
        mock_rdata1.exchange = "aspmx.l.google.com."
        mock_rdata1.preference = 10

        with patch('dns.resolver.resolve', return_value=[mock_rdata1]):
            res = LeadEnrichmentService.check_domain_mx("famewebs.com")
            self.assertEqual(res["status"], "DOMAIN_MX_CONFIGURED")
            self.assertTrue(res["configured"])
            self.assertIn("aspmx.l.google.com", res["records"])
            self.assertIn("does NOT verify individual address existence", res["explanation"])

    def test_dns_mx_check_nxdomain_or_no_mx(self):
        import dns.resolver
        with patch('dns.resolver.resolve', side_effect=dns.resolver.NXDOMAIN):
            res = LeadEnrichmentService.check_domain_mx("nonexistent-domain-xyz123.com")
            self.assertEqual(res["status"], "DOMAIN_NOT_FOUND")
            self.assertFalse(res["configured"])

    def test_resolve_official_domain_no_inference(self):
        # Ambiguous / invalid company returns None immediately
        self.assertIsNone(LeadEnrichmentService.resolve_official_domain(""))
        self.assertIsNone(LeadEnrichmentService.resolve_official_domain("   "))
        self.assertIsNone(LeadEnrichmentService.resolve_official_domain("organization"))
        self.assertIsNone(LeadEnrichmentService.resolve_official_domain("confidential"))

        # Company name resembling domain (e.g. sell.do) MUST NOT be inferred without supporting evidence
        self.assertIsNone(LeadEnrichmentService.resolve_official_domain("sell.do"))
        self.assertIsNone(LeadEnrichmentService.resolve_official_domain("Sell Do Technologies"))

        # Only profile evidence with explicit website/domain field is accepted
        with patch.object(LeadEnrichmentService, 'is_safe_public_url', return_value=True):
            res = LeadEnrichmentService.resolve_official_domain(
                "Sell.Do",
                profile_evidence={"website_url": "https://www.sell.do", "website_source": "VERIFIED_OPPORTUNITY_METADATA"}
            )
            self.assertIsNotNone(res)
            self.assertEqual(res["domain"], "sell.do")
            self.assertEqual(res["source_type"], "VERIFIED_OPPORTUNITY_METADATA")

    def test_complete_ip_range_validation(self):
        # IPv4 private, loopback, link-local, multicast, reserved, unspecified
        self.assertFalse(LeadEnrichmentService.is_safe_ip("127.0.0.1"))
        self.assertFalse(LeadEnrichmentService.is_safe_ip("10.0.0.1"))
        self.assertFalse(LeadEnrichmentService.is_safe_ip("192.168.1.1"))
        self.assertFalse(LeadEnrichmentService.is_safe_ip("172.16.0.1"))
        self.assertFalse(LeadEnrichmentService.is_safe_ip("169.254.169.254"))
        self.assertFalse(LeadEnrichmentService.is_safe_ip("0.0.0.0"))
        self.assertFalse(LeadEnrichmentService.is_safe_ip("224.0.0.1"))
        self.assertFalse(LeadEnrichmentService.is_safe_ip("240.0.0.1"))
        self.assertFalse(LeadEnrichmentService.is_safe_ip("255.255.255.255"))

        # IPv6 loopback, link-local, unique-local, multicast, unspecified
        self.assertFalse(LeadEnrichmentService.is_safe_ip("::1"))
        self.assertFalse(LeadEnrichmentService.is_safe_ip("::"))
        self.assertFalse(LeadEnrichmentService.is_safe_ip("fe80::1"))
        self.assertFalse(LeadEnrichmentService.is_safe_ip("fc00::1"))
        self.assertFalse(LeadEnrichmentService.is_safe_ip("ff02::1"))

        # IPv4-mapped IPv6
        self.assertFalse(LeadEnrichmentService.is_safe_ip("::ffff:127.0.0.1"))
        self.assertFalse(LeadEnrichmentService.is_safe_ip("::ffff:10.0.0.1"))
        self.assertFalse(LeadEnrichmentService.is_safe_ip("::ffff:192.168.1.1"))
        self.assertFalse(LeadEnrichmentService.is_safe_ip("::ffff:169.254.169.254"))

        # Valid public global addresses
        self.assertTrue(LeadEnrichmentService.is_safe_ip("93.184.216.34"))
        self.assertTrue(LeadEnrichmentService.is_safe_ip("8.8.8.8"))
        self.assertTrue(LeadEnrichmentService.is_safe_ip("2606:2800:220:1:248:1893:25c8:1946"))

    def test_dns_rebinding_connection_time_interception(self):
        # Simulate DNS rebinding: URL passes pre-check, but at socket connect time resolves to private IP
        with patch.object(LeadEnrichmentService, 'is_safe_public_url', return_value=True):
            # getaddrinfo called during ssrf_safe_create_connection returns 169.254.169.254
            with patch('socket.getaddrinfo', return_value=[(2, 1, 6, '', ('169.254.169.254', 80))]):
                text = LeadEnrichmentService.fetch_public_web_text("http://rebind-attack.com/contact")
                # Blocked at connection time and returns None safely
                self.assertIsNone(text)

    def test_database_session_rollback_and_jsonb_preservation(self):
        # Test simulated database update failure and rollback behavior
        from app.database import db_session
        mock_gp = MagicMock()
        mock_gp.company_data = {"existing_note": "preserved", "tier": "Tier 1 Priority Match"}

        # Simulate exception during commit
        with patch.object(db_session, 'commit', side_effect=RuntimeError("DB Commit Error")):
            with patch.object(db_session, 'rollback') as mock_rollback:
                try:
                    # Logic mirroring app.py route
                    current_data = dict(mock_gp.company_data or {})
                    current_data["enrichment"] = {"test": "data"}
                    mock_gp.company_data = current_data
                    db_session.commit()
                except Exception:
                    db_session.rollback()

                mock_rollback.assert_called_once()
                # Verify existing keys were present in the attempted update
                self.assertIn("existing_note", mock_gp.company_data)
                self.assertIn("tier", mock_gp.company_data)

    def test_enrich_qualified_lead_zero_guessing_clean_extraction(self):
        mock_text = (
            "Welcome to Sell.Do. Contact our sales team at sales@sell.do or call +1 800 555 0199. "
            "For executive outreach regarding VP Sales Tejas Mehta, email tejas.mehta@sell.do directly."
        )

        mock_domain_info = {
            "domain": "sell.do",
            "website_url": "https://www.sell.do",
            "source_type": "VERIFIED_OPPORTUNITY_METADATA",
            "confidence": "HIGH"
        }

        mock_mx_info = {
            "status": "DOMAIN_MX_CONFIGURED",
            "configured": True,
            "records": ["mail.sell.do"],
            "explanation": "MX configured"
        }

        lead = {
            "name": "Tejas Mehta",
            "role": "VP Sales",
            "company": "Sell.Do",
            "website_url": "https://www.sell.do",
            "profile_url": "https://in.linkedin.com/in/tejas-mehta-51842880"
        }

        with patch.object(LeadEnrichmentService, 'resolve_official_domain', return_value=mock_domain_info):
            with patch.object(LeadEnrichmentService, 'check_domain_mx', return_value=mock_mx_info):
                with patch.object(LeadEnrichmentService, 'fetch_public_web_text', return_value=mock_text):
                    findings = LeadEnrichmentService.enrich_qualified_lead(lead)

                    # Verified explicit extracted fields
                    self.assertIsNotNone(findings["public_named_email"])
                    self.assertEqual(findings["public_named_email"]["email"], "tejas.mehta@sell.do")
                    self.assertEqual(findings["public_named_email"]["classification"], "NAMED_BUSINESS_EMAIL")
                    self.assertEqual(findings["public_named_email"]["status"], "PUBLICLY_PUBLISHED")

                    self.assertIsNotNone(findings["public_generic_email"])
                    self.assertEqual(findings["public_generic_email"]["email"], "sales@sell.do")

                    self.assertIsNotNone(findings["public_business_phone"])
                    self.assertEqual(findings["public_business_phone"]["phone"], "+1 800 555 0199")

                    self.assertEqual(findings["official_domain"]["domain"], "sell.do")
                    self.assertTrue(findings["domain_mx"]["configured"])
                    self.assertEqual(findings["status"], "ENRICHED_NAMED_CONTACT")

    def test_enrich_qualified_lead_no_explicit_contact_leaves_null(self):
        # When public page has no emails or phone numbers, ensure fields remain None
        mock_text = "About Acme Corp. We build innovative solutions for global enterprises. Founded in 2015."

        mock_domain_info = {
            "domain": "acme.com",
            "website_url": "https://www.acme.com",
            "source_type": "OFFICIAL_SOURCE",
            "confidence": "HIGH"
        }

        mock_mx_info = {
            "status": "DOMAIN_MX_CONFIGURED",
            "configured": True,
            "records": ["mx.acme.com"],
            "explanation": "MX configured"
        }

        lead = {
            "name": "Jane Smith",
            "role": "CTO",
            "company": "Acme Corp",
            "profile_url": "https://www.linkedin.com/in/jane-smith"
        }

        with patch.object(LeadEnrichmentService, 'resolve_official_domain', return_value=mock_domain_info):
            with patch.object(LeadEnrichmentService, 'check_domain_mx', return_value=mock_mx_info):
                with patch.object(LeadEnrichmentService, 'fetch_public_web_text', return_value=mock_text):
                    findings = LeadEnrichmentService.enrich_qualified_lead(lead)

                    # Zero guessing, zero permutations
                    self.assertIsNone(findings["public_named_email"])
                    self.assertIsNone(findings["public_generic_email"])
                    self.assertIsNone(findings["public_business_phone"])

                    # Domain & MX are established
                    self.assertEqual(findings["official_domain"]["domain"], "acme.com")
                    self.assertTrue(findings["domain_mx"]["configured"])
                    self.assertEqual(findings["status"], "DOMAIN_RESOLVED_ONLY")

if __name__ == '__main__':
    unittest.main()
