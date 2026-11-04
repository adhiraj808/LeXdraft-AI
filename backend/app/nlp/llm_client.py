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

`chat()` is synchronous and blocking: call it from a worker thread
(``asyncio.to_thread``), never directly from the event loop.
"""

import logging
import threading
import time
from typing import Dict, List, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    """Universal chat-completions client with retries and graceful fallback."""

    def __init__(
        self, base_url: str, api_key: str, model: str, timeout: Optional[float] = None
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout if timeout is not None else settings.LLM_TIMEOUT_SECONDS
        # One pooled HTTP client per provider: keep-alive connections skip a TCP + TLS
        # handshake on every call (7 sections per draft) and avoid allocator churn.
        self._http: Optional[httpx.Client] = None
        self._http_lock = threading.Lock()

    @property
    def available(self) -> bool:
        return bool(self.base_url and self.api_key and self.model)

    def _client(self) -> httpx.Client:
        with self._http_lock:
            if self._http is None:
                self._http = httpx.Client(
                    timeout=httpx.Timeout(self.timeout, connect=10.0),
                    limits=httpx.Limits(max_connections=4, max_keepalive_connections=2),
                )
            return self._http

    def close(self) -> None:
        with self._http_lock:
            if self._http is not None:
                self._http.close()
                self._http = None

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        retries: int = 0,  # failing fast is better: the caller has fallbacks
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
            "max_tokens": max_tokens or settings.LLM_MAX_TOKENS,
        }

        delays = [2, 5]
        for attempt in range(retries + 1):
            try:
                resp = self._client().post(url, headers=headers, json=payload)
                if resp.status_code == 200:
                    choice = resp.json()["choices"][0]
                    text = (choice.get("message", {}).get("content") or "").strip()
                    if not text:
                        # Reasoning models can spend the whole token budget on hidden "thinking",
                        # leaving `content` empty. The chain-of-thought is NOT a usable legal
                        # draft, so report a failure and let the caller fall back.
                        logger.warning(
                            f"LLM {self.model} returned empty content "
                            f"(finish_reason={choice.get('finish_reason')}); "
                            "consider raising LLM_MAX_TOKENS."
                        )
                        return None
                    return text
                if resp.status_code in (429, 500, 502, 503) and attempt < retries:
                    wait = resp.headers.get("retry-after")
                    wait_s = (
                        min(float(wait), 30.0)
                        if wait and str(wait).replace(".", "", 1).isdigit()
                        else delays[min(attempt, len(delays) - 1)]
                    )
                    logger.info(
                        f"LLM {self.model} returned {resp.status_code}, retrying in {wait_s}s..."
                    )
                    time.sleep(wait_s)
                    continue
                # Log status only - never the body or key.
                logger.warning(
                    f"LLM {self.model} returned {resp.status_code}, giving up."
                )
                return None
            except Exception as e:
                if attempt < retries:
                    logger.warning(f"LLM call failed ({type(e).__name__}), retrying...")
                    time.sleep(delays[min(attempt, len(delays) - 1)])
                    continue
                logger.warning(f"LLM call failed: {type(e).__name__}: {e}")
                return None
        return None


def build_default_clients() -> Dict[str, LLMClient]:
    """Build every configured provider client keyed by provider name.

    Priority order (first available wins unless MODEL_PROVIDER pins one):
      MODEL_PROVIDER == "hf"      -> HF Inference Providers
      MODEL_PROVIDER == "groq"    -> Groq
      MODEL_PROVIDER == "openai"  -> generic LLM_BASE_URL endpoint
      "auto"                      -> first of [generic, hf, groq] that is configured
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
