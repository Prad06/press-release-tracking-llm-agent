"""
Ingestion logic. Used by CLI and API.
"""

import asyncio
import csv
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from pr_flow_agents.crawler import crawl_from_link
from pr_flow_agents.models import PressReleaseLink


async def run_single(
    url: str,
    ticker: Optional[str] = None,
    title: Optional[str] = None,
    press_ts: Optional[datetime] = None,
    save_mongo: bool = False,
    output_path: Optional[str] = None,
    quiet: bool = False,
) -> Dict[str, Any]:
    """Crawl one URL. Optionally save to Mongo and/or file."""
    link = PressReleaseLink(url=url, selection_method="cli", all_candidates=[url])
    results, pending = await crawl_from_link(link)
    out = {"crawl_results": results.model_dump(), "pending": pending.to_dict()}

    if not quiet:
        print(f"Crawled: {results.source_url}")
        print(f"Content: {len(results.markdown_content)} chars, {len(results.all_links)} links")
        if pending.has_issues:
            print(f"Pending: empty_content={pending.empty_content}, no_links={pending.no_links}")

    if save_mongo and ticker and title:
        if press_ts is None:
            raise ValueError("press_release date is required when saving to Mongo; provide press_ts")
        from pr_flow_agents.storage import save_crawl_to_mongo
        doc_id = save_crawl_to_mongo(results, ticker=ticker, title=title, press_release_timestamp=press_ts)
        out["mongo_id"] = doc_id
        if not quiet:
            print(f"Saved to MongoDB: {doc_id}")

    if output_path:
        import json
        with open(output_path, "w") as f:
            json.dump(out, f, indent=2)
        if not quiet:
            print(f"Written to {output_path}")

    return out


def run_single_sync(**kwargs: Any) -> Dict[str, Any]:
    return asyncio.run(run_single(**kwargs))


async def run_bulk(csv_path: str, quiet: bool = False) -> List[Dict[str, Any]]:
    """Read CSV (url, ticker, date), crawl each, save to Mongo."""
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(csv_path)
    out: List[Dict[str, Any]] = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        keys = {k.strip().lower(): k for k in (reader.fieldnames or [])}
        rows = list(reader)
    url_key = keys.get("url") or keys.get("link")
    if not url_key:
        raise ValueError("CSV must have 'url' or 'link' column")
    ticker_key = keys.get("ticker") or keys.get("symbol")
    title_key = keys.get("title")
    if not title_key:
        raise ValueError("CSV must have 'title' column")
    date_key = keys.get("date") or keys.get("press_ts")
    if not date_key:
        raise ValueError("CSV must have 'date' (or 'press_ts') column; press_release date is required and will not default to crawl date")
    for i, row in enumerate(rows):
        url = (row.get(url_key) or "").strip()
        if not url:
            continue
        ticker = (row.get(ticker_key) or "").strip() if ticker_key else ""
        title = (row.get(title_key) or "").strip()
        if not title:
            continue
        date_str = (row.get(date_key) or "").strip() if date_key else ""
        press_ts: Optional[datetime] = None
        if date_str:
            try:
                press_ts = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except ValueError:
                try:
                    from datetime import datetime as dt
                    press_ts = dt.strptime(date_str, "%Y-%m-%d")
                except ValueError:
                    pass
        link = PressReleaseLink(url=url, selection_method="bulk", all_candidates=[url])
        try:
            results, pending = await crawl_from_link(link)
            if ticker and title:
                if press_ts is None:
                    rec = {
                        "url": url,
                        "ticker": ticker,
                        "ok": False,
                        "error": "press_release date is required; CSV must have 'date' column with valid ISO or YYYY-MM-DD format",
                    }
                else:
                    from pr_flow_agents.storage import save_crawl_to_mongo
                    doc_id = save_crawl_to_mongo(results, ticker=ticker, title=title, press_release_timestamp=press_ts)
                    rec = {"url": url, "ticker": ticker, "mongo_id": doc_id, "ok": True}
            else:
                rec = {"url": url, "ok": True, "mongo_id": None}
            out.append(rec)
            if not quiet:
                print(f"[{i+1}/{len(rows)}] {url} -> {rec.get('mongo_id', 'no save')}")
        except Exception as e:
            rec = {"url": url, "ticker": ticker, "ok": False, "error": str(e)}
            out.append(rec)
            if not quiet:
                print(f"[{i+1}/{len(rows)}] {url} FAILED: {e}")
    return out


def run_bulk_sync(csv_path: str, quiet: bool = False) -> List[Dict[str, Any]]:
    return asyncio.run(run_bulk(csv_path, quiet))
