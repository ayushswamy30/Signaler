"""Service-layer behaviour, exercised directly against the database."""

from datetime import timedelta

import pytest
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.models.conversation import ConversationType
from app.models.conversation_participant import ParticipantRole
from app.models.message_status import DeliveryStatus
from app.models.mixins import utcnow
from app.services import (
    auth_service,
    contact_service,
    conversation_service,
    group_service,
    message_service,
    user_service,
)
from tests.conftest import DEFAULT_PASSWORD


# --------------------------------------------------------------------------
# Users
# --------------------------------------------------------------------------


def test_usernames_are_case_insensitive(db_session: Session, alice):
    assert user_service.find_by_username(db_session, "ALICE").id == alice.id


def test_duplicate_username_is_a_conflict(db_session: Session, alice):
    with pytest.raises(ConflictError):
        user_service.create_user(
            db_session, username="Alice", password="whatever1", display_name="Impostor"
        )


def test_reserved_usernames_are_refused(db_session: Session):
    with pytest.raises(ValidationError):
        user_service.create_user(
            db_session, username="admin", password="whatever1", display_name="Admin"
        )


def test_duplicate_phone_number_is_a_conflict(db_session: Session, make_user):
    make_user("first", phone_number="+911111111")
    with pytest.raises(ConflictError):
        make_user("second", phone_number="+911111111")


def test_password_is_never_stored_in_the_clear(db_session: Session, alice):
    assert DEFAULT_PASSWORD not in alice.password_hash


def test_search_matches_username_display_name_and_phone(db_session: Session, alice, make_user):
    make_user("bhaskar", display_name="Bhaskar Rao", phone_number="+919000000")

    by_username = user_service.search_users(db_session, query="bhas", exclude_user_id=alice.id)
    by_display = user_service.search_users(db_session, query="rao", exclude_user_id=alice.id)
    by_phone = user_service.search_users(db_session, query="+919000000", exclude_user_id=alice.id)

    assert [u.username for u in by_username] == ["bhaskar"]
    assert [u.username for u in by_display] == ["bhaskar"]
    assert [u.username for u in by_phone] == ["bhaskar"]


def test_search_never_returns_the_searcher(db_session: Session, alice):
    assert user_service.search_users(db_session, query="alice", exclude_user_id=alice.id) == []


def test_blank_search_returns_nothing_rather_than_everyone(db_session: Session, alice, bob):
    assert user_service.search_users(db_session, query="   ", exclude_user_id=alice.id) == []


def test_changing_password_requires_the_current_one(db_session: Session, alice):
    with pytest.raises(ValidationError):
        user_service.change_password(
            db_session, alice, current_password="wrong", new_password="new-password-1"
        )


def test_changing_password_revokes_every_session(db_session: Session, alice):
    session = auth_service.issue_session(db_session, alice)
    user_service.change_password(
        db_session, alice, current_password=DEFAULT_PASSWORD, new_password="new-password-1"
    )
    with pytest.raises(AuthenticationError):
        auth_service.refresh_session(db_session, refresh_token=session.refresh_token)


def test_going_offline_stamps_last_seen(db_session: Session, alice):
    user_service.set_presence(db_session, alice, is_online=True)
    assert alice.last_seen is None
    user_service.set_presence(db_session, alice, is_online=False)
    assert alice.last_seen is not None


# --------------------------------------------------------------------------
# Authentication
# --------------------------------------------------------------------------


def test_authenticate_accepts_correct_credentials(db_session: Session, alice):
    assert auth_service.authenticate(
        db_session, username="alice", password=DEFAULT_PASSWORD
    ).id == alice.id


def test_unknown_user_and_wrong_password_give_the_same_message(db_session: Session, alice):
    """Otherwise the login form tells an attacker which usernames exist."""
    with pytest.raises(AuthenticationError) as missing:
        auth_service.authenticate(db_session, username="nobody", password="x" * 12)
    with pytest.raises(AuthenticationError) as wrong:
        auth_service.authenticate(db_session, username="alice", password="x" * 12)
    assert missing.value.message == wrong.value.message


