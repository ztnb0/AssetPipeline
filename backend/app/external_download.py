from urllib.parse import urljoin, urlparse

import httpx


class ExternalDownloadError(RuntimeError):
    pass


def _allowed(url: str, domains: tuple[str, ...]) -> bool:
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    return parsed.scheme == "https" and any(
        hostname == domain or hostname.endswith(f".{domain}") for domain in domains
    )


def download(url: str, max_bytes: int, domains: tuple[str, ...]) -> bytes:
    current_url = url
    for _redirect in range(4):
        if not _allowed(current_url, domains):
            raise ExternalDownloadError("素材平台返回了不受信任的下载地址")
        try:
            with httpx.stream(
                "GET", current_url, timeout=httpx.Timeout(60.0, connect=10.0), follow_redirects=False
            ) as response:
                if response.status_code in (301, 302, 303, 307, 308):
                    location = response.headers.get("location")
                    if not location:
                        raise ExternalDownloadError("素材下载重定向缺少目标地址")
                    current_url = urljoin(current_url, location)
                    continue
                response.raise_for_status()
                declared_size = int(response.headers.get("content-length", "0") or 0)
                if declared_size > max_bytes:
                    raise ExternalDownloadError("素材文件超过系统允许的大小")
                chunks = []
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > max_bytes:
                        raise ExternalDownloadError("素材文件超过系统允许的大小")
                    chunks.append(chunk)
                if not size:
                    raise ExternalDownloadError("素材平台返回了空文件")
                return b"".join(chunks)
        except httpx.HTTPError as exc:
            raise ExternalDownloadError("下载外部素材失败") from exc
    raise ExternalDownloadError("素材下载重定向次数过多")
