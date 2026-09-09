import io
import json
import mimetypes
import re
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import unquote, urlencode

import httpx
from scrapling.fetchers import Fetcher

from .config import settings
from .external_download import ExternalDownloadError, download as safe_download


class IbaotuError(RuntimeError):
    pass


BASE_URL = "https://ibaotu.com"
SEARCH_URL = f"{BASE_URL}/"
SEARCH_CONVERT_URL = "https://ajax.ibaotu.com/"
LICENSE_NAME = "Ibaotu licensed material"
LICENSE_URL = "https://ibaotu.com/?m=aboutus&a=announce"
OAPI_URL = "https://oapi.ibaotu.com"
# The official download API currently returns signed files through this broker.
DOWNLOAD_DOMAINS = ("ibaotu.com", "www.isignapi.com")
MEDIA_EXTENSIONS = {
    "image": {".jpg", ".jpeg", ".png", ".webp"},
    "video": {".mp4", ".mov", ".mkv", ".webm"},
}
MEDIA_MIME_TYPES = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp",
    ".mp4": "video/mp4", ".mov": "video/quicktime", ".mkv": "video/x-matroska", ".webm": "video/webm",
}


def _absolute_url(value: str | None) -> str:
    value = (value or "").strip().replace("\\/", "/")
    if value.startswith("//"):
        return f"https:{value}"
    return value if value.startswith("https://") else ""


def _duration_seconds(value: str | None) -> float | None:
    if not value:
        return None
    try:
        parts = [int(part) for part in value.split(":")]
    except ValueError:
        return None
    if len(parts) == 2:
        return float(parts[0] * 60 + parts[1])
    if len(parts) == 3:
        return float(parts[0] * 3600 + parts[1] * 60 + parts[2])
    return None


def _search_keyword(query: str) -> str:
    try:
        response = Fetcher.get(
            f"{SEARCH_CONVERT_URL}?{urlencode({'m': 'AjaxSearch', 'a': 'check', 'kw': query})}",
            impersonate="chrome",
            stealthy_headers=True,
            headers={"Referer": "https://plus.ibaotu.com/"},
            timeout=20,
        )
        payload = json.loads(response.body)
    except Exception as exc:
        raise IbaotuError("无法转换包图网搜索关键词") from exc
    keyword = str(payload.get("py") or "").strip()
    if not keyword:
        raise IbaotuError("包图网没有返回可用的搜索关键词")
    return keyword


def _page(query: str, page: int):
    keyword = _search_keyword(query)
    params = {
        "m": "PlusApi", "a": "search", "keyword": keyword, "c1g": 0,
        "c1": "", "c2": "", "c3": "", "c4": "", "format_type": "",
        "width": "", "height": "", "copyright": "", "resolution": "",
        "duration": "", "page": page, "size": 80, "sort": "", "format": "",
        "color": "", "authscope": 3, "compose": 0, "portrait": "",
        "jingbie": "", "technique": "", "formats": "",
    }
    try:
        response = Fetcher.get(
            f"{SEARCH_URL}?{urlencode(params)}",
            impersonate="chrome",
            stealthy_headers=True,
            headers={"Referer": "https://plus.ibaotu.com/"},
            timeout=20,
        )
        payload = json.loads(response.body)
    except Exception as exc:
        raise IbaotuError("无法连接包图网公开素材搜索服务") from exc
    if payload.get("code") != 200 or not isinstance(payload.get("data"), dict):
        raise IbaotuError(payload.get("message") or "包图网搜索服务返回异常")
    return payload["data"]


