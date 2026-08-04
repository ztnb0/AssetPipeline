import hashlib
import logging
import threading
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
from .fred import FredError, generate_chart as generate_fred_chart, list_series as list_fred_series
from .openverse import OpenverseError, download as download_openverse, get_download as get_openverse_download, search as search_openverse
from .pexels import PexelsError, download as download_pexels, get_download as get_pexels_download, search as search_pexels
from .pixabay import PixabayError, download as download_pixabay, get_download as get_pixabay_download, search as search_pixabay
from .processor import process_asset
from .schemas import AssetList, AssetOut, AssetUpdate, ExternalAssetImport, ExternalAssetList, FredChartCreate
from .semantic import expand_from_assets, expand_query
from .storage import delete_object, ensure_bucket, get_object, move_object, put_bytes
from .unsplash import UnsplashError, download as download_unsplash, get_download as get_unsplash_download, search as search_unsplash
from .vector_store import reindex_ready_assets, safe_delete_asset_vector, safe_index_asset, search_assets


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
logger = logging.getLogger(__name__)


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
    threading.Thread(target=reindex_ready_assets, daemon=True, name="vector-index-sync").start()
    yield


app = FastAPI(title="Asset Pipeline API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[item.strip() for item in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def serialize(asset: Asset, search_score: float | None = None) -> AssetOut:
    categories = asset.categories or ([asset.category] if asset.category else ["其他"])
    return AssetOut.model_validate({
        **asset.__dict__,
        "media_metadata": asset.media_metadata or {},
        "source_type": asset.source_type or "upload",
        "categories": categories,
        "content_url": f"/api/assets/{asset.id}/content",
        "thumbnail_url": f"/api/assets/{asset.id}/thumbnail" if asset.thumbnail_key else None,
        "search_score": search_score,
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


def _create_asset(
    db: Session,
    data: bytes,
    filename: str,
    media_type: str,
    mime_type: str,
    *,
    source_type: str = "upload",
    source_id: str | None = None,
    source_page_url: str | None = None,
    source_author: str | None = None,
    source_license: str | None = None,
    source_metadata: dict | None = None,
) -> Asset:
    asset_id = str(uuid.uuid4())
    suffix = Path(filename).suffix.lower() or ".bin"
    object_key = f"media/{media_type}/未分类/{asset_id}{suffix}"
    content_hash = hashlib.sha256(data).hexdigest()
    put_bytes(object_key, data, mime_type)
    asset = Asset(
        id=asset_id,
        original_name=filename,
        object_key=object_key,
        media_type=media_type,
        mime_type=mime_type,
        file_size=len(data),
        status=AssetStatus.processing,
        category="未分类",
        categories=["未分类"],
        source_type=source_type,
        source_id=source_id,
        source_page_url=source_page_url,
        source_author=source_author,
        source_license=source_license,
        source_metadata=source_metadata or {},
        content_hash=content_hash,
    )
    try:
        db.add(asset)
        db.commit()
        db.refresh(asset)
    except Exception:
        db.rollback()
        delete_object(object_key)
        raise
    return asset


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

    asset = _create_asset(db, data, file.filename or f"media{suffix}", media_type, mime_type)
    if asset.status == AssetStatus.processing:
        background_tasks.add_task(process_asset, asset.id)
    return serialize(asset)


@app.get("/api/external-assets/search", response_model=ExternalAssetList)
def search_external_assets(
    q: str = Query(min_length=1, max_length=100),
    provider: str = Query(default="pexels", pattern="^(pexels|pixabay|unsplash|openverse)$"),
    media_type: str = Query(default="image", pattern="^(image|video)$"),
    page: int = Query(default=1, ge=1, le=100),
    per_page: int = Query(default=12, ge=1, le=40),
):
    try:
        searchers = {"pexels": search_pexels, "pixabay": search_pixabay, "unsplash": search_unsplash, "openverse": search_openverse}
        return searchers[provider](q.strip(), media_type, page, per_page)
    except (PexelsError, PixabayError, UnsplashError, OpenverseError) as exc:
        raise HTTPException(503, str(exc)) from exc


@app.post("/api/external-assets/import", response_model=AssetOut, status_code=202)
def import_external_asset(
    payload: ExternalAssetImport,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    existing = db.scalar(select(Asset).where(
        Asset.source_type == payload.provider,
        Asset.source_id == payload.external_id,
    ))
    if existing:
        return serialize(existing)
    try:
        providers = {
            "pexels": (get_pexels_download, download_pexels, PexelsError, "Pexels License"),
            "pixabay": (get_pixabay_download, download_pixabay, PixabayError, "Pixabay Content License"),
            "unsplash": (get_unsplash_download, download_unsplash, UnsplashError, "Unsplash License"),
            "openverse": (get_openverse_download, download_openverse, OpenverseError, None),
        }
        get_download, download, error_type, license_name = providers[payload.provider]
        source = get_download(payload.external_id, payload.media_type)
        if not source.get("url"):
            raise error_type("该素材没有可用下载地址")
        data = download(source["url"], settings.max_upload_mb * 1024 * 1024)
    except (PexelsError, PixabayError, UnsplashError, OpenverseError) as exc:
        raise HTTPException(502, str(exc)) from exc

    asset = _create_asset(
        db, data, source["filename"], payload.media_type, source["mime_type"],
        source_type=payload.provider,
        source_id=payload.external_id,
        source_page_url=source["page_url"],
        source_author=source["author"],
        source_license=source.get("license") or license_name,
        source_metadata=source["metadata"],
    )
    if asset.status == AssetStatus.processing:
        background_tasks.add_task(process_asset, asset.id)
    return serialize(asset)


@app.get("/api/fred/series")
def fred_series():
    return {"items": list_fred_series()}


@app.post("/api/fred/charts", response_model=AssetOut, status_code=202)
def create_fred_chart(
    payload: FredChartCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    try:
        chart = generate_fred_chart(payload.series_id, payload.years)
    except FredError as exc:
        raise HTTPException(503, str(exc)) from exc
    asset = _create_asset(
        db, chart["data"], chart["filename"], "image", "image/png",
        source_type="fred",
        source_id=f"{payload.series_id}:{payload.years}y",
        source_page_url=chart["page_url"],
        source_author="Federal Reserve Bank of St. Louis",
        source_license="FRED Terms of Use; verify series notes",
        source_metadata=chart["metadata"],
    )
    asset.original_name = chart["title"]
    asset.category = chart["category"]
    asset.categories = ["财经", chart["category"]]
    db.commit()
    background_tasks.add_task(process_asset, asset.id)
    return serialize(asset)


@app.get("/api/assets", response_model=AssetList)
def list_assets(
    q: str = Query(default="", max_length=100),
    media_type: str | None = Query(default=None),
    category: str | None = Query(default=None, max_length=80),
    db: Session = Depends(get_db),
):
    base_filters = []
    query_terms = []
    if media_type:
        base_filters.append(Asset.media_type == media_type)
    if category:
        base_filters.append(cast(Asset.categories, String).like(f'%"{category}"%'))

    if q.strip():
        source_query = q.strip()
        generic_terms = expand_query(source_query)
        candidate_matches = []
        for candidate_term in generic_terms:
            term = f"%{candidate_term}%"
            candidate_matches.extend([
                Asset.original_name.like(term), Asset.description.like(term), Asset.scene.like(term),
                Asset.category.like(term), cast(Asset.categories, String).like(term), cast(Asset.tags, String).like(term),
            ])
        candidate_query = select(Asset).where(or_(*candidate_matches), *base_filters).limit(50)
        candidates = db.scalars(candidate_query).all()
        corpus = []
        for asset in candidates:
            corpus.extend([
                asset.original_name, asset.description or "", asset.scene or "", asset.category or "",
                *(asset.categories or []), *(asset.tags or []),
            ])
        asset_terms = expand_from_assets(source_query, corpus)
        query_terms = [source_query, *asset_terms]
        search_terms = list(dict.fromkeys([*generic_terms, *asset_terms]))
        semantic_matches = []
        for query_term in search_terms:
            term = f"%{query_term}%"
            semantic_matches.extend([
                Asset.original_name.like(term), Asset.description.like(term), Asset.scene.like(term),
                Asset.category.like(term), cast(Asset.categories, String).like(term), cast(Asset.tags, String).like(term),
            ])
        keyword_query = select(Asset).where(or_(*semantic_matches), *base_filters).limit(100)
        keyword_assets = list(db.scalars(keyword_query).all())
        keyword_ids = {asset.id for asset in keyword_assets}

        vector_scores: dict[str, float] = {}
        try:
            vector_scores = dict(search_assets(
                source_query,
                media_type=media_type,
                category=category,
                limit=100,
            ))
        except Exception:
            logger.exception("Vector search unavailable; falling back to keyword search")

        asset_ids = keyword_ids | set(vector_scores)
        if not asset_ids:
            return AssetList(items=[], total=0, query_terms=query_terms)
        assets = list(db.scalars(select(Asset).where(Asset.id.in_(asset_ids), *base_filters)).all())
        combined_scores = {
            asset.id: round(0.75 * vector_scores.get(asset.id, 0.0) + (0.25 if asset.id in keyword_ids else 0.0), 6)
            for asset in assets
        }
        assets.sort(key=lambda asset: (combined_scores[asset.id], asset.created_at), reverse=True)
        return AssetList(
            items=[serialize(asset, combined_scores[asset.id]) for asset in assets[:100]],
            total=len(assets),
            query_terms=query_terms,
        )

    query = select(Asset).where(*base_filters).order_by(Asset.created_at.desc()).limit(100)
    count_query = select(func.count()).select_from(Asset).where(*base_filters)
    items = db.scalars(query).all()
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
    safe_delete_asset_vector(asset.id)
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
    safe_index_asset(asset)
    return serialize(asset)


@app.patch("/api/assets/{asset_id}", response_model=AssetOut)
def update_asset(asset_id: str, payload: AssetUpdate, db: Session = Depends(get_db)):
    asset = db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(404, "素材不存在")
    changes = payload.model_dump(exclude_unset=True)
    if "original_name" in changes:
        original_name = (changes["original_name"] or "").strip()
        if not original_name:
            raise HTTPException(400, "素材名称不能为空")
        asset.original_name = original_name
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
    safe_index_asset(asset)
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
    safe_delete_asset_vector(asset_id)
