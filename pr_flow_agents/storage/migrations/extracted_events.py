"""Persisted extracted events from ingestion orchestrator."""

COLLECTION = "extracted_events"

INDEXES = [
    ("press_release_id_1_event_index_1", [("press_release_id", 1), ("event_index", 1)], {"unique": True}),
    ("company_ticker_1_press_release_timestamp_-1", [("company_ticker", 1), ("press_release_timestamp", -1)]),
    ("fiscal_year_1_fiscal_quarter_1", [("fiscal_year", 1), ("fiscal_quarter", 1)]),
    ("event_type_1", [("event_type", 1)]),
]
