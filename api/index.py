from http.server import BaseHTTPRequestHandler
import sys
import os
import pkg_resources

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        
        output = []
        output.append("--- Vercel Diagnostic ---")
        output.append("Status: Running")
        output.append(f"CWD: {os.getcwd()}")
        output.append(f"Sys Path: {sys.path}")
        
        output.append("\n--- Installed Packages ---")
        try:
            installed_packages = [f"{d.project_name}=={d.version}" for d in pkg_resources.working_set]
            output.extend(installed_packages)
        except Exception as e:
            output.append(f"Error listing packages: {e}")
            
        output.append("\n--- Import Check ---")
        try:
            import video_downloader.main
            output.append("SUCCESS: Imported video_downloader.main")
        except Exception as e:
            output.append(f"FAILURE: Could not import video_downloader.main\n{e}")

        self.wfile.write("\n".join(output).encode('utf-8'))
