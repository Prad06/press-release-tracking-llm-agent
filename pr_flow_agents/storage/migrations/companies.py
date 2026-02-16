"""Companies collection."""

COLLECTION = "companies"

# (index_name, index_keys, optional_opts)
INDEXES = [
    ("ticker_1", [("ticker", 1)], {"unique": True}),
]
