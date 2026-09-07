"""Contact routes."""

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.common import Message
from app.schemas.contact import ContactCreate, ContactRead
from app.services import contact_service

router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.get("", response_model=list[ContactRead])
def list_contacts(db: DbSession, current_user: CurrentUser) -> list[ContactRead]:
    """Everyone the signed-in user has saved, by display name."""
    contacts = contact_service.list_contacts(db, current_user.id)
    return [ContactRead.model_validate(contact) for contact in contacts]


@router.post("", response_model=ContactRead, status_code=status.HTTP_201_CREATED)
def add_contact(payload: ContactCreate, db: DbSession, current_user: CurrentUser) -> ContactRead:
    """Save another user as a contact. One-way: it does not add you to theirs."""
    contact = contact_service.add_contact(
        db, user_id=current_user.id, contact_user_id=payload.user_id
    )
    return ContactRead.model_validate(contact)


@router.delete("/{user_id}", response_model=Message)
def remove_contact(user_id: int, db: DbSession, current_user: CurrentUser) -> Message:
    """Remove a saved contact."""
    contact_service.remove_contact(db, user_id=current_user.id, contact_user_id=user_id)
    return Message(detail="Contact removed.")