def search(query: str, media_type: str, page: int, per_page: int) -> dict:
    data = _page(query, page)
    items = []
    for item in data.get("result", []):
        if item.get("type") != media_type:
            continue
        external_id = str(item.get("id") or "")
        thumbnail = _absolute_url(item.get("poster") or item.get("img"))
        content = _absolute_url(item.get("preview_url") or item.get("url")) if media_type == "video" else thumbnail
        if not external_id or not thumbnail:
            continue
        items.append({
            "provider": "ibaotu",
            "external_id": external_id,
            "media_type": media_type,
            "title": (item.get("title") or f"包图网素材 {external_id}").strip(),
            "preview_url": thumbnail,
            "preview_content_url": content or thumbnail,
            "author": item.get("flag") or "包图网",
            "source_page_url": f"{BASE_URL}/sucai/{external_id}.html",
            "width": item.get("width") if isinstance(item.get("width"), int) else None,
            "height": item.get("height") if isinstance(item.get("height"), int) else None,
            "duration": _duration_seconds(item.get("duration")) if media_type == "video" else None,
            "license": LICENSE_NAME,
            "license_url": LICENSE_URL,
        })
        if len(items) >= per_page:
            break
    return {
        "items": items,
        "page": page,
        "per_page": per_page,
        "total_results": int(data.get("count") or len(items)),
    }


def _authorized_request(method: str, path: str, *, payload: dict | None = None) -> dict:
    token = settings.ibaotu_id_token.strip()
    if not token:
        raise IbaotuError("尚未配置包图网 VIP 登录令牌 IBAOTU_ID_TOKEN")
    try:
        response = httpx.request(
            method,
            f"{OAPI_URL}/{path.lstrip('/')}",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": token,
                "Referer": "https://plus.ibaotu.com/",
            },
            json=payload,
            timeout=20,
        )
        response.raise_for_status()
        result = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise IbaotuError("包图网 VIP 服务连接失败") from exc
    if result.get("code") != 200:
        code = result.get("code")
        message = result.get("message") or "当前账号无权下载该素材"
        if code == 10009:
            message = "包图网要求完成下载验证码，请先在包图网页面完成验证后重试"
        elif code == 10008:
            message = "包图网提示下载过于频繁，请稍后重试"
        raise IbaotuError(message)
    return result.get("data") or {}


def _entitlement(external_id: str) -> dict:
    data = _authorized_request("GET", f"plus/user/resource/validpackage?id={external_id}")
    downloaded_oid = data.get("downloaded_oid")
    if downloaded_oid and str(downloaded_oid) != "0":
        return {"oid": str(downloaded_oid), "already_downloaded": True, "package": "downloaded"}
    team_packages = data.get("team_pack") or []
    if team_packages:
        return {"oid": "", "already_downloaded": False, "package": "vip"}
    packages = data.get("pack") or []
    if packages and packages[0].get("id") is not None:
        return {"oid": str(packages[0]["id"]), "already_downloaded": False, "package": "material_pack"}
    raise IbaotuError("该素材不在当前包图网 VIP 或素材包的可下载权益内")


def _detail(external_id: str) -> dict:
    try:
        response = httpx.get(
            f"{OAPI_URL}/plus/resource/detail?id={external_id}&is_seo=0",
            headers={"Accept": "application/json", "Referer": "https://plus.ibaotu.com/"},
            timeout=20,
        )
        response.raise_for_status()
        result = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise IbaotuError("无法读取包图网素材详情") from exc
    if result.get("code") != 200:
        raise IbaotuError(result.get("message") or "包图网素材详情不可用")
    return result.get("data") or {}


