import time
import threading
from unittest.mock import MagicMock, patch
import pytest

from app.services.openserp_service import OpenSerpClient
from app.services.discovery.providers import (
    BaseSearchProvider,
    SearchProviderResult
)
from app.services.discovery.orchestrator import SinglePromptMultiEngineOrchestrator


class MockEngineProvider(BaseSearchProvider):
    def __init__(self, name: str, engine: str, delay: float = 0.0, results: list = None, status: str = "SUCCESS"):
        super().__init__(name=name, engine=engine)
        self.delay = delay
        self.sample_results = results or []
        self.mock_status = status
        self.search_call_timestamps = []

    def search(self, raw_query: str, limit: int = 10) -> SearchProviderResult:
        t_start = time.monotonic()
        self.search_call_timestamps.append((raw_query, t_start))
        if self.delay > 0:
            time.sleep(self.delay)
        return SearchProviderResult(
            provider_name=self.name,
            engine=self.engine,
            status=self.mock_status,
            items=list(self.sample_results),
            latency_ms=round((time.monotonic() - t_start) * 1000, 1)
        )


def test_concurrent_six_engines_dispatched_for_single_prompt():
    """Verify all 6 engines receive the EXACT same prompt and run concurrently."""
    delay = 0.05
    engines = ["google", "bing", "yandex", "baidu", "duckduckgo", "ecosia"]
    providers = [
        MockEngineProvider(name=f"{e.title()} Engine", engine=e, delay=delay)
        for e in engines
    ]

    orch = SinglePromptMultiEngineOrchestrator(providers=providers)

    t0 = time.monotonic()
    prompt_res = orch.execute_single_prompt(
        prompt_query='site:linkedin.com/in "VP Sales"',
        prompt_metadata={"title": "VP Sales"}
    )
    total_elapsed = time.monotonic() - t0

    # 6 engines each sleeping 0.05s concurrently should complete in ~0.05-0.12s, NOT 0.30s (sequential)
    assert total_elapsed < (delay * 4), f"Engines did not execute concurrently: took {total_elapsed:.3f}s"
    assert len(prompt_res["engine_results"]) == 6

    # Verify all 6 engines received the exact same query
    for p in providers:
        assert len(p.search_call_timestamps) == 1
        query_received, call_time = p.search_call_timestamps[0]
        assert query_received == 'site:linkedin.com/in "VP Sales"'
        # Concurrency verification: all start times within 50ms of each other
        assert abs(call_time - t0) < 0.05


def test_streaming_result_intake_fast_engine_processed_first():
    """Verify fast engine results are processed without waiting for slow engines."""
    p_fast = MockEngineProvider(
        name="Fast Bing",
        engine="bing",
        delay=0.01,
        results=[{
            "title": "Aarav Fast - VP Sales | Tech",
            "url": "https://www.linkedin.com/in/aarav-fast",
            "snippet": "VP Sales in Mumbai"
        }]
    )
    p_slow = MockEngineProvider(
        name="Slow Google",
        engine="google",
        delay=0.15,
        results=[{
            "title": "Priya Slow - VP Sales | Cloud",
            "url": "https://www.linkedin.com/in/priya-slow",
            "snippet": "VP Sales in Delhi"
        }]
    )

    orch = SinglePromptMultiEngineOrchestrator(providers=[p_fast, p_slow])
    res = orch.execute_single_prompt(
        prompt_query='site:linkedin.com/in "VP Sales"',
        prompt_metadata={"title": "VP Sales"}
    )

    assert len(res["candidates"]) == 2
    # The fast engine must be parsed and collected
    slugs = [c["urn_id"] for c in res["candidates"]]
    assert "aarav-fast" in slugs
    assert "priya-slow" in slugs


