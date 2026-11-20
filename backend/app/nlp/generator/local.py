"""Local GGUF model generation (llama-cpp-python)."""

import asyncio
import logging
import os
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class LocalGenerator:
    """Generates legal drafts using local GGUF model via llama-cpp-python."""

    def __init__(self):
        self._llama = None
        self._loaded = False

    def _ensure_loaded(self) -> bool:
        """Load llama-cpp-python model if enabled and available."""
        if self._loaded:
            return self._llama is not None

        if not settings.ENABLE_LOCAL_LLM:
            logger.info("Local LLM disabled via settings")
            self._loaded = True
            return False

        model_path = settings.resolve_backend_path(settings.GGUF_MODEL_PATH)
        if not os.path.exists(model_path):
            logger.warning(f"GGUF model not found at {model_path}")
            self._loaded = True
            return False

        try:
            from llama_cpp import Llama

            logger.info(f"Loading GGUF model from {model_path}...")
            self._llama = Llama(
                model_path=model_path,
                n_ctx=settings.GGUF_CONTEXT_WINDOW,
                n_gpu_layers=settings.GGUF_GPU_LAYERS,
                verbose=False,
            )
            logger.info("GGUF model loaded successfully")
        except ImportError:
            logger.warning("llama-cpp-python not installed, local LLM unavailable")
        except Exception as e:
            logger.error(f"Failed to load GGUF model: {e}")

        self._loaded = True
        return self._llama is not None

    def is_available(self) -> bool:
        return self._ensure_loaded() and self._llama is not None

    def generate(self, prompt: str, max_tokens: int = 2048) -> Optional[str]:
        """Generate text using local GGUF model."""
        if not self._ensure_loaded() or self._llama is None:
            return None

        try:
            # Run in thread pool to avoid blocking event loop
            import concurrent.futures

            def _generate():
                return self._llama(
                    prompt,
                    max_tokens=max_tokens,
                    temperature=0.2,
                    top_p=0.9,
                    stop=["</s>", "<|endoftext|>"],
                    echo=False,
                )

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_generate)
                result = future.result(timeout=settings.LLM_TIMEOUT_SECONDS)

            text = result["choices"][0]["text"].strip()
            return text if text else None

        except Exception as e:
            logger.error(f"Local LLM generation failed: {e}")
            return None

    async def generate_async(self, prompt: str, max_tokens: int = 2048) -> Optional[str]:
        """Async wrapper for generate."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.generate, prompt, max_tokens)