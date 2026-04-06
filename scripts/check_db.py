import pymongo
import os
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.environ.get("MONGODB_URI")
MONGODB_DATABASE = os.environ.get("MONGODB_DATABASE", "pr_release_db")

client = pymongo.MongoClient(MONGODB_URI)
db = client[MONGODB_DATABASE]

print("=== COLLECTIONS ===")
print(db.list_collection_names())

print("\n=== CRAWL RESULTS PER TICKER ===")
pipeline = [
    {"$group": {
        "_id": "$ticker",
        "count": {"$sum": 1},
        "earliest": {"$min": "$press_release_timestamp"},
        "latest": {"$max": "$press_release_timestamp"}
    }},
    {"$sort": {"_id": 1}}
]
for r in db.crawl_results.aggregate(pipeline):
    earliest = str(r['earliest'])[:10] if r['earliest'] else "N/A"
    latest = str(r['latest'])[:10] if r['latest'] else "N/A"
    print(f"  {r['_id']}: {r['count']} docs | {earliest} → {latest}")

print("\n=== EVENTS PER TICKER ===")
pipeline2 = [
    {"$group": {
        "_id": "$ticker",
        "count": {"$sum": 1},
        "earliest": {"$min": "$event_date"},
        "latest": {"$max": "$event_date"}
    }},
    {"$sort": {"_id": 1}}
]
for r in db.events.aggregate(pipeline2):
    earliest = str(r['earliest'])[:10] if r['earliest'] else "N/A"
    latest = str(r['latest'])[:10] if r['latest'] else "N/A"
    print(f"  {r['_id']}: {r['count']} events | {earliest} → {latest}")

print("\n=== LINKED EVENTS PER TICKER ===")
try:
    pipeline3 = [
        {"$group": {
            "_id": "$ticker",
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id": 1}}
    ]
    for r in db.linked_events.aggregate(pipeline3):
        print(f"  {r['_id']}: {r['count']} linked events")
except Exception as e:
    print(f"  linked_events error: {e}")

print("\n=== BASELINE SUMMARIES PER TICKER ===")
try:
    pipeline4 = [
        {"$group": {
            "_id": "$ticker",
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id": 1}}
    ]
    for r in db.baseline_summaries.aggregate(pipeline4):
        print(f"  {r['_id']}: {r['count']} summaries")
except Exception as e:
    print(f"  baseline_summaries error: {e}")
