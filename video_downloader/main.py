
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
try:
    from .security import validate_url, sanitize_filename, safe_subprocess_run, logger as sec_logger
except ImportError:
    # Fallback for direct execution
    from security import validate_url, sanitize_filename, safe_subprocess_run, logger as sec_logger

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TurboDL")

app = FastAPI(title="TurboDL Downloader")

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https:; media-src 'self' blob: https:; connect-src 'self'; frame-ancestors 'none'"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

import tempfile

# Constants
# Use system temp directory for Vercel/Cloud compatibility
TEMP_DIR = os.path.join(tempfile.gettempdir(), "turbo_dl_temp")

# FFMPEG Detection (defensive for Vercel)
def get_ffmpeg_path():
    local_ffmpeg_win = os.path.join(os.path.dirname(__file__), "ffmpeg.exe")
    local_ffmpeg_unix = os.path.join(os.path.dirname(__file__), "ffmpeg")
    
    if os.path.exists(local_ffmpeg_win):
        return local_ffmpeg_win
    if os.path.exists(local_ffmpeg_unix):
        return local_ffmpeg_unix
    return "ffmpeg" # Fallback to system path

FFMPEG_PATH = get_ffmpeg_path()

@app.on_event("startup")
async def startup_event():
    # Defensive directory creation for Vercel
    try:
        if os.path.exists(TEMP_DIR):
            shutil.rmtree(TEMP_DIR, ignore_errors=True)
        os.makedirs(TEMP_DIR, exist_ok=True)
        logger.info(f"Startup complete: Temp directory initialized at {TEMP_DIR}")
    except Exception as e:
        logger.warning(f"Non-critical startup error: {e}")

# Rate Limiting Setup
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Mount static files
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

# Templates
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

# Jobs storage (In-memory for simplicity)
processing_jobs: Dict[str, Dict] = {}

# Helper to write cookies from environment variable to a file
def get_cookies_path():
    """Reads YOUTUBE_COOKIES env var and writes to a temp file for yt-dlp."""
    cookies_content = os.environ.get("YOUTUBE_COOKIES")
    if not cookies_content:
        return None
        
    try:
        # Create a unique temp file for cookies
        cookie_file = os.path.join(TEMP_DIR, f"youtube_cookies_{uuid.uuid4().hex[:8]}.txt")
        with open(cookie_file, "w", encoding='utf-8') as f:
            f.write(cookies_content)
        return cookie_file
    except Exception as e:
        logger.error(f"Failed to create cookies file: {e}")
        return None

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
        cookie_path = get_cookies_path()
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'no_playlist': True,
                # Enforce IPv4 (Vercel IPv6 is almost always blocked)
                'source_address': '0.0.0.0',
                # Use ONLY the iOS client with a matching User-Agent
                'extractor_args': {
                    'youtube': {
                        'player_client': ['ios'],
                    }
                },
                'http_headers': {
                    'User-Agent': 'com.google.ios.youtube/19.05.6 (iPhone16,2; U; CPU iOS 17_3_1 like Mac OS X; en_US)',
                    'Accept': '*/*',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Origin': 'https://www.youtube.com',
                }
            }

            # --- PROXY / SCRAPER API SUPPORT ---
            proxy_url = os.environ.get("PROXY_URL")
            scraper_key = os.environ.get("SCRAPER_API_KEY")
            
            if scraper_key:
                # ScraperAPI Proxy Integration
                proxy_url = f"http://scraperapi:{scraper_key}@proxy-server.scraperapi.com:8001"
            
            if proxy_url:
                ydl_opts['proxy'] = proxy_url
                logger.info(f"Using proxy for extraction.")
            else:
                logger.warning("No proxy detected in environment.")
            
            if cookie_path:
                ydl_opts['cookiefile'] = cookie_path
                logger.info("Using authenticated cookies for request.")

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(safe_url, download=False)
            except Exception as e:
                error_str = str(e).lower()
                if "sign in to confirm you're not a bot" in error_str:
                    logger.error("YouTube blocked Vercel IP: Bot detection triggered.")
                    
                    status_info = " [Key Detected]" if scraper_key else " [NO KEY DETECTED]"
                    msg = f"YouTube is STILL blocking this server.{status_info} "
                    
                    if not (proxy_url or cookie_path):
                        msg += "IMPORTANT: You must go to the 'Deployments' tab in Vercel and 'Redeploy' for your key to work."
                    else:
                        msg += "The ScraperAPI key may be invalid or out of credits."
                    
                    raise HTTPException(status_code=403, detail=msg)
                raise e
        finally:
            if cookie_path and os.path.exists(cookie_path):
                try:
                    os.remove(cookie_path)
                except:
                    pass
        
        title = info.get('title', 'Unknown Video')
        formats_raw = info.get('formats', [])
        
        # Build format list for frontend
        formats_list = []
        seen_heights = set()
        
        # Video formats (progressive - direct download with audio)
        progressive = [f for f in formats_raw 
                      if f.get('vcodec') != 'none' 
                      and f.get('acodec') != 'none'
                      and f.get('height')]
        progressive.sort(key=lambda x: x.get('height', 0), reverse=True)
        
        # Store best progressive for preview (has audio)
        best_progressive = progressive[0] if progressive else None
        
        for f in progressive:
            h = f.get('height')
            if h and h not in seen_heights:  # Include ALL progressive formats (they have audio)
                formats_list.append({
                    'url': f['url'],
                    'stream_url': f['url'],  # Use same URL for preview (has audio)
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
                # For preview, use best progressive format (has audio) instead of video-only
                preview_url = best_progressive['url'] if best_progressive else f['url']
                formats_list.append({
                    'url': f['url'],
                    'stream_url': preview_url,  # Preview uses progressive (has audio)
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
            'postprocessor_args': [
                '-c:v', 'copy',  # Copy video stream without re-encoding
                '-c:a', 'aac',   # Encode audio to AAC codec
            ],
            'quiet': False,  # Show output for debugging
            'no_warnings': False,
            'no_playlist': True,
            'verbose': True,  # Verbose output to see what's happening
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
        
        logger.info(f"Starting download+merge for job {job_id}: URL={url}, Quality={quality}p")
        
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
