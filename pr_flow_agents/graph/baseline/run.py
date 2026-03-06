"""CLI runner for baseline graph."""

from __future__ import annotations

import argparse
import json
import os

from pr_flow_agents.graph.baseline.graph import build_graph
from pr_flow_agents.graph.baseline.state import BaselineState
from pr_flow_agents.logging_utils import configure_logging, get_logger

logger = get_logger(__name__)
MLFLOW_EXPERIMENT = "baseline_flow"


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run baseline summary graph")
    p.add_argument("--press-release-id", required=True, help="MongoDB _id from crawl_results")
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

    state: BaselineState = {"press_release_id": args.press_release_id}
    logger.info("baseline_graph_start press_release_id=%s", args.press_release_id)
    app = build_graph()

    if mlflow is not None:
        with mlflow.start_run(run_name=f"baseline_{args.press_release_id}"):
            with mlflow.start_span(name="baseline_graph") as span:
                span.set_inputs(state)
                out = app.invoke(state)
                span.set_outputs(out.get("result") or {})
    else:
        out = app.invoke(state)

    logger.info("baseline_graph_done press_release_id=%s", args.press_release_id)
    print(json.dumps(out.get("result") or {}, indent=2))


if __name__ == "__main__":
    main()
