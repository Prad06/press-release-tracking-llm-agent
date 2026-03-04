"""Ingestion graph with Stage 2 iterative expert-hop loop (k=2 default)."""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from pr_flow_agents.graph.ingestion import nodes
from pr_flow_agents.graph.ingestion.state import IngestionState


def build_graph():
    builder = StateGraph(IngestionState)

    builder.add_node("load_press_release", nodes.load_press_release)
    builder.add_node("route_sector", nodes.route_sector)
    builder.add_node("configure_biotech_agent", nodes.configure_biotech_agent)
    builder.add_node("configure_aviation_agent", nodes.configure_aviation_agent)
    builder.add_node("configure_experts", nodes.configure_experts)
    builder.add_node("configure_unsupported", nodes.configure_unsupported)

    builder.add_node("run_extractor", nodes.run_extractor)
    builder.add_node("validate_events", nodes.validate_events)
    builder.add_node("run_expert_review", nodes.run_expert_review)
    builder.add_node("revise_extraction", nodes.revise_extraction)
    builder.add_node("finalize_output", nodes.finalize_output)

    builder.set_entry_point("load_press_release")

    def _route_after_load(state: IngestionState) -> str:
        return "configure_unsupported" if state.get("error") else "route_sector"

    def _route_after_sector(state: IngestionState) -> str:
        route = state.get("route")
        if route == "biotech":
            return "configure_biotech_agent"
        if route == "aviation":
            return "configure_aviation_agent"
        return "configure_unsupported"

    def _route_after_review(state: IngestionState) -> str:
        status = state.get("loop_status")
        if status in {"ACCEPT", "NO_CHANGE", "MAX_HOPS", "ERROR"}:
            return "finalize_output"
        return "revise_extraction"

    builder.add_conditional_edges(
        "load_press_release",
        _route_after_load,
        {
            "route_sector": "route_sector",
            "configure_unsupported": "configure_unsupported",
        },
    )

    builder.add_conditional_edges(
        "route_sector",
        _route_after_sector,
        {
            "configure_biotech_agent": "configure_biotech_agent",
            "configure_aviation_agent": "configure_aviation_agent",
            "configure_unsupported": "configure_unsupported",
        },
    )

    builder.add_edge("configure_biotech_agent", "configure_experts")
    builder.add_edge("configure_aviation_agent", "configure_experts")
    builder.add_edge("configure_experts", "run_extractor")

    builder.add_edge("run_extractor", "validate_events")
    builder.add_edge("validate_events", "run_expert_review")

    builder.add_conditional_edges(
        "run_expert_review",
        _route_after_review,
        {
            "revise_extraction": "revise_extraction",
            "finalize_output": "finalize_output",
        },
    )

    builder.add_edge("revise_extraction", "run_extractor")

    builder.add_edge("configure_unsupported", "finalize_output")
    builder.add_edge("finalize_output", END)

    return builder.compile()
