import logging
from collections.abc import Iterable
from functools import lru_cache

import httpx
from sqlalchemy import select

from .config import settings
from .database import SessionLocal
from .models import Asset, AssetStatus


logger = logging.getLogger(__name__)
QUERY_INSTRUCTION = "检索与用户需求语义相关的图片、视频或音频素材"


def _embedding_headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if settings.embedding_api_key:
        headers["Authorization"] = f"Bearer {settings.embedding_api_key}"
    return headers


def _qdrant_headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if settings.qdrant_api_key:
        headers["api-key"] = settings.qdrant_api_key
    return headers


def build_search_document(asset: Asset) -> str:
    metadata = asset.media_metadata or {}
    frame_analysis = metadata.get("frame_analysis") or []
    frame_descriptions = [
        str(item.get("description", "")).strip()
        for item in frame_analysis
        if isinstance(item, dict) and str(item.get("description", "")).strip()
    ]
    parts = [
        f"素材类型：{asset.media_type}",
        f"名称：{asset.original_name}",
        f"描述：{asset.description or ''}",
        f"场景：{asset.scene or ''}",
        f"题材：{'、'.join(asset.categories or ([asset.category] if asset.category else []))}",
        f"标签：{'、'.join(asset.tags or [])}",
    ]
    if frame_descriptions:
        parts.append(f"视频画面：{'；'.join(frame_descriptions)}")
    transcript = str(metadata.get("transcript", "")).strip()
    if transcript:
        parts.append(f"语音内容：{transcript[:6000]}")
    return "\n".join(parts)


def embed_texts(texts: list[str], *, query: bool = False) -> list[list[float]]:
    if not texts:
        return []
    inputs = [f"Instruct: {QUERY_INSTRUCTION}\nQuery: {text}" for text in texts] if query else texts
    with httpx.Client(timeout=120) as client:
        response = client.post(
            f"{settings.embedding_api_base_url.rstrip('/')}/embeddings",
            headers=_embedding_headers(),
            json={"model": settings.embedding_model, "input": inputs},
        )
        response.raise_for_status()
        data = response.json()
    vectors = [item["embedding"] for item in sorted(data["data"], key=lambda item: item["index"])]
    if any(len(vector) != settings.embedding_dimension for vector in vectors):
        dimensions = sorted({len(vector) for vector in vectors})
        raise ValueError(f"Embedding 维度不匹配，配置为 {settings.embedding_dimension}，实际为 {dimensions}")
    return vectors


@lru_cache(maxsize=512)
def embed_query(query: str) -> tuple[float, ...]:
    """Cache search embeddings so media-specific searches share one remote call."""
    return tuple(embed_texts([query.strip()], query=True)[0])


def ensure_collection() -> None:
    base_url = settings.qdrant_url.rstrip("/")
    with httpx.Client(timeout=20) as client:
        response = client.get(
            f"{base_url}/collections/{settings.qdrant_collection}",
            headers=_qdrant_headers(),
        )
        if response.status_code == 404:
            response = client.put(
                f"{base_url}/collections/{settings.qdrant_collection}",
                headers=_qdrant_headers(),
                json={"vectors": {"size": settings.embedding_dimension, "distance": "Cosine"}},
            )
        response.raise_for_status()


def index_assets(assets: Iterable[Asset]) -> None:
    asset_list = [asset for asset in assets if asset.status == AssetStatus.ready]
    if not asset_list:
        return
    ensure_collection()
    vectors = embed_texts([build_search_document(asset) for asset in asset_list])
    points = []
    for asset, vector in zip(asset_list, vectors, strict=True):
        points.append({
            "id": asset.id,
            "vector": vector,
            "payload": {
                "asset_id": asset.id,
                "media_type": asset.media_type,
                "categories": asset.categories or ([asset.category] if asset.category else ["其他"]),
                "status": asset.status.value,
            },
        })
    with httpx.Client(timeout=120) as client:
        response = client.put(
            f"{settings.qdrant_url.rstrip('/')}/collections/{settings.qdrant_collection}/points",
            params={"wait": "true"},
            headers=_qdrant_headers(),
            json={"points": points},
        )
        response.raise_for_status()


def index_asset(asset: Asset) -> None:
    index_assets([asset])


def delete_asset_vector(asset_id: str) -> None:
    with httpx.Client(timeout=20) as client:
        response = client.post(
            f"{settings.qdrant_url.rstrip('/')}/collections/{settings.qdrant_collection}/points/delete",
            params={"wait": "true"},
            headers=_qdrant_headers(),
            json={"points": [asset_id]},
        )
        if response.status_code != 404:
            response.raise_for_status()


def search_assets(
    query: str,
    *,
    media_type: str | None = None,
    category: str | None = None,
    limit: int = 10,
) -> list[tuple[str, float]]:
    ensure_collection()
    vector = embed_query(query)
    must = [{"key": "status", "match": {"value": AssetStatus.ready.value}}]
    if media_type:
        must.append({"key": "media_type", "match": {"value": media_type}})
    if category:
        must.append({"key": "categories", "match": {"value": category}})
    body = {
        "vector": vector,
        "limit": limit,
        "with_payload": True,
        "score_threshold": 0.25,
        "filter": {"must": must},
    }
    with httpx.Client(timeout=60) as client:
        response = client.post(
            f"{settings.qdrant_url.rstrip('/')}/collections/{settings.qdrant_collection}/points/search",
            headers=_qdrant_headers(),
            json=body,
        )
        response.raise_for_status()
        result = response.json().get("result", [])
    return [(str(item.get("payload", {}).get("asset_id") or item["id"]), float(item["score"])) for item in result]


def reindex_ready_assets(batch_size: int = 16) -> None:
    db = SessionLocal()
    try:
        assets = list(db.scalars(select(Asset).where(Asset.status == AssetStatus.ready)).all())
        for offset in range(0, len(assets), batch_size):
            index_assets(assets[offset:offset + batch_size])
        logger.info("Vector index synchronized for %s ready assets", len(assets))
    except Exception:
        logger.exception("Unable to synchronize the vector index; keyword search remains available")
    finally:
        db.close()


def safe_index_asset(asset: Asset) -> None:
    try:
        index_asset(asset)
    except Exception:
        logger.exception("Unable to index asset %s", asset.id)


def safe_delete_asset_vector(asset_id: str) -> None:
    try:
        delete_asset_vector(asset_id)
    except Exception:
        logger.exception("Unable to delete vector for asset %s", asset_id)
