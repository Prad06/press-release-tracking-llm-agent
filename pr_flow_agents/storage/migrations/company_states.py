"""Company states collection."""

COLLECTION = "company_states"

INDEXES = [
    ("ticker_1", [("ticker", 1)], {"unique": True}),
]

