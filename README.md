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

## Docker-based Proof-of-Origin (PO) Token Provider (Optional)

This app can automatically start and use the community POT provider for yt-dlp to improve access to restricted formats when YouTube enforces additional checks.

- Provider: `bgutil-ytdlp-pot-provider` (Docker image)
- Reference: <https://github.com/Brainicism/bgutil-ytdlp-pot-provider>

### How it works

- Detects Docker and the Docker daemon at runtime
- Ensures a provider container is running (starts existing or creates a new one)
- Waits until the provider’s HTTP server is ready
- Wires yt-dlp `--extractor-args` to use the provider automatically
- Falls back cleanly without PO tokens if any step fails

### Configuration options

The `config/settings.json` contains a `pot_provider` section:

```json
{
  "pot_provider": {
    "enabled": true,
    "method": "docker",
    "docker_image": "brainicism/bgutil-ytdlp-pot-provider",
    "docker_container_name": "bgutil-provider",
    "docker_port": 4416,
    "base_url": "http://127.0.0.1:4416",
    "disable_innertube": false
  }
}
```

- `enabled`: toggle provider integration on/off
- `docker_image`, `docker_container_name`, `docker_port`: override defaults
- `base_url`: override if you map a different host/port
- `disable_innertube`: passes `disable_innertube=1` to provider extractor args if true

### Manual PO token (optional)

You can also provide a manual PO token via environment variable:

```bash
# Example token format: mweb.gvs+XXXX
set YT_PO_TOKEN=mweb.gvs+XXXX  # Windows (cmd)
export YT_PO_TOKEN=mweb.gvs+XXXX  # PowerShell/Core or Unix shells
```

If set, yt-dlp will include it as `--extractor-args "youtube:po_token=..."`.

### Prerequisites

- Docker Desktop or Docker Engine must be installed and running.
- If Docker is not available or the container fails to start, the app logs a warning and continues without PO tokens.

### Notes

- This is a best-effort enhancement. It may not bypass all restrictions.
- The provider container is started with `--restart unless-stopped` and mapped to `127.0.0.1:<port>`.
- Health is checked with an exponential backoff (up to ~30s) prior to wiring yt-dlp.

### Provider lifecycle

- On app start, the provider container is started automatically if Docker is available and the feature is enabled.
- On app exit, the container is stopped if `pot_provider.stop_on_exit` is `true` (default).

## Troubleshooting

### Common issues

1. Make sure you're in the project directory
2. Install requirements with `pip install -r requirements.txt`
3. Try running `python main.py`
4. For audio-only MP3, FFmpeg must be installed and on PATH
