from urllib.parse import urlparse

import httpx

from .config import settings
from .external_download import ExternalDownloadError, download as safe_download


class UnsplashError(RuntimeError):
    pass


def _headers() -> dict[str, str]:
    if not settings.unsplash_access_key:
        raise UnsplashError("Unsplash Access Key 尚未配置")
    return {"Authorization": f"Client-ID {settings.unsplash_access_key}", "Accept-Version": "v1"}


def _request(path: str, params: dict | None = None) -> dict:
    return _request_url(f"{settings.unsplash_api_base_url.rstrip('/')}{path}", params)


def _request_url(url: str, params: dict | None = None) -> dict:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "api.unsplash.com":
        raise UnsplashError("Unsplash 返回了不受信任的 API 地址")
    try:
        response = httpx.get(url, headers=_headers(), params=params, timeout=20.0)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (401, 403):
            raise UnsplashError("Unsplash Access Key 无效或请求额度受限") from exc
        raise UnsplashError(f"Unsplash 请求失败（HTTP {exc.response.status_code}）") from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise UnsplashError("无法连接 Unsplash 服务") from exc


def search(query: str, media_type: str, page: int, per_page: int) -> dict:
    if media_type != "image":
        raise UnsplashError("Unsplash 当前只提供图片搜索")
    data = _request("/search/photos", {"query": query, "page": page, "per_page": per_page, "content_filter": "high"})
    items = [{
        "provider": "unsplash",
        "external_id": item["id"],
        "media_type": "image",
        "title": item.get("alt_description") or item.get("description") or f"Unsplash 图片 {item['id']}",
        "preview_url": item.get("urls", {}).get("small", ""),
        "preview_content_url": item.get("urls", {}).get("full") or item.get("urls", {}).get("regular"),
        "author": item.get("user", {}).get("name", ""),
        "source_page_url": item.get("links", {}).get("html", ""),
        "width": item.get("width"),
        "height": item.get("height"),
    } for item in data.get("results", [])]
    return {"items": items, "page": page, "per_page": per_page, "total_results": data.get("total", len(items))}


def get_download(external_id: str, media_type: str) -> dict:
    if media_type != "image":
        raise UnsplashError("Unsplash 当前只提供图片导入")
    item = _request(f"/photos/{external_id}")
    tracking_url = item.get("links", {}).get("download_location")
    if not tracking_url:
        raise UnsplashError("该 Unsplash 图片没有可用下载地址")
    tracked = _request_url(tracking_url)
    return {
        "url": tracked.get("url"),
        "filename": f"unsplash-{external_id}.jpg",
        "mime_type": "image/jpeg",
        "page_url": item.get("links", {}).get("html", ""),
        "author": item.get("user", {}).get("name", ""),
        "metadata": item,
    }


def download(url: str, max_bytes: int) -> bytes:
    try:
        return safe_download(url, max_bytes, ("unsplash.com",))
    except ExternalDownloadError as exc:
        raise UnsplashError(str(exc)) from exc
