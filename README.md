# BoltLoad Video Downloader

A secure and efficient video downloader application built with FastAPI, yt-dlp, and ffmpeg.

## Prerequisites

- Python 3.8 or higher
- [FFmpeg](https://ffmpeg.org/download.html) (Ensure it's in your system PATH or placed in the project root)
- Git

## Installation

1.  **Clone the repository:**

    ```bash
    git clone <repository_url>
    cd project-dl
    ```

2.  **Create a virtual environment:**

    ```bash
    python -m venv .venv
    ```

3.  **Activate the virtual environment:**

    -   **Windows:**
        ```bash
        .venv\Scripts\activate
        ```
    -   **macOS/Linux:**
        ```bash
        source .venv/bin/activate
        ```

4.  **Install dependencies:**

    ```bash
    pip install -r video_downloader/requirements.txt
    ```

## Configuration

1.  Navigate to the `video_downloader` directory:
    ```bash
    cd video_downloader
    ```

2.  (Optional) Create a `.env` file if you have specific configurations (currently none required for basic usage).

## Running the Application

1.  Ensure your virtual environment is activated.

2.  Start the server using Uvicorn:

    ```bash
    uvicorn main:app --reload
    ```

3.  Open your browser and navigate to:
    `http://127.0.0.1:8000`

## Usage

1.  Paste a video URL to analyze.
2.  Select the desired quality/format to download.

## Troubleshooting

-   **FFmpeg not found:** Ensure `ffmpeg.exe` is in the `video_downloader` folder or added to your system's PATH.
-   **Import Errors:** Make sure you have installed all requirements in your active virtual environment.
