import hashlib
import json
import math
import subprocess
import tempfile
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps, ImageStat

from .models import Asset
from .schemas import AssetExportRequest
from .storage import get_object, object_exists, put_bytes


def _run(command: list[str], timeout: int = 1800) -> None:
    try:
        subprocess.run(command, capture_output=True, check=True, timeout=timeout)
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.decode("utf-8", errors="replace")[-2000:]
        raise RuntimeError(f"媒体导出失败：{detail}") from exc


def _salient_focus(image: Image.Image) -> tuple[float, float]:
    preview = ImageOps.exif_transpose(image).convert("L")
    preview.thumbnail((320, 320))
    edges = preview.filter(ImageFilter.FIND_EDGES)
    width, height = edges.size
    columns, rows = 5, 5
    candidates: list[tuple[float, float, float]] = []
    for row in range(rows):
        for column in range(columns):
            left, top = column * width // columns, row * height // rows
            right, bottom = (column + 1) * width // columns, (row + 1) * height // rows
            energy = ImageStat.Stat(edges.crop((left, top, right, bottom))).mean[0]
            center_x = (column + 0.5) / columns
            center_y = (row + 0.5) / rows
            center_bias = 1 - 0.18 * math.hypot(center_x - 0.5, center_y - 0.45)
            candidates.append((energy * center_bias, center_x, center_y))
    weighted = sorted(candidates, reverse=True)[:5]
    total = sum(item[0] for item in weighted)
    if total <= 0:
        return 0.5, 0.5
    return (
        sum(score * x for score, x, _ in weighted) / total,
        sum(score * y for score, _, y in weighted) / total,
    )


def _crop_box(
    source_width: int,
    source_height: int,
    target_width: int,
    target_height: int,
    focus_x: float,
    focus_y: float,
    zoom: float,
) -> tuple[int, int, int, int]:
    target_ratio = target_width / target_height
    if source_width / source_height > target_ratio:
        crop_height = source_height / zoom
        crop_width = crop_height * target_ratio
    else:
        crop_width = source_width / zoom
        crop_height = crop_width / target_ratio
    crop_width = max(1, min(source_width, round(crop_width)))
    crop_height = max(1, min(source_height, round(crop_height)))
    left = round(source_width * focus_x - crop_width / 2)
    top = round(source_height * focus_y - crop_height / 2)
    left = max(0, min(source_width - crop_width, left))
    top = max(0, min(source_height - crop_height, top))
    return left, top, left + crop_width, top + crop_height


