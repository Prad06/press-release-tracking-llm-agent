"""Starter graph builder."""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from pr_flow_agents.graph import nodes
from pr_flow_agents.graph.state import GraphState


def build_graph():
    builder = StateGraph(GraphState)

    builder.add_node("starter_node", nodes.starter_node)
    builder.set_entry_point("starter_node")
    builder.add_edge("starter_node", END)

    return builder.compile()
