"""Store for baseline pipeline summaries."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

import pymongo

from pr_flow_agents.storage.config import get_database, get_uri
from pr_flow_agents.storage.migrations import run_collection
from pr_flow_agents.storage.models import BaselineSummaryDocument

COLLECTION = "baseline_summaries"


class BaselineSummaryStore:
    def __init__(self, uri: Optional[str] = None, database: Optional[str] = None) -> None:
        self._uri = uri or get_uri()
        self._db = database or get_database()
        self._client: Optional[pymongo.MongoClient] = None

    def _coll(self):
        if self._client is None:
            self._client = pymongo.MongoClient(self._uri)
            run_collection(self._uri, self._db, COLLECTION)
        return self._client[self._db][COLLECTION]

    def get_company_summary(self, ticker: str) -> Optional[Dict[str, Any]]:
        doc = self._coll().find_one(
            {
                "ticker": ticker.upper(),
                "scope": "COMPANY",
                "fiscal_year": None,
                "fiscal_quarter": None,
            }
        )
        return _normalize_doc(doc)

    def get_quarterly_summary(self, *, ticker: str, fiscal_year: int, fiscal_quarter: str) -> Optional[Dict[str, Any]]:
        doc = self._coll().find_one(
            {
                "ticker": ticker.upper(),
                "scope": "QUARTERLY",
                "fiscal_year": int(fiscal_year),
                "fiscal_quarter": str(fiscal_quarter).upper(),
            }
        )
        return _normalize_doc(doc)

    def upsert_company_summary(
        self,
        *,
        ticker: str,
        summary_text: str,
        press_release_id: str,
        press_release_timestamp: datetime,
    ) -> Dict[str, Any]:
        return self._upsert_summary(
            ticker=ticker,
            scope="COMPANY",
            fiscal_year=None,
            fiscal_quarter=None,
            summary_text=summary_text,
            press_release_id=press_release_id,
            press_release_timestamp=press_release_timestamp,
        )

    def upsert_quarterly_summary(
        self,
        *,
        ticker: str,
        fiscal_year: int,
        fiscal_quarter: str,
        summary_text: str,
        press_release_id: str,
        press_release_timestamp: datetime,
    ) -> Dict[str, Any]:
        return self._upsert_summary(
            ticker=ticker,
            scope="QUARTERLY",
            fiscal_year=int(fiscal_year),
            fiscal_quarter=str(fiscal_quarter).upper(),
            summary_text=summary_text,
            press_release_id=press_release_id,
            press_release_timestamp=press_release_timestamp,
        )

    def _upsert_summary(
        self,
        *,
        ticker: str,
        scope: str,
        fiscal_year: Optional[int],
        fiscal_quarter: Optional[str],
        summary_text: str,
        press_release_id: str,
        press_release_timestamp: datetime,
    ) -> Dict[str, Any]:
        ticker_u = str(ticker).upper()
        scope_u = str(scope).upper()
        quarter_u = str(fiscal_quarter).upper() if fiscal_quarter else None
        key = {
            "ticker": ticker_u,
            "scope": scope_u,
            "fiscal_year": fiscal_year,
            "fiscal_quarter": quarter_u,
        }
        summary_id = _summary_id(ticker=ticker_u, scope=scope_u, fiscal_year=fiscal_year, fiscal_quarter=quarter_u)
        now = datetime.utcnow()
        existing = self._coll().find_one(key)
        existing_ts = existing.get("last_release_timestamp") if isinstance(existing, dict) else None
        incoming_is_newest = True
        if isinstance(existing_ts, datetime) and existing_ts > press_release_timestamp:
            incoming_is_newest = False

        doc = BaselineSummaryDocument(
            summary_id=summary_id,
            ticker=ticker_u,
            scope=scope_u,
            fiscal_year=fiscal_year,
            fiscal_quarter=quarter_u,
            summary_text=(
                str(summary_text or "").strip()
                if incoming_is_newest
                else str((existing or {}).get("summary_text") or "").strip()
            ),
            last_release_id=(
                str(press_release_id)
                if incoming_is_newest
                else str((existing or {}).get("last_release_id") or "")
            ),
            last_release_timestamp=(
                press_release_timestamp
                if incoming_is_newest
                else existing_ts if isinstance(existing_ts, datetime) else press_release_timestamp
            ),
            source_release_ids=[str(press_release_id)],
            updated_at=now,
        ).model_dump(mode="json")
        doc.pop("created_at", None)
        doc.pop("source_release_ids", None)

        self._coll().update_one(
            key,
            {
                "$set": {
                    **doc,
                    "updated_at": now,
                },
                "$setOnInsert": {
                    "created_at": now,
                },
                "$addToSet": {
                    "source_release_ids": str(press_release_id),
                },
            },
            upsert=True,
        )

        stored = self._coll().find_one(key)
        if not stored:
            raise RuntimeError("baseline_summary_upsert_failed")
        return _normalize_doc(stored) or {}

    def list_by_ticker(self, ticker: str) -> List[Dict[str, Any]]:
        docs = list(self._coll().find({"ticker": ticker.upper()}).sort("updated_at", -1))
        out: List[Dict[str, Any]] = []
        for doc in docs:
            norm = _normalize_doc(doc)
            if norm:
                out.append(norm)
        return out


def _summary_id(*, ticker: str, scope: str, fiscal_year: Optional[int], fiscal_quarter: Optional[str]) -> str:
    if scope == "COMPANY":
        return f"{ticker}:COMPANY"
    year = fiscal_year if fiscal_year is not None else "NA"
    quarter = fiscal_quarter or "NA"
    return f"{ticker}:QUARTERLY:{year}:{quarter}"


def _normalize_doc(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not doc:
        return None
    out = dict(doc)
    if "_id" in out:
        out["_id"] = str(out["_id"])
    return out
