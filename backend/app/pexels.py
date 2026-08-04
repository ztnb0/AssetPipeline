import httpx

from .config import settings
from .external_download import ExternalDownloadError, download as safe_download


class PexelsError(RuntimeError):
    pass


def _headers() -> dict[str, str]:
    if not settings.pexels_api_key:
        raise PexelsError("Pexels API Key 尚未配置")
    return {"Authorization": settings.pexels_api_key}


def _request(path: str, params: dict | None = None) -> dict:
    try:
        response = httpx.get(
            f"{settings.pexels_api_base_url.rstrip('/')}{path}",
            headers=_headers(), params=params, timeout=20.0,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 401:
            raise PexelsError("Pexels API Key 无效") from exc
        raise PexelsError(f"Pexels 请求失败（HTTP {exc.response.status_code}）") from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise PexelsError("无法连接 Pexels 服务") from exc


def search(query: str, media_type: str, page: int, per_page: int) -> dict:
    if media_type == "image":
        data = _request("/v1/search", {"query": query, "page": page, "per_page": per_page})
        items = [{
            "provider": "pexels",
            "external_id": str(item["id"]),
            "media_type": "image",
            "title": item.get("alt") or f"Pexels 图片 {item['id']}",
            "preview_url": item.get("src", {}).get("medium", ""),
            "author": item.get("photographer", ""),
            "source_page_url": item.get("url", ""),
            "width": item.get("width"),
            "height": item.get("height"),
        } for item in data.get("photos", [])]
    else:
        data = _request("/videos/search", {"query": query, "page": page, "per_page": per_page})
        items = [{
            "provider": "pexels",
            "external_id": str(item["id"]),
            "media_type": "video",
            "title": f"Pexels 视频 {item['id']}",
            "preview_url": (item.get("image") or ""),
            "author": item.get("user", {}).get("name", ""),
            "source_page_url": item.get("url", ""),
            "width": item.get("width"),
            "height": item.get("height"),
            "duration": item.get("duration"),
        } for item in data.get("videos", [])]
    return {
        "items": items,
        "page": data.get("page", page),
        "per_page": data.get("per_page", per_page),
        "total_results": data.get("total_results", len(items)),
    }


def get_download(external_id: str, media_type: str) -> dict:
    if media_type == "image":
        item = _request(f"/v1/photos/{external_id}")
        download_url = item.get("src", {}).get("original")
        return {
            "url": download_url,
            "filename": f"pexels-{external_id}.jpg",
            "mime_type": "image/jpeg",
            "page_url": item.get("url", ""),
            "author": item.get("photographer", ""),
            "metadata": item,
        }

    item = _request(f"/videos/videos/{external_id}")
    candidates = [file for file in item.get("video_files", []) if file.get("file_type") == "video/mp4"]
    if not candidates:
        raise PexelsError("该 Pexels 视频没有可导入的 MP4 文件")
    # Prefer the best rendition no wider than 1920px to control storage and processing cost.
    selected = min(candidates, key=lambda file: (abs((file.get("width") or 0) - 1920), -(file.get("width") or 0)))
    return {
        "url": selected.get("link"),
        "filename": f"pexels-{external_id}.mp4",
        "mime_type": "video/mp4",
        "page_url": item.get("url", ""),
        "author": item.get("user", {}).get("name", ""),
        "metadata": item,
    }


def download(url: str, max_bytes: int) -> bytes:
    try:
        return safe_download(url, max_bytes, ("pexels.com",))
    except ExternalDownloadError as exc:
        raise PexelsError(str(exc)) from exc
