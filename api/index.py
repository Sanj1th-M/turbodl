import sys
import os
import traceback
from fastapi import FastAPI, Response

# Add the project root to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from video_downloader.main import app
    handler = app
except Exception as e:
    # Catch import errors (missing modules, syntax errors, etc.)
    error_msg = traceback.format_exc()
    
    app = FastAPI()
    
    @app.get("/{catchall:path}")
    def catch_all(catchall: str):
        return Response(content=f"Startup Error:\n\n{error_msg}", media_type="text/plain", status_code=500)
        
    handler = app
