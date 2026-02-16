"""Ingestion store (PART 0). Uses central config and migrations."""

from datetime import datetime
from typing import Any, Dict, Optional

import pymongo

from pr_flow_agents.storage.config import get_database, get_uri
from pr_flow_agents.storage.migrations import run_collection
from pr_flow_agents.storage.models import StoredCrawlDocument

COLLECTION = "crawl_results"


class MongoStore:
    def __init__(self, uri: Optional[str] = None, database: Optional[str] = None) -> None:
        self._uri = uri or get_uri()
        self._db = database or get_database()
        self._client: Optional[pymongo.MongoClient] = None

    def save(
        self,
        raw_result: Dict[str, Any],
        ticker: str,
        title: str,
        press_release_timestamp: datetime,
        source_url: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        if self._client is None:
            self._client = pymongo.MongoClient(self._uri)
            run_collection(self._uri, self._db, COLLECTION)
        doc = StoredCrawlDocument(
            ticker=ticker,
            title=title,
            press_release_timestamp=press_release_timestamp,
            source_url=source_url,
            crawl_timestamp=raw_result.get("timestamp", datetime.now().isoformat()),
            raw_result=raw_result,
            metadata=metadata or {},
            unprocessed=True,
        )
        inserted = self._client[self._db][COLLECTION].insert_one(
            doc.model_dump(mode="json")
        )
        return str(inserted.inserted_id)

    def list_by_ticker(self, ticker: str) -> list:
        if self._client is None:
            self._client = pymongo.MongoClient(self._uri)
            run_collection(self._uri, self._db, COLLECTION)
        docs = list(
            self._client[self._db][COLLECTION]
            .find({"ticker": ticker.upper()}, {"raw_result": 0})
            .sort("press_release_timestamp", -1)
        )
        for d in docs:
            if "_id" in d:
                d["_id"] = str(d["_id"])
        return docs

    def get_by_id(self, id: str):
        from bson import ObjectId
        try:
            oid = ObjectId(id)
        except Exception:
            return None
        if self._client is None:
            self._client = pymongo.MongoClient(self._uri)
        doc = self._client[self._db][COLLECTION].find_one({"_id": oid})
        if doc and "_id" in doc:
            doc["_id"] = str(doc["_id"])
        return doc


def save_crawl_to_mongo(
    crawl_results: Any,
    ticker: str,
    title: str,
    press_release_timestamp: datetime,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    raw = (
        crawl_results.model_dump()
        if hasattr(crawl_results, "model_dump")
        else dict(crawl_results)
    )
    return MongoStore().save(
        raw_result=raw,
        ticker=ticker,
        title=title,
        press_release_timestamp=press_release_timestamp,
        source_url=raw.get("source_url", ""),
        metadata=metadata,
    )
