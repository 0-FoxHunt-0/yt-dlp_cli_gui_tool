import yt_dlp
from typing import Callable, Optional
import os
import logging
import subprocess
import shutil
import glob
from datetime import datetime
from pathlib import Path
from src.utils.config import Config
from src.utils.log_cleaner import cleanup_logs


class Downloader:
    def __init__(self):
        # Create logs directory if it doesn't exist
        self.logs_dir = os.path.join(os.path.dirname(
            os.path.dirname(os.path.dirname(__file__))), 'logs')
        os.makedirs(self.logs_dir, exist_ok=True)

        # Load configuration for log cleaning settings
        self.config = Config()

        # Clean up old logs before setting up new logging
        cleanup_result = None
        if self.config.get('auto_clear_logs', True):
            max_logs_to_keep = self.config.get('max_logs_to_keep', 5)
            cleanup_result = cleanup_logs(
                self.logs_dir,
                max_logs_to_keep=max_logs_to_keep,
                exclude_current=False  # We'll create the new log after cleanup
            )
            if cleanup_result['cleaned_count'] > 0:
                # Use print instead of logging since logging isn't set up yet
                print(f"Log cleanup: {cleanup_result['message']}")

        # Download control
        self._should_abort = False
        self._current_ydl = None

        # Track active downloads for cleanup
        self._active_download_files = set()
        self._output_directory = None

        # Playlist tracking
        self._playlist_total_videos = 0
        self._playlist_downloaded_videos = 0
        self._playlist_failed_videos = 0
        self._playlist_skipped_videos = 0
        self._is_playlist_download = False
        self._initial_archive_count = 0  # Track initial archive count for accurate skipped detection

        # Archive file backup tracking for forced re-downloads
        self._restore_archive_after_download = False
        self._backup_archive_path = None
        self._original_archive_path = None

        # Configure logging
        log_file = os.path.join(
            self.logs_dir, f'yt-dlp_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
        logging.basicConfig(
            filename=log_file,
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s',
            encoding='utf-8'  # Ensure log file uses UTF-8 encoding
        )

        # Log the cleanup result now that logging is configured
        if cleanup_result:
            if cleanup_result['cleaned_count'] > 0:
                logging.info(f"Log cleanup completed: {cleanup_result['message']}")
            else:
                logging.info(f"Log cleanup: {cleanup_result.get('message', 'No cleanup needed')}")

        # Check if FFmpeg is available
        self.ffmpeg_available = self._check_ffmpeg()

        # Set environment variables to handle encoding issues
        os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
        os.environ.setdefault('LANG', 'C.UTF-8')

        # Log tool versions for diagnostics
        try:
            ytdlp_version = getattr(yt_dlp, "version", None)
            if ytdlp_version and hasattr(ytdlp_version, "__version__"):
                logging.info(f"yt-dlp version: {ytdlp_version.__version__}")
            else:
                logging.info("yt-dlp version: unknown")
        except Exception:
            logging.info("yt-dlp version: unknown")
        try:
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=5)
            if result.returncode == 0:
                try:
                    stdout_str = result.stdout.decode('utf-8', errors='replace')
                    first_line = stdout_str.splitlines()[0] if stdout_str else "ffmpeg (version unknown)"
                except:
                    first_line = "ffmpeg (version unknown)"
                logging.info(first_line)
        except Exception:
            pass

        self.base_options = {
            'format': 'bestaudio/best',
            'download_archive': 'archive.txt',
            'nopostoverwrites': True,
            'writethumbnail': True,  # Always download thumbnails
            'convertthumbnails': 'jpg',  # Always convert to jpg
            'retries': 5,  # Match alias: increase retries for robustness
            'fragment_retries': 5,  # Retries for individual fragments
            'progress_hooks': [],
            'outtmpl': '%(title)s.%(ext)s',
            'logger': logging.getLogger('yt-dlp'),
            'quiet': True,
            'no_warnings': True,
            'clean_infojson': True,
            # Encoding and compatibility options
            'encoding': 'utf-8',  # Force UTF-8 encoding for yt-dlp output
            'compat_opts': ['no-keep-subs'],  # Avoid subtitle encoding issues
            'ignoreerrors': True,  # Skip unavailable videos
            'abort_on_error': False,  # --no-abort-on-error equivalent
            'skip_unavailable_fragments': True,  # Skip missing HLS/DASH fragments
            'continue_dl': True,   # Continue after errors
            'concurrent_fragments': 8,  # More parallel fragments for speed
            'http_chunk_size': 20971520,  # 20MB chunks for even better speed
            'buffer_size': 65536,  # Larger buffer size for faster I/O
            'no_check_certificate': False,  # Keep security but optimize
            'geo_bypass': True,  # Bypass geo-restrictions faster
            'prefer_free_formats': False,  # Don't prefer free formats if quality is better elsewhere
            # Add proper headers to avoid mobile app detection
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Upgrade-Insecure-Requests': '1',
                'DNT': '1',
                'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                'Sec-Ch-Ua-Mobile': '?0',
                'Sec-Ch-Ua-Platform': '"Windows"',
            },
            # Additional options to handle problematic connections
            'sleep_interval_requests': 0.1,  # Small delay between requests
            'sleep_interval': 0.1,  # Small delay between downloads
            'max_sleep_interval': 1,  # Cap the sleep interval
            'sleep_interval_subtitles': 0,  # No delay for subtitles
            # Cookie handling to avoid detection - disabled by default to prevent errors
            'cookiefile': None,  # Use cookies if available
            'cookiesfrombrowser': None,  # Don't auto-load browser cookies to avoid permission errors
            # Browser impersonation
            'impersonate': None,  # Don't impersonate by default but have option ready
            # Additional retry and timeout settings
            'file_access_retries': 3,  # Retry file access issues
            'extractor_retries': 3,  # Retry extraction failures
            # Force format handling to avoid PO token issues
            'format': 'best[height<=1080][ext=mp4]/best[ext=mp4]/best[height<=1080]/best',  # Prefer non-PO-token-required formats
            # Additional YouTube-specific options
            'youtube_include_dash_manifest': False,  # Skip DASH to avoid issues
            'youtube_include_hls_manifest': False,  # Skip HLS to avoid issues
            # YouTube extractor configuration to help with PO token issues
            'extractor_args': {
                'youtube': {
                    'player_client': ['ios', 'android', 'web'],  # Try different clients to avoid PO token issues
                    'player_skip': ['js', 'configs'],  # Skip unnecessary JS/config loading
                }
            },
            # Prefer cookies from installed browsers if available (helps PO token mints)
            # Users can set cookiesfrombrowser in settings later if needed
            # Force better format compatibility
            'merge_output_format': 'mp4',  # Ensure consistent output format
            'prefer_ffmpeg': True,  # Use FFmpeg for better format handling
        }
        
        # Track skipped/failed videos for reporting
        self.skipped_videos = []
        self.failed_videos = []
        
        # Only add FFmpeg postprocessors if FFmpeg is available
        if self.ffmpeg_available:
            self.base_options['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '0',  # Keep max quality, optimize speed with CPU usage
            }, {
                'key': 'EmbedThumbnail',
                'already_have_thumbnail': False,
            }, {
                'key': 'FFmpegMetadata',
                'add_metadata': True,
            }]
        else:
            # Fallback options without FFmpeg
            self.base_options['postprocessors'] = []
            logging.warning("FFmpeg not found. Audio conversion and metadata embedding will be disabled.")

    def _check_ffmpeg(self):
        """Check if FFmpeg is available in the system PATH"""
        try:
            # Check if ffmpeg command is available
            result = subprocess.run(['ffmpeg', '-version'],
                                  capture_output=True, timeout=5)
            if result.returncode == 0:
                logging.info("FFmpeg found and available")
                return True
            else:
                logging.warning("FFmpeg command failed")
                return False
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            logging.warning(f"FFmpeg not found: {e}")
            return False

    def _get_user_friendly_error_message(self, error_msg):
        """Convert technical YouTube errors to user-friendly messages with suggestions"""
        error_msg_lower = error_msg.lower()

        if "http error 403" in error_msg_lower or "forbidden" in error_msg_lower:
            return ("YouTube is blocking the download (HTTP 403 Forbidden). "
                   "This often happens due to YouTube's anti-bot measures. "
                   "Try using browser cookies or wait a few hours before retrying.")

        elif "po token" in error_msg_lower or "gvs po token" in error_msg_lower:
            return ("YouTube's Proof of Origin (PO) token system is blocking access. "
                   "This is a newer YouTube protection mechanism. "
                   "Try using browser cookies from a logged-in session.")

        elif "no request handlers configured" in error_msg_lower:
            return ("YouTube's request handler configuration is missing. "
                   "This may be due to yt-dlp version compatibility issues. "
                   "Try updating yt-dlp or using browser cookies.")

        elif "video unavailable" in error_msg_lower:
            return ("The video is not available for download. "
                   "This could mean the video was deleted, made private, or is region-locked.")

        elif "not available on this app" in error_msg_lower:
            return ("YouTube says this content is not available on this application. "
                   "This is often due to geographic restrictions or content licensing.")

        elif "unable to download format" in error_msg_lower:
            return ("Could not find a suitable video format to download. "
                   "The video may have restricted formats or YouTube may be blocking access.")

        else:
            return "YouTube access error occurred. Try using browser cookies or updating yt-dlp."

    def _get_ffmpeg_installation_instructions(self):
        """Get platform-specific FFmpeg installation instructions"""
        import platform
        system = platform.system().lower()
        
        if system == "windows":
            return """
FFmpeg Installation for Windows:
1. Download FFmpeg from: https://ffmpeg.org/download.html#build-windows
2. Extract the archive to a folder (e.g., C:\\ffmpeg)
3. Add the bin folder to your PATH environment variable
4. Restart your terminal/command prompt
5. Verify installation: ffmpeg -version
"""
        elif system == "darwin":  # macOS
            return """
FFmpeg Installation for macOS:
1. Install Homebrew (if not already installed): /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
2. Install FFmpeg: brew install ffmpeg
3. Verify installation: ffmpeg -version
"""
        else:  # Linux
            return """
FFmpeg Installation for Linux:
Ubuntu/Debian: sudo apt update && sudo apt install ffmpeg
CentOS/RHEL: sudo yum install ffmpeg
Fedora: sudo dnf install ffmpeg
Arch: sudo pacman -S ffmpeg
Verify installation: ffmpeg -version
"""

    def download(self, url: str, output_path: str,
                 is_audio: bool = True,
                 is_playlist: bool = False,
                 metadata_options: dict = None,
                 progress_callback: Optional[Callable] = None,
                 cookie_file: str = None,
                 force_playlist_redownload: bool = False):

        options = self.base_options.copy()

        # Use cookie file if provided
        if cookie_file and os.path.exists(cookie_file):
            options['cookiefile'] = cookie_file
            logging.info(f"Using cookie file: {cookie_file}")
        elif cookie_file:
            logging.warning(f"Cookie file not found: {cookie_file}")

        # Default metadata options
        if metadata_options is None:
            metadata_options = {
                'embed_metadata': True,
                'embed_thumbnail': True,
                'write_thumbnail': True,
                'write_description': False,
                'write_info_json': False,
                'embed_chapters': True,
                'embed_subs': False
            }

        # Initialize playlist tracking
        self._reset_playlist_tracking()
        if is_playlist:
            self._is_playlist_download = True
            # Extract playlist information to get total count
            total_videos, playlist_title = self._extract_playlist_info(url)
            self._playlist_total_videos = total_videos
            logging.info(f"Playlist detected: {playlist_title} with {total_videos} videos")

        # Handle playlist folder creation and extract playlist title for metadata
        playlist_title_for_metadata = None
        if is_playlist:
            try:
                # Get playlist info to create folder
                with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True}) as temp_ydl:
                    playlist_info = temp_ydl.extract_info(url, download=False)
                    playlist_title = playlist_info.get('title', 'Unknown_Playlist')

                    # Log the playlist title being used (from YouTube's official response)
                    logging.info(f"Playlist title from YouTube: '{playlist_title}'")

                    # Store original title for metadata (before sanitization)
                    # This is the exact playlist name from YouTube's API response
                    playlist_title_for_metadata = playlist_title
                    # Sanitize playlist title for folder name
                    import re
                    playlist_title = re.sub(r'[<>:"/\\|?*]', '_', playlist_title)
                    output_path = os.path.join(output_path, playlist_title)
                    os.makedirs(output_path, exist_ok=True)
            except Exception as e:
                logging.warning(f"Could not create playlist folder: {e}")

        # Set format based on audio/video selection
        if not is_audio:
            # Use a more robust format selection to avoid choppy audio
            # Priority: best single file -> best video+audio -> fallback to best available
            options['format'] = (
                'best[height<=1080][ext=mp4]/best[height<=1080]/best[ext=mp4]/'
                'bestvideo[height<=1080]+bestaudio[ext=m4a]/bestvideo+bestaudio/'
                'best'
            )
            options.pop('extractaudio', None)  # Remove audio extraction for video
            options['postprocessors'] = []
            
            # Add video-specific options for better quality and sync
            options['merge_output_format'] = 'mp4'  # Ensure consistent output format
            options['prefer_ffmpeg'] = True  # Use FFmpeg for better merging
            options['fixup'] = 'detect_or_warn'  # Fix audio-video sync issues
            options['fragment_retries'] = 10  # Retry fragments for better stability
            options['keep_fragments'] = False  # Clean up fragments after merge
            
            # For video, use simple postprocessors
            if metadata_options.get('embed_thumbnail', True) and self.ffmpeg_available:
                options['postprocessors'].extend([
                    {
                        'key': 'FFmpegThumbnailsConvertor',
                        'format': 'jpg',
                        'when': 'before_dl',  # Convert thumbnails before download for better reliability
                    },
                    {
                        'key': 'EmbedThumbnail',
                        'already_have_thumbnail': False,  # Force re-embedding even if thumbnail exists
                    }
                ])
            
            if metadata_options.get('embed_metadata', True) and self.ffmpeg_available:
                options['postprocessors'].append({
                    'key': 'FFmpegMetadata',
                    'add_metadata': True,
                })

                # Add playlist name to metadata if this is a playlist download
                if is_playlist and playlist_title_for_metadata:
                    # Use postprocessor_args to pass custom FFmpeg metadata arguments
                    if 'postprocessor_args' not in options:
                        options['postprocessor_args'] = {}
                    if 'ffmpeg' not in options['postprocessor_args']:
                        options['postprocessor_args']['ffmpeg'] = []

                    # Add playlist metadata using FFmpeg arguments
                    # Note: album metadata will be handled by playlist_album_override if enabled
                    playlist_args = [
                        '-metadata', f'playlist={playlist_title_for_metadata}',
                        '-metadata', f'collection={playlist_title_for_metadata}',
                    ]

                    # Only add album if playlist_album_override is not enabled
                    if not metadata_options.get('playlist_album_override', False):
                        playlist_args.extend([
                            '-metadata', f'album={playlist_title_for_metadata}',
                        ])

                    options['postprocessor_args']['ffmpeg'].extend(playlist_args)
                    logging.info(f"Will embed playlist name '{playlist_title_for_metadata}' in file metadata")
            
            # Add audio normalization postprocessor for video
            if self.ffmpeg_available:
                options['postprocessors'].append({
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': 'mp4',
                })

            # Handle playlist album override for video files
            if metadata_options.get('playlist_album_override', False) and playlist_title_for_metadata:
                # Add custom metadata args to FFmpeg for playlist album override
                if 'postprocessor_args' not in options:
                    options['postprocessor_args'] = {}
                if 'ffmpeg' not in options['postprocessor_args']:
                    options['postprocessor_args']['ffmpeg'] = []

                # Force album override with explicit FFmpeg arguments
                album_args = [
                    '-metadata', f'album={playlist_title_for_metadata}',
                    '-metadata:s:v:0', f'album={playlist_title_for_metadata}',  # Force on video stream
                ]
                options['postprocessor_args']['ffmpeg'].extend(album_args)
                logging.info(f"Playlist album override: Using playlist name '{playlist_title_for_metadata}' as album metadata")
        else:
            # Enforce MP3 output: require FFmpeg, otherwise fail fast per requirement
            if not self.ffmpeg_available:
                instructions = self._get_ffmpeg_installation_instructions()
                raise Exception(
                    "Audio-only downloads require FFmpeg to convert to MP3. "
                    "Please install FFmpeg and ensure it is on your PATH.\n\n" + instructions
                )
            # For audio, use optimized approach for faster post-processing
            # Remove conflicting options first
            options.pop('extractaudio', None)
            options.pop('audioformat', None)
            options.pop('audioquality', None)
            
            # Use -x style extract-audio to MP3 and ensure final extension is mp3
            # Prefer m4a where available to avoid flaky HLS (webm) fragments
            options['format'] = 'bestaudio[ext=m4a]/bestaudio/best'
            options['extractaudio'] = True       # yt-dlp -x
            options['audioformat'] = 'mp3'       # --audio-format mp3
            options['audioquality'] = '0'        # --audio-quality 0 (best)
            options['final_ext'] = 'mp3'
            # Error behavior: be strict for single videos, but continue for playlists
            options['ignoreerrors'] = True if is_playlist else False
            # Explicit postprocessors in correct order to preserve embedding behavior
            options['postprocessors'] = [
                {
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '0',
                },
                {
                    'key': 'FFmpegThumbnailsConvertor',
                    'format': 'jpg',
                },
                {
                    'key': 'EmbedThumbnail',
                    'already_have_thumbnail': False,
                },
                {
                    'key': 'FFmpegMetadata',
                    'add_metadata': True,
                }
            ]

            # Add playlist metadata for audio downloads
            if is_playlist and playlist_title_for_metadata and metadata_options.get('embed_metadata', True):
                # Use postprocessor_args to pass custom FFmpeg metadata arguments
                if 'postprocessor_args' not in options:
                    options['postprocessor_args'] = {}
                if 'ffmpeg' not in options['postprocessor_args']:
                    options['postprocessor_args']['ffmpeg'] = []

                # Add playlist metadata using FFmpeg arguments
                # Note: album metadata will be handled by playlist_album_override if enabled
                playlist_args = [
                    '-metadata', f'playlist={playlist_title_for_metadata}',
                    '-metadata', f'collection={playlist_title_for_metadata}',
                ]

                # Only add album if playlist_album_override is not enabled
                if not metadata_options.get('playlist_album_override', False):
                    playlist_args.extend([
                        '-metadata', f'album={playlist_title_for_metadata}',
                    ])

                options['postprocessor_args']['ffmpeg'].extend(playlist_args)
                logging.info(f"Audio playlist mode: Will embed playlist name '{playlist_title_for_metadata}' in file metadata")
            
            # Allow toggling embedding via UI options while keeping MP3 enforcement
            if not metadata_options.get('embed_thumbnail', True):
                options['postprocessors'] = [pp for pp in options['postprocessors'] if pp.get('key') != 'EmbedThumbnail']
            if not metadata_options.get('embed_metadata', True):
                options['postprocessors'] = [pp for pp in options['postprocessors'] if pp.get('key') != 'FFmpegMetadata']

            # Handle playlist album override
            if metadata_options.get('playlist_album_override', False) and playlist_title_for_metadata:
                # Add custom metadata args to FFmpeg for playlist album override
                if 'postprocessor_args' not in options:
                    options['postprocessor_args'] = {}
                if 'ffmpeg' not in options['postprocessor_args']:
                    options['postprocessor_args']['ffmpeg'] = []

                # Force album override with explicit FFmpeg arguments
                album_args = [
                    '-metadata', f'album={playlist_title_for_metadata}',
                    '-metadata:s:a:0', f'album={playlist_title_for_metadata}',  # Force on audio stream
                ]
                options['postprocessor_args']['ffmpeg'].extend(album_args)
                logging.info(f"Playlist album override: Using playlist name '{playlist_title_for_metadata}' as album metadata")

        # Configure additional metadata options
        options['writedescription'] = metadata_options.get('write_description', False)
        options['writeinfojson'] = metadata_options.get('write_info_json', False)
        options['writesubtitles'] = metadata_options.get('embed_subs', False)
        options['writeautomaticsub'] = metadata_options.get('embed_subs', False)

        # Persist last metadata preferences for smarter cleanup
        self._last_metadata_prefs = {
            'write_description': bool(options['writedescription']),
            'write_info_json': bool(options['writeinfojson']),
            'embed_subs': bool(options['writesubtitles'] or options['writeautomaticsub'])
        }
        
        # Only enable chapters if FFmpeg is available
        if self.ffmpeg_available:
            options['embedchapters'] = metadata_options.get('embed_chapters', True)
        else:
            options['embedchapters'] = False
        
        # Optimize post-processing for maximum speed
        options['prefer_ffmpeg'] = True  # Always prefer FFmpeg for better performance
        options['keep_fragments'] = False  # Delete fragments after merging to save disk space
        options['embed_metadata'] = metadata_options.get('embed_metadata', True)
        
        # Windows-specific FFmpeg path fixes
        import platform
        if platform.system() == 'Windows':
            # Add Windows-specific options to handle path escaping
            options['ffmpeg_location'] = None  # Let yt-dlp find FFmpeg
            # Ensure proper path handling for Windows
            if 'postprocessor_args' not in options:
                options['postprocessor_args'] = {}
            # Add FFmpeg args optimized for maximum resource usage
            if is_audio:
                # Audio-specific FFmpeg args (safe for MP3 extraction/embedding)
                options['postprocessor_args']['ffmpeg'] = [
                    '-hide_banner',
                    '-loglevel', 'error',
                    '-threads', '0',
                    '-map_metadata', '0',
                    '-id3v2_version', '3',
                    '-write_id3v1', '1',
                ]
            else:
                # Video-specific FFmpeg args optimized for speed with maximum resource usage
                options['postprocessor_args']['ffmpeg'] = [
                    '-hide_banner',
                    '-loglevel', 'error',
                    '-threads', '0',  # Use all available CPU cores
                    '-thread_type', 'frame+slice',  # Use both frame and slice threading
                    '-c:v', 'copy',  # Copy video stream to avoid re-encoding
                    '-c:a', 'copy',  # Copy audio too if possible (much faster)
                    '-movflags', '+faststart',  # Optimize for fast streaming
                    '-avoid_negative_ts', 'make_zero',  # Fix timestamp issues
                    '-bufsize', '4M',  # Larger buffer for video processing
                    '-maxrate', '50M',  # Allow higher bitrates for faster processing
                    '-readrate_initial_burst', '3.0',  # Even faster initial processing for video
                ]

        # Set paths with improved template and sanitization
        if metadata_options.get('include_author', False):
            template = '%(uploader)s - %(title)s.%(ext)s'
        else:
            template = '%(title)s.%(ext)s'
        
        # Sanitize the template to avoid file system issues
        import re
        sanitized_template = re.sub(r'[<>:"/\\|?*]', '_', template)
        options['outtmpl'] = os.path.join(output_path, sanitized_template)
        
        # Ensure archive.txt is always in the main output directory for consistency
        options['download_archive'] = os.path.join(output_path, 'archive.txt')
        # Ensure the archive behavior is enabled
        options['break_on_existing'] = False  # Continue checking the rest of playlist even if some videos exist

        # For playlists, we want to be more aggressive about continuing downloads
        if is_playlist:
            # Ensure downloads are not skipped - override quiet mode for debugging
            options['quiet'] = False
            options['no_warnings'] = False
            logging.info("Playlist mode: Enabled verbose output to debug download issues")

            # Handle forced re-download option
            if force_playlist_redownload:
                # Temporarily move archive file to prevent skipping
                archive_file = os.path.join(output_path, 'archive.txt')
                backup_archive = os.path.join(output_path, 'archive.txt.backup')

                if os.path.exists(archive_file):
                    try:
                        # Move archive file to backup location
                        shutil.move(archive_file, backup_archive)
                        logging.info(f"Moved existing archive file to backup ({backup_archive}) for forced re-download")
                        logging.info("This ensures all playlist items will be re-evaluated for download")
                        # Schedule restoration after download
                        self._restore_archive_after_download = True
                        self._backup_archive_path = backup_archive
                        self._original_archive_path = archive_file
                    except Exception as e:
                        logging.warning(f"Could not backup archive file: {e}")
                        # If we can't backup, just disable archive
                        options['download_archive'] = None
                        logging.info("Proceeding without archive file - all playlist items will be processed")
                else:
                    logging.info("No existing archive file found - proceeding with fresh download")
                    options['download_archive'] = None
            else:
                # Keep archive file enabled for playlist downloads to prevent re-downloading existing videos
                # This prevents unnecessary re-downloads and saves bandwidth/time
                pass  # archive is already set above

            # Add thumbnail quality fallback to prevent embedding failures
            if metadata_options.get('embed_thumbnail', True) and self.ffmpeg_available:
                # Prefer higher quality thumbnails to avoid embedding issues
                options['writethumbnail'] = True
                options['thumbnail_format'] = 'jpg'  # Force JPG format for better compatibility
                logging.info("Thumbnail embedding enabled with enhanced quality settings")

            # Force download of all items regardless of archive status
            options['force_overwrites'] = False  # Don't overwrite existing files
            options['nooverwrites'] = True  # Don't overwrite existing files
            # Make sure we continue on any errors
            options['ignoreerrors'] = True
            options['continue_dl'] = True

        # Capture initial archive count for accurate skipped video detection
        # Only read archive for non-playlist downloads to avoid confusion
        if not is_playlist:
            archive_file = os.path.join(output_path, 'archive.txt')
            if os.path.exists(archive_file):
                try:
                    with open(archive_file, 'r', encoding='utf-8') as f:
                        self._initial_archive_count = len(f.readlines())
                    logging.info(f"Initial archive count: {self._initial_archive_count} videos")
                except Exception as e:
                    logging.warning(f"Could not read initial archive: {e}")
                    self._initial_archive_count = 0
            else:
                self._initial_archive_count = 0
        else:
            # For playlists, track initial archive count to accurately count skipped videos
            archive_file = os.path.join(output_path, 'archive.txt')
            if os.path.exists(archive_file):
                try:
                    with open(archive_file, 'r', encoding='utf-8') as f:
                        self._initial_archive_count = sum(1 for line in f if line.strip())
                    logging.info(f"Playlist mode: Found {self._initial_archive_count} previously downloaded videos in archive")
                except Exception as e:
                    logging.warning(f"Could not read archive file: {e}")
                    self._initial_archive_count = 0
            else:
                self._initial_archive_count = 0
                logging.info("Playlist mode: No existing archive file found - starting fresh")

            logging.info(f"Playlist mode: Will download {self._playlist_total_videos} videos, skipping already downloaded ones using archive file")

        # Add playlist-specific options with aggressive resource usage
        if is_playlist:
            # Use the same template as single videos (no track numbers)
            sanitized_playlist_template = re.sub(r'[<>:"/\\|?*]', '_', template)
            options.update({
                'yes_playlist': True,
                'sleep_interval': 0.1,  # Minimal sleep between downloads
                'max_sleep_interval': 1,  # Very low cap on sleep
                'outtmpl': os.path.join(output_path, sanitized_playlist_template),
                'restrictfilenames': True,  # Enable safe filenames
                'concurrent_fragments': 16,  # More aggressive parallel fragments
                'max_downloads': None,  # No download limit
                'abort_on_error': False,  # ensure we keep going on playlist errors
                'socket_timeout': 30,  # Faster timeout for unresponsive connections
            })
        else:
            options['noplaylist'] = True
            options['restrictfilenames'] = True  # Enable safe filenames
            options['concurrent_fragments'] = 16  # More aggressive parallel fragments
            options['socket_timeout'] = 30  # Faster timeout

        if progress_callback:
            options['progress_hooks'] = [
                self._progress_hook(progress_callback)]

        try:
            # Store output directory for cleanup and reset error tracking
            self._output_directory = output_path
            self.skipped_videos = []
            self.failed_videos = []

            # Clean up any existing incomplete files before starting
            self._cleanup_incomplete_files()

            # Try download with primary configuration
            result = self._try_download_with_fallback(url, options, output_path)

            # Clean up thumbnail files after successful download (with small delay for postprocessors)
            try:
                import time
                time.sleep(2)  # Give postprocessors time to finish
                cleanup_result = self._cleanup_incomplete_files(cleanup_type="post_processing")
                if cleanup_result["cleaned_count"] > 0:
                    logging.info(f"Post-download cleanup completed: {cleanup_result['cleaned_count']} files removed")
            except Exception as cleanup_error:
                logging.warning(f"Post-download cleanup failed: {cleanup_error}")

            # Final detection of skipped videos for accurate counting
            self._detect_skipped_videos()

            # Process existing files if playlist album override is enabled
            if is_playlist and metadata_options.get('playlist_album_override', False) and playlist_title_for_metadata:
                try:
                    self._update_existing_files_album_metadata(output_path, playlist_title_for_metadata, is_audio)
                except Exception as e:
                    logging.warning(f"Failed to update existing files album metadata: {e}")

            # Generate report if there were issues
            self._generate_error_report()
            return result
                
        except KeyboardInterrupt as e:
            # Handle abort specifically
            logging.info("Download aborted by user")
            # Cleanup and generate report
            try:
                cleanup_result = self._cleanup_incomplete_files(cleanup_type="abort")
                if cleanup_result["cleaned_count"] > 0:
                    logging.info(f"Abort cleanup completed: {cleanup_result['cleaned_count']} files removed")
            except Exception as cleanup_error:
                logging.warning(f"Cleanup after abort failed: {cleanup_error}")
            
            # Final detection of skipped videos for accurate counting
            self._detect_skipped_videos()
            
            self._generate_error_report()
            raise Exception("Download aborted by user")
            
        except Exception as e:
            error_msg = str(e)
            logging.error(f"Download failed: {error_msg}")
            
            # Always clean up on any error
            try:
                cleanup_result = self._cleanup_incomplete_files(cleanup_type="error")
                if cleanup_result["cleaned_count"] > 0:
                    logging.info(f"Error cleanup completed: {cleanup_result['cleaned_count']} files removed")
            except Exception as cleanup_error:
                logging.warning(f"Cleanup after error failed: {cleanup_error}")
            
            # Final detection of skipped videos for accurate counting
            self._detect_skipped_videos()
            
            # Generate report even on failure
            self._generate_error_report()
            
            # Categorize and handle different types of errors
            error_msg_lower = error_msg.lower()

            # Critical errors that should be re-raised
            if ("aborted" in error_msg_lower or
                "keyboardinterrupt" in error_msg_lower or
                "ffprobe" in error_msg_lower or
                "ffmpeg" in error_msg_lower):
                if "ffmpeg" in error_msg_lower:
                    instructions = self._get_ffmpeg_installation_instructions()
                    raise Exception(f"FFmpeg not found. {error_msg}\n\n{instructions}")
                else:
                    raise Exception(error_msg)

            # YouTube-specific errors that might be recoverable
            elif any(error_type in error_msg_lower for error_type in [
                "http error 403", "forbidden", "po token", "gvs po token",
                "no request handlers configured", "video unavailable",
                "not available on this app", "unable to download format"
            ]):
                user_friendly_msg = self._get_user_friendly_error_message(error_msg)
                logging.error(f"YouTube access error: {user_friendly_msg}")
                raise Exception(f"YouTube Access Error: {user_friendly_msg}\n\nOriginal error: {error_msg}")

            # Network-related errors
            elif any(error_type in error_msg_lower for error_type in [
                "connection", "timeout", "network", "dns", "ssl"
            ]):
                logging.error(f"Network error: {error_msg}")
                raise Exception(f"Network Error: Please check your internet connection and try again.\n\nOriginal error: {error_msg}")

            # File system errors
            elif any(error_type in error_msg_lower for error_type in [
                "permission denied", "disk full", "no space", "readonly",
                "file exists", "directory"
            ]):
                logging.error(f"File system error: {error_msg}")
                raise Exception(f"File System Error: {error_msg}\n\nPlease check file permissions and available disk space.")

            # Other errors - log but don't crash for playlist downloads
            else:
                if is_playlist:
                    logging.warning(f"Download completed with non-critical errors: {error_msg}")
                    return None
                else:
                    # For single videos, be more strict
                    logging.error(f"Download failed: {error_msg}")
                    raise Exception(f"Download failed: {error_msg}")
                
        finally:
            # Restore archive file if it was backed up for forced re-download
            if hasattr(self, '_restore_archive_after_download') and self._restore_archive_after_download:
                try:
                    if self._backup_archive_path and self._original_archive_path:
                        if os.path.exists(self._backup_archive_path):
                            shutil.move(self._backup_archive_path, self._original_archive_path)
                            logging.info("Restored archive file from backup after forced re-download")
                        # Clean up backup tracking
                        self._restore_archive_after_download = False
                        self._backup_archive_path = None
                        self._original_archive_path = None
                except Exception as e:
                    logging.warning(f"Could not restore archive file from backup: {e}")

            self._current_ydl = None

    def _extract_playlist_info(self, url):
        """Extract playlist information to get total video count"""
        try:
            with yt_dlp.YoutubeDL({
                'quiet': True,
                'extract_flat': True,
                'ignoreerrors': True
            }) as ydl:
                playlist_info = ydl.extract_info(url, download=False)

                if playlist_info and 'entries' in playlist_info:
                    # Count valid entries (filter out None entries)
                    all_entries = playlist_info['entries']
                    valid_entries = [entry for entry in all_entries if entry is not None]

                    logging.info(f"Playlist extraction: {len(all_entries)} total entries, {len(valid_entries)} valid entries")

                    # Log first few entries for debugging
                    for i, entry in enumerate(valid_entries[:5]):
                        if entry and isinstance(entry, dict):
                            logging.info(f"Entry {i+1}: ID={entry.get('id', 'N/A')}, Title={entry.get('title', 'N/A')[:50]}...")

                    return len(valid_entries), playlist_info.get('title', 'Unknown Playlist')
                else:
                    logging.warning("No entries found in playlist info")
                    return 0, "Unknown Playlist"
        except Exception as e:
            logging.warning(f"Could not extract playlist info: {e}")
            return 0, "Unknown Playlist"

    def get_playlist_progress(self):
        """Get current download progress information (works for both playlists and single videos)"""
        if self._is_playlist_download:
            # Calculate completed videos (downloaded + failed + skipped)
            completed = self._playlist_downloaded_videos + self._playlist_failed_videos + self._playlist_skipped_videos
            remaining = max(0, self._playlist_total_videos - completed)
            
            return {
                'total': self._playlist_total_videos,
                'downloaded': self._playlist_downloaded_videos,
                'failed': self._playlist_failed_videos,
                'skipped': self._playlist_skipped_videos,
                'completed': completed,
                'remaining': remaining
            }
        else:
            # For single videos, return simple progress
            total = 1
            completed = min(1, self._playlist_downloaded_videos + self._playlist_failed_videos + self._playlist_skipped_videos)
            
            return {
                'total': total,
                'downloaded': self._playlist_downloaded_videos,
                'failed': self._playlist_failed_videos,
                'skipped': self._playlist_skipped_videos,
                'completed': completed,
                'remaining': max(0, total - completed)
            }

    def _reset_playlist_tracking(self):
        """Reset playlist tracking variables"""
        self._playlist_total_videos = 0
        self._playlist_downloaded_videos = 0
        self._playlist_failed_videos = 0
        self._playlist_skipped_videos = 0
        self._is_playlist_download = False
        self._initial_archive_count = 0  # Reset initial archive count

    def _detect_skipped_videos(self):
        """Detect videos that were skipped (already downloaded) by checking archive file"""
        if not self._output_directory:
            return

        try:
            archive_file = os.path.join(self._output_directory, 'archive.txt')
            if os.path.exists(archive_file):
                # Count lines in archive file to see how many videos were skipped
                with open(archive_file, 'r', encoding='utf-8') as f:
                    archive_lines = f.readlines()

                # Calculate total videos in archive after this session
                total_in_archive = len(archive_lines)

                # Calculate newly added videos (total in archive - initial count)
                newly_added = total_in_archive - self._initial_archive_count

                # For playlists: the skipped count is already tracked in progress hooks
                # We just need to verify it makes sense
                if self._is_playlist_download:
                    # The skipped videos are already counted by the progress hook
                    # when it detects "already been recorded in archive" messages
                    # This method is mainly for final verification and logging
                    if self._playlist_skipped_videos > 0:
                        logging.info(f"Confirmed {self._playlist_skipped_videos} videos were already downloaded (skipped)")
                else:
                    # For single videos: if archive didn't grow and no download occurred, it was skipped
                    if newly_added == 0 and self._playlist_downloaded_videos == 0 and self._playlist_failed_videos == 0:
                        self._playlist_skipped_videos = 1  # Single video was skipped
                        logging.info("Single video was already downloaded (skipped)")

        except Exception as e:
            logging.warning(f"Error detecting skipped videos: {e}")

    def _progress_hook(self, callback: Callable):
        def hook(d):
            # Log all progress hook calls for debugging
            status = d.get('status', 'unknown')
            if self._is_playlist_download:
                logging.debug(f"Progress hook called: status={status}, filename={d.get('filename', 'N/A')}")

            # Check if download should be aborted - do this FIRST and MORE FREQUENTLY
            if self._should_abort:
                logging.info("Progress hook detected abort flag - stopping download")
                # Use KeyboardInterrupt which yt-dlp respects and will stop the entire process
                raise KeyboardInterrupt("Download aborted by user")

            # Track active download files
            if d['status'] == 'downloading' and 'filename' in d:
                self._active_download_files.add(d['filename'])

                # Log download start for debugging
                if self._is_playlist_download and 'info_dict' in d:
                    video_title = d['info_dict'].get('title', 'Unknown')
                    video_id = d['info_dict'].get('id', 'Unknown')
                    logging.info(f"Starting download: {video_title} (ID: {video_id})")

                # Check for abort more frequently during active downloading
                if self._should_abort:
                    logging.info("Download abort detected during active download - stopping")
                    raise KeyboardInterrupt("Download aborted by user")

            elif d['status'] == 'finished' and 'filename' in d:
                # Remove from active downloads when finished
                self._active_download_files.discard(d['filename'])

                # Check for abort after each completion
                if self._should_abort:
                    logging.info("Download abort detected after file completion - stopping")
                    raise KeyboardInterrupt("Download aborted by user")

                # Update playlist tracking for successful downloads
                if self._is_playlist_download:
                    self._playlist_downloaded_videos += 1
                    logging.info(f"Playlist progress: {self._playlist_downloaded_videos}/{self._playlist_total_videos} videos downloaded - {os.path.basename(d['filename'])}")

            elif d['status'] == 'error':
                # Check for abort even on errors
                if self._should_abort:
                    logging.info("Download abort detected on error - stopping")
                    raise KeyboardInterrupt("Download aborted by user")

                # Check if this is actually a "skip" due to archive, not a real error
                error_msg = str(d.get('error', '')).lower()
                if any(skip_phrase in error_msg for skip_phrase in ['already been recorded', 'already recorded', 'has already been downloaded']):
                    # This is a skip, not an error
                    if self._is_playlist_download:
                        self._playlist_skipped_videos += 1
                        logging.info(f"Video already in archive (skipped): {d.get('info_dict', {}).get('title', 'Unknown')}")
                    else:
                        self._playlist_skipped_videos = 1
                        logging.info("Single video already in archive (skipped)")
                else:
                    # Track actual failed videos
                    error_info = {
                        'title': d.get('info_dict', {}).get('title', 'Unknown'),
                        'url': d.get('info_dict', {}).get('webpage_url', 'Unknown'),
                        'error': d.get('error', 'Unknown error')
                    }
                    self.failed_videos.append(error_info)

                    # Update playlist tracking for failed videos
                    if self._is_playlist_download:
                        self._playlist_failed_videos += 1
                        logging.warning(f"Playlist video failed: {error_info['title']}")

                    logging.warning(f"Video failed: {error_info}")

            # Detect skipped videos periodically for both single videos and playlists
            if d.get('status') in ['downloading', 'finished']:
                self._detect_skipped_videos()

                # Additional abort check after skipped video detection
                if self._should_abort:
                    logging.info("Download abort detected after skipped video check - stopping")
                    raise KeyboardInterrupt("Download aborted by user")

            # Pass the original yt-dlp data to the callback
            # This allows the UI to handle formatting and reduces data transformation issues
            callback(d)

        return hook

    def abort_download(self):
        """Abort the current download"""
        self._should_abort = True
        logging.info("Download abort requested by user")

        if self._current_ydl:
            try:
                # Try to interrupt the yt-dlp downloader more aggressively
                if hasattr(self._current_ydl, '_downloader'):
                    downloader = self._current_ydl._downloader
                    # Try multiple interrupt methods
                    if hasattr(downloader, 'interrupt'):
                        try:
                            downloader.interrupt()
                            logging.info("yt-dlp downloader interrupted")
                        except Exception as e:
                            logging.warning(f"Failed to interrupt downloader: {e}")

                    # Try to set abort flag in params
                    if hasattr(downloader, 'params'):
                        downloader.params['abort'] = True
                        logging.info("Set abort flag in yt-dlp params")

                    # Try to close any open connections
                    if hasattr(downloader, '_opener'):
                        try:
                            downloader._opener.close()
                            logging.info("Closed yt-dlp opener")
                        except Exception as e:
                            logging.warning(f"Failed to close opener: {e}")

                # Also try direct KeyboardInterrupt on the yt-dlp instance
                if hasattr(self._current_ydl, '_download_retcode'):
                    self._current_ydl._download_retcode = 130  # SIGINT exit code
                    logging.info("Set download retcode to indicate interruption")

            except Exception as e:
                logging.warning(f"Error during abort attempt: {e}")

        # Cleanup immediately when abort is called
        try:
            cleanup_result = self._cleanup_incomplete_files(cleanup_type="abort")
            if cleanup_result["cleaned_count"] > 0:
                logging.info(f"Immediate cleanup completed: {cleanup_result['cleaned_count']} files removed")
        except Exception as cleanup_error:
            logging.warning(f"Immediate cleanup failed: {cleanup_error}")

    def cleanup_incomplete_files(self):
        """Manually trigger cleanup of incomplete files"""
        return self._cleanup_incomplete_files()

    def _cleanup_incomplete_files(self, cleanup_type="general"):
        """Clean up incomplete download files"""
        if not self._output_directory:
            return {"cleaned_count": 0, "error": None}
            
        try:
            output_path = Path(self._output_directory)
            if not output_path.exists():
                return {"cleaned_count": 0, "error": None}
            
            # Files to clean up
            cleanup_files = set()
            
            # Add tracked active downloads
            cleanup_files.update(self._active_download_files)
            
            # Find common partial file patterns
            partial_patterns = [
                "*.part",           # yt-dlp partial files
                "*.f*",             # format-specific partial files (f140, f137, etc.)
                "*.temp",           # temporary files
                "*.tmp",            # temporary files
                "*.temp.mp3",       # temporary MP3 files
                "*.temp.mp4",       # temporary MP4 files
                "*.temp.webm",      # temporary WebM files
                "*.temp.mkv",       # temporary MKV files
                "*.ytdl",           # yt-dlp specific temp files
                "*.ytdl.meta",      # yt-dlp meta remnants
                "*.meta",           # generic meta remnants
                "*.webm.part",      # WebM partial files
                "*.mp4.part",       # MP4 partial files
                "*.mkv.part",       # MKV partial files
                "*.m4a.part",       # M4A partial files
                "*.frag",           # HLS/DASH fragment leftovers
                "*.fragment*",      # any fragment naming
                "*.incomplete",     # incomplete files
                "*.downloading",    # downloading files
            ]
            
            # Also clean up thumbnail files when aborting or after successful embedding
            thumbnail_patterns = [
                "*.webp",       # WebP thumbnails - always clean these up as they're intermediate files
            ]
            # Always clean up WebP files as they're intermediate conversion files
            partial_patterns.extend(["*.webp"])
            
            # During abort or error, also clean up JPG thumbnails to remove partial downloads
            if cleanup_type in ["abort", "error"]:
                thumbnail_patterns.extend([
                    "*.jpg",        # JPEG thumbnails
                    "*.jpeg",       # JPEG thumbnails
                    "*.png",        # PNG thumbnails (converted thumbnails)
                ])
                partial_patterns.extend(thumbnail_patterns[1:])  # Skip WebP as already added
            
            # Handle duplicate thumbnails - find and remove duplicates
            self._cleanup_duplicate_thumbnails(output_path)
            
            # Clean up thumbnail files after successful embedding (not during abort/error)
            if cleanup_type == "post_processing":
                self._cleanup_embedded_thumbnails(output_path)
            
            for pattern in partial_patterns:
                for file_path in output_path.rglob(pattern):
                    # Only clean up recent files (modified in last hour) to avoid removing user files
                    if file_path.is_file():
                        try:
                            # Check if file was modified recently (within last hour)
                            import time
                            file_age = time.time() - file_path.stat().st_mtime
                            
                            # For WebP files, always be aggressive since they're intermediate files
                            # For thumbnail files during abort/error, be more aggressive (within 10 minutes)
                            # For other files, use 1 hour limit
                            if pattern == "*.webp":
                                time_limit = 7200  # 2 hours for WebP files (more generous but still cleanup)
                            elif cleanup_type in ["abort", "error"] and pattern in ["*.jpg", "*.jpeg", "*.png"]:
                                time_limit = 600  # 10 minutes for thumbnails during abort/error
                            else:
                                time_limit = 3600  # 1 hour for other files
                            
                            if file_age < time_limit:
                                cleanup_files.add(str(file_path))
                        except:
                            pass
            
            # Clean up auxiliary metadata files based on preferences
            try:
                prefs = getattr(self, '_last_metadata_prefs', {
                    'write_description': False,
                    'write_info_json': False,
                    'embed_subs': False
                })
                # If not requested, remove stale artifacts created by accidental flags or previous runs
                if not prefs.get('write_info_json'):
                    for fp in output_path.rglob("*.info.json"):
                        if fp.is_file():
                            cleanup_files.add(str(fp))
                if not prefs.get('write_description'):
                    for fp in output_path.rglob("*.description"):
                        if fp.is_file():
                            cleanup_files.add(str(fp))
                if not prefs.get('embed_subs'):
                    for ext in ["*.vtt", "*.srt", "*.ass", "*.lrc"]:
                        for fp in output_path.rglob(ext):
                            if fp.is_file():
                                cleanup_files.add(str(fp))
            except Exception as _:
                pass

            # Clean up the files
            cleaned_count = 0
            cleaned_files = []
            for file_path in cleanup_files:
                try:
                    if os.path.exists(file_path):
                        file_size = os.path.getsize(file_path)
                        os.remove(file_path)
                        cleaned_count += 1
                        cleaned_files.append(os.path.basename(file_path))
                        logging.info(f"Cleaned up incomplete file: {file_path} ({file_size} bytes)")
                except Exception as e:
                    logging.warning(f"Failed to clean up file {file_path}: {e}")
            
            if cleaned_count > 0:
                logging.info(f"Cleaned up {cleaned_count} incomplete download files")
                
            # Clear the tracking set
            self._active_download_files.clear()
            
            return {
                "cleaned_count": cleaned_count,
                "cleaned_files": cleaned_files,
                "error": None
            }
            
        except Exception as e:
            error_msg = f"Error during cleanup: {e}"
            logging.error(error_msg)
            return {"cleaned_count": 0, "error": error_msg}

    def _cleanup_duplicate_thumbnails(self, output_path):
        """Remove duplicate thumbnail files"""
        try:
            thumbnail_patterns = ["*.jpg", "*.jpeg", "*.png", "*.webp"]
            thumbnail_files = {}
            
            for pattern in thumbnail_patterns:
                for file_path in output_path.rglob(pattern):
                    if file_path.is_file():
                        try:
                            # Get file size and modification time as key
                            file_size = file_path.stat().st_size
                            file_mtime = file_path.stat().st_mtime
                            file_key = (file_size, round(file_mtime))
                            
                            if file_key in thumbnail_files:
                                # Duplicate found - remove the newer file
                                existing_file = thumbnail_files[file_key]
                                if file_path.stat().st_mtime > existing_file.stat().st_mtime:
                                    # Current file is newer, remove it
                                    file_path.unlink()
                                    logging.info(f"Removed duplicate thumbnail: {file_path}")
                                else:
                                    # Existing file is newer, remove it and keep current
                                    existing_file.unlink()
                                    thumbnail_files[file_key] = file_path
                                    logging.info(f"Removed duplicate thumbnail: {existing_file}")
                            else:
                                thumbnail_files[file_key] = file_path
                        except Exception as e:
                            logging.warning(f"Error processing thumbnail {file_path}: {e}")
        except Exception as e:
            logging.warning(f"Error cleaning duplicate thumbnails: {e}")

    def _cleanup_embedded_thumbnails(self, output_path):
        """Clean up thumbnail files after they've been embedded into audio/video files"""
        try:
            import time
            # Find all media files that were recently modified
            media_files = []
            for pattern in ["*.mp3", "*.m4a", "*.flac", "*.ogg", "*.mp4", "*.mkv", "*.webm"]:
                media_files.extend(output_path.rglob(pattern))
            
            # Clean up any remaining thumbnail files for recent media files
            for media_file in media_files:
                # Check if media file was modified recently (within last 5 minutes)
                file_age = time.time() - media_file.stat().st_mtime
                if file_age < 300:  # 5 minutes
                    # Look for thumbnail files with matching base name
                    base_name = media_file.stem
                    for thumb_ext in [".webp", ".jpg", ".jpeg", ".png"]:
                        thumb_file = media_file.parent / (base_name + thumb_ext)
                        if thumb_file.exists():
                            try:
                                # Remove the thumbnail file (backup cleanup in case yt-dlp didn't)
                                thumb_file.unlink()
                                logging.info(f"Cleaned up remaining thumbnail: {thumb_file}")
                            except Exception as e:
                                logging.warning(f"Failed to remove thumbnail {thumb_file}: {e}")
        
        except Exception as e:
            logging.warning(f"Error during embedded thumbnail cleanup: {e}")

    def _generate_error_report(self):
        """Generate a report of failed/skipped videos"""
        if not self.failed_videos and not self.skipped_videos:
            return
            
        try:
            report_lines = []
            report_lines.append("=== Download Report ===")
            report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            report_lines.append("")
            
            if self.failed_videos:
                report_lines.append(f"Failed Videos ({len(self.failed_videos)}):")
                for i, video in enumerate(self.failed_videos, 1):
                    report_lines.append(f"{i}. {video['title']}")
                    report_lines.append(f"   URL: {video['url']}")
                    report_lines.append(f"   Error: {video['error']}")
                    report_lines.append("")
            
            if self.skipped_videos:
                report_lines.append(f"Skipped Videos ({len(self.skipped_videos)}):")
                for i, video in enumerate(self.skipped_videos, 1):
                    report_lines.append(f"{i}. {video['title']}")
                    report_lines.append(f"   Reason: {video['reason']}")
                    report_lines.append("")
            
            # Write report to file
            if self._output_directory:
                report_path = os.path.join(self._output_directory, f"download_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
                with open(report_path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(report_lines))
                logging.info(f"Error report saved to: {report_path}")
                
        except Exception as e:
            logging.warning(f"Failed to generate error report: {e}")

    def _try_download_with_fallback(self, url, options, output_path):
        """Try download with fallback configurations for "not available on this app" errors"""
        fallback_configs = [
            # Primary configuration (already in options)
            {},
            # Fallback 1: Simple configuration without extractor_args
            {},
            # Fallback 2: Simple fallback with different user agent
            {
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
                }
            },
            # Fallback 3: Another simple fallback
            {
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
                }
            },
            # Fallback 4: Basic fallback with format preference
            {
                'format': 'best[height<=720][ext=mp4]/best[ext=mp4]/best[height<=720]/best',
            },
            # Fallback 5: Legacy user agent fallback
            {
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                }
            }
        ]

        last_error = None

        for i, fallback_config in enumerate(fallback_configs):
            try:
                # Merge fallback config with base options
                current_options = options.copy()
                if fallback_config:
                    # Deep merge the configurations
                    for key, value in fallback_config.items():
                        if key in current_options and isinstance(current_options[key], dict) and isinstance(value, dict):
                            current_options[key].update(value)
                        else:
                            current_options[key] = value

                if i > 0:
                    client_type = fallback_config.get('extractor_args', {}).get('youtube', {}).get('player_client', ['unknown'])[0]
                    extract_flat = fallback_config.get('extract_flat', False)
                    logging.info(f"Trying fallback configuration {i} ({client_type} client) to bypass YouTube restrictions")
                    logging.info(f"Fallback config {i}: extract_flat={extract_flat}, has_user_agent={'User-Agent' in str(fallback_config)}")

                with yt_dlp.YoutubeDL(current_options) as ydl:
                    self._current_ydl = ydl
                    self._should_abort = False

                    # Start a background thread to monitor abort status
                    import threading
                    import time

                    def abort_monitor():
                        """Monitor for abort requests and interrupt yt-dlp if needed"""
                        while not self._should_abort:
                            time.sleep(0.1)  # Check every 100ms
                        # Abort was requested, try to interrupt yt-dlp
                        try:
                            if hasattr(ydl, '_downloader') and hasattr(ydl._downloader, 'interrupt'):
                                ydl._downloader.interrupt()
                                logging.info("yt-dlp interrupted by abort monitor")
                        except Exception as e:
                            logging.warning(f"Failed to interrupt yt-dlp from monitor: {e}")

                    # Start the abort monitor thread
                    monitor_thread = threading.Thread(target=abort_monitor, daemon=True)
                    monitor_thread.start()

                    try:
                        logging.info(f"Starting yt-dlp download with {len([url])} URLs")
                        logging.info(f"Download options: quiet={current_options.get('quiet', 'N/A')}, download_archive={current_options.get('download_archive', 'N/A')}")
                        result = ydl.download([url])
                        logging.info(f"yt-dlp download completed with result: {result}")
                    finally:
                        # Clean up monitor thread
                        self._should_abort = True
                        monitor_thread.join(timeout=1.0)

                # If we get here, download succeeded
                if i > 0:
                    client_type = fallback_config.get('extractor_args', {}).get('youtube', {}).get('player_client', ['unknown'])[0]
                    logging.info(f"✅ Download succeeded with fallback configuration {i} ({client_type} client)")
                else:
                    logging.info("✅ Download succeeded with primary configuration (web client)")
                return result

            except Exception as e:
                error_msg = str(e)
                last_error = e

                # Check if this is a retryable error
                retryable_errors = [
                    "not available on this app",
                    "po token",
                    "gvs po token",
                    "no request handlers configured",
                    "failed to fetch.*po token",
                    "http error 403",
                    "forbidden",
                    "fragment 1 not found",
                    "unable to download format",
                    "some web client https formats have been skipped",
                    "forcing sabr streaming",
                    "missing a url",
                    "video unavailable"
                ]

                is_retryable = any(retry_phrase in error_msg.lower() for retry_phrase in retryable_errors)

                if is_retryable and i < len(fallback_configs) - 1:
                    logging.warning(f"Configuration {i} failed with retryable error: {error_msg[:100]}... Trying next fallback...")
                    continue
                else:
                    # Non-retryable error or all fallbacks exhausted
                    if is_retryable and i >= len(fallback_configs) - 1:
                        logging.error("All fallback configurations failed with retryable errors")
                    raise e

        # If all fallbacks failed, raise the last error
        raise last_error

    def _update_existing_files_album_metadata(self, output_path, playlist_title, is_audio):
        """Update album metadata for existing files in the output directory"""
        import subprocess
        import glob

        # Check if FFmpeg is available
        if not self.ffmpeg_available:
            logging.warning("FFmpeg not available - skipping existing files album metadata update")
            return

        logging.info(f"Updating album metadata for existing files to: '{playlist_title}'")

        # Define file extensions to process
        if is_audio:
            extensions = ['*.mp3', '*.m4a', '*.flac', '*.ogg']
        else:
            extensions = ['*.mp4', '*.mkv', '*.webm', '*.avi']

        updated_count = 0
        total_files = 0

        for ext in extensions:
            pattern = os.path.join(output_path, ext)
            files = glob.glob(pattern)

            for file_path in files:
                total_files += 1
                try:
                    # Use FFmpeg to update album metadata
                    # Preserve original file extension for FFmpeg to recognize format
                    file_name = os.path.basename(file_path)
                    temp_file = os.path.join(os.path.dirname(file_path), f"temp_{file_name}")

                    if is_audio:
                        # For audio files, copy and update metadata
                        cmd = [
                            'ffmpeg', '-y', '-i', file_path,
                            '-c', 'copy',
                            '-metadata', f'album={playlist_title}',
                            '-metadata:s:a:0', f'album={playlist_title}',  # Force album on audio stream
                            '-id3v2_version', '3',
                            '-write_id3v1', '1',
                            temp_file
                        ]
                    else:
                        # For video files, copy and update metadata
                        cmd = [
                            'ffmpeg', '-y', '-i', file_path,
                            '-c', 'copy',
                            '-metadata', f'album={playlist_title}',
                            '-metadata:s:v:0', f'album={playlist_title}',  # Force album on video stream
                            temp_file
                        ]

                    # Handle encoding issues properly
                    result = subprocess.run(cmd, capture_output=True, timeout=60)
                    try:
                        result.stdout = result.stdout.decode('utf-8', errors='replace')
                        result.stderr = result.stderr.decode('utf-8', errors='replace')
                    except:
                        result.stdout = str(result.stdout)
                        result.stderr = str(result.stderr)

                    if result.returncode == 0:
                        # Replace original file with updated one
                        os.replace(temp_file, file_path)
                        updated_count += 1
                        logging.info(f"Updated album metadata for: {os.path.basename(file_path)}")
                    else:
                        logging.warning(f"Failed to update metadata for {os.path.basename(file_path)}: {result.stderr}")
                        # Clean up temp file if it exists
                        if os.path.exists(temp_file):
                            os.remove(temp_file)

                except subprocess.TimeoutExpired:
                    logging.warning(f"Timeout updating metadata for {os.path.basename(file_path)}")
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                except Exception as e:
                    logging.warning(f"Error updating metadata for {os.path.basename(file_path)}: {e}")
                    if os.path.exists(temp_file):
                        os.remove(temp_file)

        if total_files > 0:
            logging.info(f"Album metadata update completed: {updated_count}/{total_files} files updated")
        else:
            logging.info("No existing media files found to update")

    def update_existing_playlist_files_album(self, output_path, playlist_title, is_audio=True):
        """Public method to update album metadata for existing playlist files"""
        return self._update_existing_files_album_metadata(output_path, playlist_title, is_audio)

    def get_error_summary(self):
        """Get a summary of errors for UI display"""
        failed_count = len(self.failed_videos)
        skipped_count = len(self.skipped_videos)

        if failed_count == 0 and skipped_count == 0:
            return None

        summary = []
        if failed_count > 0:
            summary.append(f"{failed_count} video(s) failed")
        if skipped_count > 0:
            summary.append(f"{skipped_count} video(s) skipped")

        return ", ".join(summary)

    def inspect_archive_file(self, output_path: str):
        """Inspect the contents of an archive file for debugging purposes"""
        archive_file = os.path.join(output_path, 'archive.txt')

        if not os.path.exists(archive_file):
            return {
                'exists': False,
                'entry_count': 0,
                'sample_entries': [],
                'message': 'Archive file does not exist'
            }

        try:
            with open(archive_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            entry_count = len(lines)
            sample_entries = lines[:10] if len(lines) > 10 else lines
            sample_entries = [line.strip() for line in sample_entries]

            return {
                'exists': True,
                'entry_count': entry_count,
                'sample_entries': sample_entries,
                'message': f'Archive file contains {entry_count} entries'
            }
        except Exception as e:
            return {
                'exists': True,
                'entry_count': 0,
                'sample_entries': [],
                'message': f'Error reading archive file: {e}'
            }
