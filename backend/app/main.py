import hashlib
import logging
import threading
import time
import uuid
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote

from botocore.exceptions import ClientError
from fastapi import BackgroundTasks, Depends, FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from .config import settings
from .database import Base, SessionLocal, engine, get_db, migrate_demo_schema
from .models import Asset, AssetStatus, ImportJob, ImportJobStatus
from .fred import FredError, generate_chart as generate_fred_chart, list_series as list_fred_series
from .ibaotu import IbaotuError, search as search_ibaotu
from .import_jobs import run_ibaotu_import
from .openverse import OpenverseError, download as download_openverse, get_download as get_openverse_download, search as search_openverse
from .pexels import PexelsError, download as download_pexels, get_download as get_pexels_download, search as search_pexels
from .pixabay import PixabayError, download as download_pixabay, get_download as get_pixabay_download, search as search_pixabay
from .processor import process_asset
from .media_export import export_asset
from .mixkit import MixkitError, download as download_mixkit, get_download as get_mixkit_download, get_preview as get_mixkit_preview, search as search_mixkit
from .schemas import (
    AssetBatchDelete,
    AssetBatchDeleteResult,
    AssetExportRequest,
    AssetList,
    AssetOut,
    AssetUpdate,
    ExternalAssetImport,
    ExternalAssetList,
    ExternalAssetPreviewOut,
    ImportJobOut,
    FredChartCreate,
)
from .semantic import expand_query_fast
from .storage import delete_object, delete_prefix, ensure_bucket, get_object, move_object, put_bytes
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
FORMAT_EXPORT_ENABLED = False


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
    recovery_db = SessionLocal()
    try:
        pending_jobs = recovery_db.scalars(select(ImportJob).where(
            ImportJob.status.in_((ImportJobStatus.queued, ImportJobStatus.running))
        )).all()
        for job in pending_jobs:
            threading.Thread(
                target=run_ibaotu_import,
                args=(job.id,),
                daemon=True,
                name=f"import-recovery-{job.id[:8]}",
            ).start()
    finally:
        recovery_db.close()
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
    if media_type == "audio":
        raise HTTPException(410, "音频接口暂时停用")
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
    provider: str = Query(default="pexels", pattern="^(pexels|pixabay|unsplash|openverse|mixkit|ibaotu)$"),
    media_type: str = Query(default="image", pattern="^(image|video)$"),
    page: int = Query(default=1, ge=1, le=100),
    per_page: int = Query(default=12, ge=1, le=40),
):
    try:
        searchers = {"pexels": search_pexels, "pixabay": search_pixabay, "unsplash": search_unsplash, "openverse": search_openverse, "mixkit": search_mixkit, "ibaotu": search_ibaotu}
        return searchers[provider](q.strip(), media_type, page, per_page)
    except (PexelsError, PixabayError, UnsplashError, OpenverseError, MixkitError, IbaotuError) as exc:
        raise HTTPException(503, str(exc)) from exc


@app.get("/api/external-assets/preview", response_model=ExternalAssetPreviewOut)
def external_asset_preview(
    provider: str = Query(pattern="^mixkit$"),
    external_id: str = Query(min_length=1, max_length=100),
    media_type: str = Query(pattern="^video$"),
):
    try:
        preview = get_mixkit_preview(external_id, media_type)
    except MixkitError as exc:
        raise HTTPException(502, str(exc)) from exc
    return ExternalAssetPreviewOut(
        provider=provider,
        external_id=external_id,
        media_type=media_type,
        preview_content_url=preview["url"],
        mime_type="video/mp4",
        width=preview.get("width"),
        height=preview.get("height"),
    )


