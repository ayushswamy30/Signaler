"""Conversation schemas."""

from datetime import datetime

from pydantic import BaseModel

from app.models.conversation import ConversationType
from app.models.conversation_participant import ParticipantRole
from app.schemas.common import ORMModel
from app.schemas.message import MessageRead
from app.schemas.user import UserPublic


class ParticipantRead(ORMModel):
    """One member of a conversation."""

    user: UserPublic
    role: ParticipantRole
    joined_at: datetime


class ConversationRead(BaseModel):
    """A conversation as one particular viewer sees it.

    Deliberately viewer-relative: ``unread_count``, ``muted`` and ``my_role``
    differ per member, so this is never a cacheable description of the
    conversation itself. Direct conversations carry no name -- the client
    labels them with the other participant, who is in ``participants``.
    """

    id: int
    type: ConversationType
    name: str | None
    avatar_url: str | None
    participants: list[ParticipantRead]
    last_message: MessageRead | None
    unread_count: int
    muted: bool
    my_role: ParticipantRole
    created_at: datetime
    updated_at: datetime

    @classmethod
    def build(cls, summary, last_message: MessageRead | None) -> "ConversationRead":
        """Assemble the response from a service-layer ConversationSummary."""
        conversation = summary.conversation
        return cls(
            id=conversation.id,
            type=conversation.type,
            name=conversation.name,
            avatar_url=conversation.avatar_url,
            participants=[
                ParticipantRead.model_validate(participant)
                for participant in conversation.participants
            ],
            last_message=last_message,
            unread_count=summary.unread_count,
            muted=summary.participant.muted,
            my_role=summary.participant.role,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
        )


class DirectConversationCreate(BaseModel):
    """Open (or reopen) the one-to-one conversation with another user."""

    user_id: int


class MuteUpdate(BaseModel):
    """Mute or unmute a conversation, for the caller only."""

    muted: bool
