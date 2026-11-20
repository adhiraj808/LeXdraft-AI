"""Cloud LLM generation (Groq, HF, OpenAI-compatible)."""

import asyncio
import logging
import time
from typing import Dict, List, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class CloudGenerator:
    """Generates legal drafts using cloud LLM providers."""

    def __init__(self):
        self._failed_providers: Dict[str, float] = {}
        self._failure_cooldown = settings.LLM_FAILURE_COOLDOWN_SECONDS

    def _mark_provider_failed(self, provider: str) -> None:
        self._failed_providers[provider] = time.time()

    def _is_provider_failed(self, provider: str) -> bool:
        if provider not in self._failed_providers:
            return False
        return (time.time() - self._failed_providers[provider]) < self._failure_cooldown

    def _cloud_usable(self) -> bool:
        """Check if any cloud provider is available."""
        return any(
            not self._is_provider_failed(p)
            for p in ["groq", "hf", "llm"]
            if self._provider_has_credentials(p)
        )

    def _provider_has_credentials(self, provider: str) -> bool:
        if provider == "groq":
            return bool(settings.GROQ_API_KEY)
        if provider == "hf":
            return bool(settings.HF_API_TOKEN or settings.HUGGINGFACE_TOKEN)
        if provider == "llm":
            return bool(settings.LLM_API_KEY and settings.LLM_BASE_URL)
        return False

    def _provider_order(self) -> List[str]:
        """Return ordered list of available providers (respects MODEL_PROVIDER setting)."""
        if settings.MODEL_PROVIDER == "groq":
            return ["groq"] if self._provider_has_credentials("groq") else []
        if settings.MODEL_PROVIDER == "hf":
            return ["hf"] if self._provider_has_credentials("hf") else []
        if settings.MODEL_PROVIDER == "openai":
            return ["llm"] if self._provider_has_credentials("llm") else []
        if settings.MODEL_PROVIDER == "local":
            return []
        if settings.MODEL_PROVIDER == "template":
            return []

        # Auto mode: try all available
        order = []
        if self._provider_has_credentials("groq") and not self._is_provider_failed("groq"):
            order.append("groq")
        if self._provider_has_credentials("hf") and not self._is_provider_failed("hf"):
            order.append("hf")
        if self._provider_has_credentials("llm") and not self._is_provider_failed("llm"):
            order.append("llm")
        return order

    async def _call_groq(self, prompt: str, max_tokens: int) -> Optional[str]:
        if not settings.GROQ_API_KEY:
            return None
        try:
            async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
                resp = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
                    json={
                        "model": settings.GROQ_MODEL,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": max_tokens,
                        "temperature": 0.2,
                    },
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.warning(f"Groq call failed: {e}")
            self._mark_provider_failed("groq")
            return None

    async def _call_hf(self, prompt: str, max_tokens: int) -> Optional[str]:
        token = settings.HF_API_TOKEN or settings.HUGGINGFACE_TOKEN
        if not token:
            return None
        try:
            async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
                resp = await client.post(
                    f"{settings.HF_BASE_URL}/chat/completions",
                    headers={"Authorization": f"Bearer {token}"},
                    json={
                        "model": settings.HF_MODEL,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": max_tokens,
                        "temperature": 0.2,
                    },
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.warning(f"HF call failed: {e}")
            self._mark_provider_failed("hf")
            return None

    async def _call_llm(self, prompt: str, max_tokens: int) -> Optional[str]:
        if not settings.LLM_API_KEY or not settings.LLM_BASE_URL:
            return None
        try:
            async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
                resp = await client.post(
                    f"{settings.LLM_BASE_URL}/chat/completions",
                    headers={"Authorization": f"Bearer {settings.LLM_API_KEY}"},
                    json={
                        "model": settings.LLM_MODEL,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": max_tokens,
                        "temperature": 0.2,
                    },
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.warning(f"LLM call failed: {e}")
            self._mark_provider_failed("llm")
            return None

    async def generate(self, prompt: str, max_tokens: int = 2048) -> Optional[str]:
        """Try each available provider in order until one succeeds."""
        for provider in self._provider_order():
            if provider == "groq":
                result = await self._call_groq(prompt, max_tokens)
            elif provider == "hf":
                result = await self._call_hf(prompt, max_tokens)
            elif provider == "llm":
                result = await self._call_llm(prompt, max_tokens)
            else:
                continue

            if result:
                return result

            # Small delay between providers to avoid hammering
            await asyncio.sleep(0.5)

        return None