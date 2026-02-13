import sys
import os
import traceback

# Add the project root to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Fail-safe ASGI handler
async def fallback_handler(scope, receive, send):
    """Raw ASGI handler to display errors when FastAPI fails to load."""
    if scope['type'] != 'http':
        return
        
    error_msg = "Unknown Error"
    try:
        # Re-raise the exception to get the traceback
        raise StartupException
    except:
         error_msg = traceback.format_exc()

    await send({
        'type': 'http.response.start',
        'status': 500,
        'headers': [
            [b'content-type', b'text/plain'],
        ],
    })
    await send({
        'type': 'http.response.body',
        'body': f"CRITICAL VERCEL STARTUP ERROR:\n\n{error_msg}".encode('utf-8'),
    })

StartupException = None

try:
    # Try to import the actual app
    from video_downloader.main import app
    handler = app
    
except Exception as e:
    StartupException = e
    # Use the fallback raw ASGI handler
    handler = fallback_handler

# Verify requirements were actually installed
try:
    import fastapi
    import yt_dlp
except ImportError as e:
    StartupException = e
    handler = fallback_handler
