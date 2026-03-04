"""Nodes for ingestion graph with iterative extractor-expert hops (k-budgeted)."""

from __future__ import annotations

from datetime import datetime
import json
from typing import Any, Dict, List, Optional

from pr_flow_agents.graph.ingestion.prompts import (
    AVIATION_SYSTEM_PROMPT,
    BIOTECH_SYSTEM_PROMPT,
    EXTRACTOR_PROMPT_TEMPLATE,
    FINANCIAL_IMPACT_EXPERT_PROMPT,
    GENERAL_EXPERT_PROMPT,
    OPERATIONAL_CHANGE_EXPERT_PROMPT,
    PRODUCT_PROGRAM_EXPERT_PROMPT,
    PARTNERSHIPS_EXPERT_PROMPT,
    STRATEGIC_DIRECTION_EXPERT_PROMPT,
    REGULATORY_EXPERT_PROMPT,
    VALIDATOR_PROMPT_TEMPLATE,
)
from pr_flow_agents.graph.ingestion.state import IngestionState
from pr_flow_agents.llm import generate_json
from pr_flow_agents.logging_utils import get_logger
from pr_flow_agents.storage.company_store import CompanyStore
from pr_flow_agents.storage.mongo_store import MongoStore

logger = get_logger(__name__)

MAX_HOPS_DEFAULT = 2

SECTOR_NORMALIZATION: Dict[str, str] = {
    "biotech": "biotech",
    "biotechnology": "biotech",
    "aviation": "aviation",
    "airline": "aviation",
    "airlines": "aviation",
    "aerospace": "aviation",
}

EXPERTS = [
    "Financial Impact",
    "Operational Change",
    "Product/Program",
    "Partnerships",
    "Strategic Direction",
    "Regulatory",
    "General",
]

EXPERT_PROMPT_BY_NAME: Dict[str, str] = {
    "Financial Impact": FINANCIAL_IMPACT_EXPERT_PROMPT,
    "Operational Change": OPERATIONAL_CHANGE_EXPERT_PROMPT,
    "Product/Program": PRODUCT_PROGRAM_EXPERT_PROMPT,
    "Partnerships": PARTNERSHIPS_EXPERT_PROMPT,
    "Strategic Direction": STRATEGIC_DIRECTION_EXPERT_PROMPT,
    "Regulatory": REGULATORY_EXPERT_PROMPT,
    "General": GENERAL_EXPERT_PROMPT,
}

# Primary event types each expert owns — used for pre-filtering.
# Events matching these types are "in scope" for the expert.
# All events are still sent for miscategorization detection, but
# clearly marked as in-scope vs out-of-scope in the prompt.
EXPERT_PRIMARY_TYPES: Dict[str, set[str]] = {
    "Financial Impact": {"FINANCIAL"},
    "Operational Change": {"OPERATIONAL"},
    "Product/Program": {"PRODUCT_LAUNCH", "CLINICAL_TRIAL"},
    "Partnerships": {"PARTNERSHIP", "M_AND_A"},
    "Strategic Direction": {"STRATEGIC"},
    "Regulatory": {"REGULATORY", "LEGAL"},
    "General": {"OTHER", "LEADERSHIP"},
}

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


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True)


def _mlflow_enabled() -> bool:
    return mlflow is not None and mlflow.active_run() is not None


