import json

with open("scratch/stage6_1_benchmark_raw.json", "r", encoding="utf-8") as f:
    data = json.load(f)

print("=== OPOSERAP BENCHMARK SUMMARY ===")
for i, res in enumerate(data["openserp"], 1):
    print(f"\nQuery {i}:")
    print(f"  Status: {res['status']} (Code: {res['status_code']}, Latency: {res['latency_ms']}ms)")
    print(f"  Raw count: {res['raw_count']}")
    cands = res.get("normalized_candidates", [])
    print(f"  Normalized candidates: {len(cands)}")
    for c in cands:
        print(f"    - Name: '{c.get('name')}', Role: '{c.get('role')}', Company: '{c.get('company')}', Loc: '{c.get('location')}', URL: {c.get('profile_url')}")

print("\n=== DDGS BENCHMARK SUMMARY ===")
for i, res in enumerate(data["ddgs"], 1):
    print(f"\nQuery {i}:")
    print(f"  Status: {res['status']} (Code: {res['status_code']}, Latency: {res['latency_ms']}ms)")
    print(f"  Raw count: {res['raw_count']}")
    cands = res.get("normalized_candidates", [])
    print(f"  Normalized candidates: {len(cands)}")

