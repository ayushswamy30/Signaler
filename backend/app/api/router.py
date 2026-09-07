"""Aggregates the API routers mounted under the /api prefix."""

from fastapi import APIRouter

from app.api import auth, contacts, conversations, groups, health, messages, users

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(contacts.router)
api_router.include_router(conversations.router)
api_router.include_router(messages.router)
api_router.include_router(groups.router)
