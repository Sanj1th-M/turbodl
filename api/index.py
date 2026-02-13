import sys
import os
import traceback

# Add the project root to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

def get_app():
    """Import and return the FastAPI app."""
    from video_downloader.main import app
    return app

async def app(scope, receive, send):
    """
    ASGI Proxy/Bridge.
    Attempts to run the FastAPI app, but catches any startup/invocation errors.
    """
    if scope['type'] != 'http':
        # Let the real app handle other types if it can load
        try:
            real_app = get_app()
            await real_app(scope, receive, send)
        except:
             pass
        return

    try:
        # 1. Try to load the real app
        real_app = get_app()
        # 2. Try to handle the request
        await real_app(scope, receive, send)
    except Exception as e:
        # Handle failure during import OR execution
        error_msg = traceback.format_exc()
        print(f"CRITICAL VERCEL INVOCATION ERROR:\n{error_msg}")
        
        await send({
            'type': 'http.response.start',
            'status': 500,
            'headers': [
                (b'content-type', b'text/plain'),
            ],
        })
        await send({
            'type': 'http.response.body',
            'body': f"CRITICAL VERCEL INVOCATION ERROR:\n\n{error_msg}\n\nScope:\n{scope}".encode('utf-8'),
        })

# Vercel looks for 'app' or 'handler'
handler = app