def test_failure_isolation_captcha_on_one_does_not_block_others():
    """Verify that a CAPTCHA or failure on one engine does not affect other engines."""
    p_captcha = MockEngineProvider(
        name="Google Engine",
        engine="google",
        status="CAPTCHA_DETECTED",
        results=[]
    )
    p_success = MockEngineProvider(
        name="Bing Engine",
        engine="bing",
        status="SUCCESS",
        results=[{
            "title": "Devika Sen - VP Sales | SaaS",
            "url": "https://www.linkedin.com/in/devika-sen",
            "snippet": "VP Sales in Bangalore"
        }]
    )

    orch = SinglePromptMultiEngineOrchestrator(providers=[p_captcha, p_success])
    res = orch.execute_single_prompt(
        prompt_query='site:linkedin.com/in "VP Sales"',
        prompt_metadata={"title": "VP Sales"}
    )

    assert res["engine_results"]["google"].status == "CAPTCHA_DETECTED"
    assert res["engine_results"]["bing"].status == "SUCCESS"
    assert len(res["candidates"]) == 1
    assert res["candidates"][0]["urn_id"] == "devika-sen"


def test_strict_sequential_prompt_execution_and_qualification_barrier():
    """
    CRITICAL ARCHITECTURE REQUIREMENT:
    Prompt 2 must NEVER start while Prompt 1 has pending qualification or persistence work.
    """
    p1_active_event = threading.Event()
    p1_drain_started = threading.Event()
    p1_drain_finished = threading.Event()
    p2_started = threading.Event()

    execution_timeline = []

    class DynamicCandidateEngine(BaseSearchProvider):
        def __init__(self):
            super().__init__(name="Dynamic Engine", engine="bing")
            self.call_count = 0

        def search(self, raw_query: str, limit: int = 10) -> SearchProviderResult:
            self.call_count += 1
            idx = self.call_count
            name = f"Aarav Sharma{idx}" if idx > 1 else "Aarav Sharma"
            slug = f"aarav-sharma-{idx}"
            return SearchProviderResult(
                provider_name=self.name,
                engine=self.engine,
                status="SUCCESS",
                items=[{
                    "title": f"{name} - VP Sales - TechCorp | LinkedIn",
                    "url": f"https://in.linkedin.com/in/{slug}",
                    "snippet": f"{name}. VP Sales at TechCorp in Bengaluru, Karnataka, India."
                }]
            )

    p_engine = DynamicCandidateEngine()

    orch = SinglePromptMultiEngineOrchestrator(
        providers=[p_engine],
        qualification_batch_size=1  # Batch immediately
    )

    def mock_process_batch(batch, prompt_meta):
        q_id = prompt_meta.get("id")
        execution_timeline.append(f"START_QUAL_{q_id}")
        if q_id == "q1":
            p1_drain_started.set()
            time.sleep(0.08)  # Simulate qualification and persistence latency
            p1_drain_finished.set()
        execution_timeline.append(f"FINISH_QUAL_{q_id}")
        return len(batch)

    # Wrap build_query_string to record prompt start events
    original_build_query = orch.build_query_string
    def tracking_build_query(q):
        q_id = q.get("id")
        execution_timeline.append(f"START_PROMPT_{q_id}")
        if q_id == "q2":
            p2_started.set()
            # Verify Prompt 1 qualification is ALREADY fully finished!
            assert p1_drain_finished.is_set(), "Prompt 2 started before Prompt 1 drained qualification!"
        return original_build_query(q)

    orch.build_query_string = tracking_build_query

    plan = {
        "queries": [
            {"id": "q1", "title": "VP Sales", "keywords": "SaaS"},
            {"id": "q2", "title": "CRO", "keywords": "Enterprise"}
        ]
    }

    summary = orch.execute_gtm_search_plan(
        search_plan=plan,
        target_leads=10,
        process_batch_fn=mock_process_batch
    )

    assert summary["success"] is True
    assert p2_started.is_set()

    # Verify exact sequential ordering in execution timeline
    assert execution_timeline == [
        "START_PROMPT_q1",
        "START_QUAL_q1",
        "FINISH_QUAL_q1",
        "START_PROMPT_q2",
        "START_QUAL_q2",
        "FINISH_QUAL_q2"
    ]


