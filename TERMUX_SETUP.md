# TurboDL on Android Termux - Quick Setup

## Prerequisites
- Android 7.0+ device
- Termux installed from F-Droid (NOT Play Store!)
- Stable internet connection

## Quick Start

### 1. Install Termux from F-Droid
Download: https://f-droid.org/en/packages/com.termux/

### 2. Initial Setup (Run in Termux)
```bash
# Update packages
pkg update && pkg upgrade -y

# Install required packages
pkg install -y python git ffmpeg wget

# Clone the repository
cd ~
git clone https://github.com/Sanj1th-M/turbodl.git
cd turbodl/video_downloader

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Install ngrok
```bash
cd ~
wget https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-arm64.tgz
tar -xvf ngrok-v3-stable-linux-arm64.tgz
mv ngrok $PREFIX/bin/

# Get your authtoken from https://dashboard.ngrok.com/get-started/your-authtoken
ngrok config add-authtoken YOUR_AUTH_TOKEN_HERE
```

### 4. Copy the startup script
```bash
cp ~/turbodl/start_termux.sh ~/ 
chmod +x ~/start_termux.sh
```

### 5. Run the app
```bash
~/start_termux.sh
```

Your public URL will be displayed in the ngrok output!

## Keeping it Running

### Prevent Termux from being killed:
- Settings → Battery → Termux → Unrestricted
- Settings → Apps → Termux → Battery optimization → Don't optimize

### Run in background with tmux:
```bash
pkg install tmux
tmux new -s turbodl
~/start_termux.sh
# Press Ctrl+B then D to detach
# Reattach: tmux attach -t turbodl
```

## Troubleshooting

### Server won't start:
```bash
# Check logs
cat ~/turbodl.log

# Restart
pkill -f uvicorn
~/start_termux.sh
```

### ngrok fails:
- Verify authtoken is set correctly
- Check internet connection
- Free tier gives random URLs each restart

For full documentation, see the complete Termux deployment guide.
