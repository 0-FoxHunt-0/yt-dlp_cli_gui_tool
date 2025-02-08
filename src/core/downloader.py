import yt_dlp
from typing import Callable, Optional
import os
import logging
from datetime import datetime


class Downloader:
    def __init__(self):
        # Create logs directory if it doesn't exist
        self.logs_dir = os.path.join(os.path.dirname(
            os.path.dirname(os.path.dirname(__file__))), 'logs')
        os.makedirs(self.logs_dir, exist_ok=True)

        # Configure logging
        log_file = os.path.join(
            self.logs_dir, f'yt-dlp_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
        logging.basicConfig(
            filename=log_file,
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )

        self.base_options = {
            'format': 'bestaudio/best',
            'extract_audio': True,
            'audio_format': 'mp3',
            'audio_quality': '0',
            'download_archive': 'archive.txt',
            'no_post_overwrites': True,
            'embed_thumbnail': True,
            'embed_metadata': True,
            'writethumbnail': True,
            'convert_thumbnails': 'jpg',
            'retries': 5,
            'progress_hooks': [],
            'outtmpl': '%(title)s.%(ext)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '0',
            }, {
                'key': 'EmbedThumbnail',
            }, {
                'key': 'FFmpegMetadata',
                'add_metadata': True,
            }],
            'logger': logging.getLogger('yt-dlp'),
            'quiet': True,  # Suppress console output
            'no_warnings': True,  # Suppress warnings
            'clean_infojson': True,  # Remove temporary files
        }

    def download(self, url: str, output_path: str,
                 is_audio: bool = True,
                 is_playlist: bool = False,
                 progress_callback: Optional[Callable] = None):

        options = self.base_options.copy()

        # Set format based on audio/video selection
        if not is_audio:
            options['format'] = 'bestvideo+bestaudio/best'
            options.pop('extract_audio', None)
            options['postprocessors'] = [{
                'key': 'FFmpegMetadata',
                'add_metadata': True,
            }]

        # Set paths
        options['outtmpl'] = os.path.join(output_path, '%(title)s.%(ext)s')
        options['download_archive'] = os.path.join(output_path, 'archive.txt')

        # Add playlist-specific options
        if is_playlist:
            options.update({
                'yes_playlist': True,
                'sleep_interval': 5
            })
        else:
            options['noplaylist'] = True

        if progress_callback:
            options['progress_hooks'] = [
                self._progress_hook(progress_callback)]

        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                return ydl.download([url])
        except Exception as e:
            logging.error(f"Download failed: {str(e)}")
            raise Exception(f"Download failed: {str(e)}")

    def _progress_hook(self, callback: Callable):
        def hook(d):
            if d['status'] == 'downloading':
                # Calculate progress
                total = d.get('total_bytes') or d.get(
                    'total_bytes_estimate', 0)
                downloaded = d.get('downloaded_bytes', 0)
                speed = d.get('speed', 0)

                if total > 0:
                    progress = (downloaded / total) * 100
                    speed_mb = speed / 1024 / 1024 if speed else 0
                    status = f"Downloading: {d['filename']} - {progress:.1f}% ({speed_mb:.1f} MB/s)"
                else:
                    status = f"Downloading: {d['filename']}"

                callback({'status': 'downloading',
                         'text': status, 'progress': progress})

            elif d['status'] == 'finished':
                callback(
                    {'status': 'processing', 'text': f"Processing: {d['filename']}", 'progress': 100})

            elif d['status'] == 'error':
                callback(
                    {'status': 'error', 'text': f"Error: {d.get('error', 'Unknown error')}", 'progress': 0})

        return hook


class CLIDownloader(Downloader):
    def __init__(self):
        super().__init__()
        self.base_options['progress_hooks'] = [self._cli_progress]

    def _cli_progress(self, d):
        if d['status'] == 'downloading':
            print(f"\rDownloading: {d.get('_percent_str', '0%')}", end='')
        elif d['status'] == 'finished':
            print("\nDownload complete!")
