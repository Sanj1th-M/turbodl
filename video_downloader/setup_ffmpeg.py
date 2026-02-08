import requests
import zipfile
import io
import os
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

FFMPEG_URL = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
TARGET_DIR = os.getcwd()

print(f"Downloading FFmpeg from {FFMPEG_URL}...")
try:
    # SSL verify=True is default and secure
    response = requests.get(FFMPEG_URL, stream=True)
    response.raise_for_status()
    
    print("Download complete. Extracting...")
    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        # Find ffmpeg.exe in the zip
        for file in z.namelist():
            if file.endswith("ffmpeg.exe"):
                print(f"Found {file}, extracting...")
                with z.open(file) as source, open("ffmpeg.exe", "wb") as target:
                    target.write(source.read())
                print("ffmpeg.exe extracted successfully!")
                break
    
    if os.path.exists("ffmpeg.exe"):
        print("Setup successful.")
    else:
        print("Failed to find ffmpeg.exe in the zip archive.")

except Exception as e:
    print(f"Error setting up FFmpeg: {e}")
