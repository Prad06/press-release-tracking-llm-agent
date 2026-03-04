"""Store for gold linked events."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence

import pymongo

from pr_flow_agents.storage.config import get_database, get_uri
from pr_flow_agents.storage.migrations import run_collection
from pr_flow_agents.storage.models import LinkedEventDocument

COLLECTION = "linked_events"


class LinkedEventStore:
    def __init__(self, uri: Optional[str] = None, database: Optional[str] = None) -> None:
        self._uri = uri or get_uri()
        self._db = database or get_database()
        self._client: Optional[pymongo.MongoClient] = None

    def _coll(self):
        if self._client is None:
            self._client = pymongo.MongoClient(self._uri)
            run_collection(self._uri, self._db, COLLECTION)
        return self._client[self._db][COLLECTION]

    def create(self, doc: LinkedEventDocument) -> str:
        payload = doc.model_dump(mode="json")
        self._coll().insert_one(payload)
        return doc.linked_event_id

    def get(self, linked_event_id: str) -> Optional[Dict[str, Any]]:
        doc = self._coll().find_one({"linked_event_id": linked_event_id})
        if not doc:
            return None
        if "_id" in doc:
            doc["_id"] = str(doc["_id"])
        return doc

    def list_by_ticker(
        self,
        ticker: str,
        *,
        statuses: Optional[Sequence[str]] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        query: Dict[str, Any] = {"ticker": ticker.upper()}
        if statuses:
            query["status"] = {"$in": list(statuses)}
        docs = list(self._coll().find(query).sort("updated_at", -1).limit(int(limit)))
        for doc in docs:
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])
        return docs

    def list_by_thread(
        self,
        *,
        ticker: str,
        thread_id: str,
        statuses: Optional[Sequence[str]] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        query: Dict[str, Any] = {"ticker": ticker.upper(), "thread_id": thread_id}
        if statuses:
            query["status"] = {"$in": list(statuses)}
        docs = list(self._coll().find(query).sort("updated_at", -1).limit(int(limit)))
        for doc in docs:
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])
        return docs

    def list_candidate_pool(
        self,
        *,
        ticker: str,
        statuses: Optional[Sequence[str]] = None,
        event_date: Optional[str] = None,
        days_window: int = 120,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        query: Dict[str, Any] = {"ticker": ticker.upper()}
        if statuses:
            query["status"] = {"$in": list(statuses)}

        # Pre-filter by date range for canonical YYYY-MM-DD event dates.
        dt = _parse_iso_day(event_date)
        if dt is not None:
            start = (dt - timedelta(days=max(1, int(days_window)))).strftime("%Y-%m-%d")
            end = (dt + timedelta(days=max(1, int(days_window)))).strftime("%Y-%m-%d")
            year = dt.year
            query["$or"] = [
                {"event_date": {"$gte": start, "$lte": end}},
                {"event_date": {"$regex": f"^{year}-Q[1-4]$"}},
                {"event_date": str(year)},
            ]

        docs = list(self._coll().find(query).sort("updated_at", -1).limit(int(limit)))
        for doc in docs:
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])
        return docs

    def append_supporting_silver(self, linked_event_id: str, silver_event_id: str) -> bool:
        res = self._coll().update_one(
            {"linked_event_id": linked_event_id},
            {"$addToSet": {"supporting_silver_event_ids": silver_event_id}, "$set": {"updated_at": datetime.utcnow()}},
        )
        return res.matched_count > 0

    def mark_superseded(self, *, old_linked_event_id: str, new_linked_event_id: str) -> bool:
        res = self._coll().update_one(
            {"linked_event_id": old_linked_event_id},
            {"$set": {"status": "SUPERSEDED", "superseded_by": new_linked_event_id, "updated_at": datetime.utcnow()}},
        )
        return res.matched_count > 0

    def mark_retracted(self, linked_event_id: str) -> bool:
        res = self._coll().update_one(
            {"linked_event_id": linked_event_id},
            {"$set": {"status": "RETRACTED", "updated_at": datetime.utcnow()}},
        )
        return res.matched_count > 0


def _parse_iso_day(value: Optional[str]) -> Optional[datetime]:
    raw = str(value or "").strip()
    try:
        if len(raw) == 10:
            return datetime.fromisoformat(raw)
    except Exception:
        return None
    return None
