import sys
import os

def handler(environ, start_response):
    status = '200 OK'
    output = "Vercel Python Execution Verified!\n"
    output += f"Python Version: {sys.version}\n"
    output += f"CWD: {os.getcwd()}\n"
    
    response_headers = [('Content-type', 'text/plain'),
                        ('Content-Length', str(len(output)))]
    start_response(status, response_headers)
    return [output.encode('utf-8')]
