"""PART 0: Ingestion - crawl results collection."""

COLLECTION = "crawl_results"

INDEXES = [
    (
        "ticker_1_press_release_timestamp_-1",
        [("ticker", 1), ("press_release_timestamp", -1)],
    ),
    ("source_url_1", [("source_url", 1)]),
    ("unprocessed_1", [("unprocessed", 1)]),
]
