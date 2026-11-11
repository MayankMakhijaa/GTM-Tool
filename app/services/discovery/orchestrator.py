"""
Single-Prompt Concurrent Multi-Engine Discovery Orchestrator.

Architecture:
ONE PROMPT AT A TIME -> SIX ENGINE REQUESTS CONCURRENTLY -> PROCESS RESULTS AS THEY ARRIVE -> DRAIN ALL WORK -> NEXT PROMPT.

Guarantees:
1. Strict Single-Prompt Sequentiality: Never dispatch multiple prompts concurrently.
2. Concurrent Engine Execution: Exactly one prompt dispatched to all six engines via ThreadPoolExecutor(max_workers=6).
3. Streaming Result Intake: Engines processed via as_completed() as they finish.
4. Qualification & Persistence Barrier: All candidate prequalification, batch qualification, persistence,
   and company enrichment must drain and complete before advancing to Prompt N+1.
5. Independent Engine Isolation: Error, rate-limit, or CAPTCHA on any engine never blocks or fails other engines.
6. Identity & Provenance: Retains LinkedIn URN/slug, original prompt, engine name, raw evidence, and sources list.
7. Thread & DB Safety: Network workers return plain data dicts; all DB operations execute in parent session context.
"""

import time
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable, Set, Tuple

from app.services.openserp_service import OpenSerpClient, default_openserp_client, OpenSerpDiscoveryService
from app.services.discovery.providers import (
    BaseSearchProvider,
    OpenSerpGoogleProvider,
    OpenSerpBingProvider,
    OpenSerpYandexProvider,
    OpenSerpBaiduProvider,
    OpenSerpDuckDuckGoProvider,
    OpenSerpEcosiaProvider,
    SearchProviderResult
)

logger = logging.getLogger(__name__)


