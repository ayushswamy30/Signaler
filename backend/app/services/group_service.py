"""Group conversations: creation, membership, roles, and leaving.

Direct conversations are handled entirely by ``conversation_service``; every
function here refuses to touch one, because a direct conversation has no admin
and its two-person membership is fixed by definition.
"""

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, ValidationError
from app.models.conversation import Conversation, ConversationType
from app.models.conversation_participant import ConversationParticipant, ParticipantRole
from app.services import conversation_service, user_service

MAX_GROUP_MEMBERS = 256


def _require_group(db: Session, conversation_id: int) -> Conversation:
    """Load a conversation and refuse if it is not a group."""
    conversation = conversation_service.get_conversation(db, conversation_id)
    if conversation.type is not ConversationType.GROUP:
        raise ValidationError("That conversation is not a group.")
    return conversation


def _clean_name(name: str) -> str:
    name = name.strip()
    if not name:
        raise ValidationError("A group needs a name.")
    if len(name) > 100:
        raise ValidationError("A group name cannot exceed 100 characters.")
    return name


def create_group(
    db: Session, *, creator_id: int, name: str, member_ids: list[int]
) -> Conversation:
    """Create a group with its creator as admin.

    The creator is always included and always an admin: a group that nobody can
    administer cannot add members, rename itself, or recover.
    """
    name = _clean_name(name)

    # Deduplicated, and the creator removed, before counting -- so passing
    # yourself in the member list is harmless rather than an error.
    members = {user_id for user_id in member_ids if user_id != creator_id}
    if not members:
        raise ValidationError("A group needs at least one other member.")
    if len(members) + 1 > MAX_GROUP_MEMBERS:
        raise ValidationError(f"A group cannot exceed {MAX_GROUP_MEMBERS} members.")
    for user_id in members:
        user_service.get_user(db, user_id)

    conversation = Conversation(type=ConversationType.GROUP, name=name)
    conversation.participants = [
        ConversationParticipant(user_id=creator_id, role=ParticipantRole.ADMIN),
        *(ConversationParticipant(user_id=user_id) for user_id in sorted(members)),
    ]
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def update_group(
    db: Session,
    *,
    conversation_id: int,
    user_id: int,
    name: str | None = None,
    avatar_url: str | None = None,
) -> Conversation:
    """Rename a group or change its avatar. Admins only."""
    conversation = _require_group(db, conversation_id)
    conversation_service.require_admin(db, conversation_id=conversation_id, user_id=user_id)

    if name is not None:
        conversation.name = _clean_name(name)
    if avatar_url is not None:
        conversation.avatar_url = avatar_url.strip() or None

    db.commit()
    db.refresh(conversation)
    return conversation


def add_members(
    db: Session, *, conversation_id: int, user_id: int, member_ids: list[int]
) -> list[ConversationParticipant]:
    """Add users to a group. Admins only.

    Users already in the group are skipped rather than rejected: adding four
    people of whom one is already a member should add the other three, not fail
    the whole request.
    """
    _require_group(db, conversation_id)
    conversation_service.require_admin(db, conversation_id=conversation_id, user_id=user_id)

    existing = set(conversation_service.participant_ids(db, conversation_id))
    to_add = [candidate for candidate in dict.fromkeys(member_ids) if candidate not in existing]
    if not to_add:
        raise ConflictError("Those users are already in this group.")
    if len(existing) + len(to_add) > MAX_GROUP_MEMBERS:
        raise ValidationError(f"A group cannot exceed {MAX_GROUP_MEMBERS} members.")

    added = [
        conversation_service.add_participant(
            db, conversation_id=conversation_id, user_id=candidate, commit=False
        )
        for candidate in to_add
    ]
    db.commit()
    return added


def remove_member(db: Session, *, conversation_id: int, user_id: int, member_id: int) -> None:
    """Remove someone from a group. Admins only; leaving is a separate call.

    Messages the removed member sent stay in the conversation. Their history is
    part of the group's history, and the sender foreign key is RESTRICT for
    exactly that reason.
    """
    _require_group(db, conversation_id)
    conversation_service.require_admin(db, conversation_id=conversation_id, user_id=user_id)
    if member_id == user_id:
        raise ValidationError("Use leave_group to remove yourself.")

    participant = conversation_service.require_participant(
        db, conversation_id=conversation_id, user_id=member_id
    )
    db.delete(participant)
    db.commit()


def change_role(
    db: Session, *, conversation_id: int, user_id: int, member_id: int, role: ParticipantRole
) -> ConversationParticipant:
    """Promote a member to admin, or demote an admin. Admins only."""
    _require_group(db, conversation_id)
    conversation_service.require_admin(db, conversation_id=conversation_id, user_id=user_id)
    participant = conversation_service.require_participant(
        db, conversation_id=conversation_id, user_id=member_id
    )

    if (
        participant.role is ParticipantRole.ADMIN
        and role is ParticipantRole.MEMBER
        and _admin_count(db, conversation_id) == 1
    ):
        raise ValidationError("A group must keep at least one admin.")

    participant.role = role
    db.commit()
    db.refresh(participant)
    return participant


def _admin_count(db: Session, conversation_id: int) -> int:
    return (
        db.scalar(
            select(func.count(ConversationParticipant.user_id)).where(
                ConversationParticipant.conversation_id == conversation_id,
                ConversationParticipant.role == ParticipantRole.ADMIN,
            )
        )
        or 0
    )


def leave_group(db: Session, *, conversation_id: int, user_id: int) -> None:
    """Leave a group.

    Anyone may leave, including the last admin -- being unable to leave a group
    would be worse than a group temporarily without one. The last member out
    deletes the group, which cascades to its messages: an empty group nobody
    can rejoin is not worth keeping.
    """
    conversation = _require_group(db, conversation_id)
    participant = conversation_service.require_participant(
        db, conversation_id=conversation_id, user_id=user_id
    )

    remaining = [
        other for other in conversation.participants if other.user_id != participant.user_id
    ]
    # Counted before the delete: the first query after db.delete() autoflushes
    # it, and the leaver would no longer be in the count.
    was_last_admin = (
        participant.role is ParticipantRole.ADMIN and _admin_count(db, conversation_id) == 1
    )
    db.delete(participant)

    if not remaining:
        db.delete(conversation)
    elif was_last_admin:
        # Hand the room over rather than orphaning it: the longest-standing
        # remaining member becomes admin.
        successor = min(remaining, key=lambda p: (p.joined_at, p.user_id))
        successor.role = ParticipantRole.ADMIN

    db.commit()


def list_members(db: Session, *, conversation_id: int, user_id: int) -> list[ConversationParticipant]:
    """The membership of a conversation, visible only to its own members."""
    conversation_service.require_participant(db, conversation_id=conversation_id, user_id=user_id)
    # Ordering on the role column directly would sort its stored strings, and
    # "member" happens to sort after "admin" -- so a plain descending sort puts
    # members first. The CASE states the intended precedence instead.
    admins_first = case((ConversationParticipant.role == ParticipantRole.ADMIN, 0), else_=1)
    statement = (
        select(ConversationParticipant)
        .where(ConversationParticipant.conversation_id == conversation_id)
        .order_by(admins_first, ConversationParticipant.joined_at)
    )
    return list(db.scalars(statement))


def require_group_membership(db: Session, *, conversation_id: int, user_id: int) -> Conversation:
    """Load a group the caller belongs to, or raise. Used by the group routes."""
    conversation = _require_group(db, conversation_id)
    conversation_service.require_participant(db, conversation_id=conversation_id, user_id=user_id)
    return conversation
