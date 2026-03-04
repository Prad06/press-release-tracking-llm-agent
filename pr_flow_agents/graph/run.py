"""CLI entrypoint: python -m pr_flow_agents.graph.run"""

from __future__ import annotations

import argparse
import uuid

from pr_flow_agents.graph.graph import build_graph
from pr_flow_agents.graph.state import GraphState
from pr_flow_agents.logging_utils import configure_logging, get_logger

logger = get_logger(__name__)


def _args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run starter LangGraph")
    return p.parse_args()


def main() -> None:
    configure_logging()
    _ = _args()
    run_id = str(uuid.uuid4())
    app = build_graph()
    state: GraphState = {"run_id": run_id}
    logger.info("graph_run_start run_id=%s", run_id)
    final_state = app.invoke(state)
    logger.info("graph_run_done run_id=%s final_state=%s", run_id, final_state)


if __name__ == "__main__":
    main()
