from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def migrate_demo_schema() -> None:
    """Add demo columns without discarding assets created by the image-only version."""
    existing = {column["name"] for column in inspect(engine).get_columns("assets")}
    statements = []
    if "duration" not in existing:
        statements.append("ALTER TABLE assets ADD COLUMN duration FLOAT NULL")
    if "media_metadata" not in existing:
        statements.append("ALTER TABLE assets ADD COLUMN media_metadata JSON NULL")
    if "category" not in existing:
        statements.append("ALTER TABLE assets ADD COLUMN category VARCHAR(255) NULL")
    if "categories" not in existing:
        statements.append("ALTER TABLE assets ADD COLUMN categories JSON NULL")
    if statements:
        with engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))
