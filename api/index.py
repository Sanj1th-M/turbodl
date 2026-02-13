import sys
import os

# Add the project root to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Import the FastAPI app
try:
    from video_downloader.main import app
except ImportError as e:
    # Print error to logs if import fails (though diagnostics passed)
    print(f"Error importing app: {e}")
    raise e

# Vercel supports 'app' directly for ASGI/WSGI applications
# We also alias it to 'handler' for maximum compatibility
handler = app
