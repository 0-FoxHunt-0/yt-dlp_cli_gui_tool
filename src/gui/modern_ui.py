import customtkinter as ctk
import threading
import os
import signal
import sys
from tkinter import filedialog, messagebox
from ..core.downloader import Downloader
from ..utils.config import Config

# Try to import darkdetect, fallback to system detection
try:
    import darkdetect
    DARKDETECT_AVAILABLE = True
except ImportError:
    DARKDETECT_AVAILABLE = False


class ModernUI:
    def __init__(self):
        # Initialize config first
        self.config = Config()
        
        # Configure CustomTkinter appearance
        self.setup_appearance()
        
        self.downloader = Downloader()
        self.download_thread = None
        
        # Check FFmpeg availability and show warning if needed
        if not self.downloader.ffmpeg_available:
            self.show_ffmpeg_warning()
        
        # Create the main window
        self.root = ctk.CTk()
        self.root.title("YouTube Downloader")
        self.root.geometry("800x750")
        self.root.minsize(700, 600)
        
        # Set window icon (if available)
        try:
            self.root.iconbitmap("icon.ico")
        except:
            pass
        
        # Create and pack the GUI elements
        self.create_widgets()
        
        # Center the window
        self.center_window()
        
        # Bind window close event
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Set up signal handlers for graceful exit
        self.setup_signal_handlers()
        
        # Debouncing for output directory changes
        self._output_dir_save_after_id = None

    def setup_appearance(self):
        """Configure CustomTkinter appearance"""
        # Set appearance mode based on system or config
        if DARKDETECT_AVAILABLE:
            system_mode = darkdetect.theme()
        else:
            # Fallback: assume light mode if darkdetect not available
            system_mode = "light"
        
        config_mode = self.config.get("theme", system_mode)
        
        if config_mode == "auto":
            ctk.set_appearance_mode("system")
        else:
            ctk.set_appearance_mode(config_mode)
        
        # Set color theme
        ctk.set_default_color_theme("blue")

    def create_widgets(self):
        """Create all GUI widgets"""
        # Header with title and theme toggle (outside scrollable area)
        self.create_header()
        
        # Create scrollable main container
        self.create_scrollable_container()
        
        # Create scrollable content
        self.create_scrollable_content()

    def create_scrollable_container(self):
        """Create scrollable container for the main content"""
        # Main container with scrollbar
        self.main_container = ctk.CTkFrame(self.root)
        self.main_container.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        # Create scrollable frame
        self.scrollable_frame = ctk.CTkScrollableFrame(
            self.main_container,
            width=760,  # Slightly smaller than window width
            height=650,  # Fixed height for scrollable area
            fg_color="transparent"
        )
        self.scrollable_frame.pack(fill="both", expand=True, padx=10, pady=10)

    def create_scrollable_content(self):
        """Create all content within the scrollable frame"""
        # URL input section
        self.create_url_section()
        
        # Options section
        self.create_options_section()
        
        # Metadata section
        self.create_metadata_section()
        
        # Output section
        self.create_output_section()
        
        # Download button
        self.create_download_section()
        
        # Progress section
        self.create_progress_section()
        
        # Status section
        self.create_status_section()

    def create_header(self):
        """Create header with title and theme toggle"""
        header_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=(20, 0))
        
        # Title with icon
        title_label = ctk.CTkLabel(
            header_frame, 
            text="🎬 YouTube Downloader", 
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title_label.pack(side="left", anchor="w")
        
        # Theme toggle button
        self.theme_button = ctk.CTkButton(
            header_frame,
            text="🌙",
            width=60,
            height=40,
            command=self.toggle_theme,
            fg_color=("gray80", "gray30"),
            hover_color=("gray70", "gray40"),
            text_color=("gray10", "gray90"),
            font=ctk.CTkFont(size=18),
            anchor="center",
            border_width=1,
            border_color=("gray60", "gray40")
        )
        self.theme_button.pack(side="right", pady=(0, 10))

    def create_url_section(self):
        """Create URL input section"""
        url_frame = ctk.CTkFrame(self.scrollable_frame)
        url_frame.pack(fill="x", pady=(0, 15))
        
        # URL label
        url_label = ctk.CTkLabel(
            url_frame, 
            text="YouTube URL", 
            font=ctk.CTkFont(size=14, weight="bold")
        )
        url_label.pack(anchor="w", padx=15, pady=(15, 5))
        
        # URL entry with placeholder
        self.url_entry = ctk.CTkEntry(
            url_frame,
            placeholder_text="https://www.youtube.com/watch?v=...",
            height=40,
            font=ctk.CTkFont(size=12)
        )
        self.url_entry.pack(fill="x", padx=15, pady=(0, 15))

    def create_options_section(self):
        """Create download options section"""
        options_frame = ctk.CTkFrame(self.scrollable_frame)
        options_frame.pack(fill="x", pady=(0, 15))
        
        # Options label
        options_label = ctk.CTkLabel(
            options_frame, 
            text="Download Options", 
            font=ctk.CTkFont(size=14, weight="bold")
        )
        options_label.pack(anchor="w", padx=15, pady=(15, 10))
        
        # Format selection
        format_frame = ctk.CTkFrame(options_frame, fg_color="transparent")
        format_frame.pack(fill="x", padx=15, pady=(0, 10))
        
        format_label = ctk.CTkLabel(
            format_frame, 
            text="Format:", 
            font=ctk.CTkFont(size=12, weight="bold")
        )
        format_label.pack(anchor="w")
        
        # Radio buttons for format
        self.format_var = ctk.StringVar(value=self.config.get("default_format", "audio"))
        
        format_radio_frame = ctk.CTkFrame(format_frame, fg_color="transparent")
        format_radio_frame.pack(fill="x", pady=(5, 0))
        
        audio_radio = ctk.CTkRadioButton(
            format_radio_frame,
            text="🎵 Audio Only (MP3)",
            variable=self.format_var,
            value="audio",
            font=ctk.CTkFont(size=12)
        )
        audio_radio.pack(side="left", padx=(0, 20))
        
        video_radio = ctk.CTkRadioButton(
            format_radio_frame,
            text="🎬 Video + Audio",
            variable=self.format_var,
            value="video",
            font=ctk.CTkFont(size=12)
        )
        video_radio.pack(side="left")

    def create_metadata_section(self):
        """Create metadata options section"""
        metadata_frame = ctk.CTkFrame(self.scrollable_frame)
        metadata_frame.pack(fill="x", pady=(0, 15))
        
        # Metadata label
        metadata_label = ctk.CTkLabel(
            metadata_frame, 
            text="Metadata Options", 
            font=ctk.CTkFont(size=14, weight="bold")
        )
        metadata_label.pack(anchor="w", padx=15, pady=(15, 10))
        
        # Create metadata checkboxes in a 3-column grid layout
        metadata_grid = ctk.CTkFrame(metadata_frame, fg_color="transparent")
        metadata_grid.pack(fill="x", padx=15, pady=(0, 15))
        
        # Create three columns
        left_column = ctk.CTkFrame(metadata_grid, fg_color="transparent")
        left_column.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        middle_column = ctk.CTkFrame(metadata_grid, fg_color="transparent")
        middle_column.pack(side="left", fill="both", expand=True, padx=5)
        
        right_column = ctk.CTkFrame(metadata_grid, fg_color="transparent")
        right_column.pack(side="left", fill="both", expand=True, padx=(5, 0))
        
        # Initialize metadata variables
        self.metadata_vars = {}
        
        # Column 1 options
        ffmpeg_disabled = not self.downloader.ffmpeg_available
        col1_options = [
            ("embed_metadata", "📝 Embed Metadata", True and not ffmpeg_disabled),
            ("embed_thumbnail", "🖼️ Embed Thumbnail", True and not ffmpeg_disabled),
            ("embed_chapters", "📚 Embed Chapters", True and not ffmpeg_disabled),
        ]
        
        # Column 2 options
        col2_options = [
            ("write_thumbnail", "💾 Save Thumbnail", True),
            ("include_author", "👤 Include Author", False),
            ("write_description", "📄 Save Description", False),
        ]
        
        # Column 3 options
        col3_options = [
            ("write_info_json", "📋 Save Info JSON", False),
            ("embed_subs", "📝 Download Subtitles", False),
        ]
        
        # Add performance note
        perf_note = ctk.CTkLabel(
            metadata_frame,
            text="🚀 Optimized for maximum speed using all available CPU cores",
            font=ctk.CTkFont(size=10),
            text_color=("gray50", "gray50")
        )
        perf_note.pack(anchor="w", padx=15, pady=(0, 5))
        
        # Create checkboxes for each column
        for column, options in [(left_column, col1_options), (middle_column, col2_options), (right_column, col3_options)]:
            for key, text, default in options:
                var = ctk.BooleanVar(value=default)
                self.metadata_vars[key] = var
                checkbox = ctk.CTkCheckBox(
                    column,
                    text=text,
                    variable=var,
                    font=ctk.CTkFont(size=11),
                    state="disabled" if ffmpeg_disabled and key in ["embed_metadata", "embed_thumbnail", "embed_chapters"] else "normal"
                )
                checkbox.pack(anchor="w", pady=1)

    def create_output_section(self):
        """Create output directory section"""
        output_frame = ctk.CTkFrame(self.scrollable_frame)
        output_frame.pack(fill="x", pady=(0, 15))
        
        # Output label
        output_label = ctk.CTkLabel(
            output_frame, 
            text="Output Directory", 
            font=ctk.CTkFont(size=14, weight="bold")
        )
        output_label.pack(anchor="w", padx=15, pady=(15, 10))
        
        # Output path
        output_path_frame = ctk.CTkFrame(output_frame, fg_color="transparent")
        output_path_frame.pack(fill="x", padx=15, pady=(0, 15))
        
        self.output_var = ctk.StringVar(value=self.config.get("output_directory", self.config.get_default_output_directory()))
        # Add trace callback to save directory when user types/pastes
        self.output_var.trace_add("write", self._on_output_directory_changed)
        self.output_entry = ctk.CTkEntry(
            output_path_frame,
            textvariable=self.output_var,
            height=35,
            font=ctk.CTkFont(size=12)
        )
        self.output_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        # Bind focus out event to save directory immediately
        self.output_entry.bind("<FocusOut>", self._on_output_directory_focus_out)
        self.output_entry.bind("<Return>", self._on_output_directory_focus_out)
        
        # Button frame for Browse and Clear buttons
        button_frame = ctk.CTkFrame(output_path_frame, fg_color="transparent")
        button_frame.pack(side="right")
        
        browse_button = ctk.CTkButton(
            button_frame,
            text="Browse",
            width=80,
            height=35,
            command=self.browse_output
        )
        browse_button.pack(side="left", padx=(0, 5))
        
        clear_button = ctk.CTkButton(
            button_frame,
            text="Clear",
            width=60,
            height=35,
            command=self.clear_output,
            fg_color=("gray70", "gray30"),
            hover_color=("gray60", "gray40")
        )
        clear_button.pack(side="left")

    def create_download_section(self):
        """Create download button section"""
        download_frame = ctk.CTkFrame(self.scrollable_frame, fg_color="transparent")
        download_frame.pack(fill="x", pady=15)
        
        self.download_button = ctk.CTkButton(
            download_frame,
            text="⬇️ Download",
            height=45,
            font=ctk.CTkFont(size=16, weight="bold"),
            command=self.start_download
        )
        self.download_button.pack(pady=10)
        
        # Abort button (initially hidden)
        self.abort_button = ctk.CTkButton(
            download_frame,
            text="⏹️ Abort Download",
            height=45,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=("red", "darkred"),
            hover_color=("darkred", "red"),
            command=self.abort_download
        )
        # Don't pack initially - will be shown/hidden as needed

    def create_progress_section(self):
        """Create progress bar section"""
        progress_frame = ctk.CTkFrame(self.scrollable_frame)
        progress_frame.pack(fill="x", pady=(0, 15))
        
        # Progress label
        progress_label = ctk.CTkLabel(
            progress_frame, 
            text="Progress", 
            font=ctk.CTkFont(size=14, weight="bold")
        )
        progress_label.pack(anchor="w", padx=15, pady=(15, 10))
        
        # Playlist counter (initially hidden)
        self.playlist_counter = ctk.CTkLabel(
            progress_frame,
            text="",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=("blue", "lightblue")
        )
        self.playlist_counter.pack(anchor="w", padx=15, pady=(0, 5))
        self.playlist_counter.pack_forget()  # Hide initially
        
        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(progress_frame)
        self.progress_bar.pack(fill="x", padx=15, pady=(0, 10))
        self.progress_bar.set(0)
        
        # Progress text
        self.progress_text = ctk.CTkLabel(
            progress_frame,
            text="Ready to download",
            font=ctk.CTkFont(size=12)
        )
        self.progress_text.pack(anchor="w", padx=15, pady=(0, 15))

    def create_status_section(self):
        """Create status section"""
        status_frame = ctk.CTkFrame(self.scrollable_frame)
        status_frame.pack(fill="x", pady=(0, 15))
        
        # Status label
        status_label = ctk.CTkLabel(
            status_frame, 
            text="Status Log", 
            font=ctk.CTkFont(size=14, weight="bold")
        )
        status_label.pack(anchor="w", padx=15, pady=(15, 10))
        
        # Status text area
        self.status_text = ctk.CTkTextbox(
            status_frame,
            height=150,
            font=ctk.CTkFont(size=11, family="Consolas")
        )
        self.status_text.pack(fill="x", padx=15, pady=(0, 10))
        
        # Clear button
        clear_button = ctk.CTkButton(
            status_frame,
            text="Clear Log",
            width=100,
            height=30,
            command=self.clear_status
        )
        clear_button.pack(anchor="w", padx=15, pady=(0, 15))

    def browse_output(self):
        """Browse for output directory"""
        directory = filedialog.askdirectory(initialdir=self.output_var.get())
        if directory:
            self.output_var.set(directory)
            # Save to config
            self._save_output_directory(directory)

    def _save_output_directory(self, directory):
        """Save output directory to config"""
        self.config.set("output_directory", directory)

    def _on_output_directory_changed(self, *args):
        """Callback when output directory is changed by typing/pasting"""
        directory = self.output_var.get().strip()
        if directory:
            # Cancel previous save timer if it exists
            if self._output_dir_save_after_id:
                self.root.after_cancel(self._output_dir_save_after_id)
            
            # Schedule save after 500ms delay (debouncing)
            self._output_dir_save_after_id = self.root.after(500, self._save_output_directory_delayed, directory)

    def _save_output_directory_delayed(self, directory):
        """Save output directory with validation after delay"""
        try:
            # Check if it's a valid path (even if it doesn't exist yet)
            if os.path.isabs(directory) or os.path.normpath(directory) != '.':
                self._save_output_directory(directory)
        except Exception:
            # If there's any error with the path, don't save
            pass
        finally:
            self._output_dir_save_after_id = None

    def _on_output_directory_focus_out(self, event):
        """Callback when output directory entry loses focus"""
        directory = self.output_var.get().strip()
        if directory:
            self._save_output_directory(directory)

    def clear_output(self):
        """Clear output directory and reset to default"""
        default_dir = self.config.reset_output_directory()
        self.output_var.set(default_dir)
        self.log_status(f"📁 Output directory reset to default: {default_dir}")

    def abort_download(self):
        """Abort the current download"""
        if self.download_thread and self.download_thread.is_alive():
            self.downloader.abort_download()
            self.log_status("🛑 Download abort requested...")
            self.progress_text.configure(text="⏹️ Aborting download...")
            self.log_status("🧹 Cleaning up incomplete files...")
            
            # Hide playlist counter
            self.hide_playlist_counter()
            
            # Hide abort button and show download button
            self.abort_button.pack_forget()
            self.download_button.pack(pady=10)
    
    def is_playlist_url(self, url):
        """Detect if the URL is a playlist based on YouTube URL parameters"""
        import re
        
        # YouTube playlist patterns
        playlist_patterns = [
            r'[?&]list=([^&]+)',  # Standard playlist parameter
            r'playlist\?list=([^&]+)',  # Playlist URL format
            r'watch\?v=[^&]+&list=([^&]+)',  # Video with playlist
        ]
        
        for pattern in playlist_patterns:
            if re.search(pattern, url):
                return True
        
        # Check for playlist-specific domains
        if 'youtube.com/playlist' in url or 'youtube.com/watch?list=' in url:
            return True
            
        return False

    def update_progress(self, d):
        """Update progress bar and status"""
        try:
            # Update playlist counter if this is a playlist download
            playlist_progress = self.downloader.get_playlist_progress()
            if playlist_progress:
                self.update_playlist_counter(playlist_progress)
            
            if d['status'] == 'downloading':
                # Extract progress percentage
                if d.get('total_bytes'):
                    downloaded = d.get('downloaded_bytes', 0)
                    total = d.get('total_bytes', 0)
                    progress = (downloaded / total) if total > 0 else 0
                else:
                    progress_str = d.get('_percent_str', '0%').replace('%', '')
                    try:
                        progress = float(progress_str) / 100
                    except ValueError:
                        progress = 0
                
                # Update progress bar
                self.progress_bar.set(progress)
                
                # Update progress text
                filename = os.path.basename(d.get('filename', '')).rsplit('.', 1)[0]
                speed = d.get('speed', 0)
                eta = d.get('eta', 0)
                
                if speed and eta:
                    speed_mb = speed / 1024 / 1024
                    if eta > 60:
                        eta_str = f"{eta // 60}m {eta % 60}s"
                    else:
                        eta_str = f"{eta}s"
                    status_text = f"Downloading: {filename} ({speed_mb:.1f} MB/s, ETA: {eta_str})"
                else:
                    status_text = f"Downloading: {filename}"
                
                self.progress_text.configure(text=status_text)
                
                # Only log status periodically to avoid spam (every 5% progress or significant events)
                progress_percent = progress * 100
                if not hasattr(self, '_last_logged_progress'):
                    self._last_logged_progress = 0
                    self._last_logged_filename = ""
                
                # Log only if progress increased by 5% or filename changed
                if (progress_percent - self._last_logged_progress >= 5.0 or 
                    filename != self._last_logged_filename):
                    self.log_status(f"⏬ {status_text}")
                    self._last_logged_progress = progress_percent
                    self._last_logged_filename = filename
                
            elif d['status'] == 'finished':
                filename = os.path.basename(d.get('filename', '')).rsplit('.', 1)[0]
                self.progress_text.configure(text=f"Processing: {filename}")
                self.log_status(f"🔄 Processing: {filename}")
                # Reset progress tracking for next download
                self._last_logged_progress = 0
                self._last_logged_filename = ""
                
            elif d['status'] == 'error':
                error_msg = d.get('error', 'Unknown error')
                self.progress_text.configure(text=f"Error: {error_msg}")
                self.log_status(f"❌ Error: {error_msg}")
                
        except Exception as e:
            self.log_status(f"❌ Progress update error: {str(e)}")

    def log_status(self, message):
        """Add message to status log"""
        self.status_text.insert("end", f"{message}\n")
        self.status_text.see("end")
        self.root.update_idletasks()

    def clear_status(self):
        """Clear status log"""
        self.status_text.delete("0.0", "end")

    def show_playlist_counter(self, total_videos):
        """Show playlist counter with total video count"""
        self.playlist_counter.configure(text=f"📋 Playlist: {total_videos} videos total")
        self.playlist_counter.pack(anchor="w", padx=15, pady=(0, 5))

    def hide_playlist_counter(self):
        """Hide playlist counter"""
        self.playlist_counter.pack_forget()

    def update_playlist_counter(self, progress_info):
        """Update playlist counter with current progress"""
        if progress_info:
            downloaded = progress_info['downloaded']
            failed = progress_info['failed']
            skipped = progress_info['skipped']
            completed = progress_info['completed']
            total = progress_info['total']
            
            # Create status text with emojis
            status_parts = []
            if downloaded > 0:
                status_parts.append(f"✅ {downloaded}")
            if failed > 0:
                status_parts.append(f"❌ {failed}")
            if skipped > 0:
                status_parts.append(f"⏭️ {skipped}")
            
            # Show completed/total as the main counter
            if status_parts:
                status_text = " | ".join(status_parts)
                counter_text = f"📋 Playlist Progress: {completed}/{total} videos ({status_text})"
            else:
                counter_text = f"📋 Playlist Progress: {completed}/{total} videos"
            
            self.playlist_counter.configure(text=counter_text)

    def start_download(self):
        """Start the download process"""
        url = self.url_entry.get().strip()
        
        # Validate URL
        if not url or url == "https://www.youtube.com/watch?v=...":
            messagebox.showerror("Error", "Please enter a valid YouTube URL")
            return
        
        if not url.startswith(('http://', 'https://')):
            messagebox.showerror("Error", "Please enter a valid URL starting with http:// or https://")
            return
        
        # Validate output directory
        output_dir = self.output_var.get()
        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except Exception as e:
                messagebox.showerror("Error", f"Cannot create output directory: {str(e)}")
                return
        
        # Auto-detect playlist and provide immediate feedback
        is_playlist = self.is_playlist_url(url)
        if is_playlist:
            self.progress_text.configure(text="📑 Detected playlist - preparing download...")
            self.log_status("📑 Detected playlist URL - will download all videos")
        else:
            self.progress_text.configure(text="🎬 Detected single video - preparing download...")
            self.log_status("🎬 Detected single video URL")
        
        # Switch to abort button
        self.download_button.pack_forget()
        self.abort_button.pack(pady=10)
        
        self.progress_bar.set(0)
        # Reset progress tracking for new download
        self._last_logged_progress = 0
        self._last_logged_filename = ""
        self.log_status("🚀 Starting download...")
        
        # Start download in separate thread
        self.download_thread = threading.Thread(target=self.download_worker, args=(url,))
        self.download_thread.daemon = True
        self.download_thread.start()

    def download_worker(self, url):
        """Worker thread for download"""
        try:
            # Auto-detect if this is a playlist
            is_playlist = self.is_playlist_url(url)
            
            # Show playlist counter if this is a playlist
            if is_playlist:
                # Get playlist info to show initial counter
                try:
                    import yt_dlp
                    with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True}) as ydl:
                        playlist_info = ydl.extract_info(url, download=False)
                        if playlist_info and 'entries' in playlist_info:
                            valid_entries = [entry for entry in playlist_info['entries'] if entry is not None]
                            total_videos = len(valid_entries)
                            self.root.after(0, self.show_playlist_counter, total_videos)
                except Exception as e:
                    # If we can't get playlist info, still show counter with unknown count
                    self.root.after(0, self.show_playlist_counter, "?")
            
            # Collect metadata options
            metadata_options = {
                key: var.get() for key, var in self.metadata_vars.items()
            }
            
            self.downloader.download(
                url=url,
                output_path=self.output_var.get(),
                is_audio=self.format_var.get() == "audio",
                is_playlist=is_playlist,
                metadata_options=metadata_options,
                progress_callback=self.update_progress
            )
            
            # Update UI on completion
            self.root.after(0, self.download_completed, True, "Download completed successfully!")
            
        except Exception as e:
            # Update UI on error
            self.root.after(0, self.download_completed, False, f"Download failed: {str(e)}")

    def download_completed(self, success, message):
        """Handle download completion"""
        # Hide playlist counter
        self.hide_playlist_counter()
        
        # Check for error summary
        error_summary = self.downloader.get_error_summary()
        
        if success:
            if error_summary:
                self.progress_text.configure(text="⚠️ Download completed with issues")
                self.log_status(f"⚠️ Download completed with issues: {error_summary}")
                messagebox.showwarning("Completed with Issues", f"Download completed but some videos had issues:\n{error_summary}\n\nCheck the error report in the output folder for details.")
            else:
                self.progress_text.configure(text="✅ Download completed!")
                self.log_status(f"✅ {message}")
                messagebox.showinfo("Success", "Download completed successfully!")
        else:
            # Check if it was aborted
            if "aborted" in message.lower():
                self.progress_text.configure(text="⏹️ Download aborted")
                self.log_status(f"⏹️ {message}")
                messagebox.showinfo("Aborted", "Download was aborted by user")
            else:
                if error_summary:
                    self.progress_text.configure(text="⚠️ Download completed with errors")
                    self.log_status(f"⚠️ Download completed with errors: {error_summary}")
                    messagebox.showwarning("Completed with Errors", f"Download completed but encountered errors:\n{error_summary}\n\nCheck the error report in the output folder for details.")
                else:
                    self.progress_text.configure(text="❌ Download failed")
                    self.log_status(f"❌ {message}")
                    messagebox.showerror("Error", message)
        
        # Switch back to download button
        self.abort_button.pack_forget()
        self.download_button.pack(pady=10)
        self.progress_bar.set(0)

    def toggle_theme(self):
        """Toggle between dark and light themes"""
        current_mode = ctk.get_appearance_mode()
        new_mode = "Light" if current_mode == "Dark" else "Dark"
        
        # Disable button temporarily to prevent double-clicks during theme change
        self.theme_button.configure(state="disabled")
        
        # Update CustomTkinter appearance (this causes the visual refresh)
        ctk.set_appearance_mode(new_mode)
        
        # Save to config
        self.config.set("theme", new_mode.lower())
        
        # Update theme button text and re-enable after a short delay
        self.root.after(100, self._finish_theme_toggle)
    
    def _finish_theme_toggle(self):
        """Complete the theme toggle process"""
        self.update_theme_button()
        self.theme_button.configure(state="normal")

    def update_theme_button(self):
        """Update theme button text"""
        current_mode = ctk.get_appearance_mode()
        # Use better contrast icons that work in both themes
        if current_mode == "Dark":
            icon_text = "☀"  # Sun for switching to light mode
            text_color = "yellow"
        else:
            icon_text = "🌙"  # Moon for switching to dark mode  
            text_color = ("gray20", "gray80")
        
        self.theme_button.configure(text=icon_text, text_color=text_color)

    def center_window(self):
        """Center the window on screen"""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')

    def setup_signal_handlers(self):
        """Set up signal handlers for graceful exit"""
        def signal_handler(signum, frame):
            """Handle SIGINT (Ctrl+C) and SIGTERM signals"""
            if self.download_thread and self.download_thread.is_alive():
                print("\n🛑 Download in progress. Aborting and cleaning up incomplete files...")
                self.downloader.abort_download()
                # Give a moment for cleanup to complete
                import time
                time.sleep(1)
                print("✅ Cleanup completed. Exiting...")
            else:
                print("\n👋 Exiting gracefully...")
            
            # Save config before exit
            try:
                geometry = self.root.geometry()
                self.config.set("window_size", geometry)
            except:
                pass
            
            # Exit cleanly
            try:
                self.root.quit()
                self.root.destroy()
            except:
                pass
            sys.exit(0)
        
        # Register signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        if hasattr(signal, 'SIGTERM'):
            signal.signal(signal.SIGTERM, signal_handler)

    def on_closing(self):
        """Handle window closing"""
        # Save window size to config
        geometry = self.root.geometry()
        self.config.set("window_size", geometry)
        
        if self.download_thread and self.download_thread.is_alive():
            if messagebox.askokcancel("Quit", "Download in progress. Are you sure you want to quit?\n\nIncomplete files will be cleaned up automatically."):
                # Abort the download gracefully
                self.downloader.abort_download()
                self.root.destroy()
        else:
            self.root.destroy()

    def run(self):
        """Start the GUI application"""
        # Update theme button after window is created
        self.update_theme_button()
        
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            # This should be handled by the signal handler, but just in case
            print("\n👋 Exiting gracefully...")
            if self.download_thread and self.download_thread.is_alive():
                self.downloader.abort_download()
            sys.exit(0)
    
    def show_ffmpeg_warning(self):
        """Show warning about FFmpeg not being available"""
        warning_text = """⚠️  FFmpeg Not Found

FFmpeg is required for:
• Audio conversion to MP3
• Metadata embedding
• Thumbnail embedding

Some features will be disabled until FFmpeg is installed.

Installation Instructions:
• Windows: Download from https://ffmpeg.org/download.html
• macOS: brew install ffmpeg
• Linux: sudo apt install ffmpeg (Ubuntu/Debian)

Downloads will still work but without advanced features."""
        
        messagebox.showwarning("FFmpeg Not Found", warning_text) 