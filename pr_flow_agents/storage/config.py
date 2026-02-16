"""Central MongoDB config. Single source of truth for DB connection."""

import os


def get_uri() -> str:
    uri = os.environ.get("MONGODB_URI", "").strip()
    if not uri:
        raise ValueError("MONGODB_URI not set")
    return uri


def get_database() -> str:
    return os.environ.get("MONGODB_DATABASE", "pr_flow").strip()
