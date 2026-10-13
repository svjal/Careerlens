"""Create the disposable SQLite schema used by the browser journey test."""

from app import models  # noqa: F401 - registers model tables with Base.metadata
from app.db.base import Base
from app.db.session import engine


Base.metadata.create_all(bind=engine)
