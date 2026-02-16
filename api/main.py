"""FastAPI app. Ingestion endpoints."""

from contextlib import asynccontextmanager
from io import StringIO
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pr_flow_agents.ingestion import run_bulk
from pr_flow_agents.storage import add_company, save_crawl_to_mongo, CompanyStore, MongoStore
from pr_flow_agents.crawler import crawl_from_link
from pr_flow_agents.models import PressReleaseLink
from datetime import datetime


class CompanyIn(BaseModel):
    ticker: str
    name: str
    sector: str | None = None


class PressReleaseIn(BaseModel):
    url: str
    ticker: str
    title: str
    press_ts: str  # ISO format required


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/companies")
async def list_companies():
    return {"companies": CompanyStore().list_all()}


@app.post("/companies")
async def add_company_single(body: CompanyIn):
    add_company(body.ticker, body.name, body.sector)
    return {"ok": True, "ticker": body.ticker}


@app.post("/companies/bulk")
async def add_company_bulk(file: UploadFile = File(...)):
    content = (await file.read()).decode("utf-8")
    import csv
    reader = csv.DictReader(StringIO(content))
    keys = {k.strip().lower(): k for k in (reader.fieldnames or [])}
    tk = keys.get("ticker") or keys.get("symbol")
    nm = keys.get("name") or keys.get("company")
    sc = keys.get("sector")
    if not tk or not nm:
        raise HTTPException(400, "CSV needs ticker and name columns")
    added = []
    for row in reader:
        t, n = (row.get(tk) or "").strip(), (row.get(nm) or "").strip()
        s = (row.get(sc) or "").strip() if sc else None
        if t and n:
            add_company(t, n, s)
            added.append({"ticker": t, "name": n})
    return {"ok": True, "added": added}


@app.get("/press-releases")
async def list_press_releases(ticker: str | None = None):
    if not ticker:
        raise HTTPException(400, "ticker required")
    return {"press_releases": MongoStore().list_by_ticker(ticker)}


@app.get("/press-releases/{id}")
async def get_press_release(id: str):
    doc = MongoStore().get_by_id(id)
    if not doc:
        raise HTTPException(404, "Not found")
    return doc


@app.post("/press-releases")
async def add_press_release_single(body: PressReleaseIn):
    link = PressReleaseLink(url=body.url, selection_method="ui", all_candidates=[body.url])
    results, _ = await crawl_from_link(link)
    ts = datetime.fromisoformat(body.press_ts.replace("Z", "+00:00"))
    doc_id = save_crawl_to_mongo(results, ticker=body.ticker, title=body.title, press_release_timestamp=ts)
    return {"ok": True, "id": doc_id, "url": body.url}


@app.post("/press-releases/bulk")
async def add_press_release_bulk(file: UploadFile = File(...)):
    content = (await file.read()).decode("utf-8")
    import tempfile
    import csv
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(content)
        path = f.name
    try:
        out = await run_bulk(path, quiet=True)
        return {"ok": True, "results": out}
    finally:
        Path(path).unlink(missing_ok=True)
