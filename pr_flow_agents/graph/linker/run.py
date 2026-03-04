"""CLI runner for linker graph."""

from __future__ import annotations

import argparse
import json
import os

from pr_flow_agents.graph.linker.graph import build_graph
from pr_flow_agents.graph.linker.state import LinkerState
from pr_flow_agents.logging_utils import configure_logging, get_logger

logger = get_logger(__name__)
MLFLOW_EXPERIMENT = "linker_flow"


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run linker graph")
    p.add_argument("--press-release-id", required=True, help="MongoDB _id from crawl_results")
    p.add_argument("--ticker", required=True, help="Ticker of the release")
    p.add_argument("--sector", default="", help="Sector route used for thread heuristics")
    return p.parse_args()


def main() -> None:
    configure_logging()
    args = _parse_args()
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
            logger.info(
                "mlflow_tracking_configured tracking_uri=%s experiment=%s",
                mlflow.get_tracking_uri(),
                MLFLOW_EXPERIMENT,
            )
        except Exception as exc:  # noqa: BLE001
            mlflow = None
            logger.warning("mlflow_init_failed error=%s", exc)

    state: LinkerState = {
        "press_release_id": args.press_release_id,
        "ticker": args.ticker.upper(),
        "sector": args.sector or None,
    }
    logger.info(
        "linker_graph_start press_release_id=%s ticker=%s sector=%s",
        args.press_release_id,
        args.ticker.upper(),
        args.sector or "",
    )
    app = build_graph()
    if mlflow is not None:
        with mlflow.start_run(run_name=f"linker_{args.press_release_id}_{args.ticker.upper()}"):
            with mlflow.start_span(name="linker_graph") as span:
                span.set_inputs(state)
                out = app.invoke(state)
                result = out.get("result") or {}
                span.set_outputs(
                    {
                        "status": result.get("status"),
                        "processed_silver_events_count": result.get("processed_silver_events_count"),
                        "linked_events_created": result.get("linked_events_created"),
                        "linked_events_duplicates": result.get("linked_events_duplicates"),
                        "linked_events_updated": result.get("linked_events_updated"),
                        "linked_events_retracted": result.get("linked_events_retracted"),
                        "impacted_threads_count": result.get("impacted_threads_count"),
                    }
                )
    else:
        out = app.invoke(state)
    logger.info("linker_graph_end press_release_id=%s ticker=%s", args.press_release_id, args.ticker.upper())
    print(json.dumps(out.get("result") or {}, indent=2))


if __name__ == "__main__":
    main()
