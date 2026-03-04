"""Minimal state definition for starter LangGraph."""

from __future__ import annotations

from typing import TypedDict


class GraphState(TypedDict, total=False):
    """Starter graph state."""

    run_id: str
    step: str
