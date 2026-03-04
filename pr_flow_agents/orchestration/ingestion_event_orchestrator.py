"""High-level ingestion event orchestrator.

Runs ingestion graph for one press release and persists extracted events.
"""

from __future__ import annotations

import argparse
from contextlib import nullcontext
from datetime import datetime
import json
import os
from typing import Any, Dict, Optional, Tuple

from pr_flow_agents.graph.ingestion.graph import build_graph
from pr_flow_agents.graph.ingestion.state import IngestionState
from pr_flow_agents.graph.linker.graph import build_graph as build_linker_graph
from pr_flow_agents.graph.linker.state import LinkerState
from pr_flow_agents.logging_utils import configure_logging, get_logger
from pr_flow_agents.storage.company_store import CompanyStore
from pr_flow_agents.storage.extracted_event_store import ExtractedEventStore

logger = get_logger(__name__)
MLFLOW_EXPERIMENT = "ingestion_flow"


def _parse_iso_timestamp(value: str) -> datetime:
    ts = (value or "").strip()
    if not ts:
        raise ValueError("press_release_timestamp missing from ingestion output")
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _derive_fiscal_fields(press_release_ts: datetime) -> Tuple[int, str]:
    fiscal_year = press_release_ts.year
    fiscal_quarter = f"Q{((press_release_ts.month - 1) // 3) + 1}"
    return fiscal_year, fiscal_quarter


