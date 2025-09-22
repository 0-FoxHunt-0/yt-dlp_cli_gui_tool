def user_friendly_youtube_error(error_msg: str) -> str:
    msg = (error_msg or "").lower()
    if "http error 403" in msg or "forbidden" in msg:
        return ("YouTube is blocking the download (HTTP 403 Forbidden). "
                "Try using browser cookies or wait a few hours before retrying.")
    if "po token" in msg or "gvs po token" in msg:
        return ("YouTube's Proof of Origin (PO) token system is blocking access. "
                "Try using browser cookies from a logged-in session.")
    if "no request handlers configured" in msg:
        return ("YouTube request handler configuration error. "
                "Update yt-dlp or use browser cookies.")
    if "video unavailable" in msg:
        return ("The video is not available (deleted/private/region-locked).")
    if "not available on this app" in msg:
        return ("Content not available on this application (geo/licensing).")
    if "unable to download format" in msg:
        return ("Could not find a suitable video format to download.")
    return "YouTube access error occurred. Try using browser cookies or updating yt-dlp."


def ffmpeg_instructions(system_name: str) -> str:
    system_name = (system_name or "").lower()
    if system_name == "windows":
        return (
            "FFmpeg Installation for Windows:\n"
            "1. Download from https://ffmpeg.org/download.html#build-windows\n"
            "2. Extract (e.g., C:\\ffmpeg) and add bin to PATH\n"
            "3. Restart terminal and verify with: ffmpeg -version"
        )
    if system_name == "darwin":
        return (
            "FFmpeg Installation for macOS:\n"
            "1. Install Homebrew: https://brew.sh\n"
            "2. brew install ffmpeg\n"
            "3. Verify with: ffmpeg -version"
        )
    return (
        "FFmpeg Installation for Linux:\n"
        "Ubuntu/Debian: sudo apt update && sudo apt install ffmpeg\n"
        "Fedora: sudo dnf install ffmpeg\n"
        "Arch: sudo pacman -S ffmpeg\n"
        "Verify with: ffmpeg -version"
    )

