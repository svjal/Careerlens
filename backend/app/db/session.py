from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import DATABASE_URL


engine = create_engine(DATABASE_URL, pool_pre_ping=True)
if engine.dialect.name == "sqlite":
    # SQLite disables foreign-key rules per connection; enable them so local tests
    # exercise the same cascade and ownership behavior as PostgreSQL.
    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(connection, _connection_record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    database = SessionLocal()
    try:
        yield database
    finally:
        database.close()
