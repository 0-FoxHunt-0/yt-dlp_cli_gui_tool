import yt_dlp
import logging


def extract_playlist_count_and_title(url: str):
    try:
        with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True, 'ignoreerrors': True}) as ydl:
            playlist_info = ydl.extract_info(url, download=False)
            if playlist_info and 'entries' in playlist_info:
                entries = [e for e in (playlist_info['entries'] or []) if e is not None]
                title = playlist_info.get('title', 'Unknown Playlist')
                return len(entries), title
            return 0, 'Unknown Playlist'
    except Exception as e:
        logging.warning(f"Could not extract playlist info: {e}")
        return 0, 'Unknown Playlist'

