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

        self.base_options = {
            'format': 'bestaudio/best',
            'download_archive': 'archive.txt',
            'nopostoverwrites': True,
            'writethumbnail': True,  # Always download thumbnails
            'convertthumbnails': 'jpg',  # Always convert to jpg
            'retries': 5,
            'progress_hooks': [],
            'outtmpl': '%(title)s.%(ext)s',
            'logger': logging.getLogger('yt-dlp'),
            'quiet': True,
            'no_warnings': True,
            'clean_infojson': True,
            'ignoreerrors': True,  # Skip unavailable videos
            'continue_dl': True,   # Continue after errors
        }
        
        # Track skipped/failed videos for reporting
        self.skipped_videos = []
        self.failed_videos = []
        
        # Only add FFmpeg postprocessors if FFmpeg is available
        if self.ffmpeg_available:
            self.base_options['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '0',
            }, {
                'key': 'EmbedThumbnail',
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
        else:
            # For audio, use the EXACT same approach as your working command
            # Remove conflicting options first
            options.pop('extractaudio', None)
            options.pop('audioformat', None)
            options.pop('audioquality', None)
            
            # Set the exact options from your working command
            options['format'] = 'bestaudio/best'
            options['postprocessors'] = [
                {
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '0',
                }
            ]
            
            # Add embedding exactly like your command does it
            if metadata_options.get('embed_thumbnail', True) and self.ffmpeg_available:
                options['postprocessors'].extend([
                    {
                        'key': 'FFmpegThumbnailsConvertor',
                        'format': 'jpg',
                    },
                    {
                        'key': 'EmbedThumbnail',
                        'already_have_thumbnail': True,  # Keep thumbnail files for Windows compatibility
                    }
                ])
            
            if metadata_options.get('embed_metadata', True) and self.ffmpeg_available:
                options['postprocessors'].append({
                    'key': 'FFmpegMetadata',
                })

        # Configure additional metadata options
        options['writedescription'] = metadata_options.get('write_description', False)
        options['writeinfojson'] = metadata_options.get('write_info_json', False)
        options['writesubtitles'] = metadata_options.get('embed_subs', False)
        options['writeautomaticsub'] = metadata_options.get('embed_subs', False)
        
        # Only enable chapters if FFmpeg is available
        if self.ffmpeg_available:
            options['embedchapters'] = metadata_options.get('embed_chapters', True)
        else:
            options['embedchapters'] = False
        
        # Windows-specific FFmpeg path fixes
        import platform
        if platform.system() == 'Windows':
            # Add Windows-specific options to handle path escaping
            options['ffmpeg_location'] = None  # Let yt-dlp find FFmpeg
            # Ensure proper path handling for Windows
            if 'postprocessor_args' not in options:
                options['postprocessor_args'] = {}
            # Add FFmpeg args for better Windows compatibility
            if is_audio:
                # Audio-specific FFmpeg args for better MP3 thumbnail compatibility
                options['postprocessor_args']['ffmpeg'] = [
                    '-hide_banner', 
                    '-loglevel', 'error',
                    '-map_metadata', '0',
                    '-id3v2_version', '3',
                    '-write_id3v1', '1',
                ]
            else:
                # Video-specific FFmpeg args for better audio-video sync
                options['postprocessor_args']['ffmpeg'] = [
                    '-hide_banner',
                    '-loglevel', 'error',
                    '-c:v', 'copy',  # Copy video stream to avoid re-encoding
                    '-c:a', 'copy',  # Copy audio stream to avoid re-encoding
                    '-avoid_negative_ts', 'make_zero',  # Fix timestamp issues
                    '-fflags', '+genpts',  # Generate presentation timestamps
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
        options['download_archive'] = os.path.join(output_path, 'archive.txt')

        # Add playlist-specific options with caching enabled
        if is_playlist:
            # Use the same template as single videos (no track numbers)
            sanitized_playlist_template = re.sub(r'[<>:"/\\|?*]', '_', template)
            options.update({
                'yes_playlist': True,
                'sleep_interval': 3,  # Reduced for better performance
                'outtmpl': os.path.join(output_path, sanitized_playlist_template),
                'restrictfilenames': True,  # Enable safe filenames
            })
        else:
            options['noplaylist'] = True
            options['restrictfilenames'] = True  # Enable safe filenames

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
                
                # Generate report if there were issues
                self._generate_error_report()
                return result
                
        except KeyboardInterrupt as e:
            # Handle abort specifically
            logging.info("Download aborted by user")
            # Cleanup and generate report
            try:
                cleanup_result = self._cleanup_incomplete_files()
                if cleanup_result["cleaned_count"] > 0:
                    logging.info(f"Abort cleanup completed: {cleanup_result['cleaned_count']} files removed")
            except Exception as cleanup_error:
                logging.warning(f"Cleanup after abort failed: {cleanup_error}")
            
            self._generate_error_report()
            raise Exception("Download aborted by user")
            
        except Exception as e:
            error_msg = str(e)
            logging.error(f"Download failed: {error_msg}")
            
            # Always clean up on any error
            try:
                cleanup_result = self._cleanup_incomplete_files()
                if cleanup_result["cleaned_count"] > 0:
                    logging.info(f"Error cleanup completed: {cleanup_result['cleaned_count']} files removed")
            except Exception as cleanup_error:
                logging.warning(f"Cleanup after error failed: {cleanup_error}")
            
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
            elif d['status'] == 'error':
                # Track failed videos
                error_info = {
                    'title': d.get('info_dict', {}).get('title', 'Unknown'),
                    'url': d.get('info_dict', {}).get('webpage_url', 'Unknown'),
                    'error': d.get('error', 'Unknown error')
                }
                self.failed_videos.append(error_info)
                logging.warning(f"Video failed: {error_info}")
            
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
            cleanup_result = self._cleanup_incomplete_files()
            if cleanup_result["cleaned_count"] > 0:
                logging.info(f"Immediate cleanup completed: {cleanup_result['cleaned_count']} files removed")
        except Exception as cleanup_error:
            logging.warning(f"Immediate cleanup failed: {cleanup_error}")

    def cleanup_incomplete_files(self):
        """Manually trigger cleanup of incomplete files"""
        return self._cleanup_incomplete_files()

    def _cleanup_incomplete_files(self):
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
                "*.ytdl",           # yt-dlp specific temp files
                "*.webm.part",      # WebM partial files
                "*.mp4.part",       # MP4 partial files
                "*.m4a.part",       # M4A partial files
            ]
            
            # Also clean up thumbnail files when aborting or after successful embedding
            thumbnail_patterns = [
                "*.webp",       # WebP thumbnails
                "*.jpg",        # JPEG thumbnails
                "*.jpeg",       # JPEG thumbnails
                "*.png",        # PNG thumbnails (converted thumbnails)
            ]
            if self._should_abort:
                partial_patterns.extend(thumbnail_patterns)
            
            # Handle duplicate thumbnails - find and remove duplicates
            self._cleanup_duplicate_thumbnails(output_path)
            
            # Clean up thumbnail files after successful embedding (not during abort)
            # Skip cleanup to keep thumbnails for Windows File Explorer compatibility
            # if not self._should_abort:
            #     self._cleanup_embedded_thumbnails(output_path)
            
            for pattern in partial_patterns:
                for file_path in output_path.rglob(pattern):
                    # Only clean up recent files (modified in last hour) to avoid removing user files
                    if file_path.is_file():
                        try:
                            # Check if file was modified recently (within last hour)
                            import time
                            file_age = time.time() - file_path.stat().st_mtime
                            
                            # For thumbnail files during abort, be more aggressive (within 10 minutes)
                            # For other files, use 1 hour limit
                            if self._should_abort and pattern in ["*.webp", "*.jpg", "*.jpeg", "*.png"]:
                                time_limit = 600  # 10 minutes for thumbnails during abort
                            else:
                                time_limit = 3600  # 1 hour for other files
                            
                            if file_age < time_limit:
                                cleanup_files.add(str(file_path))
                        except:
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
        """Clean up thumbnail files after they've been embedded into audio files"""
        try:
            import time
            # Find all audio files (mp3, m4a, etc.) that were recently modified
            audio_files = []
            for pattern in ["*.mp3", "*.m4a", "*.flac", "*.ogg"]:
                audio_files.extend(output_path.rglob(pattern))
            
            # Find corresponding thumbnail files
            for audio_file in audio_files:
                # Check if audio file was modified recently (within last 10 minutes)
                file_age = time.time() - audio_file.stat().st_mtime
                if file_age < 600:  # 10 minutes
                    # Look for thumbnail files with matching base name
                    base_name = audio_file.stem
                    for thumb_ext in [".webp", ".jpg", ".jpeg", ".png"]:
                        thumb_file = audio_file.parent / (base_name + thumb_ext)
                        if thumb_file.exists():
                            try:
                                # Check if thumbnail is older than audio file (means it was embedded)
                                thumb_age = time.time() - thumb_file.stat().st_mtime
                                if thumb_age > file_age:  # Thumbnail is older, likely embedded
                                    thumb_file.unlink()
                                    logging.debug(f"Cleaned up embedded thumbnail: {thumb_file}")
                            except Exception as e:
                                logging.warning(f"Failed to remove embedded thumbnail {thumb_file}: {e}")
        
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
