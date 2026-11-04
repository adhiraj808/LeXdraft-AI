"""Small pure-ASGI middlewares.

They replace Starlette's ``BaseHTTPMiddleware``/``@app.middleware("http")`` versions:
those wrap every response in an extra streaming layer (more memory and latency per
request) and can only look at the ``Content-Length`` header, not at the real body.
"""

import uuid
from typing import Iterable, Tuple

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class RequestContextMiddleware:
    """Adds ``X-Request-ID`` (also exposed as ``request.state.request_id``) and basic hardening headers."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Request-ID"] = request_id
                headers.setdefault("X-Content-Type-Options", "nosniff")
                headers.setdefault("Referrer-Policy", "no-referrer")
                # API responses carry per-user legal data: never let a shared cache keep them.
                headers.setdefault("Cache-Control", "no-store")
            await send(message)

        await self.app(scope, receive, send_with_headers)


class HostGuardMiddleware:
    """Rejects requests whose ``Host`` header is not whitelisted (Host-header attacks).

    Unlike Starlette's TrustedHostMiddleware it can exempt paths, which is required
    for load-balancer health checks: AWS ALB/ELB probe targets by IP address, so the
    Host header is the container's private IP, which can never be whitelisted.
    """

    def __init__(
        self,
        app: ASGIApp,
        allowed_hosts: Iterable[str],
        exempt_paths: Iterable[str] = (),
    ) -> None:
        self.app = app
        hosts = [h.strip().lower() for h in allowed_hosts if h and h.strip()]
        self.allow_any = "*" in hosts
        self.exact = {h for h in hosts if not h.startswith("*.")}
        self.suffixes: Tuple[str, ...] = tuple(
            h[1:] for h in hosts if h.startswith("*.")
        )  # ".example.com"
        self.exempt_paths = frozenset(exempt_paths)

    def _is_allowed(self, host: str) -> bool:
        if host in self.exact:
            return True
        return any(host.endswith(suffix) for suffix in self.suffixes)

    @staticmethod
    def _hostname(raw_host: str) -> str:
        raw_host = raw_host.strip().lower()
        if raw_host.startswith("["):  # IPv6 literal: [::1]:8000
            return raw_host[: raw_host.find("]") + 1] if "]" in raw_host else raw_host
        return raw_host.split(":", 1)[0]

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or self.allow_any
            or scope.get("path") in self.exempt_paths
        ):
            await self.app(scope, receive, send)
            return

        host = self._hostname(Headers(scope=scope).get("host", ""))
        if self._is_allowed(host):
            await self.app(scope, receive, send)
            return

        await PlainTextResponse("Invalid host header", status_code=400)(
            scope, receive, send
        )


class BodySizeLimitMiddleware:
    """Rejects request bodies larger than ``max_bytes`` with HTTP 413.

    The ``Content-Length`` header is checked first (cheap, rejects before reading anything).
    Chunked uploads have no such header, so the bytes are also counted while the app reads them.
    """

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        declared = Headers(scope=scope).get("content-length")
        if declared is not None:
            try:
                too_large = int(declared) > self.max_bytes
            except ValueError:
                await PlainTextResponse(
                    "Invalid Content-Length header", status_code=400
                )(scope, receive, send)
                return
            if too_large:
                await PlainTextResponse("Payload too large", status_code=413)(
                    scope, receive, send
                )
                return

        received = 0
        rejected = False

        async def limited_receive() -> Message:
            nonlocal received, rejected
            message = await receive()
            if message["type"] == "http.request" and not rejected:
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    rejected = True
                    await PlainTextResponse("Payload too large", status_code=413)(
                        scope, receive, send
                    )
                    # Make the app see a dropped connection instead of a truncated body.
                    return {"type": "http.disconnect"}
            return message

        async def guarded_send(message: Message) -> None:
            if rejected:  # the 413 is already on the wire; ignore whatever the app tries to send now
                return
            await send(message)

        await self.app(scope, limited_receive, guarded_send)
