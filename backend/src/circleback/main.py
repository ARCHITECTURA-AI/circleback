"""FastAPI application entry point for Circle Back.

Configures structured JSON logging, CORS, rate limiting, session auth,
HTTPS redirect (production), and all API routers.
"""

from __future__ import annotations

import logging
import sys
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from circleback.api.auth import router as auth_router
from circleback.api.commitments import router as commitments_router
from circleback.api.health import router as health_router
from circleback.api.oauth import router as oauth_router
from circleback.api.persons import router as persons_router
from circleback.api.sync import router as sync_router
from circleback.config import get_settings

# ── Structured Logging ────────────────────────────────────────


def configure_logging(level: str = "INFO") -> None:
    """Configure structured logging with JSON-like format for production.

    Spec §10: Structured logging and error monitoring from day one.
    """
    formatter = logging.Formatter(
        fmt='{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}',
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Suppress noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


# ── Rate Limiting ─────────────────────────────────────────────

# Simple in-memory rate limiter — sufficient for a personal/portfolio project.
# For production scale, swap for redis-backed solution.
_rate_limit_store: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT_REQUESTS = 100  # per window
RATE_LIMIT_WINDOW = 60  # seconds


def _is_rate_limited(client_ip: str) -> bool:
    """Check if a client IP has exceeded the rate limit."""
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW

    # Clean old entries
    _rate_limit_store[client_ip] = [
        t for t in _rate_limit_store[client_ip] if t > window_start
    ]

    if len(_rate_limit_store[client_ip]) >= RATE_LIMIT_REQUESTS:
        return True

    _rate_limit_store[client_ip].append(now)
    return False


# ── App Factory ───────────────────────────────────────────────




if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: start optional scheduler on startup, clean up on shutdown."""
    from circleback.scheduler import start_scheduler
    start_scheduler()
    yield


def create_app() -> FastAPI:
    """Application factory — creates and configures the FastAPI app."""
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="Circle Back",
        description=(
            "A personal agent that tracks commitments made across email and Slack — "
            "yours and others' — and surfaces what's at risk before it becomes a broken promise."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_url],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── HTTPS Redirect Middleware (production only) ────────────
    @app.middleware("http")
    async def https_redirect_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        """Redirect HTTP to HTTPS when base_url is configured with https (spec §10).

        Only active in production (debug=False). Skips health checks.
        """
        if (
            not settings.debug
            and settings.base_url.startswith("https://")
            and request.url.scheme == "http"
            and request.url.path != "/health"
        ):
            https_url = str(request.url).replace("http://", "https://", 1)
            return RedirectResponse(url=https_url, status_code=301)
        return await call_next(request)

    # ── Rate Limiting Middleware ───────────────────────────────
    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        """Enforce rate limiting per client IP (spec §10)."""
        client_ip = request.client.host if request.client else "unknown"
        if _is_rate_limited(client_ip):
            return Response(
                content='{"detail":"Rate limit exceeded"}',
                status_code=429,
                media_type="application/json",
            )
        return await call_next(request)

    # ── Routers ───────────────────────────────────────────────
    app.include_router(health_router)
    app.include_router(commitments_router, prefix="/api/v1")
    app.include_router(persons_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(oauth_router, prefix="/api/v1")
    app.include_router(sync_router, prefix="/api/v1")

    return app


app = create_app()
