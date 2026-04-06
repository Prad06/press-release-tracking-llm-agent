#!/usr/bin/env python3
"""
Ingest QA final set JSONs into MongoDB.

Usage:
  python scripts/ingest_qa_set.py
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QA_DIR = ROOT / "data" / "qa_final_set"


def _load_env():
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")


def main():
    _load_env()
    import pymongo
    from pr_flow_agents.storage.config import get_database, get_uri

    client = pymongo.MongoClient(get_uri())
    db = client[get_database()]
    coll = db["qa_set"]

    # Drop and re-insert for idempotency
    coll.drop()

    total = 0
    for ticker_file in sorted(QA_DIR.glob("*.json")):
        ticker = ticker_file.stem
        questions = json.loads(ticker_file.read_text())
        for q in questions:
            q["ticker"] = ticker
        result = coll.insert_many(questions)
        print(f"  {ticker}: inserted {len(result.inserted_ids)} questions")
        total += len(result.inserted_ids)

    coll.create_index("ticker")
    coll.create_index("category")
    print(f"\nTotal: {total} questions across {len(list(QA_DIR.glob('*.json')))} companies")
    print("Collection: qa_set")


if __name__ == "__main__":
    main()
