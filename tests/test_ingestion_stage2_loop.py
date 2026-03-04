"""Unit tests for Stage 2 extraction/review loop control and validation."""

from __future__ import annotations

import copy

import pytest

from pr_flow_agents.graph.ingestion import nodes
from pr_flow_agents.graph.ingestion.graph import build_graph


@pytest.fixture()
def base_state() -> dict:
    return {
        "press_release_id": "stub-id",
        "press_release": {
            "_id": "stub-id",
            "ticker": "BEAM",
            "title": "Stub",
            "press_release_timestamp": "2026-03-04T10:00:00Z",
            "source_url": "https://example.com",
            "crawl_timestamp": "2026-03-04T10:05:00Z",
            "raw_result": {
                "markdown_content": "Revenue increased 10% in 2026.",
                "main_content": "Revenue increased 10% in 2026.",
            },
            "metadata": {},
        },
        "ticker": "BEAM",
        "press_release_timestamp": "2026-03-04T10:00:00Z",
        "press_release_content": "Revenue increased 10% in 2026.",
        "route": "biotech",
        "sector": "biotech",
        "system_prompt": "stub",
        "agent_name": "sector_event_extractor",
        "agent_config": {"sector": "biotech"},
        "experts": list(nodes.EXPERTS),
        "hop_count": 0,
        "max_hops": 2,
        "candidate_events": [],
        "expert_feedback": {},
        "validated_events": [],
        "loop_status": "PENDING",
        "review_trace": [],
        "final_events": [],
        "error": None,
    }


def _patch_common(monkeypatch: pytest.MonkeyPatch, state: dict) -> None:
    monkeypatch.setattr(nodes, "load_press_release", lambda s: copy.deepcopy(state))
    monkeypatch.setattr(nodes, "route_sector", lambda s: s)
    monkeypatch.setattr(nodes, "configure_biotech_agent", lambda s: s)
    monkeypatch.setattr(nodes, "configure_aviation_agent", lambda s: s)
    monkeypatch.setattr(nodes, "configure_experts", lambda s: s)


def test_hop_stops_early_on_accept(monkeypatch: pytest.MonkeyPatch, base_state: dict) -> None:
    _patch_common(monkeypatch, base_state)

    calls = {"extract": 0, "review": 0}

    def fake_generate_json(prompt: str):
        if "EXTRACT_EVENTS_JSON" in prompt:
            calls["extract"] += 1
            return [
                {
                    "event_type": "financial",
                    "event_date": "2026-03-04",
                    "claim": "Revenue increased.",
                    "entities": ["BEAM"],
                    "numbers": ["10%"],
                    "evidence_span": "Revenue increased 10% in 2026.",
                }
            ]
        if "VALIDATE_EVENTS_JSON" in prompt:
            return {
                "validated_events": [
                    {
                        "event_type": "financial",
                        "event_date": "2026-03-04",
                        "claim": "Revenue increased.",
                        "entities": ["BEAM"],
                        "numbers": ["10%"],
                        "evidence_span": "Revenue increased 10% in 2026.",
                    }
                ],
                "drops": [],
            }
        if "EXPERT_REVIEW_JSON" in prompt:
            calls["review"] += 1
            return {
                "decision": "ACCEPT",
                "summary": "Looks good",
                "issues": [],
                "suggestions": [],
            }
        return {}

    monkeypatch.setattr(nodes, "generate_json", fake_generate_json)

    app = build_graph()
    out = app.invoke({"press_release_id": "stub-id"})

    assert out.get("loop_status") == "ACCEPT"
    assert out.get("hop_count") == 1
    assert len(out.get("final_events", [])) == 1
    assert calls["extract"] == 1
    assert calls["review"] == len(nodes.EXPERTS)


def test_hop_stops_at_max_hops(monkeypatch: pytest.MonkeyPatch, base_state: dict) -> None:
    _patch_common(monkeypatch, base_state)

    calls = {"extract": 0, "review": 0}

    def fake_generate_json(prompt: str):
        if "EXTRACT_EVENTS_JSON" in prompt:
            calls["extract"] += 1
            return [
                {
                    "event_type": "financial",
                    "event_date": "2026-03-04",
                    "claim": "Revenue increased.",
                    "entities": ["BEAM"],
                    "numbers": ["10%"],
                    "evidence_span": "Revenue increased 10% in 2026.",
                }
            ]
        if "VALIDATE_EVENTS_JSON" in prompt:
            return {
                "validated_events": [
                    {
                        "event_type": "financial",
                        "event_date": "2026-03-04",
                        "claim": "Revenue increased.",
                        "entities": ["BEAM"],
                        "numbers": ["10%"],
                        "evidence_span": "Revenue increased 10% in 2026.",
                    }
                ],
                "drops": [],
            }
        if "EXPERT_REVIEW_JSON" in prompt:
            calls["review"] += 1
            return {
                "decision": "REVISE",
                "summary": "Needs work",
                "issues": ["refine claim"],
                "suggestions": [{"action": "UPDATE", "target": "claim", "note": "be specific"}],
            }
        return {}

    monkeypatch.setattr(nodes, "generate_json", fake_generate_json)

    app = build_graph()
    out = app.invoke({"press_release_id": "stub-id"})

    assert out.get("loop_status") == "MAX_HOPS"
    assert out.get("hop_count") == 2
    assert calls["extract"] == 2
    assert calls["review"] == 2 * len(nodes.EXPERTS)


def test_invalid_evidence_spans_are_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_generate_json(prompt: str):
        if "VALIDATE_EVENTS_JSON" in prompt:
            return {
                "validated_events": [
                    {
                        "event_type": "financial",
                        "event_date": "2026-03-04",
                        "claim": "Revenue increased.",
                        "entities": ["BEAM"],
                        "numbers": ["10%"],
                        "evidence_span": "Revenue increased 10% in 2026.",
                    }
                ],
                "drops": [{"event_index": 1, "reason": "bad_evidence_span"}],
            }
        return {}

    monkeypatch.setattr(nodes, "generate_json", fake_generate_json)

    in_state = {
        "press_release_content": "Revenue increased 10% in 2026.",
        "candidate_events": [
            {
                "event_type": "financial",
                "event_date": "2026-03-04",
                "claim": "Revenue increased.",
                "entities": ["BEAM"],
                "numbers": ["10%"],
                "evidence_span": "Revenue increased 10% in 2026.",
            },
            {
                "event_type": "financial",
                "event_date": "2026-03-04",
                "claim": "Bad evidence",
                "entities": ["BEAM"],
                "numbers": ["999"],
                "evidence_span": "Not in content",
            },
        ],
        "review_trace": [],
        "hop_count": 1,
    }

    out = nodes.validate_events(in_state)

    assert len(out.get("validated_events", [])) == 1
    assert out["validated_events"][0]["claim"] == "Revenue increased."
    hop_trace = out.get("review_trace", [])[0]
    assert hop_trace.get("dropped_count") == 1
