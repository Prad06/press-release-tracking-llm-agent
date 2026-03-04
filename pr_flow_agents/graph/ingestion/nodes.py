"""Nodes for ingestion graph with iterative extractor-expert hops (k-budgeted)."""

from __future__ import annotations

from datetime import datetime
import json
import os
from time import perf_counter
import tempfile
from typing import Any, Dict, List, Optional

from pr_flow_agents.graph.ingestion.prompts import (
    AVIATION_SYSTEM_PROMPT,
    BIOTECH_SYSTEM_PROMPT,
    EXTRACTOR_PROMPT_TEMPLATE,
    FINANCIAL_IMPACT_EXPERT_PROMPT,
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
MLFLOW_EXPERIMENT_DEFAULT = "pr_flow_ingestion"
LLM_MODEL_DEFAULT = "gemini-2.0-flash"

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
]

EXPERT_PROMPT_BY_NAME: Dict[str, str] = {
    "Financial Impact": FINANCIAL_IMPACT_EXPERT_PROMPT,
    "Operational Change": OPERATIONAL_CHANGE_EXPERT_PROMPT,
    "Product/Program": PRODUCT_PROGRAM_EXPERT_PROMPT,
    "Partnerships": PARTNERSHIPS_EXPERT_PROMPT,
    "Strategic Direction": STRATEGIC_DIRECTION_EXPERT_PROMPT,
    "Regulatory": REGULATORY_EXPERT_PROMPT,
}

try:
    import mlflow
except Exception:  # noqa: BLE001
    mlflow = None


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True)


def _mlflow_enabled() -> bool:
    flag = str(os.getenv("MLFLOW_TRACKING_ENABLED", "1")).strip().lower()
    return mlflow is not None and flag not in {"0", "false", "no", "off"}


def _mlflow_log_text(name: str, text: str) -> None:
    if not _mlflow_enabled():
        return
    if hasattr(mlflow, "log_text"):
        mlflow.log_text(text, name)
        return
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", encoding="utf-8", delete=False) as handle:
        handle.write(text)
        tmp_path = handle.name
    try:
        mlflow.log_artifact(tmp_path)
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


def _ensure_ingestion_run(state: IngestionState) -> Optional[str]:
    if not _mlflow_enabled():
        return None

    existing = str(state.get("mlflow_run_id") or "").strip()
    if existing:
        return existing
    active = mlflow.active_run()
    if active is not None:
        return active.info.run_id

    tracking_uri = str(os.getenv("MLFLOW_TRACKING_URI", "")).strip()
    if tracking_uri:
        mlflow.set_tracking_uri(tracking_uri)
    experiment_name = str(os.getenv("MLFLOW_EXPERIMENT_NAME", MLFLOW_EXPERIMENT_DEFAULT)).strip() or MLFLOW_EXPERIMENT_DEFAULT
    mlflow.set_experiment(experiment_name)

    run_name = f"ingestion_{str(state.get('press_release_id') or 'unknown')}"
    run = mlflow.start_run(run_name=run_name)
    run_id = run.info.run_id
    mlflow.log_param("press_release_id", str(state.get("press_release_id") or ""))
    if state.get("ticker"):
        mlflow.log_param("ticker", str(state.get("ticker") or ""))
    return run_id


def _log_llm_call(
    state: IngestionState,
    *,
    call_name: str,
    prompt: str,
    output: Any,
    elapsed_ms: int,
    success: bool,
    extra_metrics: Optional[Dict[str, float]] = None,
    extra_params: Optional[Dict[str, str]] = None,
) -> None:
    if not _mlflow_enabled():
        return
    run_id = str(state.get("mlflow_run_id") or "").strip()
    if not run_id:
        return

    prompt_chars = len(prompt)
    output_text = _stable_json(output)
    output_chars = len(output_text)
    call_slug = "".join(ch.lower() if ch.isalnum() else "_" for ch in call_name).strip("_") or "call"
    hop_count = int(state.get("hop_count") or 0)
    artifact_prefix = f"llm/{call_slug}_{hop_count}"

    with mlflow.start_run(run_id=run_id):
        with mlflow.start_run(run_name=call_name, nested=True):
            mlflow.log_param("llm_model", LLM_MODEL_DEFAULT)
            mlflow.log_param("call_name", call_name)
            mlflow.log_param("hop_count", hop_count)
            if extra_params:
                for key, value in extra_params.items():
                    mlflow.log_param(str(key), str(value))
            mlflow.log_metric("duration_ms", float(elapsed_ms))
            mlflow.log_metric("prompt_chars", float(prompt_chars))
            mlflow.log_metric("response_chars", float(output_chars))
            mlflow.log_metric("success", 1.0 if success else 0.0)
            if extra_metrics:
                for key, value in extra_metrics.items():
                    mlflow.log_metric(str(key), float(value))
            _mlflow_log_text(f"{artifact_prefix}_prompt.txt", prompt)
            _mlflow_log_text(f"{artifact_prefix}_output.json", output_text)


