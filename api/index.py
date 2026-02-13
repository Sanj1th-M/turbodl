import sys
import os

# Add the project root to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from video_downloader.main import app

# Vercel looks for 'app' or 'handler'
handler = app
