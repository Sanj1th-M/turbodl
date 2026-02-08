import requests
import zipfile
import os
import shutil
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

FFMPEG_URL = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
ZIP_FILENAME = "ffmpeg.zip"

def download_file(url, filename):
    print(f"Downloading {url} to {filename}...")
    try:
        with requests.get(url, stream=True, verify=False) as r:
            r.raise_for_status()
            with open(filename, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        print("Download complete.")
        return True
    except Exception as e:
        print(f"Download failed: {e}")
        return False

def setup_ffmpeg():
    if os.path.exists("ffmpeg.exe"):
        print("ffmpeg.exe already exists. Skipping download.")
        return

    if not os.path.exists(ZIP_FILENAME):
        if not download_file(FFMPEG_URL, ZIP_FILENAME):
            return

    print("Extracting ffmpeg.exe from zip...")
    try:
        with zipfile.ZipFile(ZIP_FILENAME, 'r') as z:
            # Look for ffmpeg.exe in bin folder
            target_file = None
            for name in z.namelist():
                if name.endswith("bin/ffmpeg.exe"):
                    target_file = name
                    break
            
            if target_file:
                with z.open(target_file) as source, open("ffmpeg.exe", "wb") as target:
                    shutil.copyfileobj(source, target)
                print("ffmpeg.exe extracted successfully!")
            else:
                print("ffmpeg.exe not found in zip archive.")
    except Exception as e:
        print(f"Extraction failed: {e}")
    finally:
        # Cleanup zip
        if os.path.exists(ZIP_FILENAME):
            os.remove(ZIP_FILENAME)
            print("Cleaned up zip file.")

if __name__ == "__main__":
    setup_ffmpeg()