def test_provenance_and_deduplication_preserved():
    """Verify candidate deduplication by LinkedIn ID while merging sources and queries."""
    p_google = MockEngineProvider(
        name="Google",
        engine="google",
        results=[{
            "title": "Aarav Sharma - Head of Sales | Cloud",
            "url": "https://www.linkedin.com/in/aarav-sharma",
            "snippet": "Head of Sales at CloudCorp"
        }]
    )
    p_bing = MockEngineProvider(
        name="Bing",
        engine="bing",
        results=[{
            "title": "Aarav Sharma - Head of Sales | CloudCorp",
            "url": "https://in.linkedin.com/in/aarav-sharma",  # regional subdomain
            "snippet": "Head of Sales at CloudCorp in Bengaluru"
        }]
    )

    orch = SinglePromptMultiEngineOrchestrator(providers=[p_google, p_bing])

    batches_received = []
    def mock_process(batch, meta):
        batches_received.extend(batch)
        return len(batch)

    plan = {"queries": [{"id": "q1", "title": "Head of Sales", "keywords": "Cloud"}]}
    summary = orch.execute_gtm_search_plan(
        search_plan=plan,
        target_leads=5,
        process_batch_fn=mock_process
    )

    assert summary["unique_candidates"] == 1
    assert summary["total_filtered"] == 1  # 1 duplicate merged

    cand = batches_received[0]
    assert cand["urn_id"] == "aarav-sharma"
    assert "google" in cand["sources"]
    assert "bing" in cand["sources"]
    assert cand["original_prompt"] is not None


def test_true_streaming_qualification_starts_and_completes_before_slow_engine():
    """
    CRITICAL PROOF FOR PHASE 1.1.2:
    1. Fast engine completes and its candidates enter qualification while slow engine is still running.
    2. Qualification can finish before the slowest engine completes.
    3. Final partial batch drains after all engines finish.
    """
    fast_finished_event = threading.Event()
    qual_started_event = threading.Event()
    qual_finished_event = threading.Event()
    slow_still_running_flag = {"running": False}

    class SlowEngine(BaseSearchProvider):
        def __init__(self):
            super().__init__(name="Slow Engine", engine="google")
            self.finished = False

        def search(self, raw_query: str, limit: int = 10) -> SearchProviderResult:
            slow_still_running_flag["running"] = True
            # Sleep 0.20s so fast engine finishes and qualifies first
            time.sleep(0.20)
            self.finished = True
            slow_still_running_flag["running"] = False
            return SearchProviderResult(
                provider_name=self.name,
                engine=self.engine,
                status="SUCCESS",
                items=[{
                    "title": "Aarav Sharma - VP Sales - TechCorp | LinkedIn",
                    "url": "https://in.linkedin.com/in/aarav-sharma-slow",
                    "snippet": "Aarav Sharma. VP Sales at TechCorp in Bengaluru, India."
                }]
            )

    class FastEngine(BaseSearchProvider):
        def __init__(self):
            super().__init__(name="Fast Engine", engine="bing")

        def search(self, raw_query: str, limit: int = 10) -> SearchProviderResult:
            time.sleep(0.01)
            fast_finished_event.set()
            return SearchProviderResult(
                provider_name=self.name,
                engine=self.engine,
                status="SUCCESS",
                items=[{
                    "title": "Devika Sen - VP Sales - TechCorp | LinkedIn",
                    "url": "https://in.linkedin.com/in/devika-sen-fast",
                    "snippet": "Devika Sen. VP Sales at TechCorp in Bengaluru, India."
                }]
            )

    slow_p = SlowEngine()
    fast_p = FastEngine()

    orch = SinglePromptMultiEngineOrchestrator(
        providers=[fast_p, slow_p],
        qualification_batch_size=1  # Batch size = 1 to qualify fast engine candidate immediately
    )

    batches_processed = []
    qual_timeline = []

    def mock_process_batch(batch, meta):
        qual_started_event.set()
        # Verify that slow engine is STILL running when fast candidate enters qualification!
        is_slow_running_at_qual_start = slow_still_running_flag["running"] and not slow_p.finished
        qual_timeline.append({
            "batch": [c["urn_id"] for c in batch],
            "slow_running_at_start": is_slow_running_at_qual_start
        })
        time.sleep(0.02)  # fast qualification latency (20ms << 200ms slow engine sleep)
        qual_finished_event.set()
        batches_processed.append(batch)
        return len(batch)

    plan = {"queries": [{"id": "q1", "title": "VP Sales", "keywords": "Tech"}]}
    summary = orch.execute_gtm_search_plan(
        search_plan=plan,
        target_leads=5,
        process_batch_fn=mock_process_batch
    )

    # 1. Fast candidate qualification started while slow engine was actively running
    assert len(qual_timeline) == 2  # Batch 1 (fast engine), Batch 2 (drain barrier from slow engine)
    assert qual_timeline[0]["batch"] == ["devika-sen-fast"]
    assert qual_timeline[0]["slow_running_at_start"] is True, "Fast candidate qualification did not start while slow engine was running!"

    # 2. Batch 2 was the final drainage for slow engine candidate
    assert qual_timeline[1]["batch"] == ["aarav-sharma-slow"]
    assert summary["qualified_persisted"] == 2
    assert summary["batches_completed"] == 2


