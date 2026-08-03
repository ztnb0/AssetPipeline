import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from .config import settings
from .database import Base, engine, get_db, migrate_demo_schema
from .models import Asset, AssetStatus
from .processor import process_asset
from .schemas import AssetList, AssetOut, AssetUpdate
from .semantic import expand_query
from .storage import delete_object, ensure_bucket, get_object, move_object, put_bytes


ALLOWED_TYPES = {
    "image/jpeg": "image", "image/png": "image", "image/webp": "image",
    "video/mp4": "video", "video/quicktime": "video", "video/x-matroska": "video", "video/webm": "video",
    "audio/mpeg": "audio", "audio/wav": "audio", "audio/x-wav": "audio", "audio/mp4": "audio",
    "audio/x-m4a": "audio", "audio/flac": "audio", "audio/ogg": "audio",
}
EXTENSION_TYPES = {
    ".jpg": ("image", "image/jpeg"), ".jpeg": ("image", "image/jpeg"), ".png": ("image", "image/png"),
    ".webp": ("image", "image/webp"), ".mp4": ("video", "video/mp4"), ".mov": ("video", "video/quicktime"),
    ".mkv": ("video", "video/x-matroska"), ".webm": ("video", "video/webm"), ".mp3": ("audio", "audio/mpeg"),
    ".wav": ("audio", "audio/wav"), ".m4a": ("audio", "audio/mp4"), ".flac": ("audio", "audio/flac"),
    ".ogg": ("audio", "audio/ogg"),
}


@asynccontextmanager
async def lifespan(_: FastAPI):
    last_error = None
    for _attempt in range(20):
        try:
            Base.metadata.create_all(bind=engine)
            migrate_demo_schema()
            ensure_bucket()
            last_error = None
            break
        except Exception as exc:
            last_error = exc
            time.sleep(2)
    if last_error:
        raise last_error
    yield


