"""State model for baseline summary graph."""

from __future__ import annotations

from typing import Any, Dict, Literal, Optional, TypedDict


BaselineStatus = Literal["PENDING", "DONE", "ERROR"]


class BaselineState(TypedDict, total=False):
    # Inputs
    press_release_id: str

    # Loaded source data
    ticker: str
    press_release_title: str
    press_release_timestamp: str
    press_release_content: str

    # Derived fiscal context
    fiscal_year: int
    fiscal_quarter: str

    # Existing summaries
    existing_company_summary: str
    existing_quarterly_summary: str

    # Updated summaries
    company_summary: str
    quarterly_summary: str
    change_notes: str

    # Persist outputs
    company_summary_doc: Dict[str, Any]
    quarterly_summary_doc: Dict[str, Any]

    # RAG ingestion outputs
    rag_ingestion_status: str
    rag_chunk_count: int
    rag_ingestion_error: Optional[str]

    # Final
    status: BaselineStatus
    result: Dict[str, Any]
    error: Optional[str]