def test_repeated_failures_lock_the_account(db_session: Session, alice):
    for _ in range(settings.max_failed_logins):
        with pytest.raises(AuthenticationError):
            auth_service.authenticate(db_session, username="alice", password="wrong-one")

    with pytest.raises(AuthenticationError) as locked:
        auth_service.authenticate(db_session, username="alice", password=DEFAULT_PASSWORD)
    assert "failed sign-in attempts" in locked.value.message


def test_a_successful_login_clears_the_failure_count(db_session: Session, alice):
    with pytest.raises(AuthenticationError):
        auth_service.authenticate(db_session, username="alice", password="wrong-one")
    auth_service.authenticate(db_session, username="alice", password=DEFAULT_PASSWORD)
    assert alice.failed_login_attempts == 0


def test_lock_expires_on_its_own(db_session: Session, alice):
    alice.locked_until = utcnow() - timedelta(seconds=1)
    db_session.commit()
    assert auth_service.authenticate(
        db_session, username="alice", password=DEFAULT_PASSWORD
    ).id == alice.id


def test_refresh_rotates_the_token(db_session: Session, alice):
    first = auth_service.issue_session(db_session, alice)
    second = auth_service.refresh_session(db_session, refresh_token=first.refresh_token)
    assert second.refresh_token != first.refresh_token


def test_a_refresh_token_cannot_be_replayed(db_session: Session, alice):
    first = auth_service.issue_session(db_session, alice)
    auth_service.refresh_session(db_session, refresh_token=first.refresh_token)
    with pytest.raises(AuthenticationError):
        auth_service.refresh_session(db_session, refresh_token=first.refresh_token)


def test_expired_refresh_token_is_refused(db_session: Session, alice):
    session = auth_service.issue_session(db_session, alice)
    stored = alice.refresh_tokens[-1]
    stored.expires_at = utcnow() - timedelta(seconds=1)
    db_session.commit()
    with pytest.raises(AuthenticationError):
        auth_service.refresh_session(db_session, refresh_token=session.refresh_token)


def test_logging_out_an_unknown_token_is_not_an_error(db_session: Session):
    """A client retrying a logout after a dropped response must not see a failure."""
    auth_service.revoke_session(db_session, refresh_token="never-issued")


def test_access_token_of_a_deleted_user_stops_working(db_session: Session, alice):
    token = auth_service.issue_session(db_session, alice).access_token
    db_session.delete(alice)
    db_session.commit()
    with pytest.raises(AuthenticationError):
        auth_service.user_from_access_token(db_session, token)


# --------------------------------------------------------------------------
# Contacts
# --------------------------------------------------------------------------


def test_contacts_are_one_way(db_session: Session, alice, bob):
    contact_service.add_contact(db_session, user_id=alice.id, contact_user_id=bob.id)
    assert contact_service.is_contact(db_session, user_id=alice.id, contact_user_id=bob.id)
    assert not contact_service.is_contact(db_session, user_id=bob.id, contact_user_id=alice.id)


def test_adding_the_same_contact_twice_is_a_conflict(db_session: Session, alice, bob):
    contact_service.add_contact(db_session, user_id=alice.id, contact_user_id=bob.id)
    with pytest.raises(ConflictError):
        contact_service.add_contact(db_session, user_id=alice.id, contact_user_id=bob.id)


def test_you_cannot_add_yourself(db_session: Session, alice):
    with pytest.raises(ValidationError):
        contact_service.add_contact(db_session, user_id=alice.id, contact_user_id=alice.id)


def test_adding_a_missing_user_is_a_clean_not_found(db_session: Session, alice):
    with pytest.raises(NotFoundError):
        contact_service.add_contact(db_session, user_id=alice.id, contact_user_id=9999)


def test_contacts_are_listed_by_display_name(db_session: Session, alice, make_user):
    zoe = make_user("zoe", display_name="Zoe Zachary")
    adam = make_user("adam", display_name="Adam Ant")
    for other in (zoe, adam):
        contact_service.add_contact(db_session, user_id=alice.id, contact_user_id=other.id)

    listed = contact_service.list_contacts(db_session, alice.id)
    assert [c.contact_user.display_name for c in listed] == ["Adam Ant", "Zoe Zachary"]


# --------------------------------------------------------------------------
# Conversations
# --------------------------------------------------------------------------


