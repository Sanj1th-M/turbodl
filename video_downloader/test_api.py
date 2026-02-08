import requests
import json

base_url = "http://localhost:8000"

# Use a YouTube Shorts video as it's short and fast to test
video_url = "https://www.youtube.com/shorts/51QcI54G6G0" # Just a random safe short URL or similar

print(f"Testing /download with {video_url}...")
try:
    response = requests.post(f"{base_url}/download", json={"url": video_url})
    if response.status_code == 200:
        data = response.json()
        print("Success!")
        print(f"Title: {data.get('title')}")
        formats = data.get('formats', [])
        
        # Check for 'process' type
        process_fmt = next((f for f in formats if f.get('type') == 'process'), None)
        if process_fmt:
            print("Found 'process' format option:")
            print(json.dumps(process_fmt, indent=2))
        else:
            print("WARNING: No 'process' format found!")
            
        print(f"Total formats found: {len(formats)}")
    else:
        print(f"Error {response.status_code}: {response.text}")

except Exception as e:
    print(f"Request failed: {e}")
