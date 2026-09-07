"""Contacts: one user's saved links to other users."""

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.models.contact import Contact
from app.models.user import User
from app.services import user_service


def list_contacts(db: Session, user_id: int) -> list[Contact]:
    """Every contact this user has saved, ordered by the contact's name."""
    statement = (
        select(Contact)
        .where(Contact.user_id == user_id)
        .join(User, Contact.contact_user_id == User.id)
        # Eager-loaded because the caller serialises the contact's profile for
        # every row; without it the list costs one extra query per contact.
        .options(joinedload(Contact.contact_user))
        .order_by(User.display_name)
    )
    return list(db.scalars(statement))


def is_contact(db: Session, *, user_id: int, contact_user_id: int) -> bool:
    """Whether ``user_id`` has saved ``contact_user_id``. Directed, not mutual."""
    return db.get(Contact, (user_id, contact_user_id)) is not None


def add_contact(db: Session, *, user_id: int, contact_user_id: int) -> Contact:
    """Save another user as a contact."""
    if user_id == contact_user_id:
        raise ValidationError("You cannot add yourself as a contact.")
    # Checked here so a missing user is a clean 404; the foreign key would
    # otherwise surface as an opaque IntegrityError at commit time.
    user_service.get_user(db, contact_user_id)
    if is_contact(db, user_id=user_id, contact_user_id=contact_user_id):
        raise ConflictError("That user is already in your contacts.")

    contact = Contact(user_id=user_id, contact_user_id=contact_user_id)
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


def remove_contact(db: Session, *, user_id: int, contact_user_id: int) -> None:
    """Forget a saved contact. The other user's own list is untouched."""
    contact = db.get(Contact, (user_id, contact_user_id))
    if contact is None:
        raise NotFoundError("That user is not in your contacts.")
    db.delete(contact)
    db.commit()
