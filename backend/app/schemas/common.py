"""Shared schema building blocks."""

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    """Base for response schemas built directly from ORM objects.

    ``from_attributes`` is what lets ``Model.model_validate(orm_object)`` read
    attributes instead of dict keys, so routes can return ORM rows and let
    FastAPI serialise them.
    """

    model_config = ConfigDict(from_attributes=True)


class Message(BaseModel):
    """A bare human-readable acknowledgement.

    Used by endpoints whose only result is "that worked" -- deleting, leaving,
    logging out -- so they still return a body a client can display.
    """

    detail: str


class ErrorResponse(BaseModel):
    """The body every failing endpoint returns.

    A single shape means the frontend has one error path rather than one per
    status code. It matches FastAPI's own validation-error envelope key.
    """

    detail: str
