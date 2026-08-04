import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Enum, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class AssetStatus(str, enum.Enum):
    processing = "processing"
    ready = "ready"
    failed = "failed"


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    original_name: Mapped[str] = mapped_column(String(255), index=True)
    object_key: Mapped[str] = mapped_column(String(512), unique=True)
    thumbnail_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    media_type: Mapped[str] = mapped_column(String(30), index=True)
    mime_type: Mapped[str] = mapped_column(String(100))
    file_size: Mapped[int] = mapped_column(BigInteger)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    media_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[AssetStatus] = mapped_column(Enum(AssetStatus), default=AssetStatus.processing, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    scene: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    category: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    categories: Mapped[list] = mapped_column(JSON, default=list)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(String(30), default="upload", index=True)
    source_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    source_page_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    source_author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_license: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
