"""Model-agnostic LLM client.

Speaks the OpenAI-compatible `/chat/completions` protocol, so it works with
ANY provider that exposes it:
  - Groq            https://api.groq.com/openai/v1
  - HF Inference    https://router.huggingface.co/v1
  - OpenRouter      https://openrouter.ai/api/v1
  - Together        https://api.together.xyz/v1
  - Ollama          http://host:11434/v1
  - vLLM / llama.cpp server / any OpenAI-compatible endpoint

Configure via .env:
  LLM_BASE_URL, LLM_API_KEY, LLM_MODEL

The API key is sent only in the Authorization header and never logged.
"""

import logging
import time
from typing import Dict, List, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    """Universal chat-completions client with retries and graceful fallback."""

    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    @property
    def available(self) -> bool:
        return bool(self.base_url and self.api_key and self.model)

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        retries: int = 0,  # No retries for faster failure
    ) -> Optional[str]:
        """Send a chat completion request. Returns text or None on failure.

        Retries on rate-limit (429) and transient 5xx with backoff,
        honouring Retry-After when present.
        """
        if not self.available:
            return None

        url = f"{self.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        delays = [2, 5]  # Reduced delays
        for attempt in range(retries + 1):
            try:
                with httpx.Client(timeout=min(self.timeout, 30.0)) as client:  # Reduced timeout
                    resp = client.post(url, headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    text = data["choices"][0]["message"].get("content", "").strip()
                    # If content is empty but reasoning exists, use reasoning
                    if not text:
                        text = data["choices"][0]["message"].get("reasoning", "").strip()
                    return text or None
                if resp.status_code in (429, 500, 502, 503) and attempt < retries:
                    wait = resp.headers.get("retry-after")
                    wait_s = (
                        float(wait)
                        if wait and str(wait).replace(".", "", 1).isdigit()
                        else delays[min(attempt, len(delays) - 1)]
                    )
                    logger.info(
                        f"LLM {self.model} returned {resp.status_code}, retrying in {wait_s}s..."
                    )
                    time.sleep(wait_s)
                    continue
                # Log status only — never the body or key.
                logger.warning(f"LLM {self.model} returned {resp.status_code}, giving up.")
                return None
            except Exception as e:
                if attempt < retries:
                    logger.warning(f"LLM call failed ({e}), retrying...")
                    time.sleep(delays[min(attempt, len(delays) - 1)])
                    continue
                logger.warning(f"LLM call failed repeatedly: {e}")
                return None
        return None


def build_default_clients() -> Dict[str, LLMClient]:
    """Build every configured provider client keyed by provider name.

    Priority order (first available wins unless MODEL_PROVIDER pins one):
      MODEL_PROVIDER == "hf"      -> HF Inference Providers
      MODEL_PROVIDER == "groq"    -> Groq
      MODEL_PROVIDER == "openai"  -> generic LLM_BASE_URL endpoint
      "auto"                      -> first of [generic, groq, hf] that is configured
    """
    clients: Dict[str, LLMClient] = {}

    # Generic OpenAI-compatible endpoint (explicit LLM_BASE_URL wins).
    if settings.LLM_BASE_URL and settings.LLM_API_KEY:
        clients["openai"] = LLMClient(
            settings.LLM_BASE_URL, settings.LLM_API_KEY, settings.LLM_MODEL
        )

    # Hugging Face Inference Providers (OpenAI-compatible router).
    # Accept both HF_API_TOKEN and the legacy HUGGINGFACE_TOKEN env name.
    hf_token = settings.HF_API_TOKEN or getattr(settings, "HUGGINGFACE_TOKEN", "")
    if hf_token and settings.HF_MODEL:
        hf_url = settings.HF_BASE_URL or "https://router.huggingface.co/v1"
        clients["hf"] = LLMClient(hf_url, hf_token, settings.HF_MODEL)

    # Groq.
    if settings.GROQ_API_KEY and settings.GROQ_MODEL:
        clients["groq"] = LLMClient(
            "https://api.groq.com/openai/v1", settings.GROQ_API_KEY, settings.GROQ_MODEL
        )

    return clients


def resolve_provider(clients: Dict[str, LLMClient]) -> Optional[str]:
    """Pick which provider to use based on MODEL_PROVIDER and availability."""
    requested = (settings.MODEL_PROVIDER or "auto").lower()
    if requested in clients:
        return requested
    if requested == "auto":
        for name in ("openai", "hf", "groq"):
            if name in clients:
                return name
    return None