def load_press_release(state: IngestionState) -> IngestionState:
    run_id = _ensure_ingestion_run(state)
    press_release_id = (state.get("press_release_id") or "").strip()
    if not press_release_id:
        logger.warning("load_press_release_missing_id")
        return {
            **state,
            "mlflow_run_id": run_id or state.get("mlflow_run_id"),
            "route": "unsupported",
            "error": "press_release_id is required",
            "loop_status": "ERROR",
        }

    doc = MongoStore().get_by_id(press_release_id)
    if not doc:
        logger.warning("load_press_release_not_found id=%s", press_release_id)
        return {
            **state,
            "mlflow_run_id": run_id or state.get("mlflow_run_id"),
            "route": "unsupported",
            "error": f"press_release_id not found: {press_release_id}",
            "loop_status": "ERROR",
        }

    ticker = str(doc.get("ticker") or "").strip().upper()
    raw = doc.get("raw_result") or {}
    content = str(raw.get("markdown_content") or raw.get("main_content") or "")
    ts = doc.get("press_release_timestamp")
    ts_iso = ts.isoformat() if isinstance(ts, datetime) else str(ts or "")
    mapped_doc = {
        "_id": str(doc.get("_id") or press_release_id),
        "ticker": ticker,
        "title": str(doc.get("title") or ""),
        "press_release_timestamp": ts_iso,
        "source_url": str(doc.get("source_url") or ""),
        "crawl_timestamp": str(doc.get("crawl_timestamp") or ""),
        "raw_result": raw if isinstance(raw, dict) else {},
        "metadata": doc.get("metadata") if isinstance(doc.get("metadata"), dict) else {},
    }

    logger.info("load_press_release_done id=%s ticker=%s content_chars=%s", press_release_id, ticker, len(content))
    if _mlflow_enabled() and run_id:
        with mlflow.start_run(run_id=run_id):
            mlflow.log_param("ticker", ticker)
            mlflow.log_param("press_release_timestamp", ts_iso)
            mlflow.log_metric("press_release_chars", float(len(content)))
    return {
        **state,
        "mlflow_run_id": run_id or state.get("mlflow_run_id"),
        "press_release": mapped_doc,
        "ticker": ticker,
        "press_release_timestamp": ts_iso,
        "press_release_content": content,
        "error": None,
        "loop_status": "PENDING",
    }


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
    run_id = str(state.get("mlflow_run_id") or "").strip()
    if _mlflow_enabled() and run_id:
        with mlflow.start_run(run_id=run_id):
            mlflow.log_param("sector_raw", raw_sector)
            mlflow.log_param("sector_route", canonical)
    return {**state, "ticker": ticker, "sector": raw_sector, "route": canonical, "error": None, "loop_status": "PENDING"}


def configure_biotech_agent(state: IngestionState) -> IngestionState:
    return {
        **state,
        "agent_name": "sector_event_extractor",
        "system_prompt": BIOTECH_SYSTEM_PROMPT,
        "agent_config": {"sector": "biotech"},
    }


def configure_aviation_agent(state: IngestionState) -> IngestionState:
    return {
        **state,
        "agent_name": "sector_event_extractor",
        "system_prompt": AVIATION_SYSTEM_PROMPT,
        "agent_config": {"sector": "aviation"},
    }


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


