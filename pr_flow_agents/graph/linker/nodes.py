"""Nodes for linker graph."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from pr_flow_agents.graph.linker.prompts import (
    LINKER_DECISION_PROMPT_TEMPLATE,
    LINKER_DECISION_REFINER_PROMPT_TEMPLATE,
    LINKER_THREAD_PROMPT_TEMPLATE,
)
from pr_flow_agents.graph.linker.state import LinkerState
from pr_flow_agents.llm import generate_json
from pr_flow_agents.logging_utils import get_logger
from pr_flow_agents.storage.extracted_event_store import ExtractedEventStore
from pr_flow_agents.storage.linked_event_store import LinkedEventStore
from pr_flow_agents.storage.models import LinkedEventDocument
from pr_flow_agents.storage.thread_scratchpad_store import ThreadScratchpadStore

logger = get_logger(__name__)

TOP_K = 10
ACTIVE_STATUSES = ("ACTIVE", "SUPERSEDED")

_silver_store = ExtractedEventStore()
_linked_store = LinkedEventStore()
_scratchpad_store = ThreadScratchpadStore()

try:
    import mlflow
except Exception:  # noqa: BLE001
    mlflow = None


def _trace(span_type: str = "UNKNOWN", name: str | None = None):
    """Apply @mlflow.trace only when mlflow is available."""

    def decorator(fn):
        if mlflow is not None:
            kwargs = {"span_type": span_type}
            if name:
                kwargs["name"] = name
            return mlflow.trace(**kwargs)(fn)
        return fn

    return decorator


def _mlflow_enabled() -> bool:
    return mlflow is not None and mlflow.active_run() is not None


def _safe_lower(value: Any) -> str:
    return str(value or "").strip().lower()


def _stable_thread_slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", _safe_lower(text)).strip("_")
    return slug or "general"


def _entity_set(event: Dict[str, Any]) -> set[str]:
    entities = event.get("entities") or []
    if not isinstance(entities, list):
        return set()
    return {_safe_lower(x) for x in entities if _safe_lower(x)}


def _entity_jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a.intersection(b))
    union = len(a.union(b))
    return float(inter / union) if union else 0.0


def _extract_event_payload(doc: Dict[str, Any]) -> Dict[str, Any]:
    payload = doc.get("event_payload")
    if isinstance(payload, dict):
        out = dict(payload)
        out["quality_flag"] = str(
            doc.get("quality_flag") or out.get("quality_flag") or ""
        )
        out["hop_count"] = doc.get("hop_count", out.get("hop_count"))
        out["loop_status"] = str(doc.get("loop_status") or out.get("loop_status") or "")
        return out
    return {
        "event_type": doc.get("event_type"),
        "event_date": doc.get("event_date"),
        "claim": doc.get("claim"),
        "entities": doc.get("entities") or [],
        "numbers": doc.get("numbers") or [],
        "evidence_span": doc.get("evidence_span") or "",
        "confidence": doc.get("confidence"),
        "quality_flag": str(doc.get("quality_flag") or ""),
        "hop_count": doc.get("hop_count"),
        "loop_status": str(doc.get("loop_status") or ""),
    }


def _guess_thread_for_event(
    *, ticker: str, sector: Optional[str], event: Dict[str, Any]
) -> Tuple[str, str]:
    """Delegate thread guessing to an LLM instead of hard-coded heuristics."""
    prompt = LINKER_THREAD_PROMPT_TEMPLATE.format(
        ticker=str(ticker or "").upper(),
        sector=str(sector or "").strip() or "unknown",
        event=json.dumps(event, ensure_ascii=True),
    )
    try:
        raw = generate_json(prompt)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "linker_thread_guess_failed ticker=%s sector=%s error=%s",
            ticker,
            sector,
            exc,
        )
        raw = {}

    thread_id = str((raw or {}).get("thread_id") or "").strip()
    thread_name = str((raw or {}).get("thread_name") or "").strip()

    if not thread_id:
        base = str(ticker or "").strip().lower() or "unknown"
        thread_id = f"{base}::general"
    if not thread_name:
        thread_name = "General"

    return thread_id, thread_name


def _score_candidate(
    *,
    new_event: Dict[str, Any],
    candidate: Dict[str, Any],
    provisional_thread_id: str,
) -> float:
    # Kept for backward compatibility; no longer used now that
    # candidate selection is delegated to the LLM in decide_action.
    return 0.0


def _build_scratchpad_text(doc: Optional[Dict[str, Any]]) -> str:
    if not doc:
        return "No existing thread context."
    claims = [
        str(x).strip() for x in (doc.get("latest_claims") or []) if str(x).strip()
    ]
    if claims:
        return "Recent thread claims:\n- " + "\n- ".join(claims[:10])
    summary = str(doc.get("summary") or "").strip() or "No thread context."
    ids = [str(x) for x in (doc.get("latest_linked_event_ids") or []) if str(x).strip()]
    return f"{summary}\nRecent linked ids: {', '.join(ids[:10])}" if ids else summary


def _normalize_decision(
    *, raw: Any, new_event_id: str, default_thread_id: str
) -> Dict[str, Any]:
    payload = raw if isinstance(raw, dict) else {}
    action = str(payload.get("action") or "NEW").strip().upper()
    if action not in {"NEW", "DUPLICATE", "UPDATE", "RETRACT"}:
        action = "NEW"
    return {
        "action": action,
        "new_event_id": str(payload.get("new_event_id") or new_event_id),
        "target_linked_event_id": str(
            payload.get("target_linked_event_id") or ""
        ).strip()
        or None,
        "thread_id": str(payload.get("thread_id") or default_thread_id).strip()
        or default_thread_id,
        "reason": str(payload.get("reason") or "fallback_to_new"),
    }


def _create_linked_event(
    *,
    ticker: str,
    thread_id: str,
    silver_event_id: str,
    silver_event: Dict[str, Any],
    supersedes: Optional[str] = None,
) -> str:
    now = datetime.utcnow()
    model = LinkedEventDocument(
        linked_event_id=f"le_{uuid4().hex}",
        ticker=ticker.upper(),
        thread_id=thread_id,
        event_type=str(silver_event.get("event_type") or "OTHER"),
        event_date=str(silver_event.get("event_date") or "") or None,
        canonical_claim=str(silver_event.get("claim") or ""),
        status="ACTIVE",
        supporting_silver_event_ids=[silver_event_id],
        supersedes=supersedes,
        superseded_by=None,
        created_at=now,
        updated_at=now,
    )
    return _linked_store.create(model)


@_trace(span_type="CHAIN", name="load_silver_events")
def load_silver_events(state: LinkerState) -> LinkerState:
    ticker = (state.get("ticker") or "").strip().upper()
    press_release_id = (state.get("press_release_id") or "").strip()
    if not ticker or not press_release_id:
        logger.warning(
            "linker_load_silver_events_missing_input ticker=%s press_release_id=%s",
            ticker,
            press_release_id,
        )
        return {
            **state,
            "status": "SKIPPED",
            "error": "ticker and press_release_id are required",
        }

    silver = _silver_store.list_by_release(press_release_id)
    status = "PENDING" if silver else "NO_SILVER_EVENTS"
    logger.info(
        "linker_load_silver_events_done press_release_id=%s ticker=%s silver_count=%s status=%s",
        press_release_id,
        ticker,
        len(silver),
        status,
    )
    if _mlflow_enabled():
        mlflow.log_param("linker_press_release_id", press_release_id)
        mlflow.log_param("linker_ticker", ticker)
        mlflow.log_param("linker_sector", str(state.get("sector") or ""))
        mlflow.log_metric("linker_silver_events_count", float(len(silver)))
    return {
        **state,
        "ticker": ticker,
        "silver_events": silver,
        "cursor": 0,
        "decisions": [],
        "impacted_threads": {},
        "linked_events_created": 0,
        "linked_events_duplicates": 0,
        "linked_events_updated": 0,
        "linked_events_retracted": 0,
        "status": status,  # type: ignore[typeddict-item]
        "error": None,
    }


@_trace(span_type="CHAIN", name="prepare_current_event")
def prepare_current_event(state: LinkerState) -> LinkerState:
    silver_events = state.get("silver_events") or []
    cursor = int(state.get("cursor") or 0)
    if cursor >= len(silver_events):
        return state
    silver_doc = silver_events[cursor]
    silver_event_id = str(silver_doc.get("_id") or "")
    silver_event = _extract_event_payload(silver_doc)
    thread_id, thread_name = _guess_thread_for_event(
        ticker=str(state.get("ticker") or ""),
        sector=state.get("sector"),
        event=silver_event,
    )
    scratchpad_doc = _scratchpad_store.get(
        ticker=str(state.get("ticker") or ""),
        thread_id=thread_id,
    )
    return {
        **state,
        "current_silver_event_id": silver_event_id,
        "current_silver_event": silver_event,
        "provisional_thread_id": thread_id,
        "provisional_thread_name": str(
            (scratchpad_doc or {}).get("thread_name") or thread_name
        ),
        "scratchpad_text": _build_scratchpad_text(scratchpad_doc),
    }


@_trace(span_type="CHAIN", name="retrieve_candidates")
def retrieve_candidates(state: LinkerState) -> LinkerState:
    ticker = str(state.get("ticker") or "")
    event = state.get("current_silver_event") or {}
    candidates = _linked_store.list_candidate_pool(
        ticker=ticker,
        statuses=ACTIVE_STATUSES,
        event_date=str(event.get("event_date") or ""),
        days_window=120,
        limit=200,
    )
    top = list(candidates or [])[:TOP_K]
    logger.info(
        "linker_retrieve_candidates_done ticker=%s silver_event_id=%s candidates=%s",
        ticker,
        state.get("current_silver_event_id"),
        len(top),
    )
    if _mlflow_enabled():
        mlflow.log_metric("linker_last_candidate_count", float(len(top)))
    return {**state, "candidates": top}


@_trace(span_type="CHAIN", name="decide_action")
def decide_action(state: LinkerState) -> LinkerState:
    silver_event_id = str(state.get("current_silver_event_id") or "")
    silver_event = state.get("current_silver_event") or {}
    candidates = state.get("candidates") or []
    default_thread_id = str(state.get("provisional_thread_id") or "")
    prompt = LINKER_DECISION_PROMPT_TEMPLATE.format(
        new_event_id=silver_event_id,
        new_event=json.dumps(silver_event, ensure_ascii=True),
        scratchpad=str(state.get("scratchpad_text") or ""),
        candidates=json.dumps(
            [
                {
                    "linked_event_id": c.get("linked_event_id"),
                    "thread_id": c.get("thread_id"),
                    "event_type": c.get("event_type"),
                    "event_date": c.get("event_date"),
                    "canonical_claim": c.get("canonical_claim"),
                    "status": c.get("status"),
                    "supporting_silver_event_ids": c.get("supporting_silver_event_ids")
                    or [],
                }
                for c in candidates
            ],
            ensure_ascii=True,
        ),
    )
    try:
        raw = generate_json(prompt)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "linker_decision_failed silver_event_id=%s error=%s", silver_event_id, exc
        )
        raw = {
            "action": "NEW",
            "new_event_id": silver_event_id,
            "target_linked_event_id": None,
            "thread_id": default_thread_id,
            "reason": "llm_error",
        }
    decision = _normalize_decision(
        raw=raw, new_event_id=silver_event_id, default_thread_id=default_thread_id
    )
    logger.info(
        "linker_decide_action_done silver_event_id=%s action=%s target=%s",
        silver_event_id,
        decision.get("action"),
        decision.get("target_linked_event_id"),
    )
    return {**state, "decision": decision}


@_trace(span_type="CHAIN", name="refine_decision")
def refine_decision(state: LinkerState) -> LinkerState:
    silver_event_id = str(state.get("current_silver_event_id") or "")
    silver_event = state.get("current_silver_event") or {}
    candidates = state.get("candidates") or []
    initial_decision = state.get("decision") or {}

    # Collect existing thread_ids from candidates for reuse hints
    existing_tids = sorted(
        {
            str(c.get("thread_id") or "")
            for c in candidates
            if str(c.get("thread_id") or "").strip()
        }
    )
    # Also include thread_ids from decisions made earlier in this batch
    for d in state.get("decisions") or []:
        applied = d.get("applied") or {}
        tid = str(applied.get("thread_id") or "").strip()
        if tid:
            existing_tids.append(tid)
    existing_tids = sorted(set(existing_tids))

    prompt = LINKER_DECISION_REFINER_PROMPT_TEMPLATE.format(
        new_event_id=silver_event_id,
        initial_decision=json.dumps(initial_decision, ensure_ascii=True),
        new_event=json.dumps(silver_event, ensure_ascii=True),
        existing_thread_ids=(
            "\n".join(f"- {t}" for t in existing_tids)
            if existing_tids
            else "(none yet)"
        ),
        candidates=json.dumps(
            [
                {
                    "linked_event_id": c.get("linked_event_id"),
                    "thread_id": c.get("thread_id"),
                    "event_type": c.get("event_type"),
                    "event_date": c.get("event_date"),
                    "canonical_claim": c.get("canonical_claim"),
                    "status": c.get("status"),
                    "supporting_silver_event_ids": c.get("supporting_silver_event_ids")
                    or [],
                }
                for c in candidates
            ],
            ensure_ascii=True,
        ),
    )
    try:
        raw = generate_json(prompt)
        refined = _normalize_decision(
            raw=raw,
            new_event_id=silver_event_id,
            default_thread_id=str(
                initial_decision.get("thread_id")
                or state.get("provisional_thread_id")
                or f"{state.get('ticker')}:General"
            ),
        )
        logger.info(
            "linker_refine_decision_done silver_event_id=%s initial=%s refined=%s thread=%s target=%s",
            silver_event_id,
            str(initial_decision.get("action") or ""),
            str(refined.get("action") or ""),
            refined.get("thread_id"),
            refined.get("target_linked_event_id"),
        )
        return {**state, "decision": refined}
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "linker_refine_decision_failed silver_event_id=%s error=%s",
            silver_event_id,
            exc,
        )
        return state


@_trace(span_type="CHAIN", name="apply_decision")
def apply_decision(state: LinkerState) -> LinkerState:
    ticker = str(state.get("ticker") or "")
    silver_event_id = str(state.get("current_silver_event_id") or "")
    silver_event = state.get("current_silver_event") or {}
    decision = state.get("decision") or {}
    action = str(decision.get("action") or "NEW").upper()
    target_id = decision.get("target_linked_event_id")
    thread_id = str(
        decision.get("thread_id")
        or state.get("provisional_thread_id")
        or f"{ticker}:General"
    )
    reason = str(decision.get("reason") or "")

    target_doc = _linked_store.get(str(target_id)) if target_id else None
    if action in {"DUPLICATE", "UPDATE", "RETRACT"} and not target_doc:
        action = "NEW"
        target_id = None
        reason = f"{reason}; target_missing_fallback_new".strip("; ")

    applied = {
        "action": action,
        "thread_id": thread_id,
        "target_linked_event_id": target_id,
        "created_linked_event_id": None,
        "applied": True,
        "reason": reason,
    }

    if action == "NEW":
        applied["created_linked_event_id"] = _create_linked_event(
            ticker=ticker,
            thread_id=thread_id,
            silver_event_id=silver_event_id,
            silver_event=silver_event,
        )
    elif action == "DUPLICATE":
        applied["applied"] = _linked_store.append_supporting_silver(
            str(target_id), silver_event_id
        )
    elif action == "UPDATE":
        target_thread = str((target_doc or {}).get("thread_id") or thread_id)
        new_id = _create_linked_event(
            ticker=ticker,
            thread_id=target_thread,
            silver_event_id=silver_event_id,
            silver_event=silver_event,
            supersedes=str(target_id),
        )
        _linked_store.mark_superseded(
            old_linked_event_id=str(target_id), new_linked_event_id=new_id
        )
        applied["thread_id"] = target_thread
        applied["created_linked_event_id"] = new_id
    elif action == "RETRACT":
        target_thread = str((target_doc or {}).get("thread_id") or thread_id)
        _linked_store.mark_retracted(str(target_id))
        new_id = _create_linked_event(
            ticker=ticker,
            thread_id=target_thread,
            silver_event_id=silver_event_id,
            silver_event=silver_event,
            supersedes=str(target_id),
        )
        applied["thread_id"] = target_thread
        applied["created_linked_event_id"] = new_id
    logger.info(
        "linker_apply_decision_done silver_event_id=%s action=%s target=%s created=%s",
        silver_event_id,
        action,
        target_id,
        applied.get("created_linked_event_id"),
    )

    decisions = list(state.get("decisions") or [])
    decisions.append(
        {
            "silver_event_id": silver_event_id,
            "decision": decision,
            "applied": applied,
        }
    )
    impacted = dict(state.get("impacted_threads") or {})
    impacted[str(applied.get("thread_id") or thread_id)] = str(
        state.get("provisional_thread_name") or "General"
    )

    next_state: LinkerState = {
        **state,
        "applied": applied,
        "decisions": decisions,
        "impacted_threads": impacted,
    }
    if action == "NEW":
        next_state["linked_events_created"] = (
            int(state.get("linked_events_created") or 0) + 1
        )
    elif action == "DUPLICATE":
        next_state["linked_events_duplicates"] = (
            int(state.get("linked_events_duplicates") or 0) + 1
        )
    elif action == "UPDATE":
        next_state["linked_events_updated"] = (
            int(state.get("linked_events_updated") or 0) + 1
        )
    elif action == "RETRACT":
        next_state["linked_events_retracted"] = (
            int(state.get("linked_events_retracted") or 0) + 1
        )
    return next_state


@_trace(span_type="CHAIN", name="advance_cursor")
def advance_cursor(state: LinkerState) -> LinkerState:
    return {**state, "cursor": int(state.get("cursor") or 0) + 1}


@_trace(span_type="CHAIN", name="refresh_scratchpads")
def refresh_scratchpads(state: LinkerState) -> LinkerState:
    ticker = str(state.get("ticker") or "")
    impacted = state.get("impacted_threads") or {}
    for thread_id, thread_name in impacted.items():
        latest = _linked_store.list_by_thread(
            ticker=ticker, thread_id=thread_id, statuses=("ACTIVE",), limit=10
        )
        if not latest:
            latest = _linked_store.list_by_thread(
                ticker=ticker, thread_id=thread_id, statuses=ACTIVE_STATUSES, limit=10
            )
        latest_ids = [
            str(x.get("linked_event_id") or "")
            for x in latest
            if str(x.get("linked_event_id") or "").strip()
        ]
        latest_claims = [
            str(x.get("canonical_claim") or "").strip()
            for x in latest[:10]
            if str(x.get("canonical_claim") or "").strip()
        ]
        summary = f"claims_cache_count={len(latest_claims)}"
        _scratchpad_store.upsert(
            ticker=ticker,
            thread_id=thread_id,
            thread_name=thread_name or "General",
            summary=summary,
            latest_linked_event_ids=latest_ids[:10],
            latest_claims=latest_claims[:10],
        )
    logger.info(
        "linker_refresh_scratchpads_done ticker=%s impacted_threads=%s",
        ticker,
        len(impacted),
    )
    return state


@_trace(span_type="CHAIN", name="finalize_output")
def finalize_output(state: LinkerState) -> LinkerState:
    status = str(state.get("status") or "DONE")
    if status not in {"NO_SILVER_EVENTS", "SKIPPED", "ERROR"}:
        status = "DONE"
    result = {
        "enabled": True,
        "status": status,
        "processed_silver_events_count": len(state.get("silver_events") or []),
        "linked_events_created": int(state.get("linked_events_created") or 0),
        "linked_events_duplicates": int(state.get("linked_events_duplicates") or 0),
        "linked_events_updated": int(state.get("linked_events_updated") or 0),
        "linked_events_retracted": int(state.get("linked_events_retracted") or 0),
        "impacted_threads_count": len(state.get("impacted_threads") or {}),
        "decisions": state.get("decisions") or [],
    }
    logger.info(
        "linker_graph_done press_release_id=%s ticker=%s status=%s silver=%s",
        state.get("press_release_id"),
        state.get("ticker"),
        result["status"],
        result["processed_silver_events_count"],
    )
    if _mlflow_enabled():
        mlflow.log_param("linker_status", result["status"])
        mlflow.log_metric(
            "linker_processed_silver_events_count",
            float(result["processed_silver_events_count"]),
        )
        mlflow.log_metric(
            "linker_linked_events_created", float(result["linked_events_created"])
        )
        mlflow.log_metric(
            "linker_linked_events_duplicates", float(result["linked_events_duplicates"])
        )
        mlflow.log_metric(
            "linker_linked_events_updated", float(result["linked_events_updated"])
        )
        mlflow.log_metric(
            "linker_linked_events_retracted", float(result["linked_events_retracted"])
        )
        mlflow.log_metric(
            "linker_impacted_threads_count", float(result["impacted_threads_count"])
        )
    return {**state, "result": result, "status": status}
