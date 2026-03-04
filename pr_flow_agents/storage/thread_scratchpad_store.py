"""Store for thread scratchpad cache."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

import pymongo

from pr_flow_agents.storage.config import get_database, get_uri
from pr_flow_agents.storage.migrations import run_collection
from pr_flow_agents.storage.models import ThreadScratchpadDocument

COLLECTION = "thread_scratchpads"


class ThreadScratchpadStore:
    def __init__(self, uri: Optional[str] = None, database: Optional[str] = None) -> None:
        self._uri = uri or get_uri()
        self._db = database or get_database()
        self._client: Optional[pymongo.MongoClient] = None

    def _coll(self):
        if self._client is None:
            self._client = pymongo.MongoClient(self._uri)
            run_collection(self._uri, self._db, COLLECTION)
        return self._client[self._db][COLLECTION]

    def get(self, *, ticker: str, thread_id: str) -> Optional[Dict[str, Any]]:
        doc = self._coll().find_one({"ticker": ticker.upper(), "thread_id": thread_id})
        if doc and "_id" in doc:
            doc["_id"] = str(doc["_id"])
        return doc

    def upsert(
        self,
        *,
        ticker: str,
        thread_id: str,
        thread_name: str,
        summary: str,
        latest_linked_event_ids: list[str],
        latest_claims: Optional[list[str]] = None,
    ) -> None:
        model = ThreadScratchpadDocument(
            ticker=ticker.upper(),
            thread_id=thread_id,
            thread_name=thread_name,
            summary=summary,
            latest_linked_event_ids=list(latest_linked_event_ids),
            latest_claims=list(latest_claims or []),
            updated_at=datetime.utcnow(),
        )
        self._coll().update_one(
            {"ticker": model.ticker, "thread_id": model.thread_id},
            {"$set": model.model_dump(mode="json")},
            upsert=True,
        )
