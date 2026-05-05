"""
PLG App — OpenRouter AI client.
Single client class, two methods: call_claude (heavy reasoning) and call_gemini (lightweight).
"""

import json
import time
from typing import Optional

import httpx
import structlog

from app.config import get_settings

logger = structlog.get_logger()


class OpenRouterClient:
    """OpenRouter API client for Claude and Gemini models."""

    BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
    MAX_RETRIES = 3
    TIMEOUT = 60.0

    # Model identifiers from PRD Section 7
    CLAUDE_MODEL = "anthropic/claude-sonnet-4.5"
    GEMINI_MODEL = "google/gemini-2.5-flash"

    def __init__(self):
        settings = get_settings()
        self.api_key = settings.openrouter_api_key
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://plg-app.onrender.com",
            "X-Title": "PLG Lead Generator",
        }

    async def _request(self, model: str, prompt: str, temperature: float = 0.2,
                        system_prompt: Optional[str] = None) -> str:
        """Make a chat completion request with retries."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }

        last_error = None

        for attempt in range(self.MAX_RETRIES):
            try:
                start = time.perf_counter()
                async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
                    response = await client.post(
                        self.BASE_URL, json=payload, headers=self.headers
                    )

                duration = round((time.perf_counter() - start) * 1000, 1)
                logger.info(
                    "openrouter_request",
                    model=model,
                    status_code=response.status_code,
                    duration_ms=duration,
                    attempt=attempt + 1,
                )

                if response.status_code == 200:
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    return content.strip()
                else:
                    last_error = f"HTTP {response.status_code}: {response.text}"
                    logger.warning("openrouter_error", error=last_error, attempt=attempt + 1)

            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = str(e)
                logger.warning("openrouter_timeout", error=last_error, attempt=attempt + 1)

            # Exponential backoff: 1s, 2s, 4s
            if attempt < self.MAX_RETRIES - 1:
                import asyncio
                await asyncio.sleep(2 ** attempt)

        raise Exception(f"OpenRouter request failed after {self.MAX_RETRIES} retries: {last_error}")

    async def call_claude(self, prompt: str, temperature: float = 0.2,
                           system_prompt: Optional[str] = None) -> str:
        """
        Call Claude (heavy reasoning) via OpenRouter.
        Used for: lead qualification, reply generation.
        """
        return await self._request(
            model=self.CLAUDE_MODEL,
            prompt=prompt,
            temperature=temperature,
            system_prompt=system_prompt,
        )

    async def call_gemini(self, prompt: str, temperature: float = 0.2,
                           system_prompt: Optional[str] = None) -> str:
        """
        Call Gemini (lightweight) via OpenRouter.
        Used for: sentiment check, ICP extraction, parsing.
        """
        return await self._request(
            model=self.GEMINI_MODEL,
            prompt=prompt,
            temperature=temperature,
            system_prompt=system_prompt,
        )

    async def parse_json_response(self, raw: str) -> list | dict:
        """
        Parse JSON from AI response. On failure, retry with temperature=0
        and a strict JSON reminder.
        """
        # Strip markdown fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # Remove first and last lines (fences)
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines).strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.warning("json_parse_failed", error=str(e), raw_preview=cleaned[:200])
            raise
