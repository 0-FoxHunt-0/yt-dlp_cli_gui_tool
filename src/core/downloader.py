import yt_dlp
from typing import Callable, Optional
import os
import logging
import subprocess
import shutil
import glob
from datetime import datetime
from pathlib import Path


class Downloader:
    def __init__(self):
        # Create logs directory if it doesn't exist
        self.logs_dir = os.path.join(os.path.dirname(
            os.path.dirname(os.path.dirname(__file__))), 'logs')
        os.makedirs(self.logs_dir, exist_ok=True)
        
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

        # Configure logging
        log_file = os.path.join(
            self.logs_dir, f'yt-dlp_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
        logging.basicConfig(
            filename=log_file,
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        
        # Check if FFmpeg is available
        self.ffmpeg_available = self._check_ffmpeg()

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
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                first_line = result.stdout.splitlines()[0] if result.stdout else "ffmpeg (version unknown)"
                logging.info(first_line)
        except Exception:
            pass

        self.base_options = {
            'format': 'bestaudio/best',
            'download_archive': 'archive.txt',
            'nopostoverwrites': True,
            'writethumbnail': True,  # Always download thumbnails
            'convertthumbnails': 'jpg',  # Always convert to jpg
            'retries': 3,  # Reduced retries for faster failure recovery
            'fragment_retries': 5,  # Retries for individual fragments
            'progress_hooks': [],
            'outtmpl': '%(title)s.%(ext)s',
            'logger': logging.getLogger('yt-dlp'),
            'quiet': True,
            'no_warnings': True,
            'clean_infojson': True,
            'ignoreerrors': True,  # Skip unavailable videos
            'continue_dl': True,   # Continue after errors
            'concurrent_fragments': 8,  # More parallel fragments for speed
            'http_chunk_size': 20971520,  # 20MB chunks for even better speed
            'buffer_size': 65536,  # Larger buffer size for faster I/O
            'no_check_certificate': False,  # Keep security but optimize
            'geo_bypass': True,  # Bypass geo-restrictions faster
            'prefer_free_formats': False,  # Don't prefer free formats if quality is better elsewhere
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
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                logging.info("FFmpeg found and available")
                return True
            else:
                logging.warning("FFmpeg command failed")
                return False
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            logging.warning(f"FFmpeg not found: {e}")
            return False

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
                 progress_callback: Optional[Callable] = None):

        options = self.base_options.copy()
        
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

        # Handle playlist folder creation
        if is_playlist:
            try:
                # Get playlist info to create folder
                with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True}) as temp_ydl:
                    playlist_info = temp_ydl.extract_info(url, download=False)
                    playlist_title = playlist_info.get('title', 'Unknown_Playlist')
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
                    },
                    {
                        'key': 'EmbedThumbnail',
                    }
                ])
            
            if metadata_options.get('embed_metadata', True) and self.ffmpeg_available:
                options['postprocessors'].append({
                    'key': 'FFmpegMetadata',
                })
            
            # Add audio normalization postprocessor for video
            if self.ffmpeg_available:
                options['postprocessors'].append({
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': 'mp4',
                })
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
            options['format'] = 'bestaudio/best'  # Prefer formats that need less conversion
            options['extractaudio'] = True       # yt-dlp -x
            options['audioformat'] = 'mp3'       # --audio-format mp3
            options['audioquality'] = '0'        # --audio-quality 0 (best)
            options['final_ext'] = 'mp3'
            # Explicit postprocessors in correct order to preserve embedding behavior
            options['postprocessors'] = [
                {
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '0',
                },
                {
                    'key': 'EmbedThumbnail',
                    'already_have_thumbnail': False,
                },
                {
                    'key': 'FFmpegMetadata',
                }
            ]
            
            # Allow toggling embedding via UI options while keeping MP3 enforcement
            if not metadata_options.get('embed_thumbnail', True):
                options['postprocessors'] = [pp for pp in options['postprocessors'] if pp.get('key') != 'EmbedThumbnail']
            if not metadata_options.get('embed_metadata', True):
                options['postprocessors'] = [pp for pp in options['postprocessors'] if pp.get('key') != 'FFmpegMetadata']

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
                # Audio-specific FFmpeg args optimized for speed with maximum resource usage
                options['postprocessor_args']['ffmpeg'] = [
                    '-hide_banner', 
                    '-loglevel', 'error',
                    '-threads', '0',  # Use all available CPU cores
                    '-thread_type', 'frame+slice',  # Use both frame and slice threading
                    '-cpu-used', '0',  # Use all CPU cycles for encoding (slowest but highest quality)
                    '-map_metadata', '0',
                    '-id3v2_version', '3',
                    '-write_id3v1', '1',
                    '-movflags', '+faststart',  # Optimize for fast streaming
                    '-bufsize', '2M',  # Larger buffer for smoother processing
                    '-readrate_initial_burst', '2.0',  # Allow faster initial processing
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

        # Capture initial archive count for accurate skipped video detection
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
            
            with yt_dlp.YoutubeDL(options) as ydl:
                self._current_ydl = ydl
                self._should_abort = False
                result = ydl.download([url])
                
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
            
            # Check if it's a critical error that should be re-raised
            if ("aborted" in error_msg.lower() or 
                "keyboardinterrupt" in error_msg.lower() or
                "ffprobe" in error_msg.lower() or 
                "ffmpeg" in error_msg.lower()):
                if "ffmpeg" in error_msg.lower():
                    instructions = self._get_ffmpeg_installation_instructions()
                    raise Exception(f"FFmpeg not found. {error_msg}\n\n{instructions}")
                else:
                    raise Exception(error_msg)
            else:
                # Non-critical errors - log but don't crash
                logging.warning(f"Download completed with errors: {error_msg}")
                return None
                
        finally:
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
                    valid_entries = [entry for entry in playlist_info['entries'] if entry is not None]
                    return len(valid_entries), playlist_info.get('title', 'Unknown Playlist')
                else:
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
                
                # Calculate skipped videos based on archive analysis
                if self._is_playlist_download:
                    # For playlists: calculate skipped as total existing minus what we actually processed
                    total_processed = self._playlist_downloaded_videos + self._playlist_failed_videos
                    if newly_added > total_processed:
                        # Some videos were already in archive (skipped)
                        additional_skipped = newly_added - total_processed
                        self._playlist_skipped_videos = max(0, additional_skipped)
                        logging.info(f"Detected {self._playlist_skipped_videos} already downloaded videos (skipped)")
                    elif newly_added < self._playlist_downloaded_videos:
                        # Archive count mismatch - log warning
                        logging.warning(f"Archive count mismatch: tracked {self._playlist_downloaded_videos} downloads but only {newly_added} added to archive")
                else:
                    # For single videos: if archive didn't grow, it was likely skipped
                    if newly_added == 0 and self._playlist_downloaded_videos == 0:
                        self._playlist_skipped_videos = 1  # Single video was skipped
                        logging.info("Single video was already downloaded (skipped)")
                    
        except Exception as e:
            logging.warning(f"Error detecting skipped videos: {e}")

    def _progress_hook(self, callback: Callable):
        def hook(d):
            # Check if download should be aborted
            if self._should_abort:
                # Use KeyboardInterrupt which yt-dlp respects and will stop the entire process
                raise KeyboardInterrupt("Download aborted by user")
            
            # Track active download files
            if d['status'] == 'downloading' and 'filename' in d:
                self._active_download_files.add(d['filename'])
            elif d['status'] == 'finished' and 'filename' in d:
                # Remove from active downloads when finished
                self._active_download_files.discard(d['filename'])
                
                # Update playlist tracking for successful downloads
                if self._is_playlist_download:
                    self._playlist_downloaded_videos += 1
                    logging.info(f"Playlist progress: {self._playlist_downloaded_videos}/{self._playlist_total_videos} videos downloaded")
                    
            elif d['status'] == 'error':
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
            
            # Pass the original yt-dlp data to the callback
            # This allows the UI to handle formatting and reduces data transformation issues
            callback(d)

        return hook

    def abort_download(self):
        """Abort the current download"""
        self._should_abort = True
        if self._current_ydl:
            try:
                # Multiple approaches to force stop
                self._current_ydl._downloader.interrupt()
                # Also try to set the abort flag in yt-dlp
                self._current_ydl._downloader.params['abort'] = True
                # Force close any open connections
                if hasattr(self._current_ydl._downloader, '_opener'):
                    self._current_ydl._downloader._opener.close()
            except:
                pass
        
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
