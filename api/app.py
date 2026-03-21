from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles

from newsnet.config import NewsnetConfig
from api.websocket import WebSocketHub

log = logging.getLogger(__name__)


def _make_lifespan(node, hub: WebSocketHub):
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # node.start() and node.start_sync_loop() were already called in the
        # main thread before uvicorn started (signal.signal requires main thread).
        app.state.startup_state = "ready"
        await hub.broadcast({"type": "node_ready"})
        log.info("Node ready — API fully operational")
        yield
        node.shutdown()

    return lifespan


def create_app(
    config: NewsnetConfig,
    node,
    hub: WebSocketHub,
    startup_state: Literal["starting", "ready"] = "starting",
    _lifespan_enabled: bool = True,
) -> FastAPI:
    """Create the FastAPI app.

    In production: startup_state="starting", _lifespan_enabled=True (default).
    In tests: pass startup_state="ready", _lifespan_enabled=False to skip
    node.start() and keep the app immediately operational.
    For the 503 test: pass startup_state="starting", _lifespan_enabled=False.
    """
    lifespan = _make_lifespan(node, hub) if _lifespan_enabled else None
    app = FastAPI(title="ReticulumNewsnet", lifespan=lifespan)
    app.state.config = config
    app.state.node = node
    app.state.hub = hub
    app.state.startup_state = startup_state

    # 503 middleware for /api/* during startup
    @app.middleware("http")
    async def startup_guard(request: Request, call_next):
        if (
            request.url.path.startswith("/api/")
            and app.state.startup_state == "starting"
        ):
            return Response(
                content='{"error":"starting up"}',
                status_code=503,
                media_type="application/json",
            )
        return await call_next(request)

    # Register route modules (stubs for now — filled in later tasks)
    from api.routes import groups, articles, peers, sync_route, filters, identity, config_route
    app.include_router(identity.router, prefix="/api")
    app.include_router(config_route.router, prefix="/api")
    app.include_router(groups.router, prefix="/api")
    app.include_router(articles.router, prefix="/api")
    app.include_router(peers.router, prefix="/api")
    app.include_router(sync_route.router, prefix="/api")
    app.include_router(filters.router, prefix="/api")

    # Localhost-only token endpoint — lets browser auto-connect without manual entry
    @app.get("/api/local-auth")
    async def local_auth(request: Request):
        if request.client and request.client.host not in ("127.0.0.1", "::1"):
            raise HTTPException(status_code=403, detail="local connections only")
        return {"token": request.app.state.config.api_token}

    # WebSocket endpoint (not subject to 503 guard — /ws not /api/*)
    from api.routes import websocket_route
    app.include_router(websocket_route.router)

    # Serve compiled Svelte frontend
    dist = Path(__file__).parent.parent / "frontend" / "dist"
    if dist.exists():
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="static")

    return app