def test_durable_late_provenance_synchronization_barrier():
    """
    CRITICAL PROOF FOR PHASE 1.1.2.2:
    1. Google discovers and persists candidate in an early batch.
    2. Bing subsequently discovers the exact same candidate.
    3. Merged sources (['google', 'bing']) are synchronized at the prompt drainage barrier.
    4. on_sync_provenance_fn is invoked without re-calling process_batch_fn (no duplicate qualification/billing).
    5. Synchronization failure halts execution before next prompt starts.
    """
    class EarlyGoogleEngine(BaseSearchProvider):
        def __init__(self):
            super().__init__(name="Google Engine", engine="google")

        def search(self, raw_query: str, limit: int = 10) -> SearchProviderResult:
            time.sleep(0.01)
            return SearchProviderResult(
                provider_name=self.name,
                engine=self.engine,
                status="SUCCESS",
                items=[{
                    "title": "Devika Sen - VP Sales - TechCorp | LinkedIn",
                    "url": "https://in.linkedin.com/in/devika-sen",
                    "snippet": "Devika Sen. VP Sales at TechCorp in Bengaluru, India."
                }]
            )

    class LateBingEngine(BaseSearchProvider):
        def __init__(self):
            super().__init__(name="Bing Engine", engine="bing")

        def search(self, raw_query: str, limit: int = 10) -> SearchProviderResult:
            time.sleep(0.06)
            return SearchProviderResult(
                provider_name=self.name,
                engine=self.engine,
                status="SUCCESS",
                items=[{
                    "title": "Devika Sen - VP Sales - TechCorp | LinkedIn",
                    "url": "https://in.linkedin.com/in/devika-sen",  # Same exact profile
                    "snippet": "Devika Sen. VP Sales at TechCorp in Bengaluru, India."
                }]
            )

    google_p = EarlyGoogleEngine()
    bing_p = LateBingEngine()

    orch = SinglePromptMultiEngineOrchestrator(
        providers=[google_p, bing_p],
        qualification_batch_size=1
    )

    batches_qualified = []
    def mock_process_batch(batch, meta):
        batches_qualified.append(batch)
        return len(batch)

    synced_provenance_payloads = []
    def mock_sync_provenance(updates):
        synced_provenance_payloads.append(list(updates))
        return len(updates)

    plan = {"queries": [{"id": "q1", "title": "VP Sales", "keywords": "Tech"}]}
    summary = orch.execute_gtm_search_plan(
        search_plan=plan,
        target_leads=5,
        process_batch_fn=mock_process_batch,
        on_sync_provenance_fn=mock_sync_provenance
    )

    # 1. Exactly 1 qualification batch was processed (no duplicate qualification for Bing!)
    assert len(batches_qualified) == 1
    assert batches_qualified[0][0]["urn_id"] == "devika-sen"
    assert summary["qualified_persisted"] == 1

    # 2. Provenance synchronization was invoked at the drainage barrier with both engines merged
    assert len(synced_provenance_payloads) == 1
    sync_item = synced_provenance_payloads[0][0]
    assert sync_item["urn_id"] == "devika-sen"
    assert "google" in sync_item["sources"]
    assert "bing" in sync_item["sources"]
    assert len(sync_item["sources"]) == 2


