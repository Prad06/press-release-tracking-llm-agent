"""Baseline graph for maintaining company and quarterly summaries."""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from pr_flow_agents.graph.baseline import nodes
from pr_flow_agents.graph.baseline.state import BaselineState


def build_graph():
    builder = StateGraph(BaselineState)

    builder.add_node("load_press_release", nodes.load_press_release)
    builder.add_node("derive_fiscal_context", nodes.derive_fiscal_context)
    builder.add_node("load_existing_summaries", nodes.load_existing_summaries)
    builder.add_node("update_summaries", nodes.update_summaries)
    builder.add_node("persist_summaries", nodes.persist_summaries)
    builder.add_node("finalize_output", nodes.finalize_output)

    builder.set_entry_point("load_press_release")

    def _after_load(state: BaselineState) -> str:
        return "finalize_output" if state.get("error") else "derive_fiscal_context"

    def _after_fiscal(state: BaselineState) -> str:
        return "finalize_output" if state.get("error") else "load_existing_summaries"

    def _after_update(state: BaselineState) -> str:
        return "finalize_output" if state.get("error") else "persist_summaries"

    builder.add_conditional_edges(
        "load_press_release",
        _after_load,
        {
            "derive_fiscal_context": "derive_fiscal_context",
            "finalize_output": "finalize_output",
        },
    )
    builder.add_conditional_edges(
        "derive_fiscal_context",
        _after_fiscal,
        {
            "load_existing_summaries": "load_existing_summaries",
            "finalize_output": "finalize_output",
        },
    )
    builder.add_edge("load_existing_summaries", "update_summaries")
    builder.add_conditional_edges(
        "update_summaries",
        _after_update,
        {
            "persist_summaries": "persist_summaries",
            "finalize_output": "finalize_output",
        },
    )
    builder.add_edge("persist_summaries", "finalize_output")
    builder.add_edge("finalize_output", END)

    return builder.compile()
