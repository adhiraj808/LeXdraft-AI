"""Rate limiter configuration (slowapi).

Design:
  * ONE limiter. Endpoints without their own ``@limiter.limit(...)`` get a generous
    default (RATE_LIMIT_DEFAULT); expensive or abuse-prone endpoints (login, LLM
    calls) declare a stricter limit explicitly.
  * Authenticated requests are counted per user, everything else per client IP.
    Behind a reverse proxy (nginx, AWS ALB) run uvicorn with ``--proxy-headers`` and
    ``FORWARDED_ALLOW_IPS`` set to the proxy address so ``request.client`` is the
    real client and not the proxy.
  * Health checks are exempted with ``@limiter.exempt`` on the route.
"""

import logging

from limits import parse_many
from slowapi import Limiter
from starlette.requests import Request

from app.core.config import settings

logger = logging.getLogger(__name__)


def get_client_ip(request: Request) -> str:
    client = request.client
    return client.host if client and client.host else "unknown"


def rate_limit_key(request: Request) -> str:
    """Per-user bucket once the user is authenticated, per-IP otherwise."""
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"user:{user_id}"
    return f"ip:{get_client_ip(request)}"


def _validate_limits() -> None:
    """Fail at startup (not on the first request) if a limit string is malformed."""
    for name in (
        "RATE_LIMIT_DEFAULT",
        "RATE_LIMIT_AUTH",
        "RATE_LIMIT_DRAFTS",
        "RATE_LIMIT_QA",
        "RATE_LIMIT_PUBLIC_QA",
    ):
        value = getattr(settings, name)
        try:
            parse_many(value)
        except ValueError as exc:
            raise RuntimeError(
                f"{name}={value!r} is not a valid rate limit (example: '10/minute')"
            ) from exc


_validate_limits()

limiter = Limiter(
    key_func=rate_limit_key,
    default_limits=[settings.RATE_LIMIT_DEFAULT],
    storage_uri=settings.RATE_LIMIT_STORAGE_URI,
    # Header injection requires every endpoint to accept a `response` parameter or
    # return a Response object; it is not worth the fragility here.
    headers_enabled=False,
    # If the storage backend (Redis) is down, let requests through instead of failing them.
    swallow_errors=True,
)

# Backwards-compatible alias: older modules imported `public_limiter`.
public_limiter = limiter
