"""Crawler orchestration: PressReleaseLink -> CrawlResults with pending status."""

import asyncio
import json
from dataclasses import dataclass, field
from typing import List, Optional

from pr_flow_agents.models import CrawlResults, PressReleaseLink, WebLink
from pr_flow_agents.scrapper import crawl_press_release


@dataclass
class PendingStatus:
    """What remains to be done after a crawl."""

    empty_content: bool = False
    no_links: bool = False
    pdfs_to_download: List[WebLink] = field(default_factory=list)
    candidate_urls_not_crawled: List[str] = field(default_factory=list)
    has_issues: bool = False

    def to_dict(self) -> dict:
        return {
            "empty_content": self.empty_content,
            "no_links": self.no_links,
            "pdfs_to_download": [
                {"url": l.url, "text": l.text, "title": l.title}
                for l in self.pdfs_to_download
            ],
            "candidate_urls_not_crawled": self.candidate_urls_not_crawled,
            "has_issues": self.has_issues,
        }


def get_pending_status(
    link: PressReleaseLink, results: CrawlResults
) -> PendingStatus:
    """
    Analyze CrawlResults and report what is still pending or problematic.
    """
    status = PendingStatus()

    # Check for empty content
    if not results.markdown_content and not results.main_content:
        status.empty_content = True
        status.has_issues = True

    # Check for no links
    if not results.all_links:
        status.no_links = True
        status.has_issues = True

    # PDFs that could be downloaded (by URL or by text)
    all_pdfs = {l.url: l for l in results.pdf_links_by_url + results.pdf_links_by_text}
    status.pdfs_to_download = list(all_pdfs.values())

    # Candidate URLs from PressReleaseLink that weren't the main crawled URL
    crawled_url = results.source_url.rstrip("/")
    candidates = link.all_candidates or []
    status.candidate_urls_not_crawled = [
        c for c in candidates
        if c.rstrip("/") != crawled_url
    ]

    return status


async def crawl_from_link(link: PressReleaseLink) -> tuple[CrawlResults, PendingStatus]:
    """
    Given a PressReleaseLink, crawl its URL and return CrawlResults plus pending status.
    """
    results = await crawl_press_release(link.url)
    status = get_pending_status(link, results)
    return results, status


def crawl_from_link_sync(link: PressReleaseLink) -> tuple[CrawlResults, PendingStatus]:
    """Synchronous wrapper for crawl_from_link."""
    return asyncio.run(crawl_from_link(link))
