"""Events collection."""

COLLECTION = "events"

# (index_name, index_keys, optional_opts)
INDEXES = [
    ("source_doc_id_1", [("source_doc_id", 1)]),
    ("ticker_1_event_date_1", [("ticker", 1), ("event_date", 1)]),
    ("event_type_1_event_date_1", [("event_type", 1), ("event_date", 1)]),
]

