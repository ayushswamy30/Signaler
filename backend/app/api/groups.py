"""Group routes: creation and membership management.

A group is a conversation, so reading one -- its messages, its members, its
unread count -- goes through ``/conversations``. Only the operations that exist
solely for groups live here.
"""

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.common import Message as MessageResponse
from app.schemas.conversation import ConversationRead, ParticipantRead
from app.schemas.group import GroupCreate, GroupMembersAdd, GroupRoleUpdate, GroupUpdate
from app.schemas.message import MessageRead
from app.services import conversation_service, group_service, message_service
from app.websocket import broadcast

router = APIRouter(prefix="/groups", tags=["groups"])


def _render(db, conversation_id: int, user_id: int) -> ConversationRead:
    """The group as one member sees it, in the same shape as the list."""
    summary = conversation_service.get_summary_for_user(
        db, conversation_id=conversation_id, user_id=user_id
    )
    last = summary.last_message
    return ConversationRead.build(
        summary,
        MessageRead.build(last, message_service.aggregate_status(db, last)) if last else None,
    )


@router.post("", response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
def create_group(payload: GroupCreate, db: DbSession, current_user: CurrentUser) -> ConversationRead:
    """Create a group. The caller becomes its first admin."""
    conversation = group_service.create_group(
        db, creator_id=current_user.id, name=payload.name, member_ids=payload.member_ids
    )
    broadcast.conversation_created(db, conversation)
    return _render(db, conversation.id, current_user.id)


@router.patch("/{conversation_id}", response_model=ConversationRead)
def update_group(
    conversation_id: int, payload: GroupUpdate, db: DbSession, current_user: CurrentUser
) -> ConversationRead:
    """Rename a group or change its avatar. Admins only."""
    conversation = group_service.update_group(
        db,
        conversation_id=conversation_id,
        user_id=current_user.id,
        name=payload.name,
        avatar_url=payload.avatar_url,
    )
    broadcast.conversation_updated(db, conversation)
    return _render(db, conversation.id, current_user.id)


@router.post(
    "/{conversation_id}/members",
    response_model=list[ParticipantRead],
    status_code=status.HTTP_201_CREATED,
)
def add_members(
    conversation_id: int, payload: GroupMembersAdd, db: DbSession, current_user: CurrentUser
) -> list[ParticipantRead]:
    """Add members to a group. Admins only; users already in it are skipped."""
    added = group_service.add_members(
        db,
        conversation_id=conversation_id,
        user_id=current_user.id,
        member_ids=payload.member_ids,
    )
    conversation = conversation_service.get_conversation(db, conversation_id)
    broadcast.members_added(db, conversation, added)
    return [ParticipantRead.model_validate(participant) for participant in added]


@router.delete("/{conversation_id}/members/{member_id}", response_model=MessageResponse)
def remove_member(
    conversation_id: int, member_id: int, db: DbSession, current_user: CurrentUser
) -> MessageResponse:
    """Remove someone from a group. Admins only."""
    group_service.remove_member(
        db, conversation_id=conversation_id, user_id=current_user.id, member_id=member_id
    )
    broadcast.member_removed(db, conversation_id=conversation_id, member_id=member_id)
    return MessageResponse(detail="Member removed.")


@router.patch("/{conversation_id}/members/{member_id}", response_model=ParticipantRead)
def change_role(
    conversation_id: int,
    member_id: int,
    payload: GroupRoleUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> ParticipantRead:
    """Promote a member to admin, or demote one. Admins only."""
    participant = group_service.change_role(
        db,
        conversation_id=conversation_id,
        user_id=current_user.id,
        member_id=member_id,
        role=payload.role,
    )
    broadcast.role_changed(
        db, conversation_id=conversation_id, member_id=member_id, role=payload.role
    )
    return ParticipantRead.model_validate(participant)


@router.post("/{conversation_id}/leave", response_model=MessageResponse)
def leave_group(
    conversation_id: int, db: DbSession, current_user: CurrentUser
) -> MessageResponse:
    """Leave a group. The last member out deletes it."""
    group_service.leave_group(db, conversation_id=conversation_id, user_id=current_user.id)
    broadcast.member_removed(db, conversation_id=conversation_id, member_id=current_user.id)
    return MessageResponse(detail="You left the group.")
