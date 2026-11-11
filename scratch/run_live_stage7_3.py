import os
import sys
import time
import json
from datetime import datetime

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.discovery.orchestrator import (
    FederatedDiscoveryOrchestrator,
    get_federated_session_state,
    clear_federated_session_state
)

def run_live_verification():
    user_id = 9999
    session_id = f"live_test_{int(time.time())}"
    clear_federated_session_state(user_id)

    # 1 Realistic FameWeb ICP query batch
    query_batch = [
        {
            "id": "q1",
            "title": "VP Sales",
            "keywords": "B2B SaaS",
            "location": "Bengaluru",
            "industry": "Software / Cloud"
        }
    ]

    print(f"=== STARTING LIVE FEDERATED DISCOVERY (Session: {session_id}) ===")
    print(f"Query: {query_batch[0]}")
    t0 = time.monotonic()

    orch = FederatedDiscoveryOrchestrator()
    # Execute federated discovery live
    result = orch.execute_federated_discovery(
        queries=query_batch,
        limit=15,
        user_id=user_id,
        session_id=session_id
    )
    total_duration = round(time.monotonic() - t0, 2)

    print(f"\n=== FEDERATED DISCOVERY COMPLETED in {total_duration}s ===")
    print(f"Success: {result['success']}, Status: {result['status']}")
    print(f"Raw Results Total: {result['raw_results_total']}")
    print(f"Unique Verified Prospects Count: {result['unique_profiles_count']}")
    print(f"Duplicates Merged: {result['duplicates_count']}")

    print("\n--- Provider Telemetry ---")
    for eng, telem in result["provider_telemetry"].items():
        print(f"Engine: {eng.upper()}")
        print(f"  Name: {telem.get('name')}")
        print(f"  Status: {telem.get('status')}")
        print(f"  Queries Dispatched: {telem.get('queries_dispatched')}")
        print(f"  Raw Items: {telem.get('raw_results_count')}")
        print(f"  Cooldown Remaining: {telem.get('cooldown_remaining')}s")
        print(f"  Error: {telem.get('error')}")

    print("\n--- Verified Candidates Discovered ---")
    for idx, c in enumerate(result["results"], 1):
        print(f"{idx}. {c.get('name')} | Role: {c.get('role')} | Company: {c.get('company')} | Loc: {c.get('location')}")
        print(f"   URL: {c.get('profile_url')}")
        print(f"   Sources: {c.get('sources')}")
        print(f"   Validation: {c.get('validation_flags')}")

    # Save detailed JSON output for audit
    scratch_out = os.path.join(os.path.dirname(__file__), "live_stage7_3_results.json")
    with open(scratch_out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"\nSaved raw telemetry to: {scratch_out}")

if __name__ == "__main__":
    run_live_verification()

