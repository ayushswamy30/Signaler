"""Schemas for the health endpoint."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Response body returned by the health check."""

    status: str
    app_name: str
    environment: str
