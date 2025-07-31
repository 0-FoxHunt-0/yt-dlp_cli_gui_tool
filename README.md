# YouTube Downloader

A Python-based YouTube downloader with both GUI and CLI interfaces using yt-dlp.

## Features
- Download single videos or playlists
- Choose between video or audio-only downloads
- Progress tracking with real-time updates
- Modern window-based GUI (default)
- Terminal-based UI option
- CLI support for automation
- Threaded downloads (non-blocking UI)
- Detailed status logging
- **Dark/Light mode toggle** with persistent settings
- **Configuration system** for user preferences
- **Window size persistence** across sessions

## Requirements
- Python 3.8+
- yt-dlp
- tkinter (usually comes with Python)

## Installation
1. Clone this repository
2. Install requirements: `pip install -r requirements.txt`

## Usage
- Window GUI mode (default): `python main.py`
- Terminal UI mode: `python main.py --terminal`
- Direct download mode: `python main.py --url <YouTube URL>`

## Configuration
The application automatically creates a `config/settings.json` file to store user preferences:
- **Theme**: Dark/light mode preference (defaults to dark)
- **Window size**: Application window dimensions
- **Output directory**: Default download location
- **Default format**: Preferred download format (audio/video)

Settings are automatically saved and restored between sessions.