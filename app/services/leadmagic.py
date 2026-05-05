"""
PLG App — LeadMagic API client.
Wraps all LeadMagic REST API calls with retries and caching.
"""

import time
import hashlib
from typing import Optional

import httpx
import structlog

from app.config import get_settings

logger = structlog.get_logger()

# In-memory cache: domain → (timestamp, response)
_cache: dict[str, tuple[float, dict]] = {}
CACHE_TTL = 86400  # 24 hours


class LeadMagicClient:
    """LeadMagic REST API client with retry logic and caching."""

    BASE_URL = "https://api.leadmagic.io/v1"
    MAX_RETRIES = 3
    TIMEOUT = 30.0

    def __init__(self):
        settings = get_settings()
        self.api_key = settings.leadmagic_api_key
        self.headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
        }

    def _get_cache_key(self, endpoint: str, domain: str) -> str:
        return f"{endpoint}:{domain}"

    def _get_cached(self, cache_key: str) -> Optional[dict]:
        if cache_key in _cache:
            ts, data = _cache[cache_key]
            if time.time() - ts < CACHE_TTL:
                logger.info("cache_hit", cache_key=cache_key)
                return data
            del _cache[cache_key]
        return None

    def _set_cache(self, cache_key: str, data: dict):
        _cache[cache_key] = (time.time(), data)

    async def _request(self, endpoint: str, payload: dict, cache_key: Optional[str] = None) -> dict:
        """Make a POST request with exponential backoff retries."""
        if cache_key:
            cached = self._get_cached(cache_key)
            if cached:
                return cached

        url = f"{self.BASE_URL}/{endpoint}"
        last_error = None

        for attempt in range(self.MAX_RETRIES):
            try:
                start = time.perf_counter()
                async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
                    response = await client.post(url, json=payload, headers=self.headers)

                duration = round((time.perf_counter() - start) * 1000, 1)
                logger.info(
                    "leadmagic_request",
                    endpoint=endpoint,
                    status_code=response.status_code,
                    duration_ms=duration,
                    attempt=attempt + 1,
                )

                if response.status_code == 200:
                    data = response.json()
                    if cache_key:
                        self._set_cache(cache_key, data)
                    return data
                else:
                    last_error = f"HTTP {response.status_code}: {response.text}"
                    logger.warning("leadmagic_error", error=last_error, attempt=attempt + 1)

            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = str(e)
                logger.warning("leadmagic_timeout", error=last_error, attempt=attempt + 1)

            # Exponential backoff: 1s, 2s, 4s
            if attempt < self.MAX_RETRIES - 1:
                import asyncio
                await asyncio.sleep(2 ** attempt)

        raise Exception(f"LeadMagic request failed after {self.MAX_RETRIES} retries: {last_error}")

    async def company_search(self, company_domain: Optional[str] = None,
                              company_name: Optional[str] = None,
                              profile_url: Optional[str] = None) -> dict:
        """
        Enrich a single company.
        POST /v1/companies/company-search
        """
        payload = {}
        if company_domain:
            payload["company_domain"] = company_domain
        if company_name:
            payload["company_name"] = company_name
        if profile_url:
            payload["profile_url"] = profile_url

        cache_key = self._get_cache_key("company-search", company_domain or company_name or "")
        return await self._request("companies/company-search", payload, cache_key)

    async def competitors_search(self, company_domain: Optional[str] = None,
                                  company_name: Optional[str] = None,
                                  company_url: Optional[str] = None) -> dict:
        """
        Find competitors of a company.
        POST /v1/companies/competitors-search
        """
        payload = {}
        if company_domain:
            payload["company_domain"] = company_domain
        if company_name:
            payload["company_name"] = company_name
        if company_url:
            payload["company_url"] = company_url

        cache_key = self._get_cache_key("competitors-search", company_domain or company_name or "")
        return await self._request("companies/competitors-search", payload, cache_key)

    async def company_funding(self, company_domain: Optional[str] = None,
                               company_name: Optional[str] = None) -> dict:
        """
        Get funding data for a company.
        POST /v1/companies/company-funding
        """
        payload = {}
        if company_domain:
            payload["company_domain"] = company_domain
        if company_name:
            payload["company_name"] = company_name

        cache_key = self._get_cache_key("company-funding", company_domain or company_name or "")
        return await self._request("companies/company-funding", payload, cache_key)

    async def employee_finder(self, company_domain: Optional[str] = None,
                               company_name: Optional[str] = None,
                               limit: int = 20) -> dict:
        """
        Find employees at a company.
        POST /v1/people/employee-finder
        """
        payload = {"limit": limit}
        if company_domain:
            payload["company_domain"] = company_domain
        if company_name:
            payload["company_name"] = company_name

        return await self._request("people/employee-finder", payload)
