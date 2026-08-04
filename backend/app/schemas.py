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
    source_type: str = "upload"
    source_id: str | None = None
    source_page_url: str | None = None
    source_author: str | None = None
    source_license: str | None = None
    created_at: datetime
    content_url: str
    thumbnail_url: str | None
    search_score: float | None = None

    model_config = ConfigDict(from_attributes=True)


class AssetList(BaseModel):
    items: list[AssetOut]
    total: int
    query_terms: list[str] = Field(default_factory=list)


class AssetUpdate(BaseModel):
    original_name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    scene: str | None = Field(default=None, max_length=255)
    category: str | None = Field(default=None, max_length=80)
    categories: list[str] | None = Field(default=None, max_length=8)
    tags: list[str] | None = Field(default=None, max_length=30)


class ExternalAssetOut(BaseModel):
    provider: str
    external_id: str
    media_type: str
    title: str
    preview_url: str
    author: str
    source_page_url: str
    width: int | None = None
    height: int | None = None
    duration: float | None = None
    license: str | None = None
    license_url: str | None = None


class ExternalAssetList(BaseModel):
    items: list[ExternalAssetOut]
    page: int
    per_page: int
    total_results: int


class ExternalAssetImport(BaseModel):
    provider: str = Field(pattern="^(pexels|pixabay|unsplash|openverse)$")
    external_id: str = Field(min_length=1, max_length=100)
    media_type: str = Field(pattern="^(image|video)$")


class FredChartCreate(BaseModel):
    series_id: str = Field(min_length=1, max_length=30)
    years: int = Field(default=10, ge=1, le=50)
