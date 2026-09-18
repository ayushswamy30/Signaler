"""Schema for an uploaded file."""

from pydantic import BaseModel


class UploadResult(BaseModel):
    """Where an uploaded file landed, for the client to attach to a message."""

    url: str
    name: str
    content_type: str
    size: int
