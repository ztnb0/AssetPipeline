from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .models import AssetStatus, ImportJobStatus


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


class AssetBatchDelete(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=100)


class AssetBatchDeleteResult(BaseModel):
    deleted_ids: list[str]
    failed: dict[str, str]


class ExternalAssetOut(BaseModel):
    provider: str
    external_id: str
    media_type: str
    title: str
    preview_url: str
    preview_content_url: str | None = None
    author: str
    source_page_url: str
    width: int | None = None
    height: int | None = None
    duration: float | None = None
    license: str | None = None
    license_url: str | None = None


class ExternalAssetPreviewOut(BaseModel):
    provider: str
    external_id: str
    media_type: str
    preview_content_url: str
    mime_type: str
    width: int | None = None
    height: int | None = None


class ExternalAssetList(BaseModel):
    items: list[ExternalAssetOut]
    page: int
    per_page: int
    total_results: int


class ExternalAssetImport(BaseModel):
    provider: str = Field(pattern="^(pexels|pixabay|unsplash|openverse|mixkit|ibaotu)$")
    external_id: str = Field(min_length=1, max_length=100)
    media_type: str = Field(pattern="^(image|video)$")


class ImportJobOut(BaseModel):
    id: str
    provider: str
    external_id: str
    media_type: str
    status: ImportJobStatus
    stage: str
    progress: int
    bytes_downloaded: int
    total_bytes: int | None
    asset_id: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FredChartCreate(BaseModel):
    series_id: str = Field(min_length=1, max_length=30)
    years: int = Field(default=10, ge=1, le=50)


class AssetExportRequest(BaseModel):
    ratio: str = Field(pattern="^(9:16|16:9|4:3|3:4)$")
    width: int = Field(ge=240, le=3840)
    height: int = Field(ge=240, le=3840)
    mode: str = Field(default="smart", pattern="^(smart|contain)$")
    focus_mode: str = Field(default="auto", pattern="^(auto|manual)$")
    focus_x: float = Field(default=0.5, ge=0, le=1)
    focus_y: float = Field(default=0.5, ge=0, le=1)
    zoom: float = Field(default=1, ge=1, le=3)
    track_subject: bool = True

    @model_validator(mode="after")
    def validate_dimensions(self):
        ratio_width, ratio_height = (int(value) for value in self.ratio.split(":"))
        if abs((self.width / self.height) - (ratio_width / ratio_height)) > 0.01:
            raise ValueError("分辨率与所选比例不匹配")
        if self.width % 2 or self.height % 2:
            raise ValueError("宽度和高度必须是偶数")
        return self