def configure_experts(state: IngestionState) -> IngestionState:
    run_id = str(state.get("mlflow_run_id") or "").strip()
    if _mlflow_enabled() and run_id:
        with mlflow.start_run(run_id=run_id):
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

    started = perf_counter()
    log_state = {**state, "hop_count": hop_count}
    try:
        raw_out = generate_json(prompt)
        candidate_events = raw_out if isinstance(raw_out, list) else []
        elapsed_ms = int((perf_counter() - started) * 1000)
        _log_llm_call(
            log_state,
            call_name="extractor",
            prompt=prompt,
            output=raw_out,
            elapsed_ms=elapsed_ms,
            success=True,
            extra_metrics={"candidate_events_count": float(len(candidate_events))},
        )
        logger.info("run_extractor_done hop=%s candidates=%s", hop_count, len(candidate_events))
        return {
            **state,
            "hop_count": hop_count,
            "candidate_events": candidate_events,
            "loop_status": "PENDING",
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001
        elapsed_ms = int((perf_counter() - started) * 1000)
        _log_llm_call(
            log_state,
            call_name="extractor",
            prompt=prompt,
            output={"error": str(exc)},
            elapsed_ms=elapsed_ms,
            success=False,
        )
        logger.exception("run_extractor_failed hop=%s", hop_count)
        return {
            **state,
            "hop_count": hop_count,
            "candidate_events": [],
            "error": f"extractor_failed: {exc}",
            "loop_status": "ERROR",
        }


def validate_events(state: IngestionState) -> IngestionState:
    content = state.get("press_release_content") or ""
    candidates = state.get("candidate_events", []) or []
    prompt = VALIDATOR_PROMPT_TEMPLATE.format(
        candidate_events=json.dumps(candidates, ensure_ascii=True),
        content=content,
    )

    started = perf_counter()
    try:
        raw_out = generate_json(prompt)
        out = raw_out if isinstance(raw_out, dict) else {}
        validated_raw = out.get("validated_events", [])
        drops_raw = out.get("drops", [])
        validated = [ev for ev in validated_raw if isinstance(ev, dict)] if isinstance(validated_raw, list) else []
        drops = [ev for ev in drops_raw if isinstance(ev, dict)] if isinstance(drops_raw, list) else []
        elapsed_ms = int((perf_counter() - started) * 1000)
        _log_llm_call(
            state,
            call_name="validator",
            prompt=prompt,
            output=raw_out,
            elapsed_ms=elapsed_ms,
            success=True,
            extra_metrics={
                "validated_events_count": float(len(validated)),
                "dropped_events_count": float(len(drops)),
            },
        )
    except Exception as exc:  # noqa: BLE001
        elapsed_ms = int((perf_counter() - started) * 1000)
        _log_llm_call(
            state,
            call_name="validator",
            prompt=prompt,
            output={"error": str(exc)},
            elapsed_ms=elapsed_ms,
            success=False,
        )
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

    for expert_name in experts:
        template = EXPERT_PROMPT_BY_NAME.get(expert_name)
        if not template:
            continue
        prompt = template.format(
            events=json.dumps(validated, ensure_ascii=True),
            content=content,
        )
        started = perf_counter()
        try:
            raw = generate_json(prompt)
            feedback = raw if isinstance(raw, dict) else {}
            elapsed_ms = int((perf_counter() - started) * 1000)
            _log_llm_call(
                state,
                call_name=f"expert_review_{expert_name}",
                prompt=prompt,
                output=raw,
                elapsed_ms=elapsed_ms,
                success=True,
                extra_params={"expert_name": expert_name},
            )
        except Exception as exc:  # noqa: BLE001
            elapsed_ms = int((perf_counter() - started) * 1000)
            _log_llm_call(
                state,
                call_name=f"expert_review_{expert_name}",
                prompt=prompt,
                output={"error": str(exc)},
                elapsed_ms=elapsed_ms,
                success=False,
                extra_params={"expert_name": expert_name},
            )
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


def revise_extraction(state: IngestionState) -> IngestionState:
    logger.info("revise_extraction hop=%s", state.get("hop_count"))
    return {**state, "loop_status": "PENDING"}


def finalize_output(state: IngestionState) -> IngestionState:
    logger.info("finalize_output loop_status=%s final_count=%s", state.get("loop_status"), len(state.get("validated_events", [])))
    run_id = str(state.get("mlflow_run_id") or "").strip()
    if _mlflow_enabled() and run_id:
        with mlflow.start_run(run_id=run_id):
            mlflow.log_param("final_loop_status", str(state.get("loop_status") or ""))
            mlflow.log_metric("final_events_count", float(len(state.get("validated_events", []))))
            if state.get("error"):
                mlflow.log_param("error", str(state.get("error")))
        mlflow.end_run()
    return {
        **state,
        "final_events": list(state.get("validated_events", [])),
    }
