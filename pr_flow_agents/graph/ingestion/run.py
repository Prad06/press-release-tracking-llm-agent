"""CLI for ingestion graph step 1.

Example:
python -m pr_flow_agents.graph.ingestion.run \
  --press-release-id 67c6b8d6e4a87c0012345678
"""

from __future__ import annotations

import argparse
import json
import os

from pr_flow_agents.graph.ingestion.graph import build_graph
from pr_flow_agents.graph.ingestion.state import IngestionState
from pr_flow_agents.logging_utils import configure_logging, get_logger

logger = get_logger(__name__)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run ingestion step-1 router graph")
    p.add_argument(
        "--press-release-id",
        required=True,
        help="MongoDB _id from crawl_results",
    )
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
            experiment_name = "ingestion_flow"
            mlflow.set_experiment(experiment_name)
            logger.info(
                "mlflow_tracking_configured tracking_uri=%s experiment=%s",
                mlflow.get_tracking_uri(),
                experiment_name,
            )
        except Exception as exc:  # noqa: BLE001
            mlflow = None
            logger.warning("mlflow_init_failed error=%s", exc)

    state: IngestionState = {
        "press_release_id": args.press_release_id,
    }

    logger.info("ingestion_graph_start press_release_id=%s", args.press_release_id)
    app = build_graph()

    if mlflow is not None:
        with mlflow.start_run(run_name=f"ingestion_{args.press_release_id}"):
            with mlflow.start_span(name="ingestion_graph") as span:
                span.set_inputs(state)
                out = app.invoke(state)
                span.set_outputs({
                    "route": out.get("route"),
                    "sector": out.get("sector"),
                    "loop_status": out.get("loop_status"),
                    "hop_count": out.get("hop_count"),
                    "final_events_count": len(out.get("final_events", []) or []),
                    "error": out.get("error"),
                })
    else:
        out = app.invoke(state)

    logger.info("ingestion_graph_done route=%s", out.get("route"))
    compact = {
        "press_release_id": out.get("press_release_id"),
        "ticker": out.get("ticker"),
        "press_release_timestamp": out.get("press_release_timestamp"),
        "route": out.get("route"),
        "sector": out.get("sector"),
        "loop_status": out.get("loop_status"),
        "hop_count": out.get("hop_count"),
        "max_hops": out.get("max_hops"),
        "final_events_count": len(out.get("final_events", []) or []),
        "final_events": out.get("final_events", []),
        "error": out.get("error"),
    }
    print(json.dumps(compact, indent=2))


if __name__ == "__main__":
    main()