class SinglePromptMultiEngineOrchestrator:
    """
    Orchestrates candidate discovery across six search engines under a strict
    single-active-prompt model.
    """

    def __init__(
        self,
        client: Optional[OpenSerpClient] = None,
        providers: Optional[List[BaseSearchProvider]] = None,
        qualification_batch_size: int = 5,
        engine_timeout: float = 15.0
    ):
        self.client = client or default_openserp_client
        self.engine_timeout = engine_timeout
        self.qualification_batch_size = max(1, qualification_batch_size)

        if providers is not None:
            self.providers = providers
        else:
            self.providers = [
                OpenSerpGoogleProvider(client=self.client),
                OpenSerpBingProvider(client=self.client),
                OpenSerpYandexProvider(client=self.client),
                OpenSerpBaiduProvider(client=self.client),
                OpenSerpDuckDuckGoProvider(client=self.client),
                OpenSerpEcosiaProvider(client=self.client)
            ]

    @staticmethod
    def build_query_string(q: Dict[str, Any]) -> str:
        """
        Builds a canonical LinkedIn search query string from query metadata:
        site:linkedin.com/in "Title" "Keyword" Location
        """
        q_title = (q.get("title") or "").strip()
        q_keywords = (q.get("keywords") or "").strip()
        q_loc = (q.get("location") or "").strip()

        # Sanitize comma-separated lists to single primary token
        if "," in q_keywords:
            parts = [p.strip() for p in q_keywords.split(",") if p.strip()]
            q_keywords = parts[0] if parts else ""

        terms = ["site:linkedin.com/in"]
        if q_title:
            terms.append(f'"{q_title}"')
        if q_keywords:
            terms.append(f'"{q_keywords}"')
        if q_loc:
            terms.append(q_loc)

        return " ".join(terms)

    def execute_single_prompt(
        self,
        prompt_query: str,
        prompt_metadata: Dict[str, Any],
        engine_limit: int = 10,
        stop_check_fn: Optional[Callable[[], bool]] = None,
        on_candidate_discovered_fn: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        Dispatches a SINGLE prompt query across all 6 engines concurrently using
        ThreadPoolExecutor(max_workers=6), streaming candidates via on_candidate_discovered_fn
        as each engine completes.

        Returns:
        {
            "prompt": str,
            "engine_results": Dict[str, SearchProviderResult],
            "raw_items_count": int,
            "candidates": List[Dict[str, Any]],
            "stopped": bool
        }
        """
        if stop_check_fn and stop_check_fn():
            return {
                "prompt": prompt_query,
                "engine_results": {},
                "raw_items_count": 0,
                "candidates": [],
                "stopped": True
            }

        engine_results: Dict[str, SearchProviderResult] = {}
        candidates_for_prompt: List[Dict[str, Any]] = []
        raw_items_count = 0

        # Execute all 6 engines concurrently for this prompt
        with ThreadPoolExecutor(max_workers=len(self.providers), thread_name_prefix="OpenSERP-Engine") as executor:
            future_to_provider = {
                executor.submit(
                    provider.search,
                    raw_query=prompt_query,
                    limit=engine_limit
                ): provider
                for provider in self.providers
            }

            # Streaming intake as each engine completes
            for future in as_completed(future_to_provider):
                provider = future_to_provider[future]
                engine_name = provider.engine
                try:
                    res: SearchProviderResult = future.result()
                except Exception as exc:
                    logger.error(f"[MultiEngineOrchestrator] Engine {engine_name} thread raised: {exc}")
                    res = SearchProviderResult(
                        provider_name=provider.name,
                        engine=engine_name,
                        status="ERROR",
                        items=[],
                        error_message=str(exc)
                    )

                engine_results[engine_name] = res
                items = res.items or []
                raw_items_count += len(items)

                # Process results immediately as this engine finishes
                for raw_item in items:
                    cand = OpenSerpDiscoveryService.parse_candidate_evidence(raw_item, prompt_metadata)
                    if cand:
                        cand["original_prompt"] = prompt_query
                        cand["engine"] = engine_name
                        cand["sources"] = [engine_name]
                        cand["queries"] = [prompt_query]
                        cand["discovered_at"] = datetime.utcnow().isoformat()
                        candidates_for_prompt.append(cand)
                        if on_candidate_discovered_fn:
                            on_candidate_discovered_fn(cand)

                if stop_check_fn and stop_check_fn():
                    logger.info("[MultiEngineOrchestrator] Stop signaled during engine intake.")
                    break

        return {
            "prompt": prompt_query,
            "engine_results": engine_results,
            "raw_items_count": raw_items_count,
            "candidates": candidates_for_prompt,
            "stopped": bool(stop_check_fn and stop_check_fn())
        }

    def execute_gtm_search_plan(
        self,
        search_plan: Dict[str, Any],
        target_leads: int,
        process_batch_fn: Callable[[List[Dict[str, Any]], Dict[str, Any]], int],
        on_progress_fn: Optional[Callable[[Dict[str, Any]], None]] = None,
        stop_check_fn: Optional[Callable[[], bool]] = None,
        on_sync_provenance_fn: Optional[Callable[[List[Dict[str, Any]]], int]] = None
    ) -> Dict[str, Any]:
        """
        Executes the search plan adhering strictly to:
        ONE PROMPT AT A TIME -> SIX ENGINE REQUESTS CONCURRENTLY -> PROCESS RESULTS AS THEY ARRIVE -> DRAIN ALL WORK -> NEXT PROMPT.

        Parameters:
        - search_plan: Dictionary containing 'queries' (list of query dicts).
        - target_leads: Total desired qualified leads to persist.
        - process_batch_fn: Callback (batch, prompt_metadata) -> saved_count. Must perform qualification,
                            enrichment, and persistence for the batch synchronously.
        - on_progress_fn: Callback (progress_dict) -> None.
        - stop_check_fn: Callback () -> bool.
        - on_sync_provenance_fn: Callback (late_provenance_updates) -> updated_count. Synchronizes merged sources/queries
                                 to database for already-persisted candidates without requalifying or recharging credits.

        Returns summary dictionary.
        """
        queries_to_run = search_plan.get("queries") or []
        if not queries_to_run:
            fallback_title = search_plan.get("keyword_title", "Executive")
            fallback_kw = search_plan.get("search_keywords", "B2B SaaS")
            queries_to_run = [{
                "id": "q1",
                "title": fallback_title,
                "keywords": fallback_kw,
                "location": ""
            }]

        total_prompts = len(queries_to_run)
        total_discovered = 0
        total_filtered = 0
        total_qualified_persisted = 0
        total_batches_completed = 0

        # Global deduplication across all prompts
        # Map: normalized_slug -> candidate_dict
        seen_candidates: Dict[str, Dict[str, Any]] = {}
        all_engine_telemetry: Dict[str, Dict[str, Any]] = {
            p.engine: {
                "name": p.name,
                "last_status": "READY",
                "total_results": 0,
                "last_latency_ms": 0.0,
                "error": None,
                "cooldown_remaining": 0.0
            }
            for p in self.providers
        }

        # -----------------------------------------------------------------
        # STRICT BARRIER: LOOP OVER PROMPTS SEQUENTIALLY (ONE PROMPT AT A TIME)
        # -----------------------------------------------------------------
        for prompt_idx, q_meta in enumerate(queries_to_run, start=1):
            if stop_check_fn and stop_check_fn():
                logger.info(f"[MultiEngineOrchestrator] Stop requested before prompt {prompt_idx}/{total_prompts}")
                break

            if total_qualified_persisted >= target_leads:
                logger.info(f"[MultiEngineOrchestrator] Target leads ({target_leads}) reached. Ending prompt execution.")
                break

            prompt_query = self.build_query_string(q_meta)
            logger.info(
                f"[MultiEngineOrchestrator] === Starting Prompt {prompt_idx}/{total_prompts}: '{prompt_query}' ==="
            )

            # Report prompt starting progress
            if on_progress_fn:
                on_progress_fn({
                    "current_prompt_index": prompt_idx,
                    "total_prompts": total_prompts,
                    "prompt_status": "SEARCHING",
                    "current_prompt_query": prompt_query,
                    "engine_status": {
                        eng: tel["last_status"] for eng, tel in all_engine_telemetry.items()
                    },
                    "engine_result_counts": {
                        eng: tel["total_results"] for eng, tel in all_engine_telemetry.items()
                    },
                    "total_discovered": total_discovered,
                    "total_filtered": total_filtered,
                    "batches_completed": total_batches_completed,
                    "qualified_persisted": total_qualified_persisted
                })

            # State tracked for streaming candidate ingestion & qualification in Prompt N
            unqualified_batch_for_prompt: List[Dict[str, Any]] = []
            late_provenance_updates: Dict[str, Dict[str, Any]] = {}
            persisted_urn_ids: Set[str] = set()
            prompt_lock = threading.Lock()

            def _handle_streaming_candidate(cand: Dict[str, Any]):
                nonlocal total_discovered, total_filtered, total_qualified_persisted, total_batches_completed
                with prompt_lock:
                    total_discovered += 1
                    norm_id = cand.get("urn_id", "").lower().strip()
                    if not norm_id:
                        total_filtered += 1
                        return

                    if norm_id in seen_candidates:
                        # Merge provenance without creating duplicate prospect
                        existing = seen_candidates[norm_id]
                        changed = False
                        if cand["engine"] not in existing.setdefault("sources", []):
                            existing["sources"].append(cand["engine"])
                            changed = True
                        if prompt_query not in existing.setdefault("queries", []):
                            existing["queries"].append(prompt_query)
                            changed = True
                        if not existing.get("company") and cand.get("company"):
                            existing["company"] = cand.get("company")
                            changed = True
                        if not existing.get("location") and cand.get("location"):
                            existing["location"] = cand.get("location")
                            changed = True

                        total_filtered += 1

                        # If candidate was already persisted in a prior batch, track late provenance change
                        if changed and norm_id in persisted_urn_ids:
                            late_provenance_updates[norm_id] = {
                                "urn_id": norm_id,
                                "profile_url": existing.get("profile_url"),
                                "sources": list(existing.get("sources", [])),
                                "queries": list(existing.get("queries", [])),
                                "company": existing.get("company"),
                                "location": existing.get("location")
                            }
                    else:
                        seen_candidates[norm_id] = cand
                        # If target already reached, do not queue new candidates for qualification
                        if total_qualified_persisted < target_leads:
                            unqualified_batch_for_prompt.append(cand)
                        else:
                            total_filtered += 1

                    # Trigger qualification as soon as batch threshold is reached
                    # Executes while remaining engines are still actively searching
                    if len(unqualified_batch_for_prompt) >= self.qualification_batch_size and total_qualified_persisted < target_leads:
                        batch_to_process = list(unqualified_batch_for_prompt)
                        unqualified_batch_for_prompt.clear()

                        batch_res = process_batch_fn(batch_to_process, q_meta)
                        saved = int(batch_res) if not isinstance(batch_res, dict) else batch_res.get("saved_count", 0)

                        # Strictly track confirmed persisted identities
                        confirmed_urns = []
                        if isinstance(batch_res, dict):
                            confirmed_urns = batch_res.get("persisted_urns") or []
                        elif hasattr(batch_res, "persisted_urns"):
                            confirmed_urns = batch_res.persisted_urns
                        elif saved == len(batch_to_process):
                            confirmed_urns = [(c.get("urn_id") or "").lower().strip() for c in batch_to_process if c.get("urn_id")]

                        for u in confirmed_urns:
                            if u:
                                persisted_urn_ids.add(str(u).lower().strip())

                        total_qualified_persisted += saved
                        total_batches_completed += 1

                        if on_progress_fn:
                            on_progress_fn({
                                "current_prompt_index": prompt_idx,
                                "total_prompts": total_prompts,
                                "prompt_status": "QUALIFYING",
                                "current_prompt_query": prompt_query,
                                "engine_status": {
                                    eng: tel["last_status"] for eng, tel in all_engine_telemetry.items()
                                },
                                "engine_result_counts": {
                                    eng: tel["total_results"] for eng, tel in all_engine_telemetry.items()
                                },
                                "total_discovered": total_discovered,
                                "total_filtered": total_filtered,
                                "batches_completed": total_batches_completed,
                                "qualified_persisted": total_qualified_persisted
                            })

            # Dispatch 6 engines concurrently for this single prompt, streaming candidates immediately
            prompt_res = self.execute_single_prompt(
                prompt_query=prompt_query,
                prompt_metadata=q_meta,
                engine_limit=10,
                stop_check_fn=stop_check_fn,
                on_candidate_discovered_fn=_handle_streaming_candidate
            )

            # Update engine telemetry from this prompt
            for eng, res in prompt_res["engine_results"].items():
                if eng in all_engine_telemetry:
                    all_engine_telemetry[eng]["last_status"] = res.status
                    all_engine_telemetry[eng]["total_results"] += len(res.items)
                    all_engine_telemetry[eng]["last_latency_ms"] = res.latency_ms
                    all_engine_telemetry[eng]["error"] = res.error_message
                    all_engine_telemetry[eng]["cooldown_remaining"] = res.cooldown_seconds

            # -----------------------------------------------------------------
            # QUALIFICATION DRAINAGE BARRIER: DRAIN REMAINING BATCH FOR THIS PROMPT
            # -----------------------------------------------------------------
            with prompt_lock:
                if unqualified_batch_for_prompt and total_qualified_persisted < target_leads:
                    logger.info(
                        f"[MultiEngineOrchestrator] Draining final batch of {len(unqualified_batch_for_prompt)} "
                        f"candidates for Prompt {prompt_idx} before barrier."
                    )
                    batch_to_process = list(unqualified_batch_for_prompt)
                    unqualified_batch_for_prompt.clear()
                    batch_res = process_batch_fn(batch_to_process, q_meta)
                    saved = int(batch_res) if not isinstance(batch_res, dict) else batch_res.get("saved_count", 0)

                    confirmed_urns = []
                    if isinstance(batch_res, dict):
                        confirmed_urns = batch_res.get("persisted_urns") or []
                    elif hasattr(batch_res, "persisted_urns"):
                        confirmed_urns = batch_res.persisted_urns
                    elif saved == len(batch_to_process):
                        confirmed_urns = [(c.get("urn_id") or "").lower().strip() for c in batch_to_process if c.get("urn_id")]

                    for u in confirmed_urns:
                        if u:
                            persisted_urn_ids.add(str(u).lower().strip())

                    total_qualified_persisted += saved
                    total_batches_completed += 1

                # -----------------------------------------------------------------
                # DURABLE LATE-PROVENANCE SYNCHRONIZATION BARRIER
                # -----------------------------------------------------------------
                if late_provenance_updates and on_sync_provenance_fn:
                    logger.info(
                        f"[MultiEngineOrchestrator] Synchronizing durable provenance for "
                        f"{len(late_provenance_updates)} candidate(s) discovered across multiple engines in Prompt {prompt_idx}."
                    )
                    synced = on_sync_provenance_fn(list(late_provenance_updates.values()))
                    logger.debug(f"[MultiEngineOrchestrator] Durable provenance synced for {synced} profile(s).")
                    late_provenance_updates.clear()

            # Barrier reached: Prompt N is 100% complete, qualified, and persisted.
            logger.info(
                f"[MultiEngineOrchestrator] === Completed and Drained Prompt {prompt_idx}/{total_prompts}. "
                f"Total Persisted So Far: {total_qualified_persisted} ==="
            )

            if on_progress_fn:
                on_progress_fn({
                    "current_prompt_index": prompt_idx,
                    "total_prompts": total_prompts,
                    "prompt_status": "COMPLETED",
                    "current_prompt_query": prompt_query,
                    "engine_status": {
                        eng: tel["last_status"] for eng, tel in all_engine_telemetry.items()
                    },
                    "engine_result_counts": {
                        eng: tel["total_results"] for eng, tel in all_engine_telemetry.items()
                    },
                    "total_discovered": total_discovered,
                    "total_filtered": total_filtered,
                    "batches_completed": total_batches_completed,
                    "qualified_persisted": total_qualified_persisted
                })

        return {
            "success": True,
            "total_prompts_executed": prompt_idx if 'prompt_idx' in locals() else 0,
            "total_prompts": total_prompts,
            "total_discovered": total_discovered,
            "total_filtered": total_filtered,
            "unique_candidates": len(seen_candidates),
            "batches_completed": total_batches_completed,
            "qualified_persisted": total_qualified_persisted,
            "engine_telemetry": all_engine_telemetry
        }


# Backward compatibility alias for any existing imports
class FederatedDiscoveryOrchestrator(SinglePromptMultiEngineOrchestrator):
    """Backward compatibility wrapper aliasing to SinglePromptMultiEngineOrchestrator."""
    INTER_QUERY_INTERVAL = 0.0

    def execute_federated_discovery(
        self,
        queries: List[Dict[str, Any]],
        limit: int = 10,
        stop_check_fn: Optional[Callable[[], bool]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Backward compatibility adapter for existing tests."""
        plan = {"queries": queries}
        saved_items = []

        def _mock_process(batch, meta):
            saved_items.extend(batch)
            return len(batch)

        summary = self.execute_gtm_search_plan(
            search_plan=plan,
            target_leads=limit,
            process_batch_fn=_mock_process,
            stop_check_fn=stop_check_fn
        )
        # Adapt engine telemetry to legacy provider_telemetry format expected by older tests
        prov_telemetry = {}
        for eng, tel in summary["engine_telemetry"].items():
            cd_rem = tel.get("cooldown_remaining", 0.0)
            status = tel.get("last_status", "READY")
            # If engine provider is in cooldown, reflect status accordingly
            for p in self.providers:
                if p.engine == eng:
                    in_cd, rem = p.is_in_cooldown()
                    if in_cd:
                        status = "CAPTCHA_DETECTED" if "google" in eng else "RATE_LIMITED"
                        cd_rem = rem
            prov_telemetry[eng] = {
                "name": tel.get("name", eng),
                "status": status,
                "raw_results_count": tel.get("total_results", 0),
                "cooldown_remaining": cd_rem,
                "error": tel.get("error")
            }

        return {
            "success": True,
            "results": saved_items,
            "count": len(saved_items),
            "unique_profiles_count": summary["unique_candidates"],
            "duplicates_count": summary["total_filtered"],
            "provider_telemetry": prov_telemetry
        }
