"""Nodes for baseline summary graph."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from pr_flow_agents.graph.baseline.prompts import (
    UPDATE_COMPANY_SUMMARY_PROMPT,
    UPDATE_QUARTERLY_SUMMARY_PROMPT,
)
from pr_flow_agents.graph.baseline.state import BaselineState
from pr_flow_agents.llm import generate_json
from pr_flow_agents.logging_utils import get_logger
from pr_flow_agents.storage.baseline_summary_store import BaselineSummaryStore
from pr_flow_agents.storage.mongo_store import MongoStore

logger = get_logger(__name__)

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


@_trace(span_type="CHAIN", name="load_press_release")
def load_press_release(state: BaselineState) -> BaselineState:
    press_release_id = str(state.get("press_release_id") or "").strip()
    if not press_release_id:
        return {
            **state,
            "status": "ERROR",
            "error": "press_release_id is required",
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
        return {
            **state,
            "status": "ERROR",
            "error": f"press_release_id not found: {press_release_id}",
        }

    ticker = str(doc.get("ticker") or "").strip().upper()
    raw = doc.get("raw_result") or {}
    content = str(raw.get("markdown_content") or "")
    ts = doc.get("press_release_timestamp")
    ts_iso = ts.isoformat() if isinstance(ts, datetime) else str(ts or "")

    logger.info("baseline_load_press_release_done id=%s ticker=%s content_chars=%s", press_release_id, ticker, len(content))
    if _mlflow_enabled():
        mlflow.log_param("baseline_press_release_id", press_release_id)
        mlflow.log_param("baseline_ticker", ticker)
        mlflow.log_param("baseline_press_release_timestamp", ts_iso)
        mlflow.log_metric("baseline_press_release_chars", float(len(content)))

    return {
        **state,
        "ticker": ticker,
        "press_release_title": str(doc.get("title") or ""),
        "press_release_timestamp": ts_iso,
        "press_release_content": content,
        "status": "PENDING",
        "error": None,
    }


@_trace(span_type="CHAIN", name="derive_fiscal_context")
def derive_fiscal_context(state: BaselineState) -> BaselineState:
    ts_raw = str(state.get("press_release_timestamp") or "").strip()
    if not ts_raw:
        return {**state, "status": "ERROR", "error": "press_release_timestamp missing"}

    try:
        ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
    except Exception as exc:  # noqa: BLE001
        return {**state, "status": "ERROR", "error": f"invalid_press_release_timestamp: {exc}"}

    fiscal_year = ts.year
    fiscal_quarter = f"Q{((ts.month - 1) // 3) + 1}"
    return {
        **state,
        "fiscal_year": fiscal_year,
        "fiscal_quarter": fiscal_quarter,
    }


@_trace(span_type="CHAIN", name="load_existing_summaries")
def load_existing_summaries(state: BaselineState) -> BaselineState:
    ticker = str(state.get("ticker") or "").strip().upper()
    fiscal_year = state.get("fiscal_year")
    fiscal_quarter = str(state.get("fiscal_quarter") or "").upper()
    if not ticker or not fiscal_year or not fiscal_quarter:
        return {**state, "status": "ERROR", "error": "missing_ticker_or_fiscal_context"}

    store = BaselineSummaryStore()
    company_doc = store.get_company_summary(ticker)
    quarter_doc = store.get_quarterly_summary(ticker=ticker, fiscal_year=int(fiscal_year), fiscal_quarter=fiscal_quarter)

    company_summary = str((company_doc or {}).get("summary_text") or "")
    quarterly_summary = str((quarter_doc or {}).get("summary_text") or "")

    logger.info(
        "baseline_load_existing_summaries_done ticker=%s has_company=%s has_quarter=%s",
        ticker,
        bool(company_summary),
        bool(quarterly_summary),
    )
    return {
        **state,
        "existing_company_summary": company_summary,
        "existing_quarterly_summary": quarterly_summary,
    }


@_trace(span_type="CHAIN", name="update_summaries")
def update_summaries(state: BaselineState) -> BaselineState:
    company_prompt = UPDATE_COMPANY_SUMMARY_PROMPT.format(
        ticker=str(state.get("ticker") or ""),
        press_release_id=str(state.get("press_release_id") or ""),
        press_release_title=str(state.get("press_release_title") or ""),
        press_release_timestamp=str(state.get("press_release_timestamp") or ""),
        existing_company_summary=str(state.get("existing_company_summary") or "<none>"),
        press_release_content=str(state.get("press_release_content") or ""),
    )
    quarterly_prompt = UPDATE_QUARTERLY_SUMMARY_PROMPT.format(
        ticker=str(state.get("ticker") or ""),
        press_release_id=str(state.get("press_release_id") or ""),
        press_release_title=str(state.get("press_release_title") or ""),
        press_release_timestamp=str(state.get("press_release_timestamp") or ""),
        fiscal_year=int(state.get("fiscal_year") or 0),
        fiscal_quarter=str(state.get("fiscal_quarter") or ""),
        existing_quarterly_summary=str(state.get("existing_quarterly_summary") or "<none>"),
        press_release_content=str(state.get("press_release_content") or ""),
    )

    try:
        company_out = generate_json(company_prompt)
        company_payload = company_out if isinstance(company_out, dict) else {}
        quarterly_out = generate_json(quarterly_prompt)
        quarterly_payload = quarterly_out if isinstance(quarterly_out, dict) else {}
    except Exception as exc:  # noqa: BLE001
        logger.exception("baseline_update_summaries_failed")
        return {
            **state,
            "status": "ERROR",
            "error": f"baseline_update_summaries_failed: {exc}",
        }

    company_summary = str(company_payload.get("summary") or "").strip()
    quarterly_summary = str(quarterly_payload.get("summary") or "").strip()
    company_change_notes = str(company_payload.get("change_notes") or "").strip()
    quarterly_change_notes = str(quarterly_payload.get("change_notes") or "").strip()
    parts = []
    if company_change_notes:
        parts.append(f"company: {company_change_notes}")
    if quarterly_change_notes:
        parts.append(f"quarterly: {quarterly_change_notes}")
    change_notes = " | ".join(parts)

    if not company_summary:
        company_summary = str(state.get("existing_company_summary") or "").strip()
    if not quarterly_summary:
        quarterly_summary = str(state.get("existing_quarterly_summary") or "").strip()

    if _mlflow_enabled():
        mlflow.log_metric("baseline_company_summary_chars", float(len(company_summary)))
        mlflow.log_metric("baseline_quarterly_summary_chars", float(len(quarterly_summary)))

    logger.info(
        "baseline_update_summaries_done ticker=%s company_chars=%s quarter_chars=%s",
        state.get("ticker"),
        len(company_summary),
        len(quarterly_summary),
    )
    return {
        **state,
        "company_summary": company_summary,
        "quarterly_summary": quarterly_summary,
        "change_notes": change_notes,
    }


@_trace(span_type="CHAIN", name="persist_summaries")
def persist_summaries(state: BaselineState) -> BaselineState:
    ticker = str(state.get("ticker") or "").strip().upper()
    press_release_id = str(state.get("press_release_id") or "").strip()
    if not ticker or not press_release_id:
        return {**state, "status": "ERROR", "error": "missing_ticker_or_press_release_id"}

    ts_raw = str(state.get("press_release_timestamp") or "")
    try:
        release_ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
    except Exception as exc:  # noqa: BLE001
        return {**state, "status": "ERROR", "error": f"invalid_press_release_timestamp: {exc}"}

    fiscal_year = int(state.get("fiscal_year") or 0)
    fiscal_quarter = str(state.get("fiscal_quarter") or "").upper()
    if fiscal_year <= 0 or fiscal_quarter not in {"Q1", "Q2", "Q3", "Q4"}:
        return {**state, "status": "ERROR", "error": "invalid_fiscal_context"}

    store = BaselineSummaryStore()
    company_doc = store.upsert_company_summary(
        ticker=ticker,
        summary_text=str(state.get("company_summary") or ""),
        press_release_id=press_release_id,
        press_release_timestamp=release_ts,
    )
    quarter_doc = store.upsert_quarterly_summary(
        ticker=ticker,
        fiscal_year=fiscal_year,
        fiscal_quarter=fiscal_quarter,
        summary_text=str(state.get("quarterly_summary") or ""),
        press_release_id=press_release_id,
        press_release_timestamp=release_ts,
    )

    logger.info(
        "baseline_persist_summaries_done ticker=%s fiscal=%s-%s",
        ticker,
        fiscal_year,
        fiscal_quarter,
    )
    return {
        **state,
        "company_summary_doc": company_doc,
        "quarterly_summary_doc": quarter_doc,
        "status": "DONE",
    }


@_trace(span_type="CHAIN", name="finalize_output")
def finalize_output(state: BaselineState) -> BaselineState:
    result = {
        "status": str(state.get("status") or "ERROR"),
        "press_release_id": state.get("press_release_id"),
        "ticker": state.get("ticker"),
        "fiscal_year": state.get("fiscal_year"),
        "fiscal_quarter": state.get("fiscal_quarter"),
        "company_summary": str(state.get("company_summary") or ""),
        "quarterly_summary": str(state.get("quarterly_summary") or ""),
        "change_notes": str(state.get("change_notes") or ""),
        "company_summary_id": (state.get("company_summary_doc") or {}).get("summary_id"),
        "quarterly_summary_id": (state.get("quarterly_summary_doc") or {}).get("summary_id"),
        "error": state.get("error"),
    }
    if _mlflow_enabled():
        mlflow.log_param("baseline_status", str(result.get("status") or ""))
        mlflow.log_metric("baseline_has_error", 1.0 if result.get("error") else 0.0)
    return {**state, "result": result}
