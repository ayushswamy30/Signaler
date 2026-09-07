"""Aggregates the API routers mounted under the /api prefix."""

from fastapi import APIRouter

from app.api import health

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