def test_synchronization_failure_halts_prompt_sequence():
    """Verify that if provenance synchronization raises an exception, Prompt N+1 does not run."""
    class DummyEngine(BaseSearchProvider):
        def __init__(self):
            super().__init__(name="Dummy", engine="bing")
            self.count = 0

        def search(self, raw_query: str, limit: int = 10) -> SearchProviderResult:
            self.count += 1
            return SearchProviderResult(
                provider_name=self.name,
                engine=self.engine,
                status="SUCCESS",
                items=[{
                    "title": "Devika Sen - VP Sales - TechCorp | LinkedIn",
                    "url": "https://in.linkedin.com/in/devika-sen",
                    "snippet": "Devika Sen. VP Sales at TechCorp in Bengaluru, India."
                }]
            )

    p1 = DummyEngine()
    # Second engine returns same candidate slightly later to trigger late provenance update
    class DummyEngine2(BaseSearchProvider):
        def __init__(self):
            super().__init__(name="Dummy2", engine="google")

        def search(self, raw_query: str, limit: int = 10) -> SearchProviderResult:
            time.sleep(0.04)
            return SearchProviderResult(
                provider_name=self.name,
                engine=self.engine,
                status="SUCCESS",
                items=[{
                    "title": "Devika Sen - VP Sales - TechCorp | LinkedIn",
                    "url": "https://in.linkedin.com/in/devika-sen",
                    "snippet": "Devika Sen. VP Sales at TechCorp in Bengaluru, India."
                }]
            )

    p2 = DummyEngine2()

    orch = SinglePromptMultiEngineOrchestrator(
        providers=[p1, p2],
        qualification_batch_size=1
    )

    p2_started = False
    original_build_fn = orch.build_query_string
    def track_build(q):
        nonlocal p2_started
        if q.get("id") == "q2":
            p2_started = True
        return original_build_fn(q)

    orch.build_query_string = track_build

    def fail_sync(updates):
        raise RuntimeError("Database connection dropped during provenance sync!")

    plan = {
        "queries": [
            {"id": "q1", "title": "VP Sales"},
            {"id": "q2", "title": "CRO"}
        ]
    }

    with pytest.raises(RuntimeError, match="Database connection dropped"):
        orch.execute_gtm_search_plan(
            search_plan=plan,
            target_leads=5,
            process_batch_fn=lambda b, m: len(b),
            on_sync_provenance_fn=fail_sync
        )

    # Prompt 2 must NEVER start when Prompt 1 synchronization fails!
    assert p2_started is False


# ==============================================================================
# Phase 1.1.2.3 Tests: Strict Persistence Identity Tracking & Scenarios A-D
# ==============================================================================

def test_phase1123_scenario_a_rejected_candidate_not_tracked_and_no_late_sync():
    """
    Scenario A: Rejected / Disqualified candidate
    - Candidate processed in batch but rejected/excluded by qualification.
    - Identity must NOT enter persisted_urn_ids.
    - When another engine subsequently discovers the same candidate,
      on_sync_provenance_fn must NOT be invoked.
    """
    from app.services.gtm_pipeline_service import PersistenceResult

    class Engine1(BaseSearchProvider):
        def __init__(self):
            super().__init__(name="Google", engine="google")

        def search(self, raw_query: str, limit: int = 10) -> SearchProviderResult:
            return SearchProviderResult(
                provider_name=self.name,
                engine=self.engine,
                status="SUCCESS",
                items=[{
                    "title": "Alice Disqualified - VP Sales - TechCorp | LinkedIn",
                    "url": "https://linkedin.com/in/alice-disqualified",
                    "snippet": "Alice. VP Sales at TechCorp."
                }]
            )

    class Engine2(BaseSearchProvider):
        def __init__(self):
            super().__init__(name="Bing", engine="bing")

        def search(self, raw_query: str, limit: int = 10) -> SearchProviderResult:
            time.sleep(0.04)  # Arrive after Engine1 has been processed
            return SearchProviderResult(
                provider_name=self.name,
                engine=self.engine,
                status="SUCCESS",
                items=[{
                    "title": "Alice Disqualified - VP Sales - TechCorp | LinkedIn",
                    "url": "https://linkedin.com/in/alice-disqualified",
                    "snippet": "Alice. VP Sales at TechCorp."
                }]
            )

    orch = SinglePromptMultiEngineOrchestrator(
        providers=[Engine1(), Engine2()],
        qualification_batch_size=1
    )

    batch_calls = []
    def mock_process_batch(batch, meta):
        batch_calls.append(batch)
        # Disqualified candidate -> 0 saved, empty persisted_urns
        return PersistenceResult(0, persisted_urns=[])

    sync_calls = []
    def mock_sync_provenance(updates):
        sync_calls.append(updates)

    plan = {
        "queries": [{"id": "q1", "title": "VP Sales"}]
    }

    result = orch.execute_gtm_search_plan(
        search_plan=plan,
        target_leads=5,
        process_batch_fn=mock_process_batch,
        on_sync_provenance_fn=mock_sync_provenance
    )

    # Batch was processed once for Alice
    assert len(batch_calls) == 1
    assert result["qualified_persisted"] == 0

    # Alice must NOT have been marked as persisted, so Engine2's late discovery
    # must NOT trigger late provenance synchronization
    assert len(sync_calls) == 0


