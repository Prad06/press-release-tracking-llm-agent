"""
Migration registry. Add new domains: create migrations/<domain>.py, then register below.
Index format: (name, keys) or (name, keys, opts) e.g. opts={"unique": True}
"""

REGISTRY: dict[str, list] = {}

from pr_flow_agents.storage.migrations import ingestion, companies

REGISTRY[ingestion.COLLECTION] = ingestion.INDEXES
REGISTRY[companies.COLLECTION] = companies.INDEXES


def run_all(uri: str, database: str) -> None:
    import pymongo
    client = pymongo.MongoClient(uri)
    db = client[database]
    for coll_name, indexes in REGISTRY.items():
        coll = db[coll_name]
        for spec in indexes:
            if len(spec) == 2:
                name, keys = spec
                coll.create_index(keys, name=name)
            else:
                name, keys, opts = spec
                coll.create_index(keys, name=name, **opts)
    client.close()


def run_collection(uri: str, database: str, collection: str) -> None:
    if collection not in REGISTRY:
        return
    import pymongo
    client = pymongo.MongoClient(uri)
    coll = client[database][collection]
    for spec in REGISTRY[collection]:
        if len(spec) == 2:
            name, keys = spec
            coll.create_index(keys, name=name)
        else:
            name, keys, opts = spec
            coll.create_index(keys, name=name, **opts)
    client.close()
