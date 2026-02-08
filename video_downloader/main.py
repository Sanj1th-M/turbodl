
import os
import re
import logging
import uuid
import asyncio
import json
import shutil
from typing import Optional, List, Dict

from fastapi import FastAPI, Form, Request, HTTPException, BackgroundTasks, Depends, Response, status
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


from pydantic import BaseModel, HttpUrl
import yt_dlp

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Import Security Layer

from security import validate_url, sanitize_filename, safe_subprocess_run, logger as sec_logger

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BoltLoad")

app = FastAPI(title="BoltLoad Downloader")

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



# Constants
TEMP_DIR = "temp_downloads"

# Detect FFMPEG
local_ffmpeg = os.path.join(os.getcwd(), "ffmpeg.exe")
if os.path.exists(local_ffmpeg):
    FFMPEG_PATH = local_ffmpeg
else:
    FFMPEG_PATH = "ffmpeg" # Expecting in PATH

# Ensure temp dir exists
os.makedirs(TEMP_DIR, exist_ok=True)

# Helper to clean up old files (simple version)
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
class AnalyzeRequest(BaseModel):
    url: str

class DownloadRequest(BaseModel):
    url: str
    format_id: str
    is_audio: bool = False

# Jobs storage (In-memory for simplicity)
# Jobs storage (In-memory for simplicity)
processing_jobs: Dict[str, Dict] = {}

# --- DEPENDENCIES ---



# --- ROUTES ---

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})



@app.post("/analyze")
@limiter.limit("10/minute")
async def analyze_video(request: Request, body: AnalyzeRequest):
    """
    1. Validates URL (Anti-SSRF).
    2. Uses yt-dlp to extract metadata.
    3. Returns available formats.
    """
    logger.info(f"Analyzing URL: {body.url}")
    
    # 1. Security Check
    try:
        safe_url = validate_url(body.url)
    except ValueError as e:
        logger.warning(f"Security Alert: {e}")
        raise HTTPException(status_code=403, detail="Access denied: Invalid URL")
        
    # 2. Extract Info using yt-dlp (Dump JSON)
    # We use subprocess securely to isolate execution
    cmd = [
        "yt-dlp", 
        "--dump-json", 
        "--no-playlist", 
        "--no-warnings", 
        "--quiet", 
        safe_url
    ]
    
    try:
        # Run securely
        result = safe_subprocess_run(cmd, timeout=30)
        info = json.loads(result.stdout)
        
        # Parse formats
        formats_list = []
        
        # Title sanitization for display
        title = info.get('title', 'Unknown Video')
        
        # Video Formats
        if 'formats' in info:
            # Filter and sort
            valid_formats = [
                f for f in info['formats'] 
                if f.get('vcodec') != 'none' and f.get('height')
            ]
            valid_formats.sort(key=lambda x: x.get('height', 0) or 0, reverse=True)
            
            seen_heights = set()
            for f in valid_formats:
                h = f.get('height')
                if h and h not in seen_heights:
                    formats_list.append({
                        "id": f['format_id'],
                        "quality": f"{h}p",
                        "type": "video",
                        "height": h,
                        "ext": f.get('ext', 'mp4')
                    })
                    seen_heights.add(h)
                    
        # Audio Only (Best)
        formats_list.append({
            "id": "bestaudio/best",
            "quality": "Audio Only (MP3/M4A)",
            "type": "audio",
            "height": 0,
            "ext": "mp3"
        })
        
        return {
            "status": "success",
            "title": title,
            "thumbnail": info.get('thumbnail'),
            "formats": formats_list
        }

    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise HTTPException(status_code=400, detail="Failed to analyze video. URL might be invalid or unsupported.")

# --- BACKGROUND PROCESSING TASK ---

# --- BACKGROUND PROCESSING TASK ---