def test_opening_a_direct_conversation_twice_returns_the_same_one(db_session: Session, alice, bob):
    first = conversation_service.get_or_create_direct(
        db_session, user_id=alice.id, other_user_id=bob.id
    )
    second = conversation_service.get_or_create_direct(
        db_session, user_id=bob.id, other_user_id=alice.id
    )
    assert first.id == second.id


def test_a_two_person_group_is_not_mistaken_for_a_direct_conversation(
    db_session: Session, alice, bob
):
    group_service.create_group(
        db_session, creator_id=alice.id, name="Just us", member_ids=[bob.id]
    )
    direct = conversation_service.get_or_create_direct(
        db_session, user_id=alice.id, other_user_id=bob.id
    )
    assert direct.type is ConversationType.DIRECT


def test_you_cannot_open_a_conversation_with_yourself(db_session: Session, alice):
    with pytest.raises(ValidationError):
        conversation_service.get_or_create_direct(
            db_session, user_id=alice.id, other_user_id=alice.id
        )


def test_a_conversation_you_are_not_in_reads_as_missing(db_session: Session, alice, bob, carol):
    conversation = conversation_service.get_or_create_direct(
        db_session, user_id=alice.id, other_user_id=bob.id
    )
    # NotFound, not PermissionDenied: existence itself must not leak.
    with pytest.raises(NotFoundError):
        conversation_service.require_participant(
            db_session, conversation_id=conversation.id, user_id=carol.id
        )


def test_conversation_list_orders_by_most_recent_activity(db_session: Session, alice, bob, carol):
    older = conversation_service.get_or_create_direct(
        db_session, user_id=alice.id, other_user_id=bob.id
    )
    newer = conversation_service.get_or_create_direct(
        db_session, user_id=alice.id, other_user_id=carol.id
    )
    message_service.send_message(
        db_session, conversation_id=older.id, sender_id=bob.id, content="first"
    )
    message_service.send_message(
        db_session, conversation_id=newer.id, sender_id=carol.id, content="second"
    )

    listed = conversation_service.list_for_user(db_session, alice.id)
    assert [s.conversation.id for s in listed] == [newer.id, older.id]


def test_unread_count_ignores_your_own_messages(db_session: Session, alice, bob):
    conversation = conversation_service.get_or_create_direct(
        db_session, user_id=alice.id, other_user_id=bob.id
    )
    message_service.send_message(
        db_session, conversation_id=conversation.id, sender_id=alice.id, content="mine"
    )
    message_service.send_message(
        db_session, conversation_id=conversation.id, sender_id=bob.id, content="theirs"
    )

    summary = conversation_service.get_summary_for_user(
        db_session, conversation_id=conversation.id, user_id=alice.id
    )
    assert summary.unread_count == 1


def test_marking_read_clears_the_unread_count(db_session: Session, alice, bob):
    conversation = conversation_service.get_or_create_direct(
        db_session, user_id=alice.id, other_user_id=bob.id
    )
    message_service.send_message(
        db_session, conversation_id=conversation.id, sender_id=bob.id, content="hello"
    )
    message_service.mark_read(db_session, conversation_id=conversation.id, user_id=alice.id)

    summary = conversation_service.get_summary_for_user(
        db_session, conversation_id=conversation.id, user_id=alice.id
    )
    assert summary.unread_count == 0


def test_the_read_pointer_only_moves_forward(db_session: Session, alice, bob):
    conversation = conversation_service.get_or_create_direct(
        db_session, user_id=alice.id, other_user_id=bob.id
    )
    first = message_service.send_message(
        db_session, conversation_id=conversation.id, sender_id=bob.id, content="one"
    )
    second = message_service.send_message(
        db_session, conversation_id=conversation.id, sender_id=bob.id, content="two"
    )

    conversation_service.mark_read(
        db_session, conversation_id=conversation.id, user_id=alice.id,
        up_to_message_id=second.id,
    )
    participant = conversation_service.mark_read(
        db_session, conversation_id=conversation.id, user_id=alice.id,
        up_to_message_id=first.id,
    )
    assert participant.last_read_message_id == second.id


def test_marking_read_with_a_message_from_another_conversation_fails(
    db_session: Session, alice, bob, carol
):
    mine = conversation_service.get_or_create_direct(
        db_session, user_id=alice.id, other_user_id=bob.id
    )
    other = conversation_service.get_or_create_direct(
        db_session, user_id=alice.id, other_user_id=carol.id
    )
    elsewhere = message_service.send_message(
        db_session, conversation_id=other.id, sender_id=carol.id, content="hi"
    )
    with pytest.raises(NotFoundError):
        conversation_service.mark_read(
            db_session, conversation_id=mine.id, user_id=alice.id,
            up_to_message_id=elsewhere.id,
        )


