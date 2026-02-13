import sys
import os
import traceback

# Add the project root to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

def app(environ, start_response):
    """
    Diagnostic WSGI handler.
    Attempts to import the main application to check for dependency errors.
    """
    status = '200 OK'
    output = []
    output.append("--- Dependency Import Check ---")
    
    try:
        # Step 1: Check sys.path
        output.append("Checking sys.path...")
        
        # Step 2: Try importing main app
        output.append("Importing video_downloader.main...")
        import video_downloader.main
        output.append("SUCCESS: App module imported!")
        
        # Step 3: Check if 'app' exists
        if hasattr(video_downloader.main, 'app'):
             output.append("SUCCESS: FastAPI 'app' object found.")
        else:
             output.append("WARNING: 'app' object NOT found in module.")
             
    except Exception as e:
        output.append("\nCRITICAL FAILURE during import:")
        output.append(traceback.format_exc())
    
    response_text = "\n".join(output)
    
    response_headers = [
        ('Content-type', 'text/plain'),
        ('Content-Length', str(len(response_text)))
    ]
    
    start_response(status, response_headers)
    return [response_text.encode('utf-8')]
