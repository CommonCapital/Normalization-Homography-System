"""
Bird's-Eye View Conversion API
FastAPI backend — run with:  python main.py
or:  uvicorn main:app --reload
"""

import os
import sys
import uuid
import asyncio
from pathlib import Path
from typing import Optional

# ── Resolve all paths relative to THIS file, not cwd ──────────────
HERE        = Path(__file__).parent.resolve()
FRONTEND    = HERE.parent / "frontend"
UPLOAD_DIR  = HERE / "uploads"
OUTPUT_DIR  = HERE / "outputs"
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

import cv2
import numpy as np
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from processor import VideoProcessor, ProcessingJob, job_store

app = FastAPI(title="Bird's-Eye View Converter", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Static file mounts ─────────────────────────────────────────────
app.mount("/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")

if (FRONTEND / "static").exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND / "static")), name="static")
else:
    print(f"[WARN] Frontend static dir not found at {FRONTEND / 'static'}")


# ── Routes ─────────────────────────────────────────────────────────

@app.get("/")
async def root():
    index = FRONTEND / "index.html"
    if not index.exists():
        return JSONResponse(
            {"error": f"index.html not found at {index}. "
             "Make sure frontend/ folder is next to backend/."},
            status_code=404
        )
    return FileResponse(str(index))


@app.post("/api/upload")
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    angle: float = Form(45.0),
    output_width: int = Form(800),
    output_height: int = Form(600),
    corner_mode: str = Form("auto"),
    corners: Optional[str] = Form(None),
):
    allowed = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
    suffix = Path(file.filename).suffix.lower()
    if suffix not in allowed:
        raise HTTPException(400, f"Unsupported format: {suffix}. Allowed: {allowed}")

    job_id      = str(uuid.uuid4())[:8]
    input_path  = UPLOAD_DIR / f"{job_id}{suffix}"
    output_path = OUTPUT_DIR / f"{job_id}_birdseye.mp4"

    content = await file.read()
    with open(input_path, "wb") as f:
        f.write(content)

    manual_corners = None
    if corner_mode == "manual" and corners:
        import json
        manual_corners = np.array(json.loads(corners), dtype=np.float32)

    job = ProcessingJob(
        job_id=job_id,
        input_path=str(input_path),
        output_path=str(output_path),
        angle=angle,
        output_size=(output_width, output_height),
        manual_corners=manual_corners,
    )
    job_store[job_id] = job
    background_tasks.add_task(run_job, job)

    return JSONResponse({"job_id": job_id, "status": "queued",
                         "message": f"Processing started for {file.filename}"})


async def run_job(job: ProcessingJob):
    loop = asyncio.get_event_loop()
    processor = VideoProcessor()
    await loop.run_in_executor(None, processor.process, job)


@app.get("/api/status/{job_id}")
async def get_status(job_id: str):
    if job_id == "ping":
        return JSONResponse({"ok": True})
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return JSONResponse(job.to_dict())


@app.get("/api/download/{job_id}")
async def download(job_id: str):
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job.status != "done":
        raise HTTPException(400, f"Job not ready (status: {job.status})")
    return FileResponse(job.output_path, media_type="video/mp4",
                        filename=f"birdseye_{job_id}.mp4")


@app.get("/api/preview/{job_id}")
async def preview_frame(job_id: str, frame: int = 0):
    job = job_store.get(job_id)
    if not job or job.status != "done":
        raise HTTPException(400, "Job not ready")
    cap = cv2.VideoCapture(job.output_path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame)
    ret, img = cap.read()
    cap.release()
    if not ret:
        raise HTTPException(404, "Frame not found")
    preview_path = OUTPUT_DIR / f"{job_id}_preview_{frame}.jpg"
    cv2.imwrite(str(preview_path), img)
    return FileResponse(str(preview_path), media_type="image/jpeg")


@app.delete("/api/job/{job_id}")
async def delete_job(job_id: str):
    job = job_store.pop(job_id, None)
    if not job:
        raise HTTPException(404, "Job not found")
    for p in [job.input_path, job.output_path]:
        try:
            Path(p).unlink(missing_ok=True)
        except Exception:
            pass
    return {"deleted": job_id}


# ── Entry point ────────────────────────────────────────────────────
if __name__ == "__main__":
    print()
    print("  ╔══════════════════════════════════════╗")
    print("  ║   ApexView — Bird's-Eye Converter    ║")
    print("  ╚══════════════════════════════════════╝")
    print()
    print(f"  Backend  : {HERE}")
    print(f"  Frontend : {FRONTEND}")
    print(f"  Uploads  : {UPLOAD_DIR}")
    print(f"  Outputs  : {OUTPUT_DIR}")
    print()
    print("  Open → http://localhost:8000")
    print()
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[str(HERE)],
    )