def test_muting_is_per_member(db_session: Session, alice, bob):
    conversation = conversation_service.get_or_create_direct(
        db_session, user_id=alice.id, other_user_id=bob.id
    )
    conversation_service.set_muted(
        db_session, conversation_id=conversation.id, user_id=alice.id, muted=True
    )
    theirs = conversation_service.get_participant(
        db_session, conversation_id=conversation.id, user_id=bob.id
    )
    assert theirs.muted is False


def test_related_users_are_the_people_you_share_a_conversation_with(
    db_session: Session, alice, bob, carol
):
    conversation_service.get_or_create_direct(
        db_session, user_id=alice.id, other_user_id=bob.id
    )
    assert conversation_service.related_user_ids(db_session, alice.id) == {bob.id}


# --------------------------------------------------------------------------
# Messages
# --------------------------------------------------------------------------


@pytest.fixture
def pair(db_session: Session, alice, bob):
    """A direct conversation between alice and bob."""
    return conversation_service.get_or_create_direct(
        db_session, user_id=alice.id, other_user_id=bob.id
    )


def test_sending_creates_a_status_row_for_each_recipient_but_not_the_sender(
    db_session: Session, alice, pair
):
    message = message_service.send_message(
        db_session, conversation_id=pair.id, sender_id=alice.id, content="hello"
    )
    assert [status.user_id for status in message.statuses] != [alice.id]
    assert len(message.statuses) == 1
    assert message.statuses[0].status is DeliveryStatus.SENT


def test_an_outsider_cannot_send_into_a_conversation(db_session: Session, carol, pair):
    with pytest.raises(NotFoundError):
        message_service.send_message(
            db_session, conversation_id=pair.id, sender_id=carol.id, content="let me in"
        )


def test_empty_and_whitespace_messages_are_rejected(db_session: Session, alice, pair):
    with pytest.raises(ValidationError):
        message_service.send_message(
            db_session, conversation_id=pair.id, sender_id=alice.id, content="   \n "
        )


def test_oversized_messages_are_rejected(db_session: Session, alice, pair):
    with pytest.raises(ValidationError):
        message_service.send_message(
            db_session,
            conversation_id=pair.id,
            sender_id=alice.id,
            content="x" * (message_service.MAX_CONTENT_LENGTH + 1),
        )


def test_replying_across_conversations_is_refused(db_session: Session, alice, bob, carol, pair):
    other = conversation_service.get_or_create_direct(
        db_session, user_id=alice.id, other_user_id=carol.id
    )
    elsewhere = message_service.send_message(
        db_session, conversation_id=other.id, sender_id=alice.id, content="private"
    )
    with pytest.raises(NotFoundError):
        message_service.send_message(
            db_session,
            conversation_id=pair.id,
            sender_id=alice.id,
            content="quoting",
            reply_to_id=elsewhere.id,
        )


def test_history_is_returned_oldest_first(db_session: Session, alice, pair):
    for text in ("one", "two", "three"):
        message_service.send_message(
            db_session, conversation_id=pair.id, sender_id=alice.id, content=text
        )
    history = message_service.list_history(
        db_session, conversation_id=pair.id, user_id=alice.id
    )
    assert [m.content for m in history] == ["one", "two", "three"]


def test_history_pages_backwards_from_a_cursor(db_session: Session, alice, pair):
    sent = [
        message_service.send_message(
            db_session, conversation_id=pair.id, sender_id=alice.id, content=str(n)
        )
        for n in range(5)
    ]
    page = message_service.list_history(
        db_session, conversation_id=pair.id, user_id=alice.id, limit=2, before_id=sent[3].id
    )
    assert [m.content for m in page] == ["1", "2"]


def test_only_the_sender_may_edit(db_session: Session, alice, bob, pair):
    message = message_service.send_message(
        db_session, conversation_id=pair.id, sender_id=alice.id, content="mine"
    )
    with pytest.raises(PermissionDeniedError):
        message_service.edit_message(
            db_session, message_id=message.id, user_id=bob.id, content="tampered"
        )