@app.post("/api/external-assets/import", response_model=AssetOut | ImportJobOut, status_code=202)
def import_external_asset(
    payload: ExternalAssetImport,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    existing = db.scalar(select(Asset).where(
        Asset.source_type == payload.provider,
        Asset.source_id == payload.external_id,
    ))
    if existing and payload.provider == "ibaotu" and (existing.source_metadata or {}).get("licensed_media_filename"):
        if existing.media_type == "video" and not (existing.media_metadata or {}).get("preview_key"):
            existing.status = AssetStatus.processing
            db.commit()
            background_tasks.add_task(process_asset, existing.id)
        return serialize(existing)
    if existing and (
        payload.provider != "ibaotu"
    ):
        return serialize(existing)
    if payload.provider == "ibaotu":
        active = db.scalar(select(ImportJob).where(
            ImportJob.provider == "ibaotu",
            ImportJob.external_id == payload.external_id,
            ImportJob.status.in_((ImportJobStatus.queued, ImportJobStatus.running)),
        ).order_by(ImportJob.created_at.desc()))
        if active:
            return active
        job = ImportJob(provider="ibaotu", external_id=payload.external_id, media_type=payload.media_type)
        db.add(job)
        db.commit()
        db.refresh(job)
        background_tasks.add_task(run_ibaotu_import, job.id)
        return job
    try:
        providers = {
            "pexels": (get_pexels_download, download_pexels, PexelsError, "Pexels License"),
            "pixabay": (get_pixabay_download, download_pixabay, PixabayError, "Pixabay Content License"),
            "unsplash": (get_unsplash_download, download_unsplash, UnsplashError, "Unsplash License"),
            "openverse": (get_openverse_download, download_openverse, OpenverseError, None),
            "mixkit": (get_mixkit_download, download_mixkit, MixkitError, "Mixkit Stock Video Free License"),
        }
        get_download, download, error_type, license_name = providers[payload.provider]
        source = get_download(payload.external_id, payload.media_type)
        if not source.get("url"):
            raise error_type("该素材没有可用下载地址")
        data = download(source["url"], settings.max_upload_mb * 1024 * 1024)
    except (PexelsError, PixabayError, UnsplashError, OpenverseError, MixkitError) as exc:
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


@app.get("/api/external-assets/import-jobs/{job_id}", response_model=ImportJobOut)
def get_import_job(job_id: str, db: Session = Depends(get_db)):
    job = db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(404, "导入任务不存在")
    return job


@app.get("/api/fred/series")
def fred_series():
    raise HTTPException(410, "财经图表接口暂时停用")


@app.post("/api/fred/charts", response_model=AssetOut, status_code=202)
def create_fred_chart(
    payload: FredChartCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    raise HTTPException(410, "财经图表接口暂时停用")
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
    if media_type == "audio":
        raise HTTPException(410, "音频接口暂时停用")
    if media_type:
        base_filters.append(Asset.media_type == media_type)
    elif q.strip():
        base_filters.append(Asset.media_type.in_(("image", "video")))
    if category:
        base_filters.append(cast(Asset.categories, String).like(f'%"{category}"%'))

    if q.strip():
        source_query = q.strip()
        generic_terms = expand_query_fast(source_query)
        # Vector search already supplies semantic recall, so no generative-model
        # expansion or preliminary candidate query is needed here.
        asset_terms: list[str] = []
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
            items=[serialize(asset, combined_scores[asset.id]) for asset in assets[:20]],
            total=min(len(assets), 20),
            query_terms=query_terms,
        )

    query = select(Asset).where(*base_filters).order_by(Asset.created_at.desc()).limit(100)
    count_query = select(func.count()).select_from(Asset).where(*base_filters)
    items = db.scalars(query).all()
    total = db.scalar(count_query) or 0
    return AssetList(items=[serialize(item) for item in items], total=total, query_terms=query_terms)


def _normalized_page_url(url: str) -> str:
    value = (url or "").strip().lower().split("#", 1)[0]
    value = re.sub(r"[?&](utm_[^=&]+|fbclid|gclid)=[^&]*", "", value)
    return value.rstrip("/?")


@app.get("/api/search")
def unified_search(
    q: str = Query(min_length=1, max_length=100),
    media_type: str | None = Query(default=None, pattern="^(image|video)$"),
    category: str | None = Query(default=None, max_length=80),
    source: str = Query(default="all", pattern="^(all|local|external)$"),
    db: Session = Depends(get_db),
):
    """Search local assets and external providers without importing external files."""
    searchers = {"pexels": search_pexels, "pixabay": search_pixabay, "unsplash": search_unsplash, "openverse": search_openverse, "mixkit": search_mixkit, "ibaotu": search_ibaotu}
    provider_media = {
        "pexels": {"image", "video"},
        "pixabay": {"image", "video"},
        "unsplash": {"image"},
        "openverse": {"image"},
        "mixkit": {"video"},
        "ibaotu": {"image", "video"},
    }
    # External image priority is provider-first. Keep each provider's native
    # ranking, with licensed Baotu results shown before the other platforms.
    provider_order = {
        "ibaotu": 0,
        "pexels": 1,
        "pixabay": 2,
        "unsplash": 3,
        "openverse": 4,
        "mixkit": 5,
    }
    requested_types = [media_type] if media_type else ["image", "video"]
    started_at = time.perf_counter()
    local_groups = {"image": [], "video": []}
    query_terms = [q]
    if source != "external":
        for requested_type in requested_types:
            local = list_assets(q=q, media_type=requested_type, category=category, db=db)
            local_groups[requested_type] = [
                {"source": "local", "asset": item, "score": item.search_score or 0.0}
                for item in local.items[:20]
            ]
            query_terms.extend(local.query_terms)
    local_elapsed = time.perf_counter() - started_at

    external: list[dict] = []
    if source != "local":
        with ThreadPoolExecutor(max_workers=len(searchers) * len(requested_types)) as pool:
            futures = {
                pool.submit(searcher, q.strip(), requested_type, 1, 20): (provider, requested_type)
                for provider, searcher in searchers.items()
                for requested_type in requested_types
                if requested_type in provider_media[provider]
            }
            for future in as_completed(futures):
                provider, _requested_type = futures[future]
                try:
                    result = future.result()
                except Exception:
                    logger.warning("External search failed for %s", provider, exc_info=True)
                    continue
                for rank, item in enumerate(result.get("items", []), start=1):
                    item = {**item, "provider_rank": rank}
                    item["source"] = "external"
                    external.append(item)
    external = list({(_normalized_page_url(item.get("source_page_url", "")) or f"{item['provider']}:{item['external_id']}"): item for item in external}.values())
    external_images = [item for item in external if item.get("media_type") == "image"]
    external_image_items = []
    for provider in provider_order:
        provider_images = [
            item for item in external_images
            if item.get("provider") == provider
        ]
        # The score is only the provider's original rank; no cross-provider
        # semantic/vector re-ranking is performed for external results.
        for item in provider_images[:20]:
            item["score"] = round(max(0.0, 1.0 - ((item["provider_rank"] - 1) / 19)), 6)
            external_image_items.append({"source": "external", **item})

    external_video_items = []
    for provider in searchers:
        provider_videos = [
            item for item in external
            if item.get("media_type") == "video" and item.get("provider") == provider
        ]
        for item in provider_videos[:10]:
            rank_score = max(0.0, 1.0 - ((item["provider_rank"] - 1) / 9))
            external_video_items.append({"source": "external", **item, "score": round(rank_score, 6)})

    groups = {
        "image": {"local": local_groups["image"], "external": external_image_items},
        "video": {"local": local_groups["video"], "external": external_video_items},
    }
    results = [
        *groups["image"]["local"], *groups["image"]["external"],
        *groups["video"]["local"], *groups["video"]["external"],
    ]
    logger.info(
        "search timing query=%r source=%s local_ms=%d external_ms=%d total_ms=%d results=%d",
        q, source, local_elapsed * 1000,
        (time.perf_counter() - started_at - local_elapsed) * 1000,
        (time.perf_counter() - started_at) * 1000, len(results),
    )
    return {
        "items": results,
        "groups": groups,
        "total": len(results),
        "query": q,
        "query_terms": list(dict.fromkeys(query_terms)),
        "media_type": media_type,
    }


@app.get("/api/assets/{asset_id}", response_model=AssetOut)
def get_asset(asset_id: str, db: Session = Depends(get_db)):
    asset = db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(404, "素材不存在")
    return serialize(asset)


def stream_key(key: str, headers: dict[str, str] | None = None, range_header: str | None = None):
    try:
        response = get_object(key, range_header)
    except ClientError as exc:
        if exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 416:
            raise HTTPException(416, "请求的视频范围无效") from exc
        raise
    response_headers = {
        **(headers or {}),
        "Accept-Ranges": "bytes",
        "Content-Length": str(response.get("ContentLength", 0)),
    }
    if response.get("ContentRange"):
        response_headers["Content-Range"] = response["ContentRange"]
    return StreamingResponse(
        response["Body"].iter_chunks(),
        media_type=response.get("ContentType", "application/octet-stream"),
        headers=response_headers,
        status_code=206 if response.get("ContentRange") else 200,
    )


@app.get("/api/assets/{asset_id}/content")
def asset_content(asset_id: str, range_header: str | None = Header(default=None, alias="Range"), db: Session = Depends(get_db)):
    asset = db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(404, "素材不存在")
    metadata = asset.media_metadata or {}
    preview_key = metadata.get("preview_key") if asset.media_type == "video" else None
    return stream_key(preview_key or asset.object_key, range_header=range_header)


@app.get("/api/assets/{asset_id}/thumbnail")
def asset_thumbnail(asset_id: str, db: Session = Depends(get_db)):
    asset = db.get(Asset, asset_id)
    if not asset or not asset.thumbnail_key:
        raise HTTPException(404, "缩略图不存在")
    return stream_key(asset.thumbnail_key)


@app.post("/api/assets/{asset_id}/export")
def export_asset_download(asset_id: str, payload: AssetExportRequest, db: Session = Depends(get_db)):
    if not FORMAT_EXPORT_ENABLED:
        raise HTTPException(410, "比例裁剪下载功能暂未开放")
    asset = db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(404, "素材不存在")
    if asset.status != AssetStatus.ready:
        raise HTTPException(409, "素材尚未处理完成")
    if asset.media_type not in {"image", "video"}:
        raise HTTPException(415, "仅图片和视频支持比例导出")
    try:
        key, _content_type, filename, cache_hit = export_asset(asset, payload)
    except (RuntimeError, ValueError) as exc:
        logger.exception("Unable to export asset %s", asset_id)
        raise HTTPException(422, str(exc)) from exc
    disposition = f"attachment; filename*=UTF-8''{quote(filename)}"
    return stream_key(key, {
        "Content-Disposition": disposition,
        "X-Export-Cache": "hit" if cache_hit else "miss",
        "Access-Control-Expose-Headers": "Content-Disposition, X-Export-Cache",
    })


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


def _remove_asset(asset: Asset, db: Session) -> None:
    delete_object(asset.object_key)
    if asset.thumbnail_key:
        delete_object(asset.thumbnail_key)
    preview_key = (asset.media_metadata or {}).get("preview_key")
    if preview_key:
        delete_object(preview_key)
    source_metadata = asset.source_metadata or {}
    if source_metadata.get("source_file_key"):
        delete_object(source_metadata["source_file_key"])
    delete_prefix(f"exports/{asset.id}/")
    db.delete(asset)
    db.commit()
    safe_delete_asset_vector(asset.id)


@app.delete("/api/assets/batch", response_model=AssetBatchDeleteResult)
def remove_assets(payload: AssetBatchDelete, db: Session = Depends(get_db)):
    asset_ids = list(dict.fromkeys(payload.ids))
    assets = {
        asset.id: asset
        for asset in db.scalars(select(Asset).where(Asset.id.in_(asset_ids))).all()
    }
    deleted_ids = []
    failed = {}
    for asset_id in asset_ids:
        asset = assets.get(asset_id)
        if not asset:
            failed[asset_id] = "素材不存在"
            continue
        try:
            _remove_asset(asset, db)
            deleted_ids.append(asset_id)
        except Exception as exc:
            db.rollback()
            logger.exception("Unable to delete asset %s", asset_id)
            failed[asset_id] = str(exc)[:500] or "删除失败"
    return AssetBatchDeleteResult(deleted_ids=deleted_ids, failed=failed)


@app.delete("/api/assets/{asset_id}", status_code=204)
def remove_asset(asset_id: str, db: Session = Depends(get_db)):
    asset = db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(404, "素材不存在")
    _remove_asset(asset, db)
