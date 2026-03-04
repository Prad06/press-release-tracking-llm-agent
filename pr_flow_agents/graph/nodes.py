"""Graph nodes for the event pipeline."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId
import pymongo

from pr_flow_agents.storage.config import get_database, get_uri
from pr_flow_agents.storage.company_store import CompanyStore
from pr_flow_agents.llm.gemini_client import generate_json
from .prompts import (
    BIOTECH_EVENT_EXTRACTION_PROMPT,
    AVIATION_EVENT_EXTRACTION_PROMPT,
)

from .state import GraphState


_CLIENT: Optional[pymongo.MongoClient] = None


def _get_crawl_collection() -> pymongo.collection.Collection:
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = pymongo.MongoClient(get_uri())
    db = _CLIENT[get_database()]
    return db["crawl_results"]


def _get_events_collection() -> pymongo.collection.Collection:
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = pymongo.MongoClient(get_uri())
    db = _CLIENT[get_database()]
    return db["events"]


def _get_company_states_collection() -> pymongo.collection.Collection:
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = pymongo.MongoClient(get_uri())
    db = _CLIENT[get_database()]
    return db["company_states"]


def claim_next_doc(state: GraphState) -> GraphState:
    """Claim the next eligible crawl_results document for processing.

    Eligibility:
      - unprocessed = True
      - metadata.processing.status in [UNPROCESSED, FAILED] or missing
      - metadata.processing.review_count < metadata.processing.review_budget
        (missing counts treated as 0, budget default 3)
      - optional ticker filter if state.tickers is non-empty

    Oldest press_release_timestamp is picked first.
    """

    if state.done:
        return state

    coll = _get_crawl_collection()

    # Only pick documents that are not yet processed.
    # We treat missing status as UNPROCESSED for backwards compatibility.
    status_filter = {
        "$or": [
            {"metadata.processing.status": "UNPROCESSED"},
            {"metadata.processing.status": {"$exists": False}},
        ]
    }

    query: Dict[str, Any] = {
        "unprocessed": True,
        **status_filter,
    }

    if state.tickers:
        query["ticker"] = {"$in": [t.upper() for t in state.tickers]}

    now_iso = datetime.now(timezone.utc).isoformat()

    update = {
        "$set": {
            "metadata.processing.status": "PROCESSING",
            "metadata.processing.run_id": state.run_id,
            "metadata.processing.method_version": state.method_version,
            "metadata.processing.locked_at": now_iso,
        },
    }

    from pymongo import ReturnDocument

    doc = coll.find_one_and_update(
        query,
        update,
        sort=[("press_release_timestamp", 1)],
        return_document=ReturnDocument.AFTER,
    )

    new_state = GraphState(**asdict(state))

    if not doc:
        new_state.done = True
        new_state.doc = None
        new_state.doc_id = None
        new_state.ticker = None
        return new_state

    doc_id = str(doc.get("_id"))
    new_state.doc_id = doc_id
    new_state.doc = doc
    new_state.ticker = doc.get("ticker")
    new_state.error = None
    return new_state


def route_sector(state: GraphState) -> GraphState:
    """Route using the sector stored on the company document.

    Assumes `companies.sector` is already one of:
      - \"biotech\"
      - \"aviation\"
    """

    if state.done or not state.ticker:
        return state

    cs = CompanyStore()
    company = cs.get(state.ticker)

    new_state = GraphState(**asdict(state))

    raw_sector = (company or {}).get("sector") or ""
    s_norm = raw_sector.strip().lower()

    if s_norm in {"biotech", "aviation"}:
        new_state.sector = s_norm
    else:
        new_state.error = (
            f"Unsupported or missing sector for ticker {state.ticker}: {raw_sector!r}"
        )
        new_state.done = True

    return new_state


def _extract_events_with_prompt(
    state: GraphState,
    prompt_template: str,
) -> GraphState:
    """Common helper to call Gemini and populate events_candidate."""

    new_state = GraphState(**asdict(state))

    if not state.doc or not state.doc.get("raw_result", {}).get("markdown_content"):
        new_state.events_candidate = []
        return new_state

    content = state.doc["raw_result"]["markdown_content"]
    rendered = prompt_template.format(content=content)

    try:
        events = generate_json(rendered)
        if isinstance(events, list):
            new_state.events_candidate = events  # type: ignore[assignment]
        else:
            new_state.events_candidate = []
            new_state.error = "Gemini returned non-list JSON for events"
    except Exception as e:  # noqa: BLE001
        new_state.events_candidate = []
        new_state.error = f"Gemini extraction error: {e}"

    return new_state


def extract_biotech_events(state: GraphState) -> GraphState:
    """LLM-based event extraction for biotech sector."""

    if state.done:
        return state
    if state.sector != "biotech":
        return state

    return _extract_events_with_prompt(state, BIOTECH_EVENT_EXTRACTION_PROMPT)


def extract_aviation_events(state: GraphState) -> GraphState:
    """LLM-based event extraction for aviation sector."""

    if state.done:
        return state
    if state.sector != "aviation":
        return state

    return _extract_events_with_prompt(state, AVIATION_EVENT_EXTRACTION_PROMPT)


def validate_events(state: GraphState) -> GraphState:
    """Deterministic validation of extracted events.

    Rules:
      - event_date must be non-empty and of the form YYYY-MM-DD
      - evidence_span must be a non-empty substring of the source content
      - every entry in `numbers` (if present) must occur inside evidence_span
    """

    new_state = GraphState(**asdict(state))

    content = ""
    if state.doc and state.doc.get("raw_result"):
        raw = state.doc["raw_result"]
        content = raw.get("markdown_content") or raw.get("main_content") or ""

    candidates: List[Dict[str, Any]] = [
        e for e in (state.events_candidate or []) if isinstance(e, dict)
    ]

    def _valid_date(s: str) -> bool:
        s = s.strip()
        if len(s) != 10:
            return False
        try:
            datetime.fromisoformat(s)
        except Exception:  # noqa: BLE001
            return False
        return True

    validated: List[Dict[str, Any]] = []
    for ev in candidates:
        date = str(ev.get("event_date", "")).strip()
        evidence = str(ev.get("evidence_span", "")).strip()
        if not date or not evidence:
            continue
        if not _valid_date(date):
            continue
        if content and evidence not in content:
            continue

        nums = ev.get("numbers") or []
        if isinstance(nums, list):
            bad = False
            for n in nums:
                s = str(n).strip()
                if s and s not in evidence:
                    bad = True
                    break
            if bad:
                continue

        validated.append(ev)

    new_state.events_validated = validated
    return new_state


def write_events(state: GraphState) -> GraphState:
    """Persist validated events into the events collection."""

    new_state = GraphState(**asdict(state))
    if not state.doc_id or not state.events_validated:
        return new_state

    coll = _get_events_collection()
    now_iso = datetime.now(timezone.utc).isoformat()

    docs = []
    for ev in state.events_validated:
        doc = {
            "source_doc_id": state.doc_id,
            "source_url": state.doc.get("source_url") if state.doc else None,
            "ticker": state.ticker,
            "sector": state.sector,
            "method_version": state.method_version,
            "created_at": now_iso,
            **ev,
        }
        docs.append(doc)

    if not docs:
        return new_state

    result = coll.insert_many(docs)
    new_state.event_ids = [str(i) for i in result.inserted_ids]
    return new_state


def update_company_state(state: GraphState) -> GraphState:
    """Upsert company_states for this ticker and attach new event_ids."""

    new_state = GraphState(**asdict(state))
    if not state.ticker or not state.event_ids:
        return new_state

    coll = _get_company_states_collection()
    coll.update_one(
        {"ticker": state.ticker.upper()},
        {
            "$setOnInsert": {"ticker": state.ticker.upper()},
            "$addToSet": {"timeline_event_ids": {"$each": state.event_ids}},
        },
        upsert=True,
    )

    return new_state


def mark_processed(state: GraphState) -> GraphState:
    """Mark the currently claimed document as processed or failed.

    Success:
      - unprocessed = False
      - metadata.processing.status = SUCCESS
      - metadata.processing.event_ids = state.event_ids
      - clears metadata.processing.last_error

    Failure (state.error set):
      - unprocessed = False
      - metadata.processing.status = FAILED
      - metadata.processing.last_error = state.error
    """

    if not state.doc_id:
        return state

    coll = _get_crawl_collection()
    try:
        oid = ObjectId(state.doc_id)
    except Exception:
        new_state = GraphState(**asdict(state))
        new_state.error = f"Invalid ObjectId: {state.doc_id}"
        return new_state

    if state.error:
        update = {
            "$set": {
                "unprocessed": False,
                "metadata.processing.status": "FAILED",
                "metadata.processing.last_error": state.error,
            }
        }
    else:
        update = {
            "$set": {
                "unprocessed": False,
                "metadata.processing.status": "SUCCESS",
                "metadata.processing.event_ids": state.event_ids,
                "metadata.processing.last_error": None,
            }
        }

    coll.update_one({"_id": oid}, update)

    new_state = GraphState(**asdict(state))
    return new_state


NODE_MAP: Dict[str, Any] = {
    "claim_next_doc": claim_next_doc,
    "route_sector": route_sector,
    "extract_biotech_events": extract_biotech_events,
    "extract_aviation_events": extract_aviation_events,
    "validate_events": validate_events,
    "write_events": write_events,
    "update_company_state": update_company_state,
    "mark_processed": mark_processed,
}

