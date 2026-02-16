from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PressReleaseLink(BaseModel):
    url: str
    selection_method: str
    all_candidates: List[str]
    score: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class WebLink(BaseModel):
    url: str
    text: str = ""
    title: str = ""
    link_type: str = ""

    model_config = ConfigDict(from_attributes=True)


class CrawlResults(BaseModel):
    source_url: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    markdown_content: str = ""
    main_content: str = ""
    all_links: List[WebLink] = Field(default_factory=list)
    pdf_links_by_url: List[WebLink] = Field(default_factory=list)
    pdf_links_by_text: List[WebLink] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
