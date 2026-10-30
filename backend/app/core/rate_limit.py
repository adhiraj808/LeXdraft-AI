"""Rate limiter configuration."""
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request


def rate_limit_key_func(request: Request):
    """Key function that exempts health check from rate limiting."""
    # Exempt health check endpoints from rate limiting
    if request.url.path in ("/api/v1/health", "/health"):
        return None
    return get_remote_address(request)


# Shared rate limiter instance
limiter = Limiter(
    key_func=rate_limit_key_func,
    default_limits=["25/15minutes"],
    headers_enabled=True,
)

# Public rate limiter for public endpoints
public_limiter = Limiter(
    key_func=rate_limit_key_func,
    default_limits=["100/minute"],
    headers_enabled=True,
)