def run_download_task(job_id: str, url: str, format_id: str, is_audio: bool):
    try:
        processing_jobs[job_id]["status"] = "processing"
        
        # Create a unique directory for this job to avoid collisions
        job_dir = os.path.join(TEMP_DIR, job_id)
        os.makedirs(job_dir, exist_ok=True)
        
        # Internal filename (UUID based)
        # yt-dlp will append extension
        output_template = os.path.join(job_dir, "video.%(ext)s")
        
        # Construct yt-dlp command
        # Anti-RCE: We use list format, no shell=True
        cmd = ["yt-dlp", "--no-playlist", "--no-warnings", "--quiet", "--output", output_template]
        
        # Explicitly set ffmpeg location if we found it locally
        if FFMPEG_PATH != "ffmpeg":
             cmd.extend(["--ffmpeg-location", FFMPEG_PATH])
        
        if is_audio:
            cmd.extend(["-x", "--audio-format", "mp3", "--audio-quality", "0"])
            target_ext = "mp3"
        else:
            # If format is specific video, we try to merge best audio
            # If standard format_id passed
            if format_id == "best":
                cmd.extend(["-f", "bestvideo+bestaudio/best", "--merge-output-format", "mp4"])
            else:
                 cmd.extend(["-f", f"{format_id}+bestaudio/best", "--merge-output-format", "mp4"])
            target_ext = "mp4"
            
        # Add URL at the end
        cmd.append(url)
        
        # Execute download securely
        safe_subprocess_run(cmd, timeout=300) # 5 min timeout
        
        # Find the resulting file
        # Since we don't know exact extension if merge failed or differ, we look in the folder
        files = os.listdir(job_dir)
        if not files:
            raise Exception("No file downloaded")
            
        downloaded_file = files[0]
        full_path = os.path.join(job_dir, downloaded_file)
        
        # Verify it exists
        if os.path.exists(full_path):
             processing_jobs[job_id].update({
                "status": "completed",
                "file_path": full_path,
                "filename": downloaded_file 
            })
        else:
             raise Exception("Downloaded file missing")

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        processing_jobs[job_id].update({
            "status": "failed",
            "error": str(e)
        })

@app.post("/download")
@limiter.limit("2/minute")
async def start_download(request: Request, body: DownloadRequest, background_tasks: BackgroundTasks):
    """
    1. Validates URL.
    2. Creates a Background Task for downloading/converting.
    3. Returns a Job ID to poll.
    """
    # 1. Security Check
    try:
        safe_url = validate_url(body.url)
    except ValueError as e:
        logger.warning(f"Download blocked: {e}")
        raise HTTPException(status_code=403, detail="Access denied: Invalid URL")
        
    # Prevent memory leak: limit stored jobs
    if len(processing_jobs) >= 50:
        # Remove oldest job
        oldest_job_id = next(iter(processing_jobs))
        processing_jobs.pop(oldest_job_id)
        # Ideally clean up the file too
        old_job_dir = os.path.join(TEMP_DIR, oldest_job_id)
        cleanup_file(old_job_dir)
        
    job_id = str(uuid.uuid4())
    
    processing_jobs[job_id] = {
        "status": "queued",
        "title": "Processing...",
    }
    
    background_tasks.add_task(run_download_task, job_id, safe_url, body.format_id, body.is_audio)
    
    return {"job_id": job_id, "status": "queued"}

@app.get("/job/{job_id}")
async def get_job_status(job_id: str):
    job = processing_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # If completed, returning the download link
    result = {
        "status": job["status"],
        "error": job.get("error")
    }
    
    if job["status"] == "completed":
        # Create a signed-like temp link logic or just direct path access
        # For this task, we return a direct download endpoint
        result["download_url"] = f"/files/{job_id}"
        
    return result

@app.get("/files/{job_id}")
async def download_file(job_id: str, background_tasks: BackgroundTasks):
    job = processing_jobs.get(job_id)
    if not job:
         raise HTTPException(status_code=404, detail="File not found")
         
    if job["status"] != "completed":
        raise HTTPException(status_code=404, detail="File not ready or expired")
        
    file_path = job["file_path"]
    filename = job["filename"]
    
    # Check existence
    if not os.path.exists(file_path):
         raise HTTPException(status_code=404, detail="File purged")
         
    # Return file with correct content disposition
    return FileResponse(
        path=file_path, 
        filename=filename,
        media_type="application/octet-stream"
    )