def get_download(external_id: str, media_type: str) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9_]+", external_id) or media_type not in {"image", "video"}:
        raise IbaotuError("包图网素材 ID 或类型无效")
    entitlement = _entitlement(external_id)
    detail = _detail(external_id)
    result = _authorized_request("POST", "plus/resource/download", payload={
        "id": external_id,
        "oid": entitlement["oid"],
        "free": "",
        "clickfrom": "asset_pipeline",
        "albums": "",
        "attachment_id": "",
        "keyword": "",
        "is_ai_ser": "",
    })
    download_url = _absolute_url(result.get("download_url"))
    if not download_url:
        raise IbaotuError("包图网没有返回官方下载地址")
    preview_value = detail.get("img")
    if isinstance(preview_value, list):
        preview_value = (preview_value[0] if preview_value else {}).get("url")
    preview_url = _absolute_url(preview_value)
    if media_type == "video":
        preview_url = _absolute_url(detail.get("mp4_url")) or preview_url
    return {
        "url": download_url,
        "check_uid": str(result.get("_check_uid") or ""),
        "page_url": f"{BASE_URL}/sucai/{external_id}.html",
        "title": detail.get("title") or f"包图网素材 {external_id}",
        "preview_url": preview_url,
        "preview_media_type": media_type,
        "author": detail.get("author") or detail.get("flag") or "包图网",
        "license": LICENSE_NAME,
        "format": str(detail.get("format") or "source").lower(),
        "metadata": {
            "provider": "ibaotu",
            "external_id": external_id,
            "license_url": LICENSE_URL,
            "entitlement": entitlement,
            "source_format": detail.get("format"),
            "source_filesize": detail.get("filesize"),
        },
    }


def download_source(source: dict, max_bytes: int, progress_callback=None) -> tuple[Path, str, str]:
    headers = {"Referer": "https://plus.ibaotu.com/"}
    cookies = {"_check_uid": source["check_uid"]} if source.get("check_uid") else None
    current_url = source["url"]
    temp_path: Path | None = None
    try:
        with httpx.Client(headers=headers, cookies=cookies, timeout=httpx.Timeout(90.0, connect=10.0)) as client:
            for _redirect in range(5):
                hostname = (httpx.URL(current_url).host or "").lower()
                if not any(hostname == domain or hostname.endswith(f".{domain}") for domain in DOWNLOAD_DOMAINS):
                    raise IbaotuError(f"包图网返回了不受信任的下载地址（{hostname or '未知主机'}）")
                with client.stream("GET", current_url, follow_redirects=False) as response:
                    if response.status_code in (301, 302, 303, 307, 308):
                        location = response.headers.get("location")
                        if not location:
                            raise IbaotuError("包图网下载重定向缺少目标地址")
                        current_url = str(httpx.URL(current_url).join(location))
                        continue
                    response.raise_for_status()
                    declared_size = int(response.headers.get("content-length", "0") or 0)
                    if declared_size > max_bytes:
                        raise IbaotuError("包图网原文件超过系统允许的大小，请提高 IBAOTU_MAX_DOWNLOAD_MB 后重试")
                    size = 0
                    with tempfile.NamedTemporaryFile(prefix="ibaotu-", suffix=".download", delete=False) as output:
                        temp_path = Path(output.name)
                        for chunk in response.iter_bytes():
                            size += len(chunk)
                            if size > max_bytes:
                                raise IbaotuError("包图网原文件超过系统允许的大小，请提高 IBAOTU_MAX_DOWNLOAD_MB 后重试")
                            output.write(chunk)
                            if progress_callback:
                                progress_callback(size, declared_size or None)
                    if not size:
                        raise IbaotuError("包图网返回了空文件")
                    disposition = response.headers.get("content-disposition", "")
                    match = re.search(r"filename\*?=(?:UTF-8''|\")?([^\";]+)", disposition, re.I)
                    filename = Path(httpx.URL(current_url).path).name or f"ibaotu-{source['metadata']['external_id']}.{source['format']}"
                    if match:
                        filename = unquote(match.group(1).strip()) or filename
                    filename = Path(filename.replace("\\", "/")).name
                    mime_type = response.headers.get("content-type", "application/octet-stream").split(";", 1)[0]
                    return temp_path, filename[:255], mime_type
    except httpx.HTTPError as exc:
        if temp_path:
            temp_path.unlink(missing_ok=True)
        raise IbaotuError("包图网授权原文件下载失败") from exc
    except Exception:
        if temp_path:
            temp_path.unlink(missing_ok=True)
        raise
    raise IbaotuError("包图网下载重定向次数过多")


