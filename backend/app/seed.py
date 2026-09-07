"""Development seed data.

Run with ``python -m app.seed`` after ``alembic upgrade head``. It creates a
small cast of accounts with contacts, two group conversations and enough
history that every part of the UI -- unread badges, read receipts, replies,
edits, an empty conversation -- has something real to render.

Idempotent: it does nothing if the database already has users, unless ``--reset``
is passed, which deletes the seeded data first. It never touches a database
outside development; see ``_guard``.
"""

import argparse
import sys
from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.database import SessionLocal
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.models.conversation_participant import ConversationParticipant
from app.models.message import Message
from app.models.message_status import MessageStatus
from app.models.mixins import utcnow
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.services import (
    contact_service,
    conversation_service,
    group_service,
    message_service,
    user_service,
)

# The same password for every seeded account, so a developer only has to
# remember one. Nothing here is ever meant to reach a real deployment.
SEED_PASSWORD = "signaler123"

PEOPLE = [
    ("ayush", "Ayush Swamy", "+911234500001", "Building Signaler."),
    ("priya", "Priya Nair", "+911234500002", "Designer. Tea, not coffee."),
    ("maya", "Maya Iyer", "+911234500003", "Design systems."),
    ("devsharma", "Dev Sharma", "+911234500004", "Frontend."),
    ("rohan", "Rohan Mehta", "+911234500005", None),
    ("aditi", "Aditi Rao", "+911234500006", "Away from keyboard."),
    ("karan", "Karan Singh", "+911234500007", None),
]

# (sender username, text, optional "reply to the Nth message in this thread").
DIRECT_THREADS: dict[str, list[tuple[str, str, int | None]]] = {
    "priya": [
        ("priya", "Are we still on for dinner tonight?", None),
        ("ayush", "Yes — 7pm at the usual place.", None),
        ("ayush", "I booked a table under my name.", None),
        ("priya", "Perfect. I'll head straight from the office.", 1),
        ("priya", "See you at 7 then", None),
    ],
    "rohan": [
        ("rohan", "Do you have the deployment notes from Friday?", None),
        ("ayush", "Sent them to your inbox just now.", None),
        ("rohan", "Thanks, that helps", None),
    ],
    "aditi": [
        ("aditi", "Can you check the draft when you get a minute?", None),
    ],
    "karan": [
        ("karan", "Are you joining the standup tomorrow?", None),
        ("ayush", "Yes, I'll be there.", None),
        ("karan", "Sounds good to me", None),
    ],
}

GROUPS: list[tuple[str, list[str], list[tuple[str, str]]]] = [
    (
        "Design Guild",
        ["maya", "devsharma", "priya", "rohan"],
        [
            ("ayush", "Did the new tokens land?"),
            ("maya", "Pushed the new tokens to the shared library."),
            ("maya", "Light and dark are both covered."),
            ("devsharma", "Nice — I'll rebind the components this afternoon."),
        ],
    ),
    (
        "Weekend Plans",
        ["priya", "karan", "aditi"],
        [
            ("priya", "Trek on Saturday, or the beach?"),
            ("karan", "Trek. The weather is finally reasonable."),
        ],
    ),
]


def _guard() -> None:
    """Refuse to run outside development.

    Seeding writes fabricated accounts with a published password. Doing that to
    a production database would be an incident, so the environment is checked
    before anything is written rather than being left to the operator.
    """
    if settings.environment.lower() not in {"development", "dev", "test", "local"}:
        sys.exit(
            f"Refusing to seed: ENVIRONMENT is {settings.environment!r}, not development."
        )


def _reset(db: Session) -> None:
    """Delete everything the seed creates, in foreign-key order.

    Children first: messages reference users with ON DELETE RESTRICT, so a
    user deleted before their messages would be refused by the database.
    """
    for model in (
        MessageStatus,
        RefreshToken,
        Contact,
        Message,
        ConversationParticipant,
        Conversation,
        User,
    ):
        db.execute(delete(model))
    db.commit()


def _create_people(db: Session) -> dict[str, User]:
    users: dict[str, User] = {}
    for username, display_name, phone, about in PEOPLE:
        user = user_service.create_user(
            db,
            username=username,
            password=SEED_PASSWORD,
            display_name=display_name,
            phone_number=phone,
        )
        if about:
            user_service.update_profile(db, user, about=about)
        users[username] = user
    return users


