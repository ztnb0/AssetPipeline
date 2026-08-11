import hashlib
import time
import uuid
import zipfile
from pathlib import Path

from sqlalchemy import select

from .config import settings
from .database import SessionLocal
from .ibaotu import IbaotuError, download_source, get_download, licensed_media_info
from .models import Asset, AssetStatus, ImportJob, ImportJobStatus
from .processor import process_asset
from .storage import delete_object, put_fileobj


class HashingReader:
    def __init__(self, stream):
        self.stream = stream
        self.digest = hashlib.sha256()
        self.bytes_read = 0

    def read(self, size=-1):
        data = self.stream.read(size)
        if data:
            self.digest.update(data)
            self.bytes_read += len(data)
        return data


def _update(job: ImportJob, db, stage: str, progress: int, *, downloaded=None, total=None, force=False) -> None:
    now = time.monotonic()
    last = getattr(job, "_last_progress_commit", 0.0)
    if not force and progress == job.progress and now - last < 0.5:
        return
    job.status = ImportJobStatus.running
    job.stage = stage
    job.progress = max(job.progress, min(progress, 99))
    if downloaded is not None:
        job.bytes_downloaded = downloaded
    if total is not None:
        job.total_bytes = total
    db.commit()
    job._last_progress_commit = now


def run_ibaotu_import(job_id: str) -> None:
    db = SessionLocal()
    job = db.get(ImportJob, job_id)
    source_path = None
    object_key = None
    created_asset = False
    try:
        if not job:
            return
        _update(job, db, "authorizing", 2, force=True)
        source = get_download(job.external_id, job.media_type)

        def download_progress(downloaded: int, total: int | None) -> None:
            ratio = downloaded / total if total else 0
            _update(job, db, "downloading", 5 + int(min(ratio, 1) * 60), downloaded=downloaded, total=total)

        source_path, source_filename, _ = download_source(
            source,
            settings.ibaotu_max_download_mb * 1024 * 1024,
            download_progress,
        )
        _update(job, db, "extracting", 68, force=True)
        media = licensed_media_info(source_path, source_filename, job.media_type, settings.ibaotu_max_download_mb * 1024 * 1024)

        existing = db.scalar(select(Asset).where(Asset.source_type == "ibaotu", Asset.source_id == job.external_id))
        asset_id = existing.id if existing else str(uuid.uuid4())
        suffix = Path(media["filename"]).suffix.lower() or ".bin"
        object_key = existing.object_key if existing else f"media/{job.media_type}/未分类/{asset_id}{suffix}"
        uploaded = 0

        def upload_progress(chunk_size: int) -> None:
            nonlocal uploaded
            uploaded += chunk_size
            ratio = uploaded / media["size"] if media["size"] else 1
            _update(job, db, "storing", 72 + int(min(ratio, 1) * 23))

        archive = zipfile.ZipFile(source_path) if media["member"] else None
        raw_stream = archive.open(media["member"]) if archive else source_path.open("rb")
        hashing_stream = HashingReader(raw_stream)
        try:
            put_fileobj(object_key, hashing_stream, media["mime_type"], upload_progress)
        finally:
            raw_stream.close()
            if archive:
                archive.close()

        if existing:
            asset = existing
            asset.object_key = object_key
            asset.mime_type = media["mime_type"]
            asset.file_size = media["size"]
            asset.status = AssetStatus.processing
            asset.error_message = None
        else:
            created_asset = True
            asset = Asset(
                id=asset_id,
                original_name=source["title"],
                object_key=object_key,
                media_type=job.media_type,
                mime_type=media["mime_type"],
                file_size=media["size"],
                status=AssetStatus.processing,
                category="未分类",
                categories=["未分类"],
                source_type="ibaotu",
                source_id=job.external_id,
            )
            db.add(asset)
        asset.original_name = source["title"]
        asset.source_page_url = source["page_url"]
        asset.source_author = source["author"]
        asset.source_license = source["license"]
        asset.source_metadata = {**source["metadata"], "licensed_media_filename": media["filename"], "licensed_media_size": media["size"]}
        asset.content_hash = hashing_stream.digest.hexdigest()
        db.commit()

        job.asset_id = asset.id
        job.status = ImportJobStatus.completed
        job.stage = "completed"
        job.progress = 100
        job.error_message = None
        db.commit()
        process_asset(asset.id)
    except Exception as exc:
        db.rollback()
        job = db.get(ImportJob, job_id)
        if job:
            job.status = ImportJobStatus.failed
            job.stage = "failed"
            job.error_message = str(exc)[:2000]
            db.commit()
        if created_asset and object_key:
            delete_object(object_key)
    finally:
        if source_path:
            source_path.unlink(missing_ok=True)
        db.close()
