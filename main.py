#!/usr/bin/env python3
"""Run migrations. Use the API + UI for ingestion."""

from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env")

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pr_flow_agents.storage.config import get_database, get_uri
from pr_flow_agents.storage.migrations import run_all

if __name__ == "__main__":
    run_all(get_uri(), get_database())
    print("Migrations done.")
