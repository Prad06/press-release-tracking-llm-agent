"""Linker graph with deterministic retrieval + LLM decision loop."""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from pr_flow_agents.graph.linker import nodes
from pr_flow_agents.graph.linker.state import LinkerState


def build_graph():
    builder = StateGraph(LinkerState)

    builder.add_node("load_silver_events", nodes.load_silver_events)
    builder.add_node("prepare_current_event", nodes.prepare_current_event)
    builder.add_node("retrieve_candidates", nodes.retrieve_candidates)
    builder.add_node("decide_action", nodes.decide_action)
    builder.add_node("refine_decision", nodes.refine_decision)
    builder.add_node("apply_decision", nodes.apply_decision)
    builder.add_node("advance_cursor", nodes.advance_cursor)
    builder.add_node("refresh_scratchpads", nodes.refresh_scratchpads)
    builder.add_node("finalize_output", nodes.finalize_output)

    builder.set_entry_point("load_silver_events")

    def _after_load(state: LinkerState) -> str:
        status = state.get("status")
        if status in {"SKIPPED", "NO_SILVER_EVENTS", "ERROR"}:
            return "finalize_output"
        return "prepare_current_event"

    def _after_prepare(state: LinkerState) -> str:
        cursor = int(state.get("cursor") or 0)
        total = len(state.get("silver_events") or [])
        return "refresh_scratchpads" if cursor >= total else "retrieve_candidates"

    builder.add_conditional_edges(
        "load_silver_events",
        _after_load,
        {
            "prepare_current_event": "prepare_current_event",
            "finalize_output": "finalize_output",
        },
    )
    builder.add_conditional_edges(
        "prepare_current_event",
        _after_prepare,
        {
            "retrieve_candidates": "retrieve_candidates",
            "refresh_scratchpads": "refresh_scratchpads",
        },
    )

    builder.add_edge("retrieve_candidates", "decide_action")
    builder.add_edge("decide_action", "refine_decision")
    builder.add_edge("refine_decision", "apply_decision")
    builder.add_edge("apply_decision", "advance_cursor")
    builder.add_edge("advance_cursor", "prepare_current_event")
    builder.add_edge("refresh_scratchpads", "finalize_output")
    builder.add_edge("finalize_output", END)

    return builder.compile()