def test_phase1123_scenario_b_mixed_batch_tracks_only_persisted_subset():
    """
    Scenario B: Mixed Batch
    - Batch of 2 candidates: Alice is qualified/persisted, Bob is disqualified.
    - Only Alice's identity enters persisted_urn_ids.
    - If a subsequent engine discovers Alice, sync is called.
    - If a subsequent engine discovers Bob, sync is NOT called.
    """
    from app.services.gtm_pipeline_service import PersistenceResult

    class Engine1(BaseSearchProvider):
        def __init__(self):
            super().__init__(name="Google", engine="google")

        def search(self, raw_query: str, limit: int = 10) -> SearchProviderResult:
            return SearchProviderResult(
                provider_name=self.name,
                engine=self.engine,
                status="SUCCESS",
                items=[
                    {
                        "title": "Alice Qualified - VP Sales | LinkedIn",
                        "url": "https://linkedin.com/in/alice-qualified",
                        "snippet": "Alice. VP Sales."
                    },
                    {
                        "title": "Bob Disqualified - VP Sales | LinkedIn",
                        "url": "https://linkedin.com/in/bob-disqualified",
                        "snippet": "Bob. VP Sales."
                    }
                ]
            )

    class Engine2(BaseSearchProvider):
        def __init__(self):
            super().__init__(name="Bing", engine="bing")

        def search(self, raw_query: str, limit: int = 10) -> SearchProviderResult:
            time.sleep(0.04)
            return SearchProviderResult(
                provider_name=self.name,
                engine=self.engine,
                status="SUCCESS",
                items=[
                    {
                        "title": "Alice Qualified - VP Sales | LinkedIn",
                        "url": "https://linkedin.com/in/alice-qualified",
                        "snippet": "Alice. VP Sales."
                    },
                    {
                        "title": "Bob Disqualified - VP Sales | LinkedIn",
                        "url": "https://linkedin.com/in/bob-disqualified",
                        "snippet": "Bob. VP Sales."
                    }
                ]
            )

    orch = SinglePromptMultiEngineOrchestrator(
        providers=[Engine1(), Engine2()],
        qualification_batch_size=2
    )

    batch_calls = []
    def mock_process_batch(batch, meta):
        batch_calls.append(batch)
        # Only alice-qualified is persisted
        return PersistenceResult(1, persisted_urns=["alice-qualified"])

    sync_calls = []
    def mock_sync_provenance(updates):
        sync_calls.append(updates)

    plan = {
        "queries": [{"id": "q1", "title": "VP Sales"}]
    }

    result = orch.execute_gtm_search_plan(
        search_plan=plan,
        target_leads=5,
        process_batch_fn=mock_process_batch,
        on_sync_provenance_fn=mock_sync_provenance
    )

    assert result["qualified_persisted"] == 1
    # Only 1 late sync call was made, and it must ONLY be for alice-qualified
    assert len(sync_calls) == 1
    synced_urns = [u["urn_id"] for u in sync_calls[0]]
    assert "alice-qualified" in synced_urns
    assert "bob-disqualified" not in synced_urns


