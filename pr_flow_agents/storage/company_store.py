"""Company store. Reusable by CLI and API."""

from typing import Any, Dict, List, Optional

import pymongo

from pr_flow_agents.storage.config import get_database, get_uri
from pr_flow_agents.storage.migrations import run_collection
from pr_flow_agents.storage.models import Company

COLLECTION = "companies"


class CompanyStore:
    def __init__(self, uri: Optional[str] = None, database: Optional[str] = None) -> None:
        self._uri = uri or get_uri()
        self._db = database or get_database()
        self._client: Optional[pymongo.MongoClient] = None

    def _coll(self):
        if self._client is None:
            self._client = pymongo.MongoClient(self._uri)
            run_collection(self._uri, self._db, COLLECTION)
        return self._client[self._db][COLLECTION]

    def add(self, ticker: str, name: str, sector: Optional[str] = None, **metadata: Any) -> str:
        doc = Company(ticker=ticker.upper(), name=name, sector=sector, metadata=dict(metadata))
        r = self._coll().update_one(
            {"ticker": doc.ticker},
            {"$set": doc.model_dump(mode="json")},
            upsert=True,
        )
        return doc.ticker

    def get(self, ticker: str) -> Optional[Dict[str, Any]]:
        doc = self._coll().find_one({"ticker": ticker.upper()})
        if doc and "_id" in doc:
            doc["_id"] = str(doc["_id"])
        return doc

    def list_all(self) -> List[Dict[str, Any]]:
        docs = list(self._coll().find({}))
        for d in docs:
            if "_id" in d:
                d["_id"] = str(d["_id"])
        return docs


def add_company(ticker: str, name: str, sector: Optional[str] = None, **metadata: Any) -> str:
    return CompanyStore().add(ticker, name, sector, **metadata)
