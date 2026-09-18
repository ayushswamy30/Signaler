"""File uploads for message attachments.

A message still carries only ``content`` (see ``app/models/message.py``); an
attachment is not a new column but a small JSON payload the client marks and
parses inside that text, the same trick ``markSticker``/``parseSticker`` use
on the frontend for stickers. This endpoint's only job is to get the file
onto disk and hand back a URL for the client to embed that way.
"""

import secrets
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, status

from app.api.deps import CurrentUser
from app.schemas.upload import UploadResult

router = APIRouter(prefix="/uploads", tags=["uploads"])

# Relative to the backend directory, like signaler.db -- every command in the
# README already runs from there, so this needs no configuration of its own.
UPLOAD_DIR = Path("uploads")

MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB

# An allowlist, not a denylist: attachments are served back out to other
# users' browsers, so the set of types accepted has to be ones a browser will
# only ever display or download, never execute.
ALLOWED_CONTENT_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "audio/mpeg", "audio/ogg", "audio/wav",
    "video/mp4", "video/webm", "video/quicktime",
    "application/pdf", "text/plain",
    "application/zip",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

# Derived from the allowlist above rather than from the caller's filename, so
# what lands on disk can never carry an executable extension a browser or the
# OS would treat specially, whatever name the upload arrived with.
EXTENSION_BY_CONTENT_TYPE = {
    "image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif", "image/webp": ".webp",
    "audio/mpeg": ".mp3", "audio/ogg": ".ogg", "audio/wav": ".wav",
    "video/mp4": ".mp4", "video/webm": ".webm", "video/quicktime": ".mov",
    "application/pdf": ".pdf", "text/plain": ".txt",
    "application/zip": ".zip",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
}


@router.post("", response_model=UploadResult, status_code=status.HTTP_201_CREATED)
async def upload_file(file: UploadFile, current_user: CurrentUser) -> UploadResult:
    """Store an uploaded file and return the URL to attach to a message.

    The caller is authenticated (``current_user`` is required, unused beyond
    that) so only a signed-in session can write to disk here at all.
    """
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="That file type isn't supported.",
        )

    body = await file.read()
    if len(body) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Files must be 20 MB or smaller.",
        )
    if not body:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The file is empty.")

    UPLOAD_DIR.mkdir(exist_ok=True)
    extension = EXTENSION_BY_CONTENT_TYPE[file.content_type]
    stored_name = f"{secrets.token_hex(16)}{extension}"
    (UPLOAD_DIR / stored_name).write_bytes(body)

    return UploadResult(
        url=f"/uploads/{stored_name}",
        name=file.filename or stored_name,
        content_type=file.content_type,
        size=len(body),
    )
