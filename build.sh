#!/usr/bin/env bash
# exit on error
set -o errexit

# Install Python dependencies
pip install --upgrade pip
pip install -r video_downloader/requirements.txt

# Install ffmpeg (Render provides apt-get on free tier)
apt-get update
apt-get install -y ffmpeg

echo "Build completed successfully!"
