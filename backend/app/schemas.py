from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .models import AssetStatus


class AssetOut(BaseModel):
    id: str
    original_name: str
    media_type: str
    mime_type: str
    file_size: int
    width: int | None
    height: int | None
    duration: float | None
    media_metadata: dict
    status: AssetStatus
    description: str | None
    scene: str | None
    tags: list[str]
    category: str | None
    categories: list[str]
    error_message: str | None
    created_at: datetime
    content_url: str
    thumbnail_url: str | None

    model_config = ConfigDict(from_attributes=True)


class AssetList(BaseModel):
    items: list[AssetOut]
    total: int
    query_terms: list[str] = Field(default_factory=list)


class AssetUpdate(BaseModel):
    description: str | None = Field(default=None, max_length=5000)
    scene: str | None = Field(default=None, max_length=255)
    category: str | None = Field(default=None, max_length=80)
    categories: list[str] | None = Field(default=None, max_length=8)
    tags: list[str] | None = Field(default=None, max_length=30)
