import subprocess
import time
import os
import zipfile
import shutil

FFMPEG_URL = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
ZIP_FILENAME = "ffmpeg.zip"

def download_with_curl_retry(url, filename, max_retries=20):
    retries = 0
    while retries < max_retries:
        print(f"Attempt {retries + 1}/{max_retries} downloading {filename}...")
        # -L: Follow redirects
        # -k: Insecure (skip SSL verify)
        # -C -: Resume transfer
        # -o: Output file
        try:
            result = subprocess.run(
                ["curl", "-L", "-k", "-C", "-", "-o", filename, url],
                check=False # Don't raise immediately, check return code
            )
            
            if result.returncode == 0:
                print("Download completed successfully.")
                return True
            else:
                print(f"Curl exited with code {result.returncode}. Retrying in 2 seconds...")
                time.sleep(2)
                retries += 1
        except Exception as e:
             print(f"Error running curl: {e}")
             retries += 1
             time.sleep(2)
             
    print("Failed to download after max retries.")
    return False

def extract_ffmpeg():
    print("Extracting ffmpeg.exe...")
    try:
        with zipfile.ZipFile(ZIP_FILENAME, 'r') as z:
            target_file = None
            for name in z.namelist():
                if name.endswith("bin/ffmpeg.exe"):
                    target_file = name
                    break
            
            if target_file:
                with z.open(target_file) as source, open("ffmpeg.exe", "wb") as target:
                    shutil.copyfileobj(source, target)
                print("ffmpeg.exe extracted successfully!")
                return True
            else:
                print("ffmpeg.exe not found in zip.")
                return False
    except zipfile.BadZipFile:
        print("Error: The downloaded file is not a valid zip file. It might be corrupted.")
        return False
    except Exception as e:
        print(f"Extraction error: {e}")
        return False

def main():
    if os.path.exists("ffmpeg.exe"):
        print("ffmpeg.exe already exists.")
        # Optional: check size or version? For now assume it's good if it exists
        return

    # Check if we have a partial or full zip
    if download_with_curl_retry(FFMPEG_URL, ZIP_FILENAME):
        if extract_ffmpeg():
            print("Setup Complete.")
            # Cleanup
            if os.path.exists(ZIP_FILENAME):
                os.remove(ZIP_FILENAME)
        else:
            print("Setup Failed during extraction.")
    else:
        print("Setup Failed during download.")

if __name__ == "__main__":
    main()