@_trace(span_type="CHAIN", name="load_press_release")
def load_press_release(state: IngestionState) -> IngestionState:
    press_release_id = (state.get("press_release_id") or "").strip()
    if not press_release_id:
        logger.warning("load_press_release_missing_id")
        return {
            **state,
            "route": "unsupported",
            "error": "press_release_id is required",
            "loop_status": "ERROR",
        }

    doc = MongoStore().get_by_id(
        press_release_id,
        projection={
            "ticker": 1,
            "title": 1,
            "press_release_timestamp": 1,
            "raw_result.markdown_content": 1,
        },
    )
    if not doc:
        logger.warning("load_press_release_not_found id=%s", press_release_id)
        return {
            **state,
            "route": "unsupported",
            "error": f"press_release_id not found: {press_release_id}",
            "loop_status": "ERROR",
        }

    ticker = str(doc.get("ticker") or "").strip().upper()
    raw = doc.get("raw_result") or {}
    content = str(raw.get("markdown_content") or "")
    ts = doc.get("press_release_timestamp")
    ts_iso = ts.isoformat() if isinstance(ts, datetime) else str(ts or "")
    mapped_doc = {
        "_id": str(doc.get("_id") or press_release_id),
        "ticker": ticker,
        "title": str(doc.get("title") or ""),
        "press_release_timestamp": ts_iso,
        "raw_result": {"markdown_content": content},
    }

    logger.info("load_press_release_done id=%s ticker=%s content_chars=%s", press_release_id, ticker, len(content))
    if _mlflow_enabled():
        mlflow.log_param("press_release_id", press_release_id)
        mlflow.log_param("ticker", ticker)
        mlflow.log_param("title", str(doc.get("title") or ""))
        mlflow.log_param("press_release_timestamp", ts_iso)
        mlflow.log_metric("press_release_chars", float(len(content)))
    return {
        **state,
        "press_release": mapped_doc,
        "ticker": ticker,
        "press_release_timestamp": ts_iso,
        "press_release_content": content,
        "error": None,
        "loop_status": "PENDING",
    }


@_trace(span_type="CHAIN", name="route_sector")
def route_sector(state: IngestionState) -> IngestionState:
    ticker = (state.get("ticker") or "").strip().upper()
    if not ticker:
        logger.warning("route_sector_missing_ticker")
        return {**state, "route": "unsupported", "error": "ticker is required", "loop_status": "ERROR"}

    company = CompanyStore().get(ticker) or {}
    raw_sector = str(company.get("sector") or "").strip().lower()
    canonical = SECTOR_NORMALIZATION.get(raw_sector)

    if not canonical:
        logger.warning("route_sector_unsupported ticker=%s raw_sector=%s", ticker, raw_sector)
        return {
            **state,
            "sector": raw_sector or None,
            "route": "unsupported",
            "error": f"Unsupported or missing sector for ticker {ticker}",
            "loop_status": "ERROR",
        }

    logger.info("route_sector_done ticker=%s raw_sector=%s canonical=%s", ticker, raw_sector, canonical)
    if _mlflow_enabled():
        mlflow.log_param("sector_raw", raw_sector)
        mlflow.log_param("sector_route", canonical)
    return {**state, "ticker": ticker, "sector": raw_sector, "route": canonical, "error": None, "loop_status": "PENDING"}


@_trace(span_type="CHAIN", name="configure_biotech_agent")
def configure_biotech_agent(state: IngestionState) -> IngestionState:
    return {
        **state,
        "agent_name": "sector_event_extractor",
        "system_prompt": BIOTECH_SYSTEM_PROMPT,
        "agent_config": {"sector": "biotech"},
    }


@_trace(span_type="CHAIN", name="configure_aviation_agent")
def configure_aviation_agent(state: IngestionState) -> IngestionState:
    return {
        **state,
        "agent_name": "sector_event_extractor",
        "system_prompt": AVIATION_SYSTEM_PROMPT,
        "agent_config": {"sector": "aviation"},
    }


@_trace(span_type="CHAIN", name="configure_unsupported")
def configure_unsupported(state: IngestionState) -> IngestionState:
    return {
        **state,
        "agent_name": "unsupported",
        "system_prompt": "",
        "agent_config": {"sector": "unsupported"},
        "experts": [],
        "candidate_events": [],
        "validated_events": [],
        "final_events": [],
    }


