"""State for ingestion graph with iterative expert-hop review."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, TypedDict


SectorRoute = Literal["biotech", "aviation", "unsupported"]
LoopStatus = Literal["PENDING", "REVISE", "ACCEPT", "NO_CHANGE", "MAX_HOPS", "ERROR"]


class PressReleaseDocument(TypedDict, total=False):
    """Subset of crawl_results fields aligned to StoredCrawlDocument."""

    _id: str
    ticker: str
    title: str
    press_release_timestamp: str
    source_url: str
    crawl_timestamp: str
    raw_result: Dict[str, Any]
    metadata: Dict[str, Any]


class IngestionState(TypedDict, total=False):
    # Input payload
    press_release_id: str

    # Loaded from crawl_results
    press_release: PressReleaseDocument
    ticker: str
    press_release_timestamp: str
    press_release_content: str

    # Routing outputs
    sector: Optional[str]
    route: SectorRoute

    # Agent selection
    agent_name: str
    system_prompt: str
    agent_config: Dict[str, Any]
    experts: List[str]

    # Stage 2 loop fields
    hop_count: int
    max_hops: int
    candidate_events: List[Dict[str, Any]]
    expert_feedback: Dict[str, Any]
    validated_events: List[Dict[str, Any]]
    loop_status: LoopStatus
    review_trace: List[Dict[str, Any]]

    # Final output
    final_events: List[Dict[str, Any]]

    # Generic diagnostics
    error: Optional[str]
