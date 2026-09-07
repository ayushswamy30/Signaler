"""Contact schemas."""

from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import ORMModel
from app.schemas.user import UserPublic


class ContactRead(ORMModel):
    """A saved contact, carrying the other user's profile inline."""

    contact_user: UserPublic
    created_at: datetime


class ContactCreate(BaseModel):
    """Save another user as a contact."""

    user_id: int
