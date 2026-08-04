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
    if "source_type" not in existing:
        statements.append("ALTER TABLE assets ADD COLUMN source_type VARCHAR(30) NOT NULL DEFAULT 'upload'")
    if "source_id" not in existing:
        statements.append("ALTER TABLE assets ADD COLUMN source_id VARCHAR(100) NULL")
    if "source_page_url" not in existing:
        statements.append("ALTER TABLE assets ADD COLUMN source_page_url VARCHAR(1000) NULL")
    if "source_author" not in existing:
        statements.append("ALTER TABLE assets ADD COLUMN source_author VARCHAR(255) NULL")
    if "source_license" not in existing:
        statements.append("ALTER TABLE assets ADD COLUMN source_license VARCHAR(255) NULL")
    if "source_metadata" not in existing:
        statements.append("ALTER TABLE assets ADD COLUMN source_metadata JSON NULL")
    if "content_hash" not in existing:
        statements.append("ALTER TABLE assets ADD COLUMN content_hash VARCHAR(64) NULL")
    if statements:
        with engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))
