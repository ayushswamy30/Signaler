"""Message routes for operations on an existing message.

Sending and listing live under ``/conversations/{id}/messages``, because they
are scoped to a conversation. Editing and deleting address one message by its
own id, so they belong here.
"""

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.common import Message as MessageResponse
from app.schemas.message import MessageRead, MessageUpdate
from app.services import message_service
from app.websocket import broadcast

router = APIRouter(prefix="/messages", tags=["messages"])


@router.patch("/{message_id}", response_model=MessageRead)
def edit_message(
    message_id: int, payload: MessageUpdate, db: DbSession, current_user: CurrentUser
) -> MessageRead:
    """Change the text of a message you sent."""
    message = message_service.edit_message(
        db, message_id=message_id, user_id=current_user.id, content=payload.content
    )
    broadcast.message_updated(db, message)
    return MessageRead.build(message, message_service.aggregate_status(db, message))


@router.delete("/{message_id}", response_model=MessageResponse)
def delete_message(message_id: int, db: DbSession, current_user: CurrentUser) -> MessageResponse:
    """Delete a message you sent, or -- as a group admin -- anyone's."""
    conversation_id = message_service.delete_message(
        db, message_id=message_id, user_id=current_user.id
    )
    broadcast.message_deleted(db, conversation_id=conversation_id, message_id=message_id)
    return MessageResponse(detail="Message deleted.")
