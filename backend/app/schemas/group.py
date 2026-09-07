"""Group management schemas."""

from pydantic import BaseModel, Field

from app.models.conversation_participant import ParticipantRole


class GroupCreate(BaseModel):
    """A new group and its initial membership.

    The creator is not listed: the service adds them as admin, and accepting
    them here would let a client create a group it does not belong to.
    """

    name: str = Field(min_length=1, max_length=100)
    member_ids: list[int] = Field(min_length=1)


class GroupUpdate(BaseModel):
    """Rename a group or change its avatar. Omitted fields are left alone."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    avatar_url: str | None = Field(default=None, max_length=512)


class GroupMembersAdd(BaseModel):
    """Users to add to an existing group."""

    member_ids: list[int] = Field(min_length=1)


class GroupRoleUpdate(BaseModel):
    """Promote or demote a member."""

    role: ParticipantRole
