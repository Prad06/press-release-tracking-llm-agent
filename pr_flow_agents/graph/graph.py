"""LangGraph graph definition."""

from __future__ import annotations

from langgraph.graph import StateGraph, END

from .state import GraphState
from . import nodes


def build_app() -> StateGraph:
    """Build the LangGraph application (incremental version).

    Current flow:
      claim_next_doc -> route_sector -> mark_processed -> END

    As we add more nodes, edges will expand into the full loop.
    """

    builder = StateGraph(GraphState)

    builder.add_node("claim_next_doc", nodes.claim_next_doc)
    builder.add_node("route_sector", nodes.route_sector)
    builder.add_node("extract_biotech_events", nodes.extract_biotech_events)
    builder.add_node("extract_aviation_events", nodes.extract_aviation_events)
    builder.add_node("validate_events", nodes.validate_events)
    builder.add_node("write_events", nodes.write_events)
    builder.add_node("update_company_state", nodes.update_company_state)
    builder.add_node("mark_processed", nodes.mark_processed)

    builder.set_entry_point("claim_next_doc")
    builder.add_edge("claim_next_doc", "route_sector")
    builder.add_edge("route_sector", "extract_biotech_events")
    builder.add_edge("extract_biotech_events", "extract_aviation_events")
    builder.add_edge("extract_aviation_events", "validate_events")
    builder.add_edge("validate_events", "write_events")
    builder.add_edge("write_events", "update_company_state")
    builder.add_edge("update_company_state", "mark_processed")
    builder.add_edge("mark_processed", END)

    return builder.compile()


def build_single_doc_app() -> StateGraph:
    """Build a single-document pipeline.

    Assumes GraphState already has:
      - doc_id, doc, ticker
    Flow:
      route_sector -> mark_processed -> END
    """

    builder = StateGraph(GraphState)

    builder.add_node("route_sector", nodes.route_sector)
    builder.add_node("extract_biotech_events", nodes.extract_biotech_events)
    builder.add_node("extract_aviation_events", nodes.extract_aviation_events)
    builder.add_node("validate_events", nodes.validate_events)
    builder.add_node("write_events", nodes.write_events)
    builder.add_node("update_company_state", nodes.update_company_state)
    builder.add_node("mark_processed", nodes.mark_processed)

    builder.set_entry_point("route_sector")
    builder.add_edge("route_sector", "extract_biotech_events")
    builder.add_edge("extract_biotech_events", "extract_aviation_events")
    builder.add_edge("extract_aviation_events", "validate_events")
    builder.add_edge("validate_events", "write_events")
    builder.add_edge("write_events", "update_company_state")
    builder.add_edge("update_company_state", "mark_processed")
    builder.add_edge("mark_processed", END)

    return builder.compile()

