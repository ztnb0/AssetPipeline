import httpx

from .config import settings
from .external_download import ExternalDownloadError, download as safe_download


class OpenverseError(RuntimeError):
    pass


ALLOWED_LICENSES = ("cc0", "pdm", "by", "by-sa")


def _request(path: str, params: dict | None = None) -> dict:
    try:
        response = httpx.get(
            f"{settings.openverse_api_base_url.rstrip('/')}{path}", params=params, timeout=20.0
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 429:
            raise OpenverseError("Openverse 请求过于频繁，请稍后重试") from exc
        raise OpenverseError(f"Openverse 请求失败（HTTP {exc.response.status_code}）") from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise OpenverseError("无法连接 Openverse 服务") from exc


def _license_name(item: dict) -> str:
    code = (item.get("license") or "").upper()
    version = item.get("license_version") or ""
    return f"CC {code} {version}".strip() if code != "PDM" else "Public Domain Mark"


def search(query: str, media_type: str, page: int, per_page: int) -> dict:
    if media_type != "image":
        raise OpenverseError("Openverse 当前只提供开放许可图片搜索")
    data = _request("/images/", {
        "q": query,
        "page": page,
        "page_size": per_page,
        "license": ",".join(ALLOWED_LICENSES),
        "mature": "false",
    })
    items = [{
        "provider": "openverse",
        "external_id": item["id"],
        "media_type": "image",
        "title": " · ".join(dict.fromkeys(filter(None, (
            item.get("title"),
            item.get("description"),
            ", ".join(
                str(tag.get("name") if isinstance(tag, dict) else tag).strip()
                for tag in (item.get("tags") or [])
                if str(tag.get("name") if isinstance(tag, dict) else tag).strip()
            ),
        )))) or f"Openverse 图片 {item['id']}",
        "preview_url": item.get("thumbnail", ""),
        "preview_content_url": item.get("url") or item.get("thumbnail", ""),
        "author": item.get("creator") or "",
        "source_page_url": item.get("foreign_landing_url") or item.get("detail_url") or "",
        "width": item.get("width"),
        "height": item.get("height"),
        "license": _license_name(item),
        "license_url": item.get("license_url"),
    } for item in data.get("results", []) if item.get("license") in ALLOWED_LICENSES]
    return {
        "items": items,
        "page": data.get("page_number", page),
        "per_page": data.get("page_size", per_page),
        "total_results": data.get("result_count", len(items)),
    }


def get_download(external_id: str, media_type: str) -> dict:
    if media_type != "image":
        raise OpenverseError("Openverse 当前只提供图片导入")
    item = _request(f"/images/{external_id}/")
    if item.get("license") not in ALLOWED_LICENSES:
        raise OpenverseError("该图片的许可证不在允许导入范围内")
    return {
        "url": item.get("thumbnail"),
        "filename": f"openverse-{external_id}.jpg",
        "mime_type": "image/jpeg",
        "page_url": item.get("foreign_landing_url") or item.get("detail_url") or "",
        "author": item.get("creator") or "",
        "license": _license_name(item),
        "metadata": item,
    }


def download(url: str, max_bytes: int) -> bytes:
    try:
        return safe_download(url, max_bytes, ("openverse.org",))
    except ExternalDownloadError as exc:
        raise OpenverseError(str(exc)) from exc
