
import socket
import ipaddress
import re
import shlex
import subprocess
import logging
from urllib.parse import urlparse
from typing import List, Tuple, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("security")




# --- STRICT CONSTANTS ---
# Blocked subnets (Private ranges)
BLOCKED_SUBNETS = [
    ipaddress.ip_network("127.0.0.0/8"),      # Loopback
    ipaddress.ip_network("10.0.0.0/8"),       # Private Class A
    ipaddress.ip_network("172.16.0.0/12"),    # Private Class B
    ipaddress.ip_network("192.168.0.0/16"),   # Private Class C
    ipaddress.ip_network("169.254.0.0/16"),   # Link-Local
    ipaddress.ip_network("::1/128"),          # IPv6 Loopback
    ipaddress.ip_network("fc00::/7"),         # IPv6 Unique Local
    ipaddress.ip_network("fe80::/10"),        # IPv6 Link-Local
]

# Allowed domains (Optional whitelist, currently permissive for public internet)
# If strict domain whitelisting is needed, add logic here.

# --- ANTI-SSRF LAYER ---
def validate_url(url: str) -> str:
    """
    Validates a URL to prevent SSRF attacks.
    1. Parses the URL.
    2. Resolves the hostname to an IP address.
    3. Checks if the IP is in a blocked subnet (Private/Local).
    4. Returns the URL if safe, raises ValueError if unsafe.
    """
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            raise ValueError("Invalid URL: No hostname found")

        # Resolve DNS
        # Note: socket.gethostbyname handles /etc/hosts, so we trust Python's resolver 
        # but check the RESULTING IP against our blocklist.
        ip_addr = socket.gethostbyname(hostname)
        
        # Check against blocklist
        ip_obj = ipaddress.ip_address(ip_addr)
        for subnet in BLOCKED_SUBNETS:
             if ip_obj in subnet:
                 logger.warning(f"SSRF Attempt Blocked: {url} resolved to {ip_addr}")
                 raise ValueError(f"Access to private network resource ({ip_addr}) is FORBIDDEN.")

        return url

    except socket.gaierror:
        raise ValueError("Invalid URL: Hostname could not be resolved")
    except ValueError as e:
        raise e
    except Exception as e:
        logger.error(f"URL Validation Error: {e}")
        raise ValueError("URL validation failed")

# --- INPUT SANITIZATION ---
def sanitize_filename(filename: str) -> str:
    """
    Sanitizes a filename to prevent directory traversal and shell injection.
    Allows only alphanumeric, dashes, underscores, and dots.
    """
    # Remove any directory components
    filename = filename.split("/")[-1].split("\\")[-1]
    
    # Whitelist characters
    safe_filename = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', filename)
    
    # Prevent empty filenames
    if not safe_filename or safe_filename == "." or safe_filename == "..":
        return "downloaded_file.mp4"
        
    return safe_filename

# --- ANTI-RCE LAYER ---
def safe_subprocess_run(command: List[str], check: bool = True, timeout: int = 300) -> subprocess.CompletedProcess:
    """
    Executes a subprocess securely.
    1. FORBIDS shell=True. 
    2. Requires command to be a list of arguments.
    3. Enforces timeout.
    """
    if isinstance(command, str):
         raise RuntimeError("SECURITY ERROR: Command must be a LIST of arguments, not a string. Shell=True is forbidden.")
    
    logger.info(f"Executing Safe Command: {shlex.join(command)}")
    
    try:
        # shell=False is default, but we explicit it for clarity
        result = subprocess.run(
            command, 
            check=check, 
            text=True, 
            capture_output=True, 
            shell=False,  # CRITICAL: Prevent shell injection
            timeout=timeout
        )
        return result
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {e.stderr}")
        raise e
    except subprocess.TimeoutExpired:
        logger.error(f"Command timed out after {timeout}s")
        raise RuntimeError("Process execution timed out")

# --- END OF SECURITY LAYER ---


