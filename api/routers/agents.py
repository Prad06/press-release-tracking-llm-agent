"""Agent pipeline endpoints (LangGraph)."""

from __future__ import annotations

import uuid
from dataclasses import asdict
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from pr_flow_agents.storage import MongoStore
from pr_flow_agents.graph.graph import build_single_doc_app
from pr_flow_agents.graph.state import GraphState


class RunSingleBody(BaseModel):
    doc_id: str
    method_version: str = "v0"


router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("/run-single")
async def run_single(body: RunSingleBody) -> Dict[str, Any]:
    """Run the single-document agent pipeline for a specific crawl_results doc."""

    doc = MongoStore().get_by_id(body.doc_id)
    if not doc:
        raise HTTPException(404, "crawl_results doc not found")

    app = build_single_doc_app()
    run_id = str(uuid.uuid4())

    state = GraphState(
        run_id=run_id,
        method_version=body.method_version,
        tickers=[doc.get("ticker", "").upper()],
        ticker=doc.get("ticker"),
        doc_id=body.doc_id,
        doc=doc,
    )

    final_state = app.invoke(state)

    return {
        "ok": final_state.error is None,
        "run_id": run_id,
        "method_version": final_state.method_version,
        "doc_id": final_state.doc_id,
        "ticker": final_state.ticker,
        "sector": final_state.sector,
        "event_ids": final_state.event_ids,
        "error": final_state.error,
    }

