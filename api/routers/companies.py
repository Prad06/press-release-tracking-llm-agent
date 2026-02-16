"""Companies API."""

import csv
from io import StringIO

from fastapi import APIRouter, File, HTTPException, UploadFile

from api.schemas import CompanyIn
from pr_flow_agents.storage import add_company, CompanyStore

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("")
async def list_companies():
    return {"companies": CompanyStore().list_all()}


@router.post("")
async def add_company_single(body: CompanyIn):
    add_company(body.ticker, body.name, body.sector)
    return {"ok": True, "ticker": body.ticker}


@router.post("/bulk")
async def add_company_bulk(file: UploadFile = File(...)):
    content = (await file.read()).decode("utf-8")
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
