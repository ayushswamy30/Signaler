"""FastAPI application entry point."""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import register_error_handlers
from app.api.router import api_router
from app.core.config import settings
from app.schemas.common import ErrorResponse
from app.websocket import events
from app.websocket.routes import router as websocket_router

logging.basicConfig(level=logging.DEBUG if settings.debug else logging.INFO)

DESCRIPTION = """
A Signal-inspired messenger backend.

Every endpoint except `/api/health` and the `/api/auth` entry points requires a
bearer access token from `POST /api/auth/login`. Live updates -- incoming
messages, typing, presence, delivery receipts -- arrive on the `/ws` socket,
authenticated with the same token as a `token` query parameter.
"""


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Bind the running event loop so HTTP routes can push socket events.

    FastAPI runs synchronous route handlers in a worker thread, which has no
    event loop of its own. Recording the application's loop here is what lets
    ``events.publish`` hand a broadcast back to it from those threads.
    """
    events.bind_event_loop(asyncio.get_running_loop())
    try:
        yield
    finally:
        events.clear_event_loop()


app = FastAPI(
    title=settings.app_name,
    description=DESCRIPTION,
    version="1.0.0",
    debug=settings.debug,
    lifespan=lifespan,
    # Documents the single error shape on every operation, so the generated
    # OpenAPI file tells a client what a failure looks like without each route
    # having to repeat it.
    responses={
        400: {"model": ErrorResponse, "description": "Bad request"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        403: {"model": ErrorResponse, "description": "Not permitted"},
        404: {"model": ErrorResponse, "description": "Not found"},
        409: {"model": ErrorResponse, "description": "Conflict"},
    },
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)

app.include_router(api_router)
# Mounted at the root, not under /api: it is not an HTTP resource, and keeping
# it out of the API prefix keeps the OpenAPI document to HTTP endpoints only.
app.include_router(websocket_router)