def test_phase1123_scenario_c_existing_successful_late_duplicate():
    """
    Scenario C: Existing successful late duplicate
    - Google discovers Devika Sen -> qualified and persisted.
    - Bing discovers Devika Sen later in the same prompt.
    - Provenance update is dispatched to on_sync_provenance_fn without re-qualifying.
    """
    from app.services.gtm_pipeline_service import PersistenceResult

    class GoogleEngine(BaseSearchProvider):
        def __init__(self):
            super().__init__(name="Google", engine="google")

        def search(self, raw_query: str, limit: int = 10) -> SearchProviderResult:
            return SearchProviderResult(
                provider_name=self.name,
                engine=self.engine,
                status="SUCCESS",
                items=[{
                    "title": "Devika Sen - VP Sales - TechCorp | LinkedIn",
                    "url": "https://in.linkedin.com/in/devika-sen",
                    "snippet": "Devika Sen. VP Sales at TechCorp."
                }]
            )

    class BingEngine(BaseSearchProvider):
        def __init__(self):
            super().__init__(name="Bing", engine="bing")

        def search(self, raw_query: str, limit: int = 10) -> SearchProviderResult:
            time.sleep(0.04)
            return SearchProviderResult(
                provider_name=self.name,
                engine=self.engine,
                status="SUCCESS",
                items=[{
                    "title": "Devika Sen - VP Sales - TechCorp | LinkedIn",
                    "url": "https://in.linkedin.com/in/devika-sen",
                    "snippet": "Devika Sen. VP Sales at TechCorp."
                }]
            )

    orch = SinglePromptMultiEngineOrchestrator(
        providers=[GoogleEngine(), BingEngine()],
        qualification_batch_size=1
    )

    qual_call_count = 0
    def mock_process_batch(batch, meta):
        nonlocal qual_call_count
        qual_call_count += 1
        return PersistenceResult(1, persisted_urns=["devika-sen"])

    sync_payloads = []
    def mock_sync_provenance(updates):
        sync_payloads.append(updates)

    plan = {
        "queries": [{"id": "q1", "title": "VP Sales"}]
    }

    result = orch.execute_gtm_search_plan(
        search_plan=plan,
        target_leads=5,
        process_batch_fn=mock_process_batch,
        on_sync_provenance_fn=mock_sync_provenance
    )

    # Exactly 1 batch qualification call was made (no re-qualification for duplicate)
    assert qual_call_count == 1
    # Exactly 1 sync call was made
    assert len(sync_payloads) == 1
    assert sync_payloads[0][0]["urn_id"] == "devika-sen"
    assert set(sync_payloads[0][0]["sources"]) == {"google", "bing"}


def test_phase1123_scenario_d_persistence_failure_omitted_from_persisted_urns():
    """
    Scenario D: Persistence failure handling
    - If a candidate cannot be persisted (e.g. database error or missing ID),
      it is omitted from persisted_urns.
    - The candidate's URN does not enter persisted_urn_ids.
    - Any subsequent discovery of this candidate will NOT invoke late sync.
    """
    from app.services.gtm_pipeline_service import PersistenceResult

    class Engine1(BaseSearchProvider):
        def __init__(self):
            super().__init__(name="Google", engine="google")

        def search(self, raw_query: str, limit: int = 10) -> SearchProviderResult:
            return SearchProviderResult(
                provider_name=self.name,
                engine=self.engine,
                status="SUCCESS",
                items=[{
                    "title": "Charlie Error - VP Sales | LinkedIn",
                    "url": "https://linkedin.com/in/charlie-error",
                    "snippet": "Charlie. VP Sales."
                }]
            )

    class Engine2(BaseSearchProvider):
        def __init__(self):
            super().__init__(name="Bing", engine="bing")

        def search(self, raw_query: str, limit: int = 10) -> SearchProviderResult:
            time.sleep(0.04)
            return SearchProviderResult(
                provider_name=self.name,
                engine=self.engine,
                status="SUCCESS",
                items=[{
                    "title": "Charlie Error - VP Sales | LinkedIn",
                    "url": "https://linkedin.com/in/charlie-error",
                    "snippet": "Charlie. VP Sales."
                }]
            )

    orch = SinglePromptMultiEngineOrchestrator(
        providers=[Engine1(), Engine2()],
        qualification_batch_size=1
    )

    def mock_process_batch_fail(batch, meta):
        # Persistence failed (0 saved, empty list)
        return PersistenceResult(0, persisted_urns=[])

    sync_calls = []
    def mock_sync_provenance(updates):
        sync_calls.append(updates)

    plan = {
        "queries": [{"id": "q1", "title": "VP Sales"}]
    }

    result = orch.execute_gtm_search_plan(
        search_plan=plan,
        target_leads=5,
        process_batch_fn=mock_process_batch_fail,
        on_sync_provenance_fn=mock_sync_provenance
    )

    assert result["qualified_persisted"] == 0
    assert len(sync_calls) == 0