def test_editing_stamps_edited_at(db_session: Session, alice, pair):
    message = message_service.send_message(
        db_session, conversation_id=pair.id, sender_id=alice.id, content="typo"
    )
    assert message.edited_at is None
    edited = message_service.edit_message(
        db_session, message_id=message.id, user_id=alice.id, content="fixed"
    )
    assert edited.edited_at is not None


def test_a_group_admin_may_delete_someone_elses_message(db_session: Session, alice, bob):
    group = group_service.create_group(
        db_session, creator_id=alice.id, name="Team", member_ids=[bob.id]
    )
    message = message_service.send_message(
        db_session, conversation_id=group.id, sender_id=bob.id, content="oops"
    )
    message_service.delete_message(db_session, message_id=message.id, user_id=alice.id)
    with pytest.raises(NotFoundError):
        message_service.get_message(db_session, message.id)


def test_a_member_may_not_delete_someone_elses_message(db_session: Session, alice, bob, pair):
    message = message_service.send_message(
        db_session, conversation_id=pair.id, sender_id=alice.id, content="mine"
    )
    with pytest.raises(PermissionDeniedError):
        message_service.delete_message(db_session, message_id=message.id, user_id=bob.id)


def test_deleting_a_quoted_message_leaves_the_reply_standing(db_session: Session, alice, bob, pair):
    original = message_service.send_message(
        db_session, conversation_id=pair.id, sender_id=alice.id, content="question"
    )
    reply = message_service.send_message(
        db_session,
        conversation_id=pair.id,
        sender_id=bob.id,
        content="answer",
        reply_to_id=original.id,
    )
    message_service.delete_message(db_session, message_id=original.id, user_id=alice.id)
    db_session.refresh(reply)
    assert reply.reply_to_id is None


def test_delivery_advances_from_sent_then_read(db_session: Session, alice, bob, pair):
    message = message_service.send_message(
        db_session, conversation_id=pair.id, sender_id=alice.id, content="hi"
    )
    assert message_service.aggregate_status(db_session, message) is DeliveryStatus.SENT

    message_service.mark_delivered(db_session, user_id=bob.id)
    assert message_service.aggregate_status(db_session, message) is DeliveryStatus.DELIVERED

    message_service.mark_read(db_session, conversation_id=pair.id, user_id=bob.id)
    assert message_service.aggregate_status(db_session, message) is DeliveryStatus.READ


def test_one_unread_recipient_holds_the_whole_group_message_back(db_session: Session, alice, bob, carol):
    group = group_service.create_group(
        db_session, creator_id=alice.id, name="Three", member_ids=[bob.id, carol.id]
    )
    message = message_service.send_message(
        db_session, conversation_id=group.id, sender_id=alice.id, content="everyone?"
    )
    message_service.mark_read(db_session, conversation_id=group.id, user_id=bob.id)
    assert message_service.aggregate_status(db_session, message) is DeliveryStatus.SENT


def test_marking_read_reports_only_the_statuses_it_changed(db_session: Session, alice, bob, pair):
    message_service.send_message(
        db_session, conversation_id=pair.id, sender_id=alice.id, content="hi"
    )
    first = message_service.mark_read(db_session, conversation_id=pair.id, user_id=bob.id)
    again = message_service.mark_read(db_session, conversation_id=pair.id, user_id=bob.id)
    assert len(first) == 1
    assert again == []


def test_unread_total_spans_conversations(db_session: Session, alice, bob, carol):
    for other in (bob, carol):
        conversation = conversation_service.get_or_create_direct(
            db_session, user_id=alice.id, other_user_id=other.id
        )
        message_service.send_message(
            db_session, conversation_id=conversation.id, sender_id=other.id, content="hi"
        )
    assert message_service.unread_total(db_session, alice.id) == 2


# --------------------------------------------------------------------------
# Groups
# --------------------------------------------------------------------------


def test_the_creator_becomes_an_admin(db_session: Session, alice, bob):
    group = group_service.create_group(
        db_session, creator_id=alice.id, name="Team", member_ids=[bob.id]
    )
    roles = {p.user_id: p.role for p in group.participants}
    assert roles[alice.id] is ParticipantRole.ADMIN
    assert roles[bob.id] is ParticipantRole.MEMBER


