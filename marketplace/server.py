"""FastAPI marketplace server entry point.

Run with:
    uvicorn marketplace.server:app --host 127.0.0.1 --port 8001
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from marketplace.routes.apps import router as apps_router
from marketplace.routes.bids import router as bids_router
from marketplace.routes.settle import router as settle_router
from marketplace.routes.treasury import router as treasury_router
from marketplace.x402_middleware import X402InsertionFeeMiddleware
from shared.config import get_settings
from shared.db import close_db, init_db
from shared.logging import get_logger, setup_logging


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    setup_logging()
    log = get_logger("marketplace.server")
    settings = get_settings()
    log.info(
        "marketplace starting host=%s port=%s db=%s",
        settings.marketplace_host,
        settings.marketplace_port,
        settings.database_url,
    )
    facilitator_mode = settings.x402_facilitator_mode.strip().lower()
    log.info(
        "x402 facilitator mode=%s url=%s",
        facilitator_mode,
        settings.x402_facilitator_url if facilitator_mode == "remote" else "(local in-process)",
    )
    await init_db()
    try:
        yield
    finally:
        await close_db()
        log.info("marketplace stopped")


def create_app() -> FastAPI:
    fastapi_app = FastAPI(
        title="Credit App+ Marketplace",
        version="0.1.0",
        lifespan=lifespan,
    )
    fastapi_app.add_middleware(X402InsertionFeeMiddleware)
    fastapi_app.include_router(apps_router)
    fastapi_app.include_router(bids_router)
    fastapi_app.include_router(settle_router)
    fastapi_app.include_router(treasury_router)
    return fastapi_app


app = create_app()


@app.get("/healthz", tags=["meta"])
async def healthz() -> dict[str, str]:
    return {"status": "ok"}
