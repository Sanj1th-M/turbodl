from http import HTTPStatus
import sys
import os

def handler(environ, start_response):
    """
    Standard WSGI handler.
    Vercel supports this natively without any libraries.
    """
    status = '200 OK'
    
    # helper to get output
    output_lines = []
    output_lines.append(b"Vercel Python WSGI is working!")
    output_lines.append(b"")
    output_lines.append(f"CWD: {os.getcwd()}".encode('utf-8'))
    output_lines.append(f"Python: {sys.version}".encode('utf-8'))
    
    output = b"\n".join(output_lines)

    response_headers = [
        ('Content-type', 'text/plain'),
        ('Content-Length', str(len(output)))
    ]
    
    start_response(status, response_headers)
    return [output]
