from datetime import UTC, datetime

from sqlalchemy.orm import DeclarativeBase


def get_utc_now():
    """Return naive UTC datetime.

    Satisfies DB column defaults while avoiding Python 3.12+
    datetime.utcnow() deprecation.
    """
    return datetime.now(UTC).replace(tzinfo=None)


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
