"""Integration tests for ingestion step-1 routing by press_release_id."""

from __future__ import annotations

from pathlib import Path
import os

import pytest
from dotenv import load_dotenv

from pr_flow_agents.graph.ingestion.graph import build_graph


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_MONGO_INTEGRATION") != "1",
    reason="Set RUN_MONGO_INTEGRATION=1 to run Mongo-backed routing tests.",
)

EXPECTED_EXPERTS = [
    "Financial Impact",
    "Operational Change",
    "Product/Program",
    "Partnerships",
    "Strategic Direction",
    "Regulatory",
]


@pytest.fixture(scope="module")
def app():
    return build_graph()


def test_biotech_route(app) -> None:
    out = app.invoke({"press_release_id": "6993932b4ff7f27eb4bd620f"})
    assert out.get("route") == "biotech"
    assert out.get("agent_name") == "sector_event_extractor"
    assert out.get("experts") == EXPECTED_EXPERTS
    assert out.get("error") is None


def test_aviation_route(app) -> None:
    out = app.invoke({"press_release_id": "6993bdc94344825951c00605"})
    assert out.get("route") == "aviation"
    assert out.get("agent_name") == "sector_event_extractor"
    assert out.get("experts") == EXPECTED_EXPERTS
    assert out.get("error") is None


def test_invalid_id_goes_to_error_path(app) -> None:
    out = app.invoke({"press_release_id": "000x000"})
    assert out.get("route") == "unsupported"
    assert out.get("agent_name") == "unsupported"
    assert out.get("experts") == []
    assert "not found" in str(out.get("error", "")).lower()
