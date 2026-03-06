"""Orchestrator for baseline summary pipeline."""

from __future__ import annotations

import argparse
from contextlib import nullcontext
import json
import os
from typing import Any, Dict

from pr_flow_agents.graph.baseline.graph import build_graph
from pr_flow_agents.graph.baseline.state import BaselineState
from pr_flow_agents.logging_utils import configure_logging, get_logger

logger = get_logger(__name__)
MLFLOW_EXPERIMENT = "baseline_flow"


class BaselineSummaryOrchestrator:
    """Runs the baseline summary graph for one press release."""

    def __init__(self) -> None:
        self._app = build_graph()

    def run(self, *, press_release_id: str) -> Dict[str, Any]:
        logger.info("baseline_orchestrator_start press_release_id=%s", press_release_id)

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
            run_ctx = mlflow.start_run(run_name=f"baseline_orchestrator_{press_release_id}")

        state: BaselineState = {"press_release_id": press_release_id}
        with run_ctx:
            if mlflow is not None:
                with mlflow.start_span(name="baseline_orchestrator") as root_span:
                    root_span.set_inputs(state)
                    with mlflow.start_span(name="baseline_graph"):
                        out = self._app.invoke(state)
                    result = out.get("result") or {}
                    root_span.set_outputs(result)
            else:
                out = self._app.invoke(state)
                result = out.get("result") or {}

            if mlflow is not None:
                mlflow.log_param("baseline_orchestrator_press_release_id", press_release_id)
                mlflow.log_param("baseline_orchestrator_status", str(result.get("status") or ""))
                mlflow.log_metric("baseline_orchestrator_has_error", 1.0 if result.get("error") else 0.0)

        logger.info(
            "baseline_orchestrator_done press_release_id=%s status=%s",
            press_release_id,
            result.get("status"),
        )
        return result


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run baseline summary orchestration")
    p.add_argument("--press-release-id", required=True, help="MongoDB _id from crawl_results")
    return p.parse_args()


def main() -> None:
    configure_logging()
    args = _parse_args()
    orchestrator = BaselineSummaryOrchestrator()
    out = orchestrator.run(press_release_id=args.press_release_id)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
