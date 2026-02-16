import logging
from typing import List

from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

from pr_flow_agents.models import CrawlResults, WebLink

logger = logging.getLogger(__name__)


async def crawl_press_release(url: str) -> CrawlResults:
    """Crawl a press release URL and return structured CrawlResults."""
    logger.info("Crawling press release at URL: %s", url)
    print(f"[crawl_press_release] Crawling press release at URL: {url}")

    config = CrawlerRunConfig(
        markdown_generator=DefaultMarkdownGenerator(
            content_filter=PruningContentFilter(
                threshold=0.3, threshold_type="dynamic"
            ),
            options={"ignore_links": True},
        )
    )

    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=url, config=config)

        if not result.success:
            logger.error("Crawl failed: %s", result.error_message)
            print(f"[crawl_press_release] Crawl failed: {result.error_message}")
            raise Exception(f"Crawl failed: {result.error_message}")

        all_links: List[WebLink] = []
        links_data = result.links or {}
        internal = links_data.get("internal", [])
        external = links_data.get("external", [])

        for link in internal:
            link_dict = link if isinstance(link, dict) else {}
            all_links.append(
                WebLink(
                    url=link_dict.get("href", ""),
                    text=link_dict.get("text", ""),
                    title=link_dict.get("title", ""),
                    link_type="internal",
                )
            )
        for link in external:
            link_dict = link if isinstance(link, dict) else {}
            all_links.append(
                WebLink(
                    url=link_dict.get("href", ""),
                    text=link_dict.get("text", ""),
                    title=link_dict.get("title", ""),
                    link_type="external",
                )
            )

        logger.info("Found %d links in the press release.", len(all_links))
        print(f"[crawl_press_release] Found {len(all_links)} links in the press release.")

        markdown_result = result.markdown
        raw_markdown = ""
        fit_markdown = ""
        if markdown_result:
            raw_markdown = getattr(markdown_result, "raw_markdown", "") or ""
            fit_markdown = getattr(markdown_result, "fit_markdown", "") or raw_markdown

        return CrawlResults(
            source_url=result.url,
            markdown_content=raw_markdown,
            main_content=fit_markdown,
            all_links=all_links,
            pdf_links_by_url=[
                link for link in all_links if link.url.lower().endswith(".pdf")
            ],
            pdf_links_by_text=[
                link
                for link in all_links
                if any(kw in (link.text or "").lower() for kw in ["pdf", "download"])
                or any(kw in (link.title or "").lower() for kw in ["pdf", "download"])
            ],
        )
