"""Store for events extracted by ingestion orchestrator."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

import pymongo

from pr_flow_agents.storage.config import get_database, get_uri
from pr_flow_agents.storage.migrations import run_collection
from pr_flow_agents.storage.models import ExtractedEventDocument

COLLECTION = "extracted_events"


class ExtractedEventStore:
    def __init__(self, uri: Optional[str] = None, database: Optional[str] = None) -> None:
        self._uri = uri or get_uri()
        self._db = database or get_database()
        self._client: Optional[pymongo.MongoClient] = None

    def _coll(self):
        if self._client is None:
            self._client = pymongo.MongoClient(self._uri)
            run_collection(self._uri, self._db, COLLECTION)
        return self._client[self._db][COLLECTION]

    def replace_for_release(
        self,
        *,
        press_release_id: str,
        company_ticker: str,
        company_id: Optional[str],
        release_title: str,
        press_release_timestamp: datetime,
        fiscal_year: int,
        fiscal_quarter: str,
        events: List[Dict[str, Any]],
    ) -> int:
        coll = self._coll()
        coll.delete_many({"press_release_id": press_release_id})

        docs: List[Dict[str, Any]] = []
        for idx, event in enumerate(events):
            if not isinstance(event, dict):
                continue
            model = ExtractedEventDocument(
                press_release_id=press_release_id,
                company_ticker=company_ticker.upper(),
                company_id=company_id,
                release_title=release_title,
                press_release_timestamp=press_release_timestamp,
                fiscal_year=fiscal_year,
                fiscal_quarter=fiscal_quarter,
                event_index=idx,
                event_type=str(event.get("event_type") or ""),
                event_date=str(event.get("event_date")) if event.get("event_date") is not None else None,
                claim=str(event.get("claim") or ""),
                entities=[str(x) for x in (event.get("entities") or []) if str(x).strip()],
                numbers=[str(x) for x in (event.get("numbers") or []) if str(x).strip()],
                evidence_span=str(event.get("evidence_span") or ""),
                confidence=str(event.get("confidence")) if event.get("confidence") is not None else None,
                event_payload=event,
            )
            docs.append(model.model_dump(mode="json"))

        if not docs:
            return 0

        coll.insert_many(docs)
        return len(docs)

    def list_by_release(self, press_release_id: str) -> List[Dict[str, Any]]:
        docs = list(self._coll().find({"press_release_id": press_release_id}).sort("event_index", 1))
        for d in docs:
            if "_id" in d:
                d["_id"] = str(d["_id"])
        return docs
