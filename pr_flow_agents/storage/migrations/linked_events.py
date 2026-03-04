"""Gold linked events for linker pipeline."""

COLLECTION = "linked_events"

INDEXES = [
    ("linked_event_id_1", [("linked_event_id", 1)], {"unique": True}),
    ("ticker_1_thread_id_1_updated_at_-1", [("ticker", 1), ("thread_id", 1), ("updated_at", -1)]),
    ("ticker_1_event_type_1_status_1", [("ticker", 1), ("event_type", 1), ("status", 1)]),
    ("ticker_1_event_date_1", [("ticker", 1), ("event_date", 1)]),
]
