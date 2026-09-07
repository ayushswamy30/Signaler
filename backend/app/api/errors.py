"""Translation of service-layer errors into HTTP responses.

Services raise plain Python exceptions so they stay usable outside HTTP. This
module is the single place that decides what each one means to a client, which
keeps status codes consistent across every route instead of being chosen ad hoc
at each raise site.
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.core.errors import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ServiceError,
    ValidationError,
)

logger = logging.getLogger(__name__)

STATUS_BY_ERROR: dict[type[ServiceError], int] = {
    NotFoundError: status.HTTP_404_NOT_FOUND,
    PermissionDeniedError: status.HTTP_403_FORBIDDEN,
    ConflictError: status.HTTP_409_CONFLICT,
    # 422 rather than 400: it is the code FastAPI already uses for a body that
    # is well-formed but unacceptable, so clients need one branch, not two.
    ValidationError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    AuthenticationError: status.HTTP_401_UNAUTHORIZED,
}


async def service_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return the mapped status and the error's own message.

    Service error messages are written for users ("That username is already
    taken."), so they are safe to pass through. An unmapped subclass falls back
    to 400 rather than surfacing as a 500.
    """
    assert isinstance(exc, ServiceError)
    status_code = STATUS_BY_ERROR.get(type(exc), status.HTTP_400_BAD_REQUEST)
    headers = {"WWW-Authenticate": "Bearer"} if isinstance(exc, AuthenticationError) else None
    return JSONResponse({"detail": exc.message}, status_code=status_code, headers=headers)


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Log the traceback, tell the client nothing.

    An unexpected exception is a bug, and its message may quote internal state,
    so the response is deliberately generic while the detail goes to the log.
    """
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        {"detail": "Something went wrong. Please try again."},
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def register_error_handlers(app: FastAPI) -> None:
    """Attach the handlers above to an application.

    Registered on the ServiceError base class: Starlette dispatches to the
    handler for the closest registered ancestor, so every subclass -- including
    ones added later -- is covered without touching this function.
    """
    app.add_exception_handler(ServiceError, service_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
