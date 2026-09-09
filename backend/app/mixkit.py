import re
from urllib.parse import quote

from scrapling.fetchers import Fetcher

from .external_download import ExternalDownloadError, download as safe_download


class MixkitError(RuntimeError):
    pass


BASE_URL = "https://mixkit.co"
LICENSE_NAME = "Mixkit Stock Video Free License"
LICENSE_URL = "https://mixkit.co/license/#videoFree"
DOWNLOAD_DOMAINS = (
    "mixkit.co",
    "assets.mixkit.co",
    "mixkit-resized.envatousercontent.com",
    "envatousercontent.com",
)


def _page(url: str):
    try:
        return Fetcher.get(url, impersonate="chrome", stealthy_headers=True, timeout=20)
    except Exception as exc:
        raise MixkitError("无法连接 Mixkit 服务") from exc


def _text(element, selector: str) -> str:
    value = element.css(selector).get()
    return re.sub(r"\s+", " ", value or "").strip()


def _slug(query: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", query.strip().lower()).strip("-")
    if not value:
        raise MixkitError("Mixkit 目前仅支持英文关键词搜索")
    return quote(value, safe="-")


def search(query: str, media_type: str, page: int, per_page: int) -> dict:
    if media_type != "video":
        raise MixkitError("Mixkit 当前只提供视频素材")
    url = f"{BASE_URL}/free-stock-video/{_slug(query)}/"
    if page > 1:
        url = f"{url}?page={page}"
    response = _page(url)
    cards = response.css(".item-grid-video-player")
    items = []
    for card in cards[:per_page]:
        external_id = card.attrib.get("data-item-grid--video-player-item-id-value", "")
        detail_path = card.css("a.item-grid-video-player__overlay-link::attr(href)").get()
        preview_url = card.css("img.item-grid-video-player__thumb::attr(src)").get()
        if not external_id or not detail_path or not preview_url:
            continue
        width = card.css("img.item-grid-video-player__thumb::attr(width)").get()
        height = card.css("img.item-grid-video-player__thumb::attr(height)").get()
        detail_slug = detail_path.strip("/").rsplit("/", 1)[-1]
        if detail_slug.endswith(f"-{external_id}"):
            detail_slug = detail_slug[:-(len(external_id) + 1)]
        stable_id = f"{external_id}:{detail_slug[:70]}"
        items.append({
            "provider": "mixkit",
            "external_id": stable_id,
            "media_type": "video",
            "title": _text(card, ".item-grid-video-player__overlay-video-title::text") or f"Mixkit 视频 {external_id}",
            "preview_url": preview_url,
            "preview_content_url": None,
            "author": "Mixkit",
            "source_page_url": f"{BASE_URL}{detail_path}",
            "width": int(width) if width and width.isdigit() else None,
            "height": int(height) if height and height.isdigit() else None,
            "license": LICENSE_NAME,
            "license_url": LICENSE_URL,
        })
    return {
        "items": items,
        "page": page,
        "per_page": per_page,
        "total_results": len(items),
    }


def _resolve_video(external_id: str, media_type: str, max_dimension: int) -> dict:
    numeric_id, separator, detail_slug = external_id.partition(":")
    if media_type != "video" or not separator or not numeric_id.isdigit() or not re.fullmatch(r"[a-z0-9-]+", detail_slug):
        raise MixkitError("Mixkit 素材 ID 或类型无效")
    detail_url = f"{BASE_URL}/free-stock-video/{detail_slug}-{numeric_id}/"
    page = _page(detail_url)
    options = []
    for option in page.css('input[name="download-option"]'):
        value = option.attrib.get("value", "")
        label = option.attrib.get("data-label", "")
        resolution = _text(option.parent, ".video-item__download-resolution::text")
        match = re.search(r"(\d+)x(\d+)", resolution)
        if value and match:
            options.append((int(match.group(1)), int(match.group(2)), label, value))
    if not options:
        raise MixkitError("该 Mixkit 视频没有可导入的下载规格")
    eligible = [item for item in options if max(item[0], item[1]) <= max_dimension] or options
    width, height, label, download_path = max(eligible, key=lambda item: item[0] * item[1])
    download_page = _page(f"{BASE_URL}{download_path}")
    download_url = download_page.css(
        ".download-modal__wrapper::attr(data-download--modal-url-value)"
    ).get()
    if not download_url:
        raise MixkitError("Mixkit 没有返回可导入的视频地址")
    return {
        "url": download_url,
        "width": width,
        "height": height,
        "label": label,
        "page_url": detail_url,
    }


def get_preview(external_id: str, media_type: str) -> dict:
    return _resolve_video(external_id, media_type, 1280)


def get_download(external_id: str, media_type: str) -> dict:
    preview = _resolve_video(external_id, media_type, 1920)
    numeric_id = external_id.partition(":")[0]
    return {
        "url": preview["url"],
        "filename": f"mixkit-{numeric_id}.mp4",
        "mime_type": "video/mp4",
        "page_url": preview["page_url"],
        "author": "Mixkit",
        "license": LICENSE_NAME,
        "metadata": {
            "provider": "mixkit",
            "external_id": numeric_id,
            "license_url": LICENSE_URL,
            "selected_resolution": f"{preview['width']}x{preview['height']}",
            "selected_label": preview["label"],
        },
    }


def download(url: str, max_bytes: int) -> bytes:
    try:
        return safe_download(url, max_bytes, DOWNLOAD_DOMAINS)
    except ExternalDownloadError as exc:
        raise MixkitError(str(exc)) from exc
