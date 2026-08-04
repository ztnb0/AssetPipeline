from datetime import date
from io import BytesIO

import httpx
from PIL import Image, ImageDraw, ImageFont

from .config import settings


class FredError(RuntimeError):
    pass


SERIES = {
    "CPIAUCSL": {"label": "US Consumer Price Index", "short": "CPI", "category": "宏观经济"},
    "FEDFUNDS": {"label": "Federal Funds Effective Rate", "short": "Fed Funds Rate", "category": "利率"},
    "UNRATE": {"label": "US Unemployment Rate", "short": "Unemployment", "category": "就业"},
    "GDP": {"label": "US Gross Domestic Product", "short": "GDP", "category": "宏观经济"},
    "DGS10": {"label": "10-Year US Treasury Yield", "short": "10Y Treasury", "category": "债券"},
    "DCOILWTICO": {"label": "WTI Crude Oil Price", "short": "WTI Oil", "category": "大宗商品"},
}


def _font(size: int, bold: bool = False):
    names = ["DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", "Arial.ttf"]
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def list_series() -> list[dict]:
    return [{"id": series_id, **details} for series_id, details in SERIES.items()]


def _request(path: str, params: dict) -> dict:
    if not settings.fred_api_key:
        raise FredError("FRED API Key 尚未配置")
    try:
        response = httpx.get(
            f"{settings.fred_api_base_url.rstrip('/')}{path}",
            params={"api_key": settings.fred_api_key, "file_type": "json", **params},
            timeout=25.0,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (400, 401, 403):
            raise FredError("FRED API Key 无效或指标请求不被允许") from exc
        raise FredError(f"FRED 请求失败（HTTP {exc.response.status_code}）") from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise FredError("无法连接 FRED 服务") from exc


def generate_chart(series_id: str, years: int) -> dict:
    definition = SERIES.get(series_id)
    if not definition:
        raise FredError("不支持的 FRED 指标")
    start_year = date.today().year - years
    metadata = _request("/series", {"series_id": series_id}).get("seriess", [{}])[0]
    payload = _request("/series/observations", {
        "series_id": series_id,
        "observation_start": f"{start_year}-01-01",
        "sort_order": "asc",
    })
    points = []
    for observation in payload.get("observations", []):
        try:
            points.append((date.fromisoformat(observation["date"]), float(observation["value"])))
        except (KeyError, TypeError, ValueError):
            continue
    if len(points) < 2:
        raise FredError("该时间范围内没有足够的 FRED 数据")

    dates, values = zip(*points)
    image = Image.new("RGB", (1600, 900), "#f7f8fa")
    draw = ImageDraw.Draw(image)
    plot = (120, 210, 1520, 760)
    draw.rounded_rectangle((75, 70, 1550, 820), radius=16, fill="#ffffff", outline="#e1e5ea", width=2)
    draw.text((120, 105), definition["label"], fill="#17212b", font=_font(36, bold=True))
    subtitle = f"{dates[0].isoformat()} to {dates[-1].isoformat()}  |  {metadata.get('units', '')}"
    draw.text((120, 158), subtitle, fill="#66717d", font=_font(18))

    minimum, maximum = min(values), max(values)
    spread = maximum - minimum or max(abs(maximum), 1.0) * 0.1
    lower, upper = minimum - spread * 0.08, maximum + spread * 0.08
    left, top, right, bottom = plot
    for index in range(6):
        ratio = index / 5
        y = top + int((bottom - top) * ratio)
        value = upper - (upper - lower) * ratio
        draw.line((left, y, right, y), fill="#dde2e8", width=2)
        label = f"{value:,.2f}"
        box = draw.textbbox((0, 0), label, font=_font(16))
        draw.text((left - 16 - (box[2] - box[0]), y - 10), label, fill="#68737f", font=_font(16))

    total_days = max((dates[-1] - dates[0]).days, 1)
    coordinates = []
    for point_date, value in points:
        x = left + int(((point_date - dates[0]).days / total_days) * (right - left))
        y = bottom - int(((value - lower) / (upper - lower)) * (bottom - top))
        coordinates.append((x, y))
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.polygon([coordinates[0], *coordinates, (coordinates[-1][0], bottom), (coordinates[0][0], bottom)], fill=(122, 215, 209, 55))
    image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(image)
    draw.line(coordinates, fill="#087f8c", width=5, joint="curve")
    latest_x, latest_y = coordinates[-1]
    draw.ellipse((latest_x - 8, latest_y - 8, latest_x + 8, latest_y + 8), fill="#c43d3d")
    latest_label = f"Latest  {values[-1]:,.2f}"
    label_box = draw.textbbox((0, 0), latest_label, font=_font(19, bold=True))
    label_x = min(max(latest_x - (label_box[2] - label_box[0]), left), right - (label_box[2] - label_box[0]))
    draw.text((label_x, max(latest_y - 42, top + 4)), latest_label, fill="#9b2c2c", font=_font(19, bold=True))
    for index in range(6):
        point_index = round(index * (len(points) - 1) / 5)
        x, _ = coordinates[point_index]
        label = dates[point_index].strftime("%Y-%m")
        box = draw.textbbox((0, 0), label, font=_font(15))
        draw.text((x - (box[2] - box[0]) / 2, bottom + 20), label, fill="#68737f", font=_font(15))
    draw.text((120, 785), "Source: Federal Reserve Bank of St. Louis (FRED)", fill="#66717d", font=_font(16))
    series_label = f"Series: {series_id}"
    series_box = draw.textbbox((0, 0), series_label, font=_font(16))
    draw.text((1520 - (series_box[2] - series_box[0]), 785), series_label, fill="#66717d", font=_font(16))
    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return {
        "data": output.getvalue(),
        "filename": f"fred-{series_id.lower()}-{years}y.png",
        "title": definition["label"],
        "category": definition["category"],
        "metadata": {"series": metadata, "observations": len(points), "years": years, "latest_value": values[-1]},
        "page_url": f"https://fred.stlouisfed.org/series/{series_id}",
    }
