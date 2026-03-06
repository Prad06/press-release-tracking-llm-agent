"""Company-wide and quarterly baseline summaries."""

COLLECTION = "baseline_summaries"

INDEXES = [
    (
        "ticker_1_scope_1_fiscal_year_1_fiscal_quarter_1",
        [("ticker", 1), ("scope", 1), ("fiscal_year", 1), ("fiscal_quarter", 1)],
        {"unique": True},
    ),
    ("ticker_1_scope_1_updated_at_-1", [("ticker", 1), ("scope", 1), ("updated_at", -1)]),
    ("last_release_timestamp_-1", [("last_release_timestamp", -1)]),
]