app = FastAPI(title="Asset Pipeline API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[item.strip() for item in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def serialize(asset: Asset) -> AssetOut:
    categories = asset.categories or ([asset.category] if asset.category else ["其他"])
    return AssetOut.model_validate({
        **asset.__dict__,
        "media_metadata": asset.media_metadata or {},
        "categories": categories,
        "content_url": f"/api/assets/{asset.id}/content",
        "thumbnail_url": f"/api/assets/{asset.id}/thumbnail" if asset.thumbnail_key else None,
    })


def _safe_category(value: str | None, media_type: str) -> str:
    value = (value or "未分类").strip()[:80]
    value = "_".join(value.split())
    value = "".join(char for char in value if char not in '/\\:*?"<>|')
    return value or "未分类"


def _organize_asset(asset: Asset, category: str | None = None) -> None:
    asset.category = _safe_category(category or asset.category or (asset.tags or [None])[0], asset.media_type)
    suffix = Path(asset.object_key).suffix
    target = f"media/{asset.media_type}/{asset.category}/{asset.id}{suffix}"
    move_object(asset.object_key, target)
    asset.object_key = target


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/assets/upload", response_model=AssetOut, status_code=202)
async def upload_asset(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    suffix = Path(file.filename or "media").suffix.lower()
    fallback = EXTENSION_TYPES.get(suffix)
    media_type = ALLOWED_TYPES.get(file.content_type or "") or (fallback[0] if fallback else None)
    mime_type = file.content_type if file.content_type in ALLOWED_TYPES else (fallback[1] if fallback else "")
    if not media_type:
        raise HTTPException(415, "支持 JPG、PNG、WebP、MP4、MOV、MKV、WebM、MP3、WAV、M4A、FLAC 和 OGG")
    data = await file.read()
    if not data:
        raise HTTPException(400, "文件为空")
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"文件不能超过 {settings.max_upload_mb} MB")

    asset_id = str(uuid.uuid4())
    suffix = suffix or ".bin"
    object_key = f"media/{media_type}/未分类/{asset_id}{suffix}"
    put_bytes(object_key, data, mime_type)
    asset = Asset(
        id=asset_id,
        original_name=file.filename or f"{asset_id}{suffix}",
        object_key=object_key,
        media_type=media_type,
        mime_type=mime_type,
        file_size=len(data),
        status=AssetStatus.processing,
        category="未分类",
        categories=["未分类"],
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    background_tasks.add_task(process_asset, asset.id)
    return serialize(asset)


@app.get("/api/assets", response_model=AssetList)
def list_assets(
    q: str = Query(default="", max_length=100),
    media_type: str | None = Query(default=None),
    category: str | None = Query(default=None, max_length=80),
    db: Session = Depends(get_db),
):
    filters = []
    query_terms = []
    if q.strip():
        query_terms = expand_query(q.strip())
        semantic_matches = []
        for query_term in query_terms:
            term = f"%{query_term}%"
            semantic_matches.extend([
                Asset.original_name.like(term), Asset.description.like(term), Asset.scene.like(term),
                Asset.category.like(term), cast(Asset.categories, String).like(term), cast(Asset.tags, String).like(term),
            ])
        filters.append(or_(*semantic_matches))
    if media_type:
        filters.append(Asset.media_type == media_type)
    if category:
        filters.append(cast(Asset.categories, String).like(f'%"{category}"%'))
    query = select(Asset)
    count_query = select(func.count()).select_from(Asset)
    if filters:
        query = query.where(*filters)
        count_query = count_query.where(*filters)
    items = db.scalars(query.order_by(Asset.created_at.desc()).limit(100)).all()
    total = db.scalar(count_query) or 0
    return AssetList(items=[serialize(item) for item in items], total=total, query_terms=query_terms)


@app.get("/api/assets/{asset_id}", response_model=AssetOut)
def get_asset(asset_id: str, db: Session = Depends(get_db)):
    asset = db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(404, "素材不存在")
    return serialize(asset)


def stream_key(key: str):
    response = get_object(key)
    return StreamingResponse(
        response["Body"].iter_chunks(), media_type=response.get("ContentType", "application/octet-stream")
    )


@app.get("/api/assets/{asset_id}/content")
def asset_content(asset_id: str, db: Session = Depends(get_db)):
    asset = db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(404, "素材不存在")
    return stream_key(asset.object_key)


@app.get("/api/assets/{asset_id}/thumbnail")
def asset_thumbnail(asset_id: str, db: Session = Depends(get_db)):
    asset = db.get(Asset, asset_id)
    if not asset or not asset.thumbnail_key:
        raise HTTPException(404, "缩略图不存在")
    return stream_key(asset.thumbnail_key)


@app.post("/api/assets/{asset_id}/reanalyze", response_model=AssetOut, status_code=202)
def reanalyze(asset_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    asset = db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(404, "素材不存在")
    asset.status = AssetStatus.processing
    asset.error_message = None
    db.commit()
    background_tasks.add_task(process_asset, asset.id)
    return serialize(asset)


@app.put("/api/assets/{asset_id}/tags", response_model=AssetOut)
def update_tags(asset_id: str, payload: dict, db: Session = Depends(get_db)):
    asset = db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(404, "素材不存在")
    tags = payload["tags"] if "tags" in payload else (asset.tags or [])
    if not isinstance(tags, list):
        raise HTTPException(400, "tags 必须是数组")
    asset.tags = list(dict.fromkeys(str(tag).strip() for tag in tags if str(tag).strip()))[:30]
    _organize_asset(asset, payload.get("category"))
    asset.categories = [asset.category]
    db.commit()
    db.refresh(asset)
    return serialize(asset)


@app.patch("/api/assets/{asset_id}", response_model=AssetOut)
def update_asset(asset_id: str, payload: AssetUpdate, db: Session = Depends(get_db)):
    asset = db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(404, "素材不存在")
    changes = payload.model_dump(exclude_unset=True)
    if "tags" in changes:
        asset.tags = list(dict.fromkeys(tag.strip() for tag in (changes["tags"] or []) if tag.strip()))[:30]
    if "description" in changes:
        asset.description = (changes["description"] or "").strip()
    if "scene" in changes:
        asset.scene = (changes["scene"] or "").strip() or "未分类"
    if "category" in changes:
        _organize_asset(asset, changes["category"])
        asset.categories = [asset.category]
    if "categories" in changes:
        categories = list(dict.fromkeys(item.strip() for item in (changes["categories"] or []) if item.strip()))[:8]
        if not categories:
            categories = ["其他"]
        asset.categories = categories
        _organize_asset(asset, categories[0])
    db.commit()
    db.refresh(asset)
    return serialize(asset)


@app.delete("/api/assets/{asset_id}", status_code=204)
def remove_asset(asset_id: str, db: Session = Depends(get_db)):
    asset = db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(404, "素材不存在")
    delete_object(asset.object_key)
    if asset.thumbnail_key:
        delete_object(asset.thumbnail_key)
    db.delete(asset)
    db.commit()
