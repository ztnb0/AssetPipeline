import json
import subprocess
import tempfile
import threading
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

from .analyzer import analyze_image, analyze_images
from .audio_analyzer import analyze_audio
from .database import SessionLocal
from .models import Asset, AssetStatus
from .storage import get_object, move_object, put_bytes
from .vector_store import safe_index_asset


# This demo runs background analysis in the API process. Limit expensive
# FFmpeg, Whisper, and Qwen work without introducing an external task queue.
ANALYSIS_SEMAPHORE = threading.BoundedSemaphore(2)


def _run(command: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(command, capture_output=True, check=True, timeout=120)


def _probe(path: Path) -> dict:
    result = _run([
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration,format_name,bit_rate:stream=index,codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels",
        "-of", "json", str(path),
    ])
    return json.loads(result.stdout.decode("utf-8"))


def _number(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _media_metadata(probe: dict) -> dict:
    fmt = probe.get("format", {})
    streams = probe.get("streams", [])
    return {
        "format": fmt.get("format_name"),
        "bit_rate": int(fmt["bit_rate"]) if str(fmt.get("bit_rate", "")).isdigit() else None,
        "streams": [{key: value for key, value in stream.items() if key != "index"} for stream in streams],
    }


def _video_frames(path: Path, duration: float) -> tuple[list[bytes], list[float]]:
    percentages = [0.05, 0.25, 0.50, 0.75, 0.95]
    points = [duration * percentage for percentage in percentages] if duration > 0.2 else [0.0]
    frames = []
    for index, point in enumerate(points):
        output = path.parent / f"frame-{index}.jpg"
        _run([
            "ffmpeg", "-y", "-ss", f"{point:.3f}", "-i", str(path),
            "-frames:v", "1", "-vf", "scale='min(1280,iw)':-2", "-q:v", "3", str(output),
        ])
        if output.exists() and output.stat().st_size:
            frames.append(output.read_bytes())
    if not frames:
        raise ValueError("视频中没有可提取的画面")
    return frames, points[:len(frames)]


def _process_image(asset: Asset, original: bytes) -> None:
    with Image.open(BytesIO(original)) as image:
        image = ImageOps.exif_transpose(image)
        asset.width, asset.height = image.size
        image.thumbnail((640, 640))
        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGB")
        thumbnail = BytesIO()
        image.save(thumbnail, format="WEBP", quality=82)
    asset.thumbnail_key = f"thumbnails/{asset.id}.webp"
    put_bytes(asset.thumbnail_key, thumbnail.getvalue(), "image/webp")
    analysis = analyze_image(original, asset.mime_type)
    asset.description, asset.tags, asset.scene, asset.categories = analysis["description"], analysis["tags"], analysis["scene"], analysis["categories"]
    asset.media_metadata = {**asset.media_metadata, "analysis_version": "visual-v2"}
    asset.category = asset.categories[0] if asset.categories else "其他"


def _process_video(asset: Asset, original: bytes) -> None:
    suffix = Path(asset.original_name).suffix or ".mp4"
    with tempfile.TemporaryDirectory() as temp_dir:
        source = Path(temp_dir) / f"source{suffix}"
        source.write_bytes(original)
        probe = _probe(source)
        asset.duration = _number(probe.get("format", {}).get("duration"), 0.0)
        video_stream = next((stream for stream in probe.get("streams", []) if stream.get("codec_type") == "video"), {})
        asset.width = video_stream.get("width")
        asset.height = video_stream.get("height")
        asset.media_metadata = _media_metadata(probe)
        frames, frame_times = _video_frames(source, asset.duration or 0.0)
    asset.thumbnail_key = f"thumbnails/{asset.id}.jpg"
    put_bytes(asset.thumbnail_key, frames[0], "image/jpeg")
    analysis = analyze_images([(frame, "image/jpeg") for frame in frames], frame_times=frame_times, asset_context=f"视频文件名：{asset.original_name}；时长：{asset.duration:.2f} 秒")
    asset.description, asset.tags, asset.scene, asset.categories = analysis["description"], analysis["tags"], analysis["scene"], analysis["categories"]
    asset.media_metadata = {**asset.media_metadata, "frame_analysis": analysis.get("frame_analysis", []), "analysis_version": "visual-v2"}
    asset.category = asset.categories[0] if asset.categories else "其他"


def _process_audio(asset: Asset, original: bytes) -> None:
    suffix = Path(asset.original_name).suffix or ".audio"
    with tempfile.TemporaryDirectory() as temp_dir:
        source = Path(temp_dir) / f"source{suffix}"
        source.write_bytes(original)
        probe = _probe(source)
        try:
            content_analysis = analyze_audio(source)
        except Exception as exc:
            content_analysis = None
            asr_error = str(exc)[:1000]
    asset.duration = _number(probe.get("format", {}).get("duration"), 0.0)
    asset.media_metadata = _media_metadata(probe)
    audio_stream = next((stream for stream in probe.get("streams", []) if stream.get("codec_type") == "audio"), {})
    codec = audio_stream.get("codec_name", "未知编码")
    filename = Path(asset.original_name).stem.lower()
    content_tags = []
    for keyword, label in {
        "配音": "配音", "旁白": "旁白", "解说": "解说", "采访": "采访",
        "访谈": "访谈", "音乐": "音乐", "bgm": "背景音乐", "音效": "音效",
        "播客": "播客", "podcast": "播客", "会议": "会议录音",
    }.items():
        if keyword in filename:
            content_tags.append(label)
    technical_tags = ["音频", "音频素材", f"{round(asset.duration or 0)}秒", codec, codec.upper(), Path(asset.original_name).suffix.lstrip(".").upper()]
    if audio_stream.get("channels") == 2:
        technical_tags.append("立体声")
    if audio_stream.get("sample_rate"):
        technical_tags.append(f"{audio_stream['sample_rate']}Hz")
    if content_analysis:
        asset.description = content_analysis["description"]
        asset.tags = list(dict.fromkeys(content_analysis["tags"] + content_tags + technical_tags))[:30]
        asset.scene = content_analysis["scene"]
        asset.categories = content_analysis["categories"]
        asset.category = asset.categories[0]
        asset.media_metadata = {
            **asset.media_metadata,
            "transcript": content_analysis["transcript"],
            "language": content_analysis["language"],
            "language_probability": content_analysis["language_probability"],
        }
    else:
        asset.description = f"音频素材，时长约 {asset.duration:.1f} 秒，编码格式为 {codec}。ASR 暂未完成，当前仅提供技术标签。"
        asset.tags = list(dict.fromkeys(content_tags + technical_tags))
        asset.scene = content_tags[0] if content_tags else "待人工分类音频"
        asset.category = "音频制作" if content_tags else "待内容识别"
        asset.categories = [asset.category]
        asset.media_metadata = {**asset.media_metadata, "asr_error": asr_error}


def _process_asset(asset_id: str) -> None:
    db = SessionLocal()
    asset = db.get(Asset, asset_id)
    if not asset:
        db.close()
        return
    try:
        response = get_object(asset.object_key)
        original = response["Body"].read()
        if asset.media_type == "image":
            _process_image(asset, original)
        elif asset.media_type == "video":
            _process_video(asset, original)
        elif asset.media_type == "audio":
            _process_audio(asset, original)
        else:
            raise ValueError(f"不支持的媒体类型：{asset.media_type}")
        asset.status = AssetStatus.ready
        asset.categories = asset.categories or ([asset.category] if asset.category else ["其他"])
        asset.category = asset.categories[0]
        category = "".join(char for char in (asset.category or "未分类") if char not in '/\\:*?"<>|').strip() or "未分类"
        suffix = Path(asset.object_key).suffix
        target = f"media/{asset.media_type}/{category}/{asset.id}{suffix}"
        move_object(asset.object_key, target)
        asset.object_key = target
        asset.error_message = None
        db.commit()
        safe_index_asset(asset)
    except Exception as exc:
        asset.status = AssetStatus.failed
        asset.error_message = str(exc)[:2000]
        db.commit()
    finally:
        db.close()


def process_asset(asset_id: str) -> None:
    with ANALYSIS_SEMAPHORE:
        _process_asset(asset_id)


# Backward-compatible import name used by older integrations.
process_image = process_asset
