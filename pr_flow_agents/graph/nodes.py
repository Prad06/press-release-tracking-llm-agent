"""Starter LangGraph nodes."""

from __future__ import annotations

from pr_flow_agents.graph.state import GraphState
from pr_flow_agents.logging_utils import get_logger

logger = get_logger(__name__)


def starter_node(state: GraphState) -> GraphState:
    """No-op starter node for graph wiring."""

    logger.debug("starter_node_run run_id=%s", state.get("run_id"))
    return {**state, "step": "starter_node_done"}
