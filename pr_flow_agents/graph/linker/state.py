"""State model for linker graph."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, TypedDict


LinkerStatus = Literal["PENDING", "DONE", "NO_SILVER_EVENTS", "SKIPPED", "ERROR"]


class LinkerState(TypedDict, total=False):
    # Inputs
    press_release_id: str
    ticker: str
    sector: Optional[str]

    # Loaded silver events
    silver_events: List[Dict[str, Any]]
    cursor: int
    current_silver_event: Dict[str, Any]
    current_silver_event_id: str
    provisional_thread_id: str
    provisional_thread_name: str
    scratchpad_text: str
    candidates: List[Dict[str, Any]]
    decision: Dict[str, Any]
    applied: Dict[str, Any]

    # Aggregates
    decisions: List[Dict[str, Any]]
    impacted_threads: Dict[str, str]
    linked_events_created: int
    linked_events_duplicates: int
    linked_events_updated: int
    linked_events_retracted: int

    # Final summary
    status: LinkerStatus
    result: Dict[str, Any]
    error: Optional[str]
