"""Graph state definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class GraphState:
    """State used by the LangGraph pipeline.

    This object flows between nodes in the graph. Nodes should treat it as
    immutable and return a new instance when updating fields.
    """

    # Run-level metadata
    run_id: Optional[str] = None
    method_version: str = "v0"
    tickers: List[str] = field(default_factory=list)

    # Current document context
    ticker: Optional[str] = None
    sector: Optional[str] = None
    doc_id: Optional[str] = None
    doc: Optional[Dict[str, Any]] = None

    # Event extraction state
    events_candidate: List[Dict[str, Any]] = field(default_factory=list)
    events_validated: List[Dict[str, Any]] = field(default_factory=list)
    event_ids: List[str] = field(default_factory=list)

    # Control flags
    done: bool = False
    error: Optional[str] = None


INITIAL_STATE = GraphState()

