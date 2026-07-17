from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


# Import all models here so they're registered with Base for Alembic autogenerate
from app.models.user import User  # noqa: F401
# pyrefly: ignore [missing-import]
from app.models.conversation import Conversation  # noqa: F401
from app.models.message import Message  # noqa: F401