def _image_export(source: bytes, request: AssetExportRequest) -> tuple[bytes, str, str]:
    with Image.open(BytesIO(source)) as original:
        image = ImageOps.exif_transpose(original).convert("RGB")
        if request.mode == "contain":
            fitted = ImageOps.contain(image, (request.width, request.height), Image.Resampling.LANCZOS)
            output = Image.new("RGB", (request.width, request.height), "black")
            output.paste(fitted, ((request.width - fitted.width) // 2, (request.height - fitted.height) // 2))
        else:
            focus = _salient_focus(image) if request.focus_mode == "auto" else (request.focus_x, request.focus_y)
            output = image.crop(_crop_box(*image.size, request.width, request.height, *focus, request.zoom))
            output = output.resize((request.width, request.height), Image.Resampling.LANCZOS)
        buffer = BytesIO()
        output.save(buffer, format="JPEG", quality=92, optimize=True, progressive=True)
    return buffer.getvalue(), "image/jpeg", ".jpg"


def _sample_video_focus(source: Path, duration: float, temp_dir: Path) -> list[tuple[float, float, float]]:
    sample_count = max(3, min(12, math.ceil(duration / 3)))
    # Sample the middle of each segment; seeking to exactly `duration` yields no frame.
    points = [duration * (index + 0.5) / sample_count for index in range(sample_count)]
    raw: list[tuple[float, float, float]] = []
    for index, timestamp in enumerate(points):
        frame = temp_dir / f"focus-{index:02d}.jpg"
        _run(["ffmpeg", "-y", "-ss", f"{timestamp:.3f}", "-i", str(source), "-frames:v", "1", "-vf", "scale=320:-2", "-q:v", "4", str(frame)], timeout=120)
        if frame.exists():
            with Image.open(frame) as image:
                x, y = _salient_focus(image)
            raw.append((timestamp, x, y))
    if not raw:
        return [(0, 0.5, 0.5)]
    smoothed = [raw[0]]
    for timestamp, x, y in raw[1:]:
        previous = smoothed[-1]
        smoothed.append((timestamp, previous[1] * 0.65 + x * 0.35, previous[2] * 0.65 + y * 0.35))
    return smoothed


def _piecewise_expression(points: list[tuple[float, float]], axis_size: int, crop_size: int) -> str:
    offsets = [(time, max(0, min(axis_size - crop_size, axis_size * focus - crop_size / 2))) for time, focus in points]
    expression = f"{offsets[-1][1]:.3f}"
    for index in range(len(offsets) - 2, -1, -1):
        start_time, start = offsets[index]
        end_time, end = offsets[index + 1]
        duration = max(0.001, end_time - start_time)
        interpolation = f"{start:.3f}+({end - start:.3f})*(t-{start_time:.3f})/{duration:.3f}"
        expression = f"if(lt(t,{end_time:.3f}),{interpolation},{expression})"
    return expression


def _video_export(source: bytes, asset: Asset, request: AssetExportRequest) -> tuple[bytes, str, str]:
    suffix = Path(asset.object_key).suffix or ".mp4"
    with tempfile.TemporaryDirectory() as directory:
        temp_dir = Path(directory)
        source_path = temp_dir / f"source{suffix}"
        output_path = temp_dir / "export.mp4"
        source_path.write_bytes(source)
        if request.mode == "contain":
            video_filter = (
                f"scale={request.width}:{request.height}:force_original_aspect_ratio=decrease,"
                f"pad={request.width}:{request.height}:(ow-iw)/2:(oh-ih)/2:black,setsar=1"
            )
        else:
            source_width, source_height = int(asset.width or 0), int(asset.height or 0)
            if not source_width or not source_height:
                raise RuntimeError("素材缺少视频尺寸，无法裁剪")
            box = _crop_box(source_width, source_height, request.width, request.height, 0.5, 0.5, request.zoom)
            crop_width, crop_height = box[2] - box[0], box[3] - box[1]
            auto_tracking = request.focus_mode == "auto" and request.track_subject and (asset.duration or 0) > 0
            if auto_tracking:
                tracked = _sample_video_focus(source_path, float(asset.duration or 0), temp_dir)
                x_points = [(time, x) for time, x, _ in tracked]
                y_points = [(time, y) for time, _, y in tracked]
                crop_x = _piecewise_expression(x_points, source_width, crop_width)
                crop_y = _piecewise_expression(y_points, source_height, crop_height)
            else:
                focus = (request.focus_x, request.focus_y) if request.focus_mode == "manual" else (0.5, 0.5)
                fixed = _crop_box(source_width, source_height, request.width, request.height, *focus, request.zoom)
                crop_x, crop_y = str(fixed[0]), str(fixed[1])
            video_filter = (
                f"crop={crop_width}:{crop_height}:'{crop_x}':'{crop_y}',"
                f"scale={request.width}:{request.height}:flags=lanczos,setsar=1"
            )
        _run([
            "ffmpeg", "-y", "-i", str(source_path), "-map", "0:v:0", "-map", "0:a?",
            "-vf", video_filter, "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(output_path),
        ])
        return output_path.read_bytes(), "video/mp4", ".mp4"


def export_asset(asset: Asset, request: AssetExportRequest) -> tuple[str, str, str, bool]:
    cache_payload = {
        "source": asset.content_hash or asset.object_key,
        **request.model_dump(),
        "export_version": 1,
    }
    digest = hashlib.sha256(json.dumps(cache_payload, sort_keys=True).encode("utf-8")).hexdigest()[:24]
    extension = ".mp4" if asset.media_type == "video" else ".jpg"
    key = f"exports/{asset.id}/{digest}{extension}"
    filename = f"{Path(asset.original_name).stem}_{request.ratio.replace(':', 'x')}_{request.width}x{request.height}{extension}"
    if object_exists(key):
        return key, "video/mp4" if asset.media_type == "video" else "image/jpeg", filename, True
    source = get_object(asset.object_key)["Body"].read()
    if asset.media_type == "image":
        output, content_type, _ = _image_export(source, request)
    elif asset.media_type == "video":
        output, content_type, _ = _video_export(source, asset, request)
    else:
        raise ValueError("仅图片和视频支持比例导出")
    put_bytes(key, output, content_type)
    return key, content_type, filename, False
