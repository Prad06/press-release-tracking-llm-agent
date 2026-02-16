"""MongoDB document models."""

from datetime import datetime
from typing import Any, Dict, Optional

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
    unprocessed: bool = Field(default=True, description="Not yet processed by agents")

    model_config = ConfigDict(from_attributes=True)
