"""High-level ingestion event orchestrator.

Runs ingestion graph for one press release and persists extracted events.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from typing import Any, Dict, Optional, Tuple

from pr_flow_agents.graph.ingestion.graph import build_graph
from pr_flow_agents.graph.ingestion.state import IngestionState
from pr_flow_agents.logging_utils import configure_logging, get_logger
from pr_flow_agents.storage.company_store import CompanyStore
from pr_flow_agents.storage.extracted_event_store import ExtractedEventStore

logger = get_logger(__name__)


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
    """Orchestrates graph execution and persistence of extracted events."""

    def __init__(self) -> None:
        self._app = build_graph()
        self._company_store = CompanyStore()
        self._event_store = ExtractedEventStore()

    def run(self, *, press_release_id: str, max_hops: Optional[int] = None) -> Dict[str, Any]:
        state: IngestionState = {"press_release_id": press_release_id}
        if max_hops is not None:
            state["max_hops"] = int(max_hops)

        logger.info("ingestion_event_orchestrator_start press_release_id=%s", press_release_id)
        out = self._app.invoke(state)

        ticker = str(out.get("ticker") or "").upper()
        release_ts_iso = str(out.get("press_release_timestamp") or "")
        release_title = str((out.get("press_release") or {}).get("title") or "")
        final_events = out.get("final_events", []) or []
        loop_status = str(out.get("loop_status") or "")
        error = out.get("error")

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
            )

        summary = {
            "press_release_id": press_release_id,
            "ticker": ticker or None,
            "loop_status": loop_status or None,
            "hop_count": out.get("hop_count"),
            "final_events_count": len(final_events) if isinstance(final_events, list) else 0,
            "persisted_events_count": inserted_count,
            "fiscal_year": fiscal_year,
            "fiscal_quarter": fiscal_quarter,
            "error": error,
        }
        logger.info(
            "ingestion_event_orchestrator_done press_release_id=%s persisted_events=%s loop_status=%s",
            press_release_id,
            inserted_count,
            loop_status,
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