@_trace(span_type="CHAIN", name="configure_experts")
def configure_experts(state: IngestionState) -> IngestionState:
    if _mlflow_enabled():
        mlflow.log_param("max_hops", int(state.get("max_hops") or MAX_HOPS_DEFAULT))
        mlflow.log_param("experts", ",".join(EXPERTS))
    return {
        **state,
        "experts": list(EXPERTS),
        "hop_count": 0,
        "max_hops": int(state.get("max_hops") or MAX_HOPS_DEFAULT),
        "candidate_events": state.get("candidate_events", []),
        "expert_feedback": state.get("expert_feedback", {}),
        "validated_events": state.get("validated_events", []),
        "review_trace": state.get("review_trace", []),
        "loop_status": "PENDING",
        "final_events": state.get("final_events", []),
    }


@_trace(span_type="CHAIN", name="run_extractor")
def run_extractor(state: IngestionState) -> IngestionState:
    hop_count = int(state.get("hop_count") or 0) + 1
    max_hops = int(state.get("max_hops") or MAX_HOPS_DEFAULT)
    content = state.get("press_release_content") or ""

    prompt = EXTRACTOR_PROMPT_TEMPLATE.format(
        system_prompt=state.get("system_prompt", ""),
        hop_count=hop_count,
        max_hops=max_hops,
        experts=state.get("experts", []),
        expert_feedback=state.get("expert_feedback", {}),
        content=content,
    )

    try:
        raw_out = generate_json(prompt)
        candidate_events = raw_out if isinstance(raw_out, list) else []
        logger.info("run_extractor_done hop=%s candidates=%s", hop_count, len(candidate_events))
        return {
            **state,
            "hop_count": hop_count,
            "candidate_events": candidate_events,
            "loop_status": "PENDING",
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("run_extractor_failed hop=%s", hop_count)
        return {
            **state,
            "hop_count": hop_count,
            "candidate_events": [],
            "error": f"extractor_failed: {exc}",
            "loop_status": "ERROR",
        }


@_trace(span_type="CHAIN", name="validate_events")
def validate_events(state: IngestionState) -> IngestionState:
    content = state.get("press_release_content") or ""
    candidates = state.get("candidate_events", []) or []
    prompt = VALIDATOR_PROMPT_TEMPLATE.format(
        candidate_events=json.dumps(candidates, ensure_ascii=True),
        content=content,
    )

    try:
        raw_out = generate_json(prompt)
        out = raw_out if isinstance(raw_out, dict) else {}
        validated_raw = out.get("validated_events", [])
        drops_raw = out.get("drops", [])
        validated = [ev for ev in validated_raw if isinstance(ev, dict)] if isinstance(validated_raw, list) else []
        drops = [ev for ev in drops_raw if isinstance(ev, dict)] if isinstance(drops_raw, list) else []
    except Exception as exc:  # noqa: BLE001
        logger.exception("validate_events_failed hop=%s", state.get("hop_count"))
        validated = []
        drops = [{"reason": f"validator_failed: {exc}"}]

    trace = list(state.get("review_trace", []))
    trace.append(
        {
            "hop": int(state.get("hop_count") or 0),
            "candidate_count": len(candidates),
            "validated_count": len(validated),
            "dropped_count": len(drops),
            "validated_events": validated,
            "drops": drops,
        }
    )

    logger.info("validate_events_done hop=%s validated=%s dropped=%s", state.get("hop_count"), len(validated), len(drops))
    return {**state, "validated_events": validated, "review_trace": trace}


@_trace(span_type="CHAIN", name="run_expert_review")
def run_expert_review(state: IngestionState) -> IngestionState:
    max_hops = int(state.get("max_hops") or MAX_HOPS_DEFAULT)
    hop_count = int(state.get("hop_count") or 0)
    validated = state.get("validated_events", []) or []

    content = state.get("press_release_content") or ""
    experts = state.get("experts", []) or []
    by_expert: Dict[str, Dict[str, Any]] = {}
    issues: List[str] = []
    suggestions: List[Dict[str, Any]] = []
    any_revise = False

    # Route each event to its owning expert only.
    event_buckets: Dict[str, List[Dict[str, Any]]] = {}
    for ev in validated:
        if not isinstance(ev, dict):
            continue
        event_type = str(ev.get("event_type") or "").strip().upper()
        owners = [name for name, types in EXPERT_PRIMARY_TYPES.items() if event_type in types]
        if not owners:
            owners = ["General"]
        for owner in owners:
            if owner in experts:
                event_buckets.setdefault(owner, []).append(ev)

    selected_experts = [name for name in experts if name in event_buckets]
    if not selected_experts and "General" in experts:
        # Keep one lightweight guard pass when no events are available.
        selected_experts = ["General"]

    for expert_name in selected_experts:
        template = EXPERT_PROMPT_BY_NAME.get(expert_name)
        if not template:
            continue

        in_scope = event_buckets.get(expert_name, [])
        if not in_scope:
            by_expert[expert_name] = {
                "decision": "ACCEPT",
                "summary": "No events to review",
                "issues": [],
                "suggestions": [],
            }
            continue

        events_payload = json.dumps(
            {"in_scope": in_scope, "out_of_scope_for_miscategorization_check": []},
            ensure_ascii=True,
        )

        prompt = template.format(
            events=events_payload,
            content=content,
        )
        try:
            raw = generate_json(prompt)
            feedback = raw if isinstance(raw, dict) else {}
        except Exception as exc:  # noqa: BLE001
            feedback = {
                "decision": "REVISE",
                "summary": f"{expert_name} review failed: {exc}",
                "issues": [f"{expert_name}: expert_review_failed"],
                "suggestions": [],
            }
        by_expert[expert_name] = feedback
        decision = str(feedback.get("decision") or "REVISE").upper()
        if decision != "ACCEPT":
            any_revise = True
        for issue in feedback.get("issues", []) or []:
            issues.append(f"{expert_name}: {issue}")
        for suggestion in feedback.get("suggestions", []) or []:
            if isinstance(suggestion, dict):
                suggestions.append({"expert": expert_name, **suggestion})

    feedback = {
        "decision": "REVISE" if any_revise else "ACCEPT",
        "summary": "Merged specialist feedback",
        "issues": issues,
        "suggestions": suggestions,
        "by_expert": by_expert,
    }
    decision = feedback["decision"]

    no_change = False
    trace = state.get("review_trace", []) or []
    if len(trace) >= 2:
        prev = trace[-2].get("validated_events", [])
        curr = trace[-1].get("validated_events", [])
        no_change = _stable_json(prev) == _stable_json(curr)

    if decision == "ACCEPT":
        loop_status = "ACCEPT"
    elif no_change:
        loop_status = "NO_CHANGE"
    elif hop_count >= max_hops:
        loop_status = "MAX_HOPS"
    else:
        loop_status = "REVISE"

    trace = list(trace)
    trace.append(
        {
            "hop": hop_count,
            "review_decision": decision,
            "no_change": no_change,
            "loop_status": loop_status,
            "feedback": feedback,
        }
    )

    logger.info("run_expert_review_done hop=%s decision=%s loop_status=%s", hop_count, decision, loop_status)
    return {
        **state,
        "expert_feedback": feedback,
        "loop_status": loop_status,
        "review_trace": trace,
    }


@_trace(span_type="CHAIN", name="revise_extraction")
def revise_extraction(state: IngestionState) -> IngestionState:
    logger.info("revise_extraction hop=%s", state.get("hop_count"))
    return {**state, "loop_status": "PENDING"}


@_trace(span_type="CHAIN", name="finalize_output")
def finalize_output(state: IngestionState) -> IngestionState:
    logger.info("finalize_output loop_status=%s final_count=%s", state.get("loop_status"), len(state.get("validated_events", [])))
    if _mlflow_enabled():
        mlflow.log_param("final_loop_status", str(state.get("loop_status") or ""))
        mlflow.log_metric("final_events_count", float(len(state.get("validated_events", []))))
        if state.get("error"):
            mlflow.log_param("error", str(state.get("error")))
    return {
        **state,
        "final_events": list(state.get("validated_events", [])),
    }