def extract_licensed_media(
    source_data: bytes | Path,
    source_filename: str,
    media_type: str,
    max_bytes: int,
) -> tuple[bytes, str, str]:
    """Return a browser-compatible, licensed media file from the official download."""
    allowed_extensions = MEDIA_EXTENSIONS.get(media_type)
    if not allowed_extensions:
        raise IbaotuError("包图网素材类型无效")

    source_suffix = Path(source_filename).suffix.lower()
    if source_suffix in allowed_extensions:
        data = source_data.read_bytes() if isinstance(source_data, Path) else source_data
        return data, Path(source_filename).name, MEDIA_MIME_TYPES[source_suffix]

    archive = source_data if isinstance(source_data, Path) else io.BytesIO(source_data)
    if not zipfile.is_zipfile(archive):
        raise IbaotuError("包图网授权原文件不是可预览媒体或 ZIP，无法生成无水印素材")

    try:
        with zipfile.ZipFile(archive) as package:
            candidates = [
                item for item in package.infolist()
                if not item.is_dir()
                and Path(item.filename).suffix.lower() in allowed_extensions
                and not item.filename.replace("\\", "/").startswith("__MACOSX/")
            ]
            if not candidates:
                raise IbaotuError("包图网授权 ZIP 中没有可用于素材库的无水印图片或视频")
            candidates.sort(key=lambda item: item.file_size, reverse=True)
            selected = candidates[0]
            if selected.file_size <= 0:
                raise IbaotuError("包图网授权 ZIP 中的媒体文件为空")
            if selected.file_size > max_bytes:
                raise IbaotuError("包图网无水印媒体超过系统允许的大小，请提高 IBAOTU_MAX_DOWNLOAD_MB 后重试")
            data = package.read(selected)
    except (zipfile.BadZipFile, RuntimeError, OSError) as exc:
        raise IbaotuError("包图网授权 ZIP 无法解压") from exc

    filename = Path(selected.filename.replace("\\", "/")).name
    suffix = Path(filename).suffix.lower()
    mime_type = MEDIA_MIME_TYPES.get(suffix) or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return data, filename[:255], mime_type


def licensed_media_info(source_path: Path, source_filename: str, media_type: str, max_bytes: int) -> dict:
    allowed_extensions = MEDIA_EXTENSIONS.get(media_type)
    if not allowed_extensions:
        raise IbaotuError("包图网素材类型无效")
    source_suffix = Path(source_filename).suffix.lower()
    if source_suffix in allowed_extensions:
        size = source_path.stat().st_size
        if size > max_bytes:
            raise IbaotuError("包图网无水印媒体超过系统允许的大小")
        return {"filename": Path(source_filename).name, "mime_type": MEDIA_MIME_TYPES[source_suffix], "size": size, "member": None}
    if not zipfile.is_zipfile(source_path):
        raise IbaotuError("包图网授权原文件不是可预览媒体或 ZIP，无法生成无水印素材")
    with zipfile.ZipFile(source_path) as package:
        candidates = [item for item in package.infolist() if not item.is_dir() and Path(item.filename).suffix.lower() in allowed_extensions and not item.filename.replace("\\", "/").startswith("__MACOSX/")]
        if not candidates:
            raise IbaotuError("包图网授权 ZIP 中没有可用于素材库的无水印图片或视频")
        selected = max(candidates, key=lambda item: item.file_size)
        if selected.file_size <= 0 or selected.file_size > max_bytes:
            raise IbaotuError("包图网授权 ZIP 中的媒体文件为空或超过大小限制")
        suffix = Path(selected.filename).suffix.lower()
        return {"filename": Path(selected.filename.replace("\\", "/")).name[:255], "mime_type": MEDIA_MIME_TYPES[suffix], "size": selected.file_size, "member": selected.filename}


def download_preview(url: str, max_bytes: int) -> bytes:
    try:
        return safe_download(url, max_bytes, DOWNLOAD_DOMAINS)
    except ExternalDownloadError as exc:
        raise IbaotuError(str(exc)) from exc
