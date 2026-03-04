"""Thread scratchpad cache for linker context."""

COLLECTION = "thread_scratchpads"

INDEXES = [
    ("ticker_1_thread_id_1", [("ticker", 1), ("thread_id", 1)], {"unique": True}),
    ("ticker_1_updated_at_-1", [("ticker", 1), ("updated_at", -1)]),
]
