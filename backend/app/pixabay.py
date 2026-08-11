import httpx

from .config import settings
from .external_download import ExternalDownloadError, download as safe_download


class PixabayError(RuntimeError):
    pass


def _request(path: str, params: dict) -> dict:
    if not settings.pixabay_api_key:
        raise PixabayError("Pixabay API Key 尚未配置")
    try:
        response = httpx.get(
            f"{settings.pixabay_api_base_url.rstrip('/')}{path}",
            params={"key": settings.pixabay_api_key, **params}, timeout=20.0,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (400, 401, 403):
            raise PixabayError("Pixabay API Key 无效或请求额度受限") from exc
        raise PixabayError(f"Pixabay 请求失败（HTTP {exc.response.status_code}）") from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise PixabayError("无法连接 Pixabay 服务") from exc


def search(query: str, media_type: str, page: int, per_page: int) -> dict:
    path = "/api/" if media_type == "image" else "/api/videos/"
    requested_per_page = max(per_page, 3)
    params = {"q": query, "page": page, "per_page": requested_per_page, "safesearch": "true"}
    if media_type == "image":
        params["image_type"] = "photo"
    data = _request(path, params)
    items = []
    for item in data.get("hits", []):
        if media_type == "image":
            preview_url = item.get("webformatURL", "")
            preview_content_url = item.get("largeImageURL") or preview_url
            width, height, duration = item.get("imageWidth"), item.get("imageHeight"), None
        else:
            rendition = item.get("videos", {}).get("medium") or item.get("videos", {}).get("small") or {}
            preview_url = rendition.get("thumbnail", "")
            preview_content_url = rendition.get("url")
            width, height, duration = rendition.get("width"), rendition.get("height"), item.get("duration")
        items.append({
            "provider": "pixabay",
            "external_id": str(item["id"]),
            "media_type": media_type,
            "title": item.get("tags") or f"Pixabay 素材 {item['id']}",
            "preview_url": preview_url,
            "preview_content_url": preview_content_url,
            "author": item.get("user", ""),
            "source_page_url": item.get("pageURL", ""),
            "width": width,
            "height": height,
            "duration": duration,
        })
    return {"items": items, "page": page, "per_page": requested_per_page, "total_results": data.get("totalHits", len(items))}


def get_download(external_id: str, media_type: str) -> dict:
    path = "/api/" if media_type == "image" else "/api/videos/"
    data = _request(path, {"id": external_id})
    item = next((hit for hit in data.get("hits", []) if str(hit.get("id")) == external_id), None)
    if not item:
        raise PixabayError("Pixabay 素材不存在或不可访问")
    if media_type == "image":
        url = item.get("largeImageURL") or item.get("webformatURL")
        filename, mime_type = f"pixabay-{external_id}.jpg", "image/jpeg"
    else:
        renditions = list(item.get("videos", {}).values())
        candidates = [video for video in renditions if video.get("url")]
        if not candidates:
            raise PixabayError("该 Pixabay 视频没有可导入的文件")
        selected = min(candidates, key=lambda video: (abs((video.get("width") or 0) - 1920), -(video.get("width") or 0)))
        url = selected["url"]
        filename, mime_type = f"pixabay-{external_id}.mp4", "video/mp4"
    return {
        "url": url,
        "filename": filename,
        "mime_type": mime_type,
        "page_url": item.get("pageURL", ""),
        "author": item.get("user", ""),
        "metadata": item,
    }


def download(url: str, max_bytes: int) -> bytes:
    try:
        return safe_download(url, max_bytes, ("pixabay.com", "pixabayusercontent.com"))
    except ExternalDownloadError as exc:
        raise PixabayError(str(exc)) from exc
