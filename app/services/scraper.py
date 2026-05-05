"""
PLG App — Website scraper.
Uses httpx + BeautifulSoup to extract text from target websites.
"""

import time
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx
import structlog
from bs4 import BeautifulSoup

logger = structlog.get_logger()


class WebsiteScraper:
    """Scrape homepage and about page from a target website."""

    TIMEOUT = 15.0
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml",
    }
    ABOUT_PATHS = ["/about", "/about-us", "/about-us/", "/about/", "/company", "/who-we-are"]

    async def scrape(self, website_url: str) -> str:
        if not website_url.startswith(("http://", "https://")):
            website_url = f"https://{website_url}"

        combined = []
        homepage = await self._fetch_and_extract(website_url)
        if homepage:
            combined.append(f"=== HOMEPAGE ===\n{homepage}")

        about = await self._find_about_page(website_url)
        if about:
            combined.append(f"=== ABOUT PAGE ===\n{about}")

        result = "\n\n".join(combined) if combined else "No content could be extracted."
        logger.info("scrape_completed", url=website_url, chars=len(result))
        return result[:8000]

    async def _fetch_and_extract(self, url: str) -> Optional[str]:
        try:
            async with httpx.AsyncClient(timeout=self.TIMEOUT, follow_redirects=True, verify=False) as client:
                response = await client.get(url, headers=self.HEADERS)
            if response.status_code != 200:
                return None
            soup = BeautifulSoup(response.text, "lxml")
            for tag in soup(["script", "style", "nav", "footer", "noscript", "iframe"]):
                tag.decompose()
            sections = []
            for el in soup.select("h1, h2, h3, p, li")[:40]:
                text = el.get_text(strip=True)
                if text and len(text) > 15:
                    sections.append(text)
            return "\n".join(sections) if sections else soup.get_text(separator="\n", strip=True)[:3000]
        except Exception as e:
            logger.warning("scrape_exception", url=url, error=str(e))
            return None

    async def _find_about_page(self, base_url: str) -> Optional[str]:
        parsed = urlparse(base_url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        for path in self.ABOUT_PATHS:
            text = await self._fetch_and_extract(urljoin(base, path))
            if text and len(text) > 100:
                return text
        return None
