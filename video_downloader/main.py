
import os
import re
import logging
import uuid
import asyncio
import json
import shutil
import subprocess
from typing import Optional, List, Dict
from urllib.parse import unquote

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, Query
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from pydantic import BaseModel
import yt_dlp

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Import Security Layer
from security import validate_url, sanitize_filename, safe_subprocess_run, logger as sec_logger

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TurboDL")

app = FastAPI(title="TurboDL Downloader")

# Constants
TEMP_DIR = "temp_downloads"

# Detect FFMPEG
local_ffmpeg = os.path.join(os.getcwd(), "ffmpeg.exe")
if os.path.exists(local_ffmpeg):
    FFMPEG_PATH = local_ffmpeg
else:
    FFMPEG_PATH = "ffmpeg"  # Expecting in PATH

# Ensure temp dir exists
os.makedirs(TEMP_DIR, exist_ok=True)

@app.on_event("startup")
async def startup_event():
    # Clean up temp directory on startup
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)
    os.makedirs(TEMP_DIR, exist_ok=True)
    logger.info("Startup complete: Temp directory cleaned.")

# Rate Limiting Setup
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# Jobs storage (In-memory for simplicity)
processing_jobs: Dict[str, Dict] = {}

# Helper to clean up old files
def cleanup_file(path: str):
    try:
        if os.path.exists(path):
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
            logger.info(f"Cleaned up: {path}")
    except Exception as e:
        logger.error(f"Cleanup error for {path}: {e}")

# Data Models
class DownloadRequest(BaseModel):
    url: str

class ProcessRequest(BaseModel):
    url: str
    quality: int  # Height in pixels, e.g., 1080, 720

# --- ROUTES ---

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/download")
@limiter.limit("10/minute")
async def download_video(request: Request, body: DownloadRequest):
    """
    Analyzes video URL and returns available formats
    Frontend expects: { title, formats[] }
    """
    logger.info(f"Analyzing URL: {body.url}")
    
    # Security Check
    try:
        safe_url = validate_url(body.url)
    except ValueError as e:
        logger.warning(f"Security Alert: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    
    try:
        # Use yt-dlp to get video info
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'no_playlist': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(safe_url, download=False)
        
        title = info.get('title', 'Unknown Video')
        formats_raw = info.get('formats', [])
        
        # Build format list for frontend
        formats_list = []
        seen_heights = set()
        
        # Video formats (progressive - direct download)
        progressive = [f for f in formats_raw 
                      if f.get('vcodec') != 'none' 
                      and f.get('acodec') != 'none'
                      and f.get('height')]
        progressive.sort(key=lambda x: x.get('height', 0), reverse=True)
        
        for f in progressive:
            h = f.get('height')
            if h and h not in seen_heights and h <= 720:  # Progressive typically only 720p and below
                formats_list.append({
                    'url': f['url'],
                    'quality': f'{h}p',
                    'type': 'video',  # Direct download
                    'height': h
                })
                seen_heights.add(h)
        
        # High quality formats (video-only, need processing)
        video_only = [f for f in formats_raw
                     if f.get('vcodec') != 'none'
                     and f.get('acodec') == 'none'
                     and f.get('height')]
        video_only.sort(key=lambda x: x.get('height', 0), reverse=True)
        
        for f in video_only:
            h = f.get('height')
            if h and h not in seen_heights and h >= 1080:  # High quality only
                formats_list.append({
                    'url': f['url'],
                    'stream_url': f['url'],  # For preview
                    'quality': f'{h}p',
                    'type': 'process',  # Needs server processing
                    'height': h
                })
                seen_heights.add(h)
        
        # Audio only
        audio_formats = [f for f in formats_raw if f.get('acodec') != 'none' and f.get('vcodec') == 'none']
        if audio_formats:
            best_audio = max(audio_formats, key=lambda x: x.get('abr', 0) or 0)
            formats_list.append({
                'url': best_audio['url'],
                'quality': 'Audio',
                'type': 'audio',
                'height': 0
            })
        
        return {
            "title": title,
            "formats": formats_list
        }
        
    except Exception as e:
        logger.error(f"Download failed: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to process video: {str(e)}")


@app.post("/process_video")
@limiter.limit("5/minute")
async def process_video(request: Request, body: ProcessRequest, background_tasks: BackgroundTasks):
    """
    Process high-quality video (merge video + audio)
    Returns job_id for polling
    """
    logger.info(f"Processing video: {body.url} at {body.quality}p")
    
    # Security Check
    try:
        safe_url = validate_url(body.url)
    except ValueError as e:
        logger.warning(f"Security Alert: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    
    # Create job
    job_id = str(uuid.uuid4())
    processing_jobs[job_id] = {
        "status": "queued",
        "progress": 0,
    }
    
    # Start background task
    background_tasks.add_task(run_merge_task, job_id, safe_url, body.quality)
    
    return {"job_id": job_id}


def run_merge_task(job_id: str, url: str, quality: int):
    """Background task to download and merge video+audio"""
    try:
        processing_jobs[job_id]["status"] = "processing"
        processing_jobs[job_id]["progress"] = 10
        
        # Create job directory
        job_dir = os.path.join(TEMP_DIR, job_id)
        os.makedirs(job_dir, exist_ok=True)
        
        output_file = os.path.join(job_dir, "output.mp4")
        
        # Use yt-dlp to download and merge
        ydl_opts = {
            'format': f'bestvideo[height<={quality}]+bestaudio/best',
            'outtmpl': output_file,
            'merge_output_format': 'mp4',
            'quiet': True,
            'no_warnings': True,
            'no_playlist': True,
        }
        
        if FFMPEG_PATH != "ffmpeg":
            ydl_opts['ffmpeg_location'] = FFMPEG_PATH
        
        # Progress hook
        def progress_hook(d):
            if d['status'] == 'downloading':
                try:
                    percent = d.get('downloaded_bytes', 0) / d.get('total_bytes', 1) * 100
                    processing_jobs[job_id]["progress"] = min(int(percent * 0.8), 80)  # 0-80%
                except:
                    pass
            elif d['status'] == 'finished':
                processing_jobs[job_id]["progress"] = 90
        
        ydl_opts['progress_hooks'] = [progress_hook]
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        processing_jobs[job_id]["progress"] = 100
        processing_jobs[job_id]["status"] = "completed"
        processing_jobs[job_id]["download_url"] = f"/download_file/{job_id}"
        processing_jobs[job_id]["file_path"] = output_file
        
        logger.info(f"Job {job_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        processing_jobs[job_id]["status"] = "failed"
        processing_jobs[job_id]["error"] = str(e)


@app.get("/process_status/{job_id}")
async def get_process_status(job_id: str):
    """Get status of processing job"""
    job = processing_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {
        "status": job["status"],
        "progress": job.get("progress", 0),
        "download_url": job.get("download_url"),
        "error": job.get("error")
    }


@app.get("/download_file/{job_id}")
async def download_processed_file(job_id: str):
    """Download completed processed file"""
    job = processing_jobs.get(job_id)
    if not job or job["status"] != "completed":
        raise HTTPException(status_code=404, detail="File not ready")
    
    file_path = job.get("file_path")
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        path=file_path,
        filename="video.mp4",
        media_type="video/mp4"
    )


@app.get("/stream_video")
async def stream_video(url: str = Query(...), title: str = Query("video")):
    """Proxy video stream for preview/download"""
    try:
        # Decode URL
        video_url = unquote(url)
        
        # For direct downloads, redirect to the source
        # This works for most video platforms
        return RedirectResponse(url=video_url)
        
    except Exception as e:
        logger.error(f"Stream error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
