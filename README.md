# YouTube Downloader

A Python-based YouTube downloader with both GUI and CLI interfaces using yt-dlp.

## Features

- Download single videos or playlists
- Choose between video or audio-only downloads
- Progress tracking with real-time updates
- **Modern CustomTkinter GUI** (default) with automatic dark/light mode
- Terminal-based UI option
- CLI support for automation
- Threaded downloads (non-blocking UI)
- Detailed status logging
- **Automatic theme detection** with manual toggle
- **Configuration system** for user preferences
- **Window size persistence** across sessions

## Requirements

- Python 3.8+
- yt-dlp
- tkinter (usually comes with Python)

## Installation

### Option 1: Install as a package (recommended)

```bash
# Install in development mode (for development)
pip install -e .

# Or install globally
pip install .
```

After installation, you can run the tool from anywhere:

```bash
# Modern GUI mode (default)
yt-dlp-gui

# Terminal UI mode
yt-dlp-gui --terminal

# Direct download mode
yt-dlp-gui --url <YouTube URL> [--audio-only] [--output <directory>]

# Alternative command name
ytdlp-gui --url <YouTube URL>
```

### Option 2: Run directly from source

```bash
# Clone this repository
git clone https://github.com/yourusername/yt-dlp_cli_gui_tool.git
cd yt-dlp_cli_gui_tool

# Install requirements
pip install -r requirements.txt

# Run the application
python main.py
```

## Usage

### Package installation (Option 1)

- Modern GUI mode (default): `yt-dlp-gui`
- Terminal UI mode: `yt-dlp-gui --terminal`
- Direct download mode: `yt-dlp-gui --url <YouTube URL>`

### Direct execution (Option 2)

- Modern GUI mode (default): `python main.py`
- Terminal UI mode: `python main.py --terminal`
- Direct download mode: `python main.py --url <YouTube URL>`

## Examples

```bash
# Download a video with GUI
yt-dlp-gui

# Download audio only from a specific URL
yt-dlp-gui --url "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --audio-only

# Download to a specific directory
yt-dlp-gui --url "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --output "C:\Downloads"

# Use terminal interface
yt-dlp-gui --terminal
```

## Configuration

The application automatically creates a `config/settings.json` file to store user preferences:

- **Theme**: Auto/dark/light mode preference (defaults to auto - follows system theme)
- **Window size**: Application window dimensions
- **Output directory**: Default download location
- **Default format**: Preferred download format (audio/video)

### Cookies (age-restricted/region-locked content)

- You can set a `cookie_file` path to an exported `cookies.txt`.
- Or enable `use_cookies_from_browser` and set `cookies_from_browser` (default: `brave`) to auto-load cookies from your browser.
- To change these, edit `config/settings.json` or use the GUI Cookie section.

Settings are automatically saved and restored between sessions.

## Troubleshooting

### If you get import errors:

1. Make sure you're in the project directory
2. Install requirements: `pip install -r requirements.txt`
3. Try running: `python main.py`
4. For audio-only MP3, FFmpeg must be installed and on PATH.