def _link_contacts(db: Session, users: dict[str, User]) -> None:
    """Everyone saves everyone else.

    A dense contact graph is the useful case for a development database: it
    means the "new message" picker and the contact list are never empty
    whichever account you sign in as.
    """
    for owner in users.values():
        for other in users.values():
            if owner.id != other.id:
                contact_service.add_contact(
                    db, user_id=owner.id, contact_user_id=other.id
                )


def _seed_direct(db: Session, users: dict[str, User]) -> None:
    me = users["ayush"]
    for partner_username, script in DIRECT_THREADS.items():
        conversation = conversation_service.get_or_create_direct(
            db, user_id=me.id, other_user_id=users[partner_username].id
        )
        sent: list[Message] = []
        for sender_username, text, reply_index in script:
            sent.append(
                message_service.send_message(
                    db,
                    conversation_id=conversation.id,
                    sender_id=users[sender_username].id,
                    content=text,
                    reply_to_id=sent[reply_index].id if reply_index is not None else None,
                )
            )

        # An edited message, so the "edited" affordance has something to show.
        if partner_username == "priya":
            message_service.edit_message(
                db,
                message_id=sent[2].id,
                user_id=me.id,
                content="I booked a table under my name — corner seat.",
            )

        # Read state: caught up on most threads, deliberately behind on two so
        # the conversation list shows unread badges.
        if partner_username not in {"aditi", "karan"}:
            message_service.mark_read(
                db, conversation_id=conversation.id, user_id=me.id
            )
        message_service.mark_read(
            db, conversation_id=conversation.id, user_id=users[partner_username].id
        )

    # One conversation with no messages at all, for the empty-thread state.
    conversation_service.get_or_create_direct(
        db, user_id=me.id, other_user_id=users["devsharma"].id
    )


def _seed_groups(db: Session, users: dict[str, User]) -> None:
    me = users["ayush"]
    for name, member_usernames, script in GROUPS:
        conversation = group_service.create_group(
            db,
            creator_id=me.id,
            name=name,
            member_ids=[users[username].id for username in member_usernames],
        )
        for sender_username, text in script:
            message_service.send_message(
                db,
                conversation_id=conversation.id,
                sender_id=users[sender_username].id,
                content=text,
            )
        # Maya co-administers the design group, so admin-only controls are
        # reachable from more than one seeded account.
        if name == "Design Guild":
            from app.models.conversation_participant import ParticipantRole

            group_service.change_role(
                db,
                conversation_id=conversation.id,
                user_id=me.id,
                member_id=users["maya"].id,
                role=ParticipantRole.ADMIN,
            )


def _stagger_timestamps(db: Session) -> None:
    """Spread message times over the last two days.

    Everything above is written in one burst, which would leave every message
    in the same second and make date separators and relative times untestable.
    """
    messages = list(db.scalars(select(Message).order_by(Message.id)))
    now = utcnow()
    for offset, message in enumerate(reversed(messages)):
        message.created_at = now - timedelta(minutes=7 * offset + 3)
        if message.edited_at is not None:
            message.edited_at = message.created_at + timedelta(minutes=1)
    for conversation in db.scalars(select(Conversation)):
        latest = [m.created_at for m in conversation.messages]
        if latest:
            conversation.updated_at = max(latest)
        else:
            # An empty conversation is ordered by when it was created, so
            # leaving it at "now" would park it above threads full of history.
            conversation.created_at = now - timedelta(days=3)
            conversation.updated_at = conversation.created_at
    db.commit()


def seed(db: Session, *, reset: bool = False) -> bool:
    """Populate the database. Returns False if it was already populated."""
    if reset:
        _reset(db)
    elif db.scalar(select(User.id).limit(1)) is not None:
        return False

    users = _create_people(db)
    _link_contacts(db, users)
    _seed_direct(db, users)
    _seed_groups(db, users)
    _stagger_timestamps(db)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reset", action="store_true", help="delete existing data before seeding"
    )
    args = parser.parse_args()

    _guard()
    db = SessionLocal()
    try:
        if seed(db, reset=args.reset):
            print(
                f"Seeded {len(PEOPLE)} accounts. Sign in as any username above "
                f"with the password {SEED_PASSWORD!r}."
            )
        else:
            print("Database already has users; nothing to do. Pass --reset to reseed.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
