"""MongoDB document models."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class Company(BaseModel):
    ticker: str
    name: str
    sector: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class StoredCrawlDocument(BaseModel):
    """
    Document shape for persisting a crawl result to MongoDB.
    Used for validation before insert; MongoDB stores as BSON.
    """

    ticker: str = Field(..., description="Stock ticker symbol of the company")
    title: str = Field(..., description="Title of the press release")
    press_release_timestamp: datetime = Field(
        ...,
        description="Publication/effective timestamp of the press release",
    )
    source_url: str = Field(..., description="URL that was crawled")
    crawl_timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="When the crawl was performed",
    )
    raw_result: Dict[str, Any] = Field(
        default_factory=dict,
        description="Full CrawlResults as dict (source_url, markdown_content, all_links, etc.)",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Optional extra fields (e.g. selection_method, score)",
    )

    model_config = ConfigDict(from_attributes=True)


class ExtractedEventDocument(BaseModel):
    """Document shape for persisted events produced by ingestion graph."""

    press_release_id: str = Field(..., description="Mongo _id of source crawl_results document")
    company_ticker: str = Field(..., description="Ticker of source company")
    company_id: Optional[str] = Field(default=None, description="Mongo _id of company document if known")
    release_title: str = Field(..., description="Title of source press release")
    press_release_timestamp: datetime = Field(..., description="Timestamp of source press release")
    fiscal_year: int = Field(..., description="Derived fiscal year from press_release_timestamp")
    fiscal_quarter: str = Field(..., description="Derived fiscal quarter from press_release_timestamp, e.g. Q1")
    event_index: int = Field(..., description="0-based event index within one release")
    event_type: str = Field(..., description="Event category")
    event_date: Optional[str] = Field(default=None, description="Event date string as extracted")
    claim: str = Field(..., description="Short event claim")
    entities: List[str] = Field(default_factory=list, description="Named entities in event")
    numbers: List[str] = Field(default_factory=list, description="Numeric strings in event evidence")
    evidence_span: str = Field(default="", description="Verbatim evidence text")
    confidence: Optional[str] = Field(default=None, description="Model confidence label")
    event_payload: Dict[str, Any] = Field(default_factory=dict, description="Full extracted event payload")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Persist timestamp")

    model_config = ConfigDict(from_attributes=True)
