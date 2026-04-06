import pymongo
import os
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.environ.get("MONGODB_URI")
MONGODB_DATABASE = os.environ.get("MONGODB_DATABASE", "pr_release_db")

client = pymongo.MongoClient(MONGODB_URI)
db = client[MONGODB_DATABASE]

# Export press releases for each ticker
for ticker in ["DAL"]:
    docs = list(
        db.crawl_results
        .find({"ticker": ticker})
        .sort("press_release_timestamp", 1)
    )

    output_path = f"./data/qa_press_releases/{ticker}_press_releases.txt"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"COMPANY: {ticker}\n")
        f.write(f"TOTAL PRESS RELEASES: {len(docs)}\n")
        f.write("=" * 80 + "\n\n")

        for i, doc in enumerate(docs, 1):
            doc_id = str(doc["_id"])
            title = doc.get("title", "N/A")
            ts = str(doc.get("press_release_timestamp", "N/A"))[:10]
            raw = doc.get("raw_result", {})

            # Use the correct field names from MongoDB
            text = (
                raw.get("markdown_content") or
                raw.get("main_content") or
                raw.get("text") or
                raw.get("content") or
                "NO CONTENT FOUND"
            )

            f.write(f"--- RELEASE {i} ---\n")
            f.write(f"ID: {doc_id}\n")
            f.write(f"DATE: {ts}\n")
            f.write(f"TITLE: {title}\n")
            f.write(f"URL: {raw.get('source_url', 'N/A')}\n")
            f.write(f"\nCONTENT:\n{text}\n")
            f.write("\n" + "=" * 80 + "\n\n")

    size_kb = os.path.getsize(output_path) // 1024
    print(f"✅ {ticker}: {len(docs)} releases → {output_path} ({size_kb} KB)")
