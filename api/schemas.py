"""Request/response schemas."""

from pydantic import BaseModel


class CompanyIn(BaseModel):
    ticker: str
    name: str
    sector: str | None = None


class PressReleaseIn(BaseModel):
    url: str
    ticker: str
    title: str
    press_ts: str  # ISO format required