class IngestionEventOrchestrator:
    """Orchestrates ingestion loop, silver persistence, and linker pipeline."""

    def __init__(self) -> None:
        self._app = build_graph()
        self._linker_app = build_linker_graph()
        self._company_store = CompanyStore()
        self._event_store = ExtractedEventStore()

    def _run_ingestion_loop(self, *, press_release_id: str, max_hops: Optional[int]) -> Dict[str, Any]:
        state: IngestionState = {"press_release_id": press_release_id}
        if max_hops is not None:
            state["max_hops"] = int(max_hops)
        return self._app.invoke(state)

    def _persist_silver_events(
        self,
        *,
        press_release_id: str,
        out: Dict[str, Any],
    ) -> Dict[str, Any]:
        ticker = str(out.get("ticker") or "").upper()
        release_ts_iso = str(out.get("press_release_timestamp") or "")
        release_title = str((out.get("press_release") or {}).get("title") or "")
        final_events = out.get("final_events", []) or []

        inserted_count = 0
        fiscal_year: Optional[int] = None
        fiscal_quarter: Optional[str] = None

        if ticker and release_ts_iso:
            release_ts = _parse_iso_timestamp(release_ts_iso)
            fiscal_year, fiscal_quarter = _derive_fiscal_fields(release_ts)
            company = self._company_store.get(ticker) or {}
            company_id = str(company.get("_id")) if company.get("_id") else None

            inserted_count = self._event_store.replace_for_release(
                press_release_id=press_release_id,
                company_ticker=ticker,
                company_id=company_id,
                release_title=release_title,
                press_release_timestamp=release_ts,
                fiscal_year=fiscal_year,
                fiscal_quarter=fiscal_quarter,
                events=final_events if isinstance(final_events, list) else [],
                quality_flag="NEEDS_REVIEW" if str(out.get("loop_status") or "").upper() == "MAX_HOPS" else "OK",
                hop_count=int(out.get("hop_count") or 0),
                loop_status=str(out.get("loop_status") or ""),
            )

        return {
            "ticker": ticker or None,
            "fiscal_year": fiscal_year,
            "fiscal_quarter": fiscal_quarter,
            "persisted_events_count": inserted_count,
        }

    def _run_linker_pipeline(
        self,
        *,
        press_release_id: str,
        ticker: Optional[str],
        sector: Optional[str],
    ) -> Dict[str, Any]:
        state: LinkerState = {
            "press_release_id": press_release_id,
            "ticker": str(ticker or "").upper(),
            "sector": sector,
        }
        out = self._linker_app.invoke(state)
        return out.get("result") or {
            "enabled": True,
            "status": "ERROR",
            "processed_silver_events_count": 0,
            "linked_events_created": 0,
            "linked_events_duplicates": 0,
            "linked_events_updated": 0,
            "linked_events_retracted": 0,
            "impacted_threads_count": 0,
            "decisions": [],
        }

    def run(self, *, press_release_id: str, max_hops: Optional[int] = None) -> Dict[str, Any]:
        logger.info("ingestion_event_orchestrator_start press_release_id=%s", press_release_id)

        tracking_enabled = str(os.getenv("MLFLOW_TRACKING_ENABLED", "1")).strip().lower() not in {"0", "false", "no", "off"}
        mlflow = None
        if tracking_enabled:
            try:
                import mlflow as _mlflow

                mlflow = _mlflow
                tracking_uri = str(os.getenv("MLFLOW_TRACKING_URI", "")).strip()
                if tracking_uri:
                    mlflow.set_tracking_uri(tracking_uri)
                mlflow.set_experiment(MLFLOW_EXPERIMENT)
            except Exception as exc:  # noqa: BLE001
                mlflow = None
                logger.warning("mlflow_init_failed error=%s", exc)

        run_ctx = nullcontext()
        if mlflow is not None and mlflow.active_run() is None:
            run_ctx = mlflow.start_run(run_name=f"orchestrator_{press_release_id}")

        with run_ctx:
            if mlflow is not None:
                with mlflow.start_span(name="ingestion_event_orchestrator") as root_span:
                    root_span.set_inputs({"press_release_id": press_release_id, "max_hops": max_hops})
                    with mlflow.start_span(name="ingestion_graph"):
                        out = self._run_ingestion_loop(press_release_id=press_release_id, max_hops=max_hops)
                    with mlflow.start_span(name="persist_silver_events"):
                        persist_summary = self._persist_silver_events(press_release_id=press_release_id, out=out)
                    with mlflow.start_span(name="linker_graph"):
                        linker_summary = self._run_linker_pipeline(
                            press_release_id=press_release_id,
                            ticker=persist_summary.get("ticker"),
                            sector=str(out.get("route") or out.get("sector") or ""),
                        )
            else:
                out = self._run_ingestion_loop(press_release_id=press_release_id, max_hops=max_hops)
                persist_summary = self._persist_silver_events(press_release_id=press_release_id, out=out)
                linker_summary = self._run_linker_pipeline(
                    press_release_id=press_release_id,
                    ticker=persist_summary.get("ticker"),
                    sector=str(out.get("route") or out.get("sector") or ""),
                )

            final_events = out.get("final_events", []) or []
            loop_status = str(out.get("loop_status") or "")
            error = out.get("error")

            summary = {
                "press_release_id": press_release_id,
                "ticker": persist_summary.get("ticker"),
                "loop_status": loop_status or None,
                "hop_count": out.get("hop_count"),
                "final_events_count": len(final_events) if isinstance(final_events, list) else 0,
                "persisted_events_count": persist_summary.get("persisted_events_count", 0),
                "fiscal_year": persist_summary.get("fiscal_year"),
                "fiscal_quarter": persist_summary.get("fiscal_quarter"),
                "linker": linker_summary,
                "error": error,
            }

            if mlflow is not None:
                mlflow.log_param("orchestrator_press_release_id", press_release_id)
                mlflow.log_metric("orchestrator_final_events_count", float(summary["final_events_count"]))
                mlflow.log_metric("orchestrator_persisted_events_count", float(summary["persisted_events_count"]))
                mlflow.log_metric(
                    "orchestrator_linker_processed_silver_events_count",
                    float((summary.get("linker") or {}).get("processed_silver_events_count", 0)),
                )
                if "root_span" in locals():
                    root_span.set_outputs(
                        {
                            "ticker": summary.get("ticker"),
                            "loop_status": summary.get("loop_status"),
                            "hop_count": summary.get("hop_count"),
                            "final_events_count": summary.get("final_events_count"),
                            "persisted_events_count": summary.get("persisted_events_count"),
                            "linker_status": (summary.get("linker") or {}).get("status"),
                        }
                    )

        logger.info(
            "ingestion_event_orchestrator_done press_release_id=%s persisted_events=%s loop_status=%s",
            press_release_id,
            summary.get("persisted_events_count", 0),
            summary.get("loop_status"),
        )
        return summary


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run event orchestration and persist extracted events")
    p.add_argument("--press-release-id", required=True, help="MongoDB _id from crawl_results")
    p.add_argument("--max-hops", type=int, default=None, help="Optional override for ingestion loop hops")
    return p.parse_args()


def main() -> None:
    configure_logging()
    args = _parse_args()
    orchestrator = IngestionEventOrchestrator()
    out = orchestrator.run(
        press_release_id=args.press_release_id,
        max_hops=args.max_hops,
    )
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
