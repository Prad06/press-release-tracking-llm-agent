#!/usr/bin/env python3
"""
MongoDB checkpoint: create named snapshots and restore to them.

Usage:
  python scripts/checkpoint.py create <name>   # Save current DB state
  python scripts/checkpoint.py list            # List checkpoints
  python scripts/checkpoint.py restore <name>  # Restore to checkpoint (replaces current)
"""

import json
import re
import sys
from pathlib import Path

# Project root
ROOT = Path(__file__).resolve().parent.parent
CHECKPOINTS_DIR = ROOT / "checkpoints"

# Collections to snapshot (from migrations registry)
COLLECTIONS = ["crawl_results", "companies"]


def _sanitize_name(name: str) -> str:
    """Allow alphanumeric, hyphens, underscores."""
    if not name or not re.match(r"^[a-zA-Z0-9_-]+$", name):
        raise ValueError(f"Checkpoint name must be alphanumeric, hyphens, underscores: {name!r}")
    return name


def _load_env():
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")


def create_checkpoint(name: str) -> None:
    _load_env()
    from pr_flow_agents.storage.config import get_database, get_uri
    import pymongo
    from bson import json_util

    name = _sanitize_name(name)
    out_dir = CHECKPOINTS_DIR / name
    out_dir.mkdir(parents=True, exist_ok=True)

    uri = get_uri()
    db_name = get_database()
    client = pymongo.MongoClient(uri)
    db = client[db_name]

    for coll_name in COLLECTIONS:
        coll = db[coll_name]
        docs = list(coll.find({}))
        path = out_dir / f"{coll_name}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(docs, f, indent=2, default=json_util.default)
        print(f"  {coll_name}: {len(docs)} docs -> {path.name}")

    client.close()
    print(f"Checkpoint '{name}' saved to {out_dir}")


def list_checkpoints() -> None:
    if not CHECKPOINTS_DIR.exists():
        print("No checkpoints yet. Create one with: python scripts/checkpoint.py create <name>")
        return
    dirs = sorted(d for d in CHECKPOINTS_DIR.iterdir() if d.is_dir())
    if not dirs:
        print("No checkpoints yet.")
        return
    print("Checkpoints:")
    for d in dirs:
        print(f"  {d.name}")


def restore_checkpoint(name: str) -> None:
    _load_env()
    from pr_flow_agents.storage.config import get_database, get_uri
    import pymongo
    from bson import json_util

    name = _sanitize_name(name)
    out_dir = CHECKPOINTS_DIR / name
    if not out_dir.exists() or not out_dir.is_dir():
        raise FileNotFoundError(f"Checkpoint '{name}' not found at {out_dir}")

    uri = get_uri()
    db_name = get_database()
    client = pymongo.MongoClient(uri)
    db = client[db_name]

    for coll_name in COLLECTIONS:
        path = out_dir / f"{coll_name}.json"
        if not path.exists():
            continue
        coll = db[coll_name]
        with open(path, "r", encoding="utf-8") as f:
            docs = json.load(f, object_hook=json_util.object_hook)
        coll.delete_many({})
        if docs:
            coll.insert_many(docs)
        print(f"  {coll_name}: restored {len(docs)} docs")

    client.close()
    print(f"Restored checkpoint '{name}'")


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    cmd = args[0].lower()
    try:
        if cmd == "create":
            if len(args) < 2:
                print("Usage: python scripts/checkpoint.py create <name>")
                sys.exit(1)
            create_checkpoint(args[1])
        elif cmd == "list":
            list_checkpoints()
        elif cmd == "restore":
            if len(args) < 2:
                print("Usage: python scripts/checkpoint.py restore <name>")
                sys.exit(1)
            restore_checkpoint(args[1])
        else:
            print(f"Unknown command: {cmd}")
            print(__doc__)
            sys.exit(1)
    except (ValueError, FileNotFoundError) as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
