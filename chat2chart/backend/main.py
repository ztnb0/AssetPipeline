import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from runner import FRONTEND_DIR, JOBS_DIR, JobRunner

try:  # optional: load chat2chart/.env so local run needs no shell exports
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except Exception:  # noqa: BLE001
    pass

app = FastAPI(title="chat2chart · 文字生成图表", version="0.1.0")
runner = JobRunner()


class JobIn(BaseModel):
    prompt: str = Field(..., min_length=2, max_length=4000, description="用户想画的图表描述，如：对比中美近几年的黄金储备量")
    extra: str = Field("", max_length=1000, description="可选附加要求，如：用彩色、做 3 张、Lupi 风格")
    anim_seconds: float | None = Field(None, ge=2, le=300, description="入场动画/视频总时长（秒），缺省用后端 C2C_ANIM_SECONDS")
    anim_loop: bool = Field(False, description="动画/视频结束后是否循环重播")
    mode: str = Field("chart", description="生成模式：chart（HTML 图表）或 video（Remotion 动画视频）")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "skill_dir": str(runner._skill or ""),
            "akshare_python": str(runner._akshare_py or ""),
            "remotion_dir": str(runner._remotion_dir or "")}


@app.get("/api/jobs")
def list_jobs() -> dict:
    return {"items": runner.list_jobs()}


@app.post("/api/jobs", status_code=202)
async def create_job(body: JobIn) -> dict:
    return runner.create(body.prompt.strip(), body.extra.strip(),
                         anim_seconds=body.anim_seconds, anim_loop=body.anim_loop,
                         mode=body.mode)


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    job = runner.get(job_id)
    if not job:
        raise HTTPException(404, "任务不存在")
    return job


@app.get("/api/jobs/{job_id}/chart")
def get_chart(job_id: str) -> FileResponse:
    chart = JOBS_DIR / job_id / "chart.html"
    if not chart.exists():
        raise HTTPException(404, "图表尚未生成或不存在")
    return FileResponse(chart, media_type="text/html; charset=utf-8")


@app.get("/api/jobs/{job_id}/video")
def get_video(job_id: str) -> FileResponse:
    video = JOBS_DIR / job_id / "video.mp4"
    if not video.exists():
        raise HTTPException(404, "视频尚未生成或不存在")
    return FileResponse(video, media_type="video/mp4")


@app.get("/", response_class=HTMLResponse)
def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html", media_type="text/html; charset=utf-8")


# /static etc. are not needed; index.html is self-contained.
