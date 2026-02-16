"""Press releases API."""

import tempfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from api.schemas import PressReleaseIn
from pr_flow_agents.ingestion import run_bulk
from pr_flow_agents.storage import save_crawl_to_mongo, MongoStore
from pr_flow_agents.crawler import crawl_from_link
from pr_flow_agents.models import PressReleaseLink

router = APIRouter(prefix="/press-releases", tags=["press-releases"])


@router.get("")
async def list_press_releases(ticker: str | None = None):
    if not ticker:
        raise HTTPException(400, "ticker required")
    return {"press_releases": MongoStore().list_by_ticker(ticker)}


@router.post("")
async def add_press_release_single(body: PressReleaseIn):
    link = PressReleaseLink(url=body.url, selection_method="ui", all_candidates=[body.url])
    results, _ = await crawl_from_link(link)
    ts = datetime.fromisoformat(body.press_ts.replace("Z", "+00:00"))
    doc_id = save_crawl_to_mongo(results, ticker=body.ticker, title=body.title, press_release_timestamp=ts)
    return {"ok": True, "id": doc_id, "url": body.url}


@router.post("/bulk")
async def add_press_release_bulk(file: UploadFile = File(...)):
    content = (await file.read()).decode("utf-8")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(content)
        path = f.name
    try:
        out = await run_bulk(path, quiet=True)
        return {"ok": True, "results": out}
    finally:
        Path(path).unlink(missing_ok=True)


@router.get("/{id}")
async def get_press_release(id: str):
    doc = MongoStore().get_by_id(id)
    if not doc:
        raise HTTPException(404, "Not found")
    return doc
