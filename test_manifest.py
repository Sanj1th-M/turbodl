import yt_dlp
import json

url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ" # Generic test
ydl_opts = {'quiet': True, 'no_warnings': True}

with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    info = ydl.extract_info(url, download=False)
    # Check for manifests
    print(f"Manifest URL: {info.get('manifest_url')}")
    print(f"Webpage URL: {info.get('webpage_url')}")
    
    # Check formats for manifest types
    for f in info.get('formats', []):
        if 'manifest_url' in f:
             print(f"Format {f['format_id']} has manifest: {f['manifest_url']}")
             break
