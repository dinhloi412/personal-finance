"""Shared route helpers: one session type, one 404, one 422.

A router that hand-writes its own `HTTPException` is a router whose wording
will drift from the next one's. There is one session alias, one `get_or_404`
and one `not_found` here, and every router uses them.
"""

from __future__ import annotations

from typing import Annotated, TypeVar

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db

T = TypeVar("T")

#: The request's database session. One per request, closed when it ends.
DbSession = Annotated[Session, Depends(get_db)]


def not_found(what: str, identifier: object) -> HTTPException:
    """One 404, worded one way, everywhere."""
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"{what} {identifier} not found",
    )


def get_or_404(db: Session, model: type[T], identifier: object, what: str) -> T:
    """Fetch a row by primary key or raise the app's one 404."""
    row = db.get(model, identifier)
    if row is None:
        raise not_found(what, identifier)
    return row


#: 422, spelled out. The named constant in this version of Starlette is
#: deprecated in favour of "CONTENT", and the number is the one thing that does
#: not change between the two spellings.
UNPROCESSABLE = 422


def refused(message: str) -> HTTPException:
    """A refused value is a 422: the request was wrong, the server is not."""
    return HTTPException(status_code=UNPROCESSABLE, detail=message)