def test_a_group_needs_someone_other_than_its_creator(db_session: Session, alice):
    with pytest.raises(ValidationError):
        group_service.create_group(
            db_session, creator_id=alice.id, name="Just me", member_ids=[alice.id]
        )


def test_only_admins_may_rename_a_group(db_session: Session, alice, bob):
    group = group_service.create_group(
        db_session, creator_id=alice.id, name="Team", member_ids=[bob.id]
    )
    with pytest.raises(PermissionDeniedError):
        group_service.update_group(
            db_session, conversation_id=group.id, user_id=bob.id, name="Hijacked"
        )


def test_group_operations_refuse_direct_conversations(db_session: Session, alice, pair):
    with pytest.raises(ValidationError):
        group_service.update_group(
            db_session, conversation_id=pair.id, user_id=alice.id, name="Not a group"
        )


def test_adding_members_skips_those_already_in_the_group(db_session: Session, alice, bob, carol):
    group = group_service.create_group(
        db_session, creator_id=alice.id, name="Team", member_ids=[bob.id]
    )
    added = group_service.add_members(
        db_session, conversation_id=group.id, user_id=alice.id, member_ids=[bob.id, carol.id]
    )
    assert [p.user_id for p in added] == [carol.id]


def test_an_admin_cannot_remove_themselves_through_remove_member(db_session: Session, alice, bob):
    group = group_service.create_group(
        db_session, creator_id=alice.id, name="Team", member_ids=[bob.id]
    )
    with pytest.raises(ValidationError):
        group_service.remove_member(
            db_session, conversation_id=group.id, user_id=alice.id, member_id=alice.id
        )


def test_a_removed_members_messages_stay(db_session: Session, alice, bob):
    group = group_service.create_group(
        db_session, creator_id=alice.id, name="Team", member_ids=[bob.id]
    )
    message = message_service.send_message(
        db_session, conversation_id=group.id, sender_id=bob.id, content="history"
    )
    group_service.remove_member(
        db_session, conversation_id=group.id, user_id=alice.id, member_id=bob.id
    )
    assert message_service.get_message(db_session, message.id).content == "history"


def test_the_last_admin_cannot_be_demoted(db_session: Session, alice, bob):
    group = group_service.create_group(
        db_session, creator_id=alice.id, name="Team", member_ids=[bob.id]
    )
    with pytest.raises(ValidationError):
        group_service.change_role(
            db_session,
            conversation_id=group.id,
            user_id=alice.id,
            member_id=alice.id,
            role=ParticipantRole.MEMBER,
        )


def test_the_last_admin_leaving_hands_the_group_over(db_session: Session, alice, bob):
    group = group_service.create_group(
        db_session, creator_id=alice.id, name="Team", member_ids=[bob.id]
    )
    group_service.leave_group(db_session, conversation_id=group.id, user_id=alice.id)

    successor = conversation_service.get_participant(
        db_session, conversation_id=group.id, user_id=bob.id
    )
    assert successor.role is ParticipantRole.ADMIN


def test_the_last_member_leaving_deletes_the_group(db_session: Session, alice, bob):
    group = group_service.create_group(
        db_session, creator_id=alice.id, name="Team", member_ids=[bob.id]
    )
    message_service.send_message(
        db_session, conversation_id=group.id, sender_id=alice.id, content="bye"
    )
    for user in (alice, bob):
        group_service.leave_group(db_session, conversation_id=group.id, user_id=user.id)

    with pytest.raises(NotFoundError):
        conversation_service.get_conversation(db_session, group.id)


def test_members_are_listed_admins_first(db_session: Session, alice, bob, carol):
    group = group_service.create_group(
        db_session, creator_id=alice.id, name="Team", member_ids=[bob.id, carol.id]
    )
    members = group_service.list_members(
        db_session, conversation_id=group.id, user_id=alice.id
    )
    assert members[0].role is ParticipantRole.ADMIN


def test_an_outsider_cannot_list_members(db_session: Session, alice, bob, carol):
    group = group_service.create_group(
        db_session, creator_id=alice.id, name="Team", member_ids=[bob.id]
    )
    with pytest.raises(NotFoundError):
        group_service.list_members(db_session, conversation_id=group.id, user_id=carol.id)
