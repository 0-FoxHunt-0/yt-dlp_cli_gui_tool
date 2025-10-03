# 🎵 YouTube Downloader GUI

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![yt-dlp](https://img.shields.io/badge/yt--dlp-2024+-red.svg)](https://github.com/yt-dlp/yt-dlp)
[![CustomTkinter](https://img.shields.io/badge/CustomTkinter-5.2+-green.svg)](https://github.com/TomSchimansky/CustomTkinter)
[![License](https://img.shields.io/badge/license-MIT-purple.svg)](LICENSE)

A modern, feature-rich YouTube downloader with a beautiful GUI interface, built on top of yt-dlp. Download videos, playlists, and audio with advanced features like cookie support, progress tracking, and Docker-based PO token providers.

![GUI Screenshot](https://via.placeholder.com/800x450/2b2b2b/ffffff?text=YouTube+Downloader+GUI)

## ✨ Features

### 🎨 **Modern Interface**

- **Beautiful CustomTkinter GUI** with dark/light mode support
- **Automatic theme detection** (follows system theme)
- **Responsive design** with window size persistence
- **Terminal UI option** for server environments

### 📥 **Download Capabilities**

- **Single videos and playlists** support
- **Audio-only or video downloads** with quality selection
- **Batch processing** for multiple URLs
- **Progress tracking** with real-time updates and ETA
- **Resume support** for interrupted downloads

### 🔧 **Advanced Features**

- **Cookie support** for age-restricted/region-locked content
- **Browser cookie extraction** (Chrome, Firefox, Edge, Brave, etc.)
- **Custom cookie files** support
- **FFmpeg integration** for audio conversion and metadata embedding
- **Archive file tracking** to avoid re-downloads

### 🐳 **Docker Integration**

- **Automatic PO Token Provider** via Docker container
- **Enhanced YouTube access** for restricted content
- **Container lifecycle management** (auto-start/stop)
- **Fallback handling** when Docker is unavailable

### ⚙️ **Configuration & Logging**

- **Persistent settings** saved between sessions
- **Detailed logging** with configurable levels
- **Customizable output directories**
- **Metadata embedding** options

## 🚀 Quick Start

### Prerequisites

- **Python 3.8+**
- **FFmpeg** (for audio conversion) - [FFmpeg Installation](#ffmpeg-installation)
- **Docker** (optional, for PO token provider) - [Docker Installation (Optional)](#docker-installation-optional)

### Installation

#### Option 1: Install as Package (Recommended)

```bash
# Clone the repository
git clone https://github.com/yourusername/yt-dlp_cli_gui_tool.git
cd yt-dlp_cli_gui_tool

# Install dependencies
pip install -r requirements.txt

# Run directly
python -m src
```

#### Option 2: Development Installation

```bash
# Install in development mode
pip install -e .

# Run from anywhere
yt-dlp-gui
```

### Basic Usage

#### GUI Mode (Default)

```bash
# Launch the graphical interface
python -m src

# Or if installed as package
yt-dlp-gui
```

#### Terminal Mode

```bash
# Launch terminal interface
python -m src --terminal
```

#### Direct Download

```bash
# Download a single video
python -m src --url "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# Download audio only
python -m src --url "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --audio-only

# Specify output directory
python -m src --url "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --output "/path/to/downloads"
```

## 📋 Detailed Usage

### GUI Interface

1. **Launch the application** using `python -m src`
2. **Paste YouTube URLs** in the URL field
3. **Select download format** (Audio/Video)
4. **Choose output directory** or use default
5. **Configure advanced options** (cookies, metadata, etc.)
6. **Click Download** and monitor progress

### Configuration Options

#### Basic Settings

- **Theme**: Auto/Dark/Light mode
- **Default Format**: Audio or Video
- **Output Directory**: Where downloads are saved
- **Window Size**: Persistent window dimensions

#### Advanced Settings

- **Cookie File**: Path to `cookies.txt` for restricted content
- **Browser Cookies**: Auto-extract from installed browsers
- **Metadata Embedding**: Include title, artist, thumbnail, etc.
- **Archive File**: Track downloaded videos to avoid duplicates

#### PO Token Provider (Docker)

- **Enable/Disable** Docker-based PO token provider
- **Container Settings**: Image, name, port configuration
- **Auto-start/stop** container lifecycle management

### Examples

#### Download a Music Video

```bash
python -m src --url "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --audio-only --output "~/Music"
```

#### Download a Playlist

```bash
python -m src --url "https://www.youtube.com/playlist?list=PLrAXtmRdnEQy4xQG..."

# The GUI will show all videos in the playlist with individual download options
```

#### Download with Custom Settings

```bash
python -m src --url "https://www.youtube.com/watch?v=..." \
    --audio-only \
    --output "/custom/path" \
    --embed-metadata \
    --embed-thumbnail
```

## 🔧 Configuration

### Settings File

The application creates `config/settings.json` with the following structure:

```json
{
  "theme": "auto",
  "window_size": "800x600",
  "output_directory": "~/Downloads",
  "default_format": "audio",
  "cookie_file": "",
  "use_cookies_from_browser": true,
  "cookies_from_browser": "brave",
  "embed_metadata": true,
  "embed_thumbnail": true,
  "pot_provider": {
    "enabled": true,
    "docker_image": "brainicism/bgutil-ytdlp-pot-provider",
    "docker_container_name": "bgutil-provider",
    "docker_port": 4416
  }
}
```

### Cookie Setup

#### Option 1: Browser Cookies (Automatic)

```json
{
  "use_cookies_from_browser": true,
  "cookies_from_browser": "brave"
}
```

Supported browsers: `brave`, `chrome`, `firefox`, `edge`, `opera`, `safari`, `vivaldi`

#### Option 2: Cookie File (Manual)

```json
{
  "cookie_file": "/path/to/cookies.txt"
}
```

Export cookies from your browser using browser extensions or yt-dlp itself:

```bash
yt-dlp --cookies-from-browser brave > cookies.txt
```

### FFmpeg Installation

#### Windows

1. Download from [FFmpeg official site](https://ffmpeg.org/download.html#build-windows)
2. Extract to `C:\ffmpeg`
3. Add `C:\ffmpeg\bin` to PATH environment variable

#### macOS

```bash
brew install ffmpeg
```

#### Linux (Ubuntu/Debian)

```bash
sudo apt install ffmpeg
```

### Docker Installation (Optional)

#### Windows Installation

1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/)
2. Enable WSL 2 backend if prompted

#### macOS Installation

```bash
brew install --cask docker
```

#### Linux

```bash
# Install Docker Engine
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Start Docker service
sudo systemctl start docker
sudo systemctl enable docker
```

## 🐳 Docker PO Token Provider

### What is PO Token Provider?

The PO (Proof-of-Origin) Token Provider helps bypass YouTube's restrictions for certain videos by providing authentication tokens that yt-dlp can use.

### Automatic Setup

1. **Install Docker** (see above)
2. **Enable in settings**:

   ```json
   {
     "pot_provider": {
       "enabled": true
     }
   }
   ```

3. **Restart the application**

### How It Works

- Automatically starts a Docker container with the POT provider
- Configures yt-dlp to use the provider for enhanced access
- Container runs on `http://127.0.0.1:4416` by default
- Automatically stops when application exits

### Troubleshooting

- Ensure Docker Desktop is running
- Check firewall settings for port 4416
- View logs in `logs/` directory for detailed error information

## 🔍 Troubleshooting

### Common Issues

#### "FFmpeg not found"

**Solution**: Install FFmpeg and ensure it's in your PATH

```bash
# Check if FFmpeg is in PATH
ffmpeg -version

# If not found, add to PATH or install
```

#### "Docker not available"

**Solution**: Ensure Docker Desktop is installed and running

```bash
# Check Docker status
docker info

# If Docker is installed but not detected, check PATH
where docker  # Windows
which docker  # Linux/macOS
```

#### "Browser cookies not working"

**Solutions**:

1. Ensure the browser is installed and running
2. Try a different browser in settings
3. Use a cookie file instead

#### "Video says 'Requested format not available'"

**Solutions**:

1. Enable PO Token Provider (Docker)
2. Use browser cookies or cookie file
3. Try different quality settings
4. Check if video is region-restricted

### Debug Mode

Run with verbose logging:

```bash
python -c "
import logging
logging.basicConfig(level=logging.DEBUG)
# Then run your download code
"
```

### Log Files

Check `logs/` directory for detailed error information:

- `yt-dlp_*.log` - Main application logs
- Recent logs are kept (configurable in settings)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Setup

```bash
# Clone repository
git clone https://github.com/yourusername/yt-dlp_cli_gui_tool.git
cd yt-dlp_cli_gui_tool

# Install in development mode
pip install -e ".[dev]"

# Run tests
python -m pytest

# Format code
black src/
isort src/
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **yt-dlp** - The powerful command-line program to download videos
- **CustomTkinter** - Modern and customizable Python UI-library
- **bgutil-ytdlp-pot-provider** - Docker-based PO token provider
- **FFmpeg** - Audio/video processing library

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/yt-dlp_cli_gui_tool/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/yt-dlp_cli_gui_tool/discussions)
- **Documentation**: This README and inline code comments

---

⭐ **Star this repository if you found it helpful!**
