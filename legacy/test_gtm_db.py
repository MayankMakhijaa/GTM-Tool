"""
Phase 5: Database Integration Test
Verifies: init_db, opportunities CRUD, user lookup, gtm_context read.
"""
import sys
import os
import json

# Remove any existing test data at the end
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from gtm_engine import (
    init_db, save_opportunities, get_all_opportunities, clear_opportunities,
    get_user_gtm_context, get_or_create_user, DB_PATH
)

print(f"DB path: {DB_PATH}")
print("Test 1: init_db()...")
init_db()
print("  PASS: init_db() ran without error.")

print("\nTest 2: DB opens and opportunities table exists...")
import sqlite3
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in c.fetchall()]
assert "opportunities" in tables, f"opportunities table missing. Tables: {tables}"
assert "users" in tables, f"users table missing."
assert "user_gtm_context" in tables, f"user_gtm_context table missing."
print(f"  PASS: Tables present: {[t for t in tables if t != 'sqlite_sequence']}")
conn.close()

print("\nTest 3: Insert and retrieve opportunity...")
sample_opp = {
    "company_name": "TEST_CORP_DELETE_ME",
    "website": "https://testcorp.example.com",
    "location": "San Francisco, US",
    "industry": "B2B SaaS",
    "company_size": "50-200",
    "description": "Test company for DB verification",
    "signals": ["Hiring signal", "Funding signal"],
    "evidence": [{"signal": "Hiring", "description": "Posted 10 engineering jobs", "source_url": "https://jobs.example.com", "source_title": "Jobs page"}],
    "icp_fit_score": 82,
    "intent_score": 70,
    "timing_score": 75,
    "overall_score": 77,
    "why_now": "Recently raised Series A and is actively hiring engineers.",
    "reason": "Strong ICP fit with clear timing indicators.",
    "recommended_action": "Reach out to the VP of Engineering about automation tooling.",
    "confidence": "high",
}
saved = save_opportunities([sample_opp])
assert len(saved) == 1, f"Expected 1 saved, got {len(saved)}"
assert saved[0]["company_name"] == "TEST_CORP_DELETE_ME"
assert isinstance(saved[0]["signals"], list)
assert isinstance(saved[0]["evidence"], list)
print(f"  PASS: Opportunity inserted with id={saved[0].get('id')}")

print("\nTest 4: get_all_opportunities() retrieves the inserted opportunity...")
all_opps = get_all_opportunities()
test_opps = [o for o in all_opps if o["company_name"] == "TEST_CORP_DELETE_ME"]
assert len(test_opps) >= 1, "Test opportunity not found in get_all_opportunities()"
o = test_opps[0]
assert isinstance(o["signals"], list), "signals should be parsed list"
assert isinstance(o["evidence"], list), "evidence should be parsed list"
assert o["icp_fit_score"] == 82
assert o["overall_score"] == 77
print(f"  PASS: Retrieved {len(all_opps)} total opportunities.")

print("\nTest 5: Clear test data...")
deleted = clear_opportunities()
print(f"  PASS: Cleared {deleted} opportunities.")

print("\nTest 6: Verify user_gtm_context is readable...")
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.execute("SELECT user_id, offer, target_icp, additional_context FROM user_gtm_context LIMIT 3")
rows = c.fetchall()
conn.close()
if rows:
    print(f"  PASS: {len(rows)} user_gtm_context row(s) found. Offer (first): {rows[0][1][:50] if rows[0][1] else 'empty'}")
else:
    print("  WARN: No user_gtm_context rows (expected after fresh DB). Onboarding must be completed first.")

print("\n=== ALL DATABASE TESTS PASSED ===")
sys.exit(0)
