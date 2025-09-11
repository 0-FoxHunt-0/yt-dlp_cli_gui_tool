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
        
        # Keep a single downloader instance for capability checks (FFmpeg, etc.)
        self.downloader = Downloader()
        # Multi-task management
        self.tasks = []  # List of TaskItem instances
        
        # Check FFmpeg availability and show warning if needed
        if not self.downloader.ffmpeg_available:
            self.show_ffmpeg_warning()
        
        # Create the main window
        self.root = ctk.CTk()
        self.root.title("YouTube Downloader")
        self.root.geometry("800x750")
        self.root.minsize(400, 450)
        
        # Set window icon (if available)
        try:
            self.root.iconbitmap("icon.ico")
        except:
            pass
        
        # Create and pack the GUI elements
        self.create_widgets()
        
        # Track debounced persistence and restoration state
        self._persist_after_id = None
        self._restoring_tasks = False
        
        # Restore tasks state (count and URLs) from config
        self.restore_tasks_from_config()
        
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
            width=450,  # Responsive width for small screens
            fg_color="transparent"
        )
        self.scrollable_frame.pack(fill="both", expand=True, padx=10, pady=10)

    def create_scrollable_content(self):
        """Create all content within the scrollable frame"""
        # Options section
        self.create_options_section()
        
        # Metadata section
        self.create_metadata_section()

        # Cookie file section
        self.create_cookie_section()

        # Tasks section (multi-task support)
        self.create_tasks_section()

    def restore_tasks_from_config(self):
        """Restore number of tasks and their URLs from config"""
        try:
            self._restoring_tasks = True
            urls = self.config.get("task_urls", []) or []
            count = self.config.get("tasks_count", 1)
            try:
                count = int(count)
            except Exception:
                count = 1
            if count < 1:
                count = 1

            # Create tasks and set URLs
            for i in range(count):
                url_value = urls[i] if i < len(urls) else ""
                self.add_task(url=url_value)
        finally:
            self._restoring_tasks = False
            # Persist once after restore to normalize values
            self._persist_tasks_to_config()

    def _attach_task_bindings(self, task):
        """Attach listeners to task inputs for persistence"""
        try:
            task.url_var.trace_add("write", lambda *args: self._on_task_url_changed())
        except Exception:
            pass

    def _on_task_url_changed(self):
        if getattr(self, '_restoring_tasks', False):
            return
        self._schedule_persist_tasks()

    def _schedule_persist_tasks(self):
        try:
            if self._persist_after_id is not None:
                try:
                    self.root.after_cancel(self._persist_after_id)
                except Exception:
                    pass
            # Debounce saves to avoid excessive disk writes
            self._persist_after_id = self.root.after(300, self._persist_tasks_to_config)
        except Exception:
            # Fallback to immediate persist
            self._persist_tasks_to_config()

    def _persist_tasks_to_config(self):
        """Save current tasks count and URLs to config"""
        try:
            urls = []
            for t in getattr(self, 'tasks', []):
                try:
                    urls.append(t.get_url())
                except Exception:
                    urls.append("")
            # Batch update settings then save once
            self.config.settings["task_urls"] = urls
            self.config.settings["tasks_count"] = len(getattr(self, 'tasks', []))
            self.config.save_settings()
        except Exception:
            pass

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

    def create_tasks_section(self):
        """Create the tasks management section for multiple concurrent downloads"""
        tasks_frame = ctk.CTkFrame(self.scrollable_frame)
        tasks_frame.pack(fill="both", expand=True, pady=(0, 15))

        # Header row with controls
        header = ctk.CTkFrame(tasks_frame, fg_color="transparent")
        header.pack(fill="x", padx=15, pady=(15, 10))

        title_label = ctk.CTkLabel(
            header,
            text="Tasks",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        title_label.pack(side="left")

        controls_frame = ctk.CTkFrame(header, fg_color="transparent")
        controls_frame.pack(side="right")

        add_btn = ctk.CTkButton(
            controls_frame,
            text="➕ Add Task",
            width=110,
            height=32,
            command=self.add_task
        )
        add_btn.pack(side="left", padx=(0, 8))

        run_all_btn = ctk.CTkButton(
            controls_frame,
            text="▶ Run All",
            width=100,
            height=32,
            command=self.run_all_tasks
        )
        run_all_btn.pack(side="left", padx=(0, 8))

        scram_btn = ctk.CTkButton(
            controls_frame,
            text="🛑 Scram",
            width=100,
            height=32,
            fg_color=("red", "darkred"),
            hover_color=("darkred", "red"),
            command=self.scram_all_tasks
        )
        scram_btn.pack(side="left")

        # Container for task items (stacked vertically)
        self.tasks_list_frame = ctk.CTkFrame(tasks_frame)
        self.tasks_list_frame.pack(fill="both", expand=True, padx=15, pady=(0, 10))

        # Initial tasks are restored from config in __init__

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
            ("playlist_album_override", "📀 Use Playlist as Album", False),
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

    def create_cookie_section(self):
        """Create cookie file section"""
        cookie_frame = ctk.CTkFrame(self.scrollable_frame)
        cookie_frame.pack(fill="x", pady=(0, 15))

        # Cookie label
        cookie_label = ctk.CTkLabel(
            cookie_frame,
            text="Cookie File (Optional)",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        cookie_label.pack(anchor="w", padx=15, pady=(15, 10))

        # Cookie file input row
        cookie_row = ctk.CTkFrame(cookie_frame, fg_color="transparent")
        cookie_row.pack(fill="x", padx=15, pady=(0, 10))

        self.cookie_var = ctk.StringVar(value=self.config.get("cookie_file", ""))
        self.cookie_entry = ctk.CTkEntry(
            cookie_row,
            textvariable=self.cookie_var,
            placeholder_text="Path to YouTube cookies.txt file",
            height=32
        )
        self.cookie_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        browse_cookie_btn = ctk.CTkButton(
            cookie_row,
            text="Browse",
            width=80,
            height=32,
            command=self.browse_cookie_file
        )
        browse_cookie_btn.pack(side="left")

        # Cookie info text
        cookie_info = ctk.CTkLabel(
            cookie_frame,
            text="🎯 Use for age-restricted or region-blocked content.\n"
                 "Export cookies from your browser or use a cookie extractor extension.",
            font=ctk.CTkFont(size=10),
            text_color=("gray50", "gray50"),
            justify="left"
        )
        cookie_info.pack(anchor="w", padx=15, pady=(0, 15))

        # Bind to save on change (with debouncing)
        self.cookie_var.trace_add("write", self._on_cookie_file_changed)
        self._cookie_save_after_id = None

    def browse_cookie_file(self):
        """Browse for cookie file"""
        from tkinter import filedialog
        file_path = filedialog.askopenfilename(
            title="Select Cookie File",
            filetypes=[("Cookie files", "*.txt"), ("All files", "*.*")]
        )
        if file_path:
            self.cookie_var.set(file_path)
            # Save immediately when browsed
            self._save_cookie_file(file_path)

    def _on_cookie_file_changed(self, *args):
        """Handle cookie file changes with debouncing"""
        if getattr(self, '_restoring_tasks', False):
            return

        try:
            if self._cookie_save_after_id is not None:
                try:
                    self.root.after_cancel(self._cookie_save_after_id)
                except Exception:
                    pass

            # Debounce saves to avoid excessive disk writes
            self._cookie_save_after_id = self.root.after(500, self._save_cookie_file_delayed)
        except Exception:
            # Fallback to immediate save
            self._save_cookie_file_delayed()

    def _save_cookie_file(self, file_path):
        """Save cookie file path to config"""
        self.config.set("cookie_file", file_path)

    def _save_cookie_file_delayed(self):
        """Save cookie file path with validation"""
        try:
            file_path = self.cookie_var.get().strip()
            if file_path and not os.path.exists(file_path):
                # Don't save invalid paths, just warn
                return
            self._save_cookie_file(file_path)
        except Exception:
            pass
        finally:
            self._cookie_save_after_id = None

    # ===== Legacy single-output directory handlers (kept for config persistence) =====
    # These are used to persist a default output directory used to prefill new tasks
    def browse_output(self):
        """Browse for output directory (updates default for new tasks)"""
        directory = filedialog.askdirectory(initialdir=self.config.get("output_directory", self.config.get_default_output_directory()))
        if directory:
            # Save to config so newly added tasks are prefilled
            self._save_output_directory(directory)

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
        """Save output directory to config (used as default for new tasks)"""
        self.config.set("output_directory", directory)

    def _on_output_directory_changed(self, *args):
        """No-op for per-task outputs; retained for compatibility"""
        pass

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
        return

    def clear_output(self):
        """Reset default output directory used to prefill new tasks"""
        default_dir = self.config.reset_output_directory()
        # Inform the user in a dialog instead of a now-removed global log
        messagebox.showinfo("Output", f"Default output directory reset to: {default_dir}")

    # ===== Multi-task controls =====
    def add_task(self, url: str = ""):
        """Add a new task row (optionally with preset URL)"""
        default_output = self.config.get("output_directory", self.config.get_default_output_directory())
        task = TaskItem(self, parent_frame=self.tasks_list_frame, default_output=default_output)
        self.tasks.append(task)
        # Set URL if provided
        try:
            if url:
                task.url_var.set(url)
        except Exception:
            pass
        # Re-number task titles
        for idx, t in enumerate(self.tasks, start=1):
            t.update_title(f"Task {idx}")
        # Attach bindings for persistence
        self._attach_task_bindings(task)
        # Persist updated tasks unless we're restoring
        if not getattr(self, '_restoring_tasks', False):
            self._schedule_persist_tasks()
        return task

    def remove_task(self, task):
        """Remove a task row"""
        try:
            if task in self.tasks:
                # Abort if running
                if task.is_running:
                    task.abort()
                task.destroy()
                self.tasks.remove(task)
                for idx, t in enumerate(self.tasks, start=1):
                    t.update_title(f"Task {idx}")
                # Persist after removal
                self._schedule_persist_tasks()
        except Exception:
            pass

    def run_all_tasks(self):
        """Start all tasks that are not yet running and have a URL"""
        for task in self.tasks:
            if not task.is_running and task.get_url():
                task.start()

    def scram_all_tasks(self):
        """Abort all running tasks"""
        for task in self.tasks:
            if task.is_running:
                task.abort()
    
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

    # Per-task progress is handled inside TaskItem
    def update_progress(self, d):
        return

    def log_status(self, message):
        # Global logger no longer has a single textbox; print to stdout as fallback
        try:
            print(message)
        except Exception:
            pass

    def clear_status(self):
        return

    def show_playlist_counter(self, total_videos):
        return

    def hide_playlist_counter(self):
        return
    
    def show_single_video_status(self, status_text):
        return

    def update_playlist_counter(self, progress_info):
        return

    # Per-task start handled in TaskItem
    def start_download(self):
        return

    def download_worker(self, url):
        return

    def download_completed(self, success, message):
        return

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
            running = any(t.is_running for t in getattr(self, 'tasks', []))
            if running:
                print("\n🛑 Tasks in progress. Aborting all and cleaning up...")
                for t in self.tasks:
                    try:
                        if t.is_running:
                            t.abort()
                    except Exception:
                        pass
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
        # Persist tasks before closing
        try:
            self._persist_tasks_to_config()
        except Exception:
            pass
        
        running = any(t.is_running for t in getattr(self, 'tasks', []))
        if running:
            if messagebox.askokcancel("Quit", "Tasks in progress. Quit and abort all?\n\nIncomplete files will be cleaned up automatically."):
                for t in self.tasks:
                    try:
                        if t.is_running:
                            t.abort()
                    except Exception:
                        pass
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
            for t in getattr(self, 'tasks', []):
                try:
                    if t.is_running:
                        t.abort()
                except Exception:
                    pass
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


class TaskItem:
    """Represents a single download task with its own controls, progress, and terminal"""
    def __init__(self, ui: ModernUI, parent_frame, default_output: str):
        self.ui = ui
        self.frame = ctk.CTkFrame(parent_frame)
        self.frame.pack(fill="x", pady=(0, 10))

        # Per-task state
        self.downloader = Downloader()
        self.thread = None
        self.is_running = False
        self._aborted = False
        self._destroyed = False

        # Header row with title and remove button
        header = ctk.CTkFrame(self.frame, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(10, 5))

        self.title_label = ctk.CTkLabel(header, text="Task", font=ctk.CTkFont(size=13, weight="bold"))
        self.title_label.pack(side="left")

        header_btns = ctk.CTkFrame(header, fg_color="transparent")
        header_btns.pack(side="right")

        self.start_btn = ctk.CTkButton(header_btns, text="▶ Start", width=80, height=30, command=self.start)
        self.start_btn.pack(side="left", padx=(0, 6))

        self.abort_btn = ctk.CTkButton(header_btns, text="⏹ Abort", width=80, height=30,
                                       fg_color=("red", "darkred"), hover_color=("darkred", "red"),
                                       command=self.abort)
        self.abort_btn.pack(side="left", padx=(0, 6))
        self.abort_btn.configure(state="disabled")

        remove_btn = ctk.CTkButton(header_btns, text="🗑 Remove", width=90, height=30,
                                   fg_color=("gray70", "gray30"), hover_color=("gray60", "gray40"),
                                   command=lambda: self.ui.remove_task(self))
        remove_btn.pack(side="left")

        # URL row
        url_row = ctk.CTkFrame(self.frame, fg_color="transparent")
        url_row.pack(fill="x", padx=10, pady=5)

        url_label = ctk.CTkLabel(url_row, text="URL:")
        url_label.pack(side="left", padx=(0, 8))

        self.url_var = ctk.StringVar(value="")
        self.url_entry = ctk.CTkEntry(url_row, textvariable=self.url_var, placeholder_text="https://www.youtube.com/watch?v=...", height=32)
        self.url_entry.pack(side="left", fill="x", expand=True)

        # Format row (per task)
        fmt_row = ctk.CTkFrame(self.frame, fg_color="transparent")
        fmt_row.pack(fill="x", padx=10, pady=5)

        fmt_label = ctk.CTkLabel(fmt_row, text="Format:")
        fmt_label.pack(side="left", padx=(0, 8))

        self.format_var = ctk.StringVar(value=self.ui.format_var.get())
        fmt_radios = ctk.CTkFrame(fmt_row, fg_color="transparent")
        fmt_radios.pack(side="left")
        audio_radio = ctk.CTkRadioButton(fmt_radios, text="🎵 Audio (MP3)", variable=self.format_var, value="audio")
        video_radio = ctk.CTkRadioButton(fmt_radios, text="🎬 Video", variable=self.format_var, value="video")
        audio_radio.pack(side="left", padx=(0, 12))
        video_radio.pack(side="left")

        # Output row
        out_row = ctk.CTkFrame(self.frame, fg_color="transparent")
        out_row.pack(fill="x", padx=10, pady=5)

        out_label = ctk.CTkLabel(out_row, text="Output:")
        out_label.pack(side="left", padx=(0, 8))

        self.output_var = ctk.StringVar(value=default_output)
        self.output_entry = ctk.CTkEntry(out_row, textvariable=self.output_var, height=32)
        self.output_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        browse_btn = ctk.CTkButton(out_row, text="Browse", width=80, height=32, command=self._browse_output)
        browse_btn.pack(side="left")

        # Progress
        prog_row = ctk.CTkFrame(self.frame, fg_color="transparent")
        prog_row.pack(fill="x", padx=10, pady=(5, 5))

        self.progress_bar = ctk.CTkProgressBar(prog_row)
        self.progress_bar.pack(fill="x")
        self.progress_bar.set(0)

        self.progress_text = ctk.CTkLabel(self.frame, text="Waiting", font=ctk.CTkFont(size=12))
        self.progress_text.pack(anchor="w", padx=10)

        # Terminal / Status
        self.status_text = ctk.CTkTextbox(self.frame, height=130, font=ctk.CTkFont(size=11, family="Consolas"))
        self.status_text.pack(fill="x", padx=10, pady=(5, 6))

        clear_btn = ctk.CTkButton(self.frame, text="Clear Log", width=100, height=28, command=self._clear_status)
        clear_btn.pack(anchor="w", padx=10, pady=(0, 10))

        # Internal tracking for throttled logging
        self._last_logged_progress = 0
        self._last_logged_filename = ""

    def _run_on_ui(self, fn):
        """Schedule a callable to run on the Tk main thread safely."""
        try:
            if not self._is_alive():
                return
            self.ui.root.after(0, lambda: fn() if self._is_alive() else None)
        except Exception:
            pass

    def update_title(self, text: str):
        self.title_label.configure(text=text)

    def get_url(self) -> str:
        return self.url_var.get().strip()

    def _browse_output(self):
        directory = filedialog.askdirectory(initialdir=self.output_var.get())
        if directory:
            self.output_var.set(directory)
            # Also store as default for future tasks
            self.ui._save_output_directory(directory)

    def _clear_status(self):
        try:
            self.status_text.delete("0.0", "end")
        except Exception:
            pass

    def _is_alive(self) -> bool:
        try:
            return (not self._destroyed) and self.frame.winfo_exists()
        except Exception:
            return False

    def _set_progress_text_safe(self, text: str):
        if not self._is_alive():
            return
        def _apply():
            try:
                if self._is_alive():
                    self.progress_text.configure(text=text)
            except Exception:
                pass
        self._run_on_ui(_apply)

    def log(self, message: str):
        if not self._is_alive():
            return
        def _append():
            try:
                if self._is_alive():
                    self.status_text.insert("end", f"{message}\n")
                    self.status_text.see("end")
            except Exception:
                pass
        self._run_on_ui(_append)

    def start(self):
        if self.is_running:
            return
        url = self.get_url()
        if not url or not url.startswith(("http://", "https://")):
            messagebox.showerror("Error", "Please enter a valid URL starting with http:// or https://")
            return
        output_dir = self.output_var.get().strip()
        if not output_dir:
            messagebox.showerror("Error", "Please choose an output directory")
            return
        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except Exception as e:
                messagebox.showerror("Error", f"Cannot create output directory: {e}")
                return

        # Detect playlist for early feedback
        is_playlist = self._is_playlist_url(url)
        if is_playlist:
            self.progress_text.configure(text="📑 Detected playlist - preparing...")
            self.log("📑 Detected playlist URL - will download all videos")
        else:
            self.progress_text.configure(text="🎬 Detected single video - preparing...")
            self.log("🎬 Detected single video URL")

        # Build metadata options from global UI
        metadata_options = {key: var.get() for key, var in self.ui.metadata_vars.items()}
        is_audio = self.format_var.get() == "audio"

        # Switch buttons
        self.start_btn.configure(state="disabled")
        self.abort_btn.configure(state="normal")
        self.progress_bar.set(0)
        self._last_logged_progress = 0
        self._last_logged_filename = ""
        self._aborted = False
        self.log("🚀 Starting download...")

        def worker():
            try:
                # Try to get quick playlist size for UX
                if is_playlist:
                    try:
                        with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True}) as ydl:
                            info = ydl.extract_info(url, download=False)
                            if info and 'entries' in info:
                                total = len([e for e in info['entries'] if e is not None])
                                self.ui.root.after(0, lambda: self._set_progress_text_safe(f"📋 Playlist: {total} videos"))
                    except Exception:
                        pass

                # Get cookie file from UI config
                cookie_file = self.ui.config.get("cookie_file", "")
                if cookie_file:
                    cookie_file = cookie_file.strip()

                self.downloader.download(
                    url=url,
                    output_path=output_dir,
                    is_audio=is_audio,
                    is_playlist=is_playlist,
                    metadata_options=metadata_options,
                    progress_callback=self._update_progress,
                    cookie_file=cookie_file if cookie_file else None
                )
                self.ui.root.after(0, lambda: self._completed(True, "Download completed successfully!"))
            except Exception as e:
                # Normalize aborts vs errors
                msg = str(e) if e is not None else ""
                if (msg and 'aborted' in msg.lower()) or self._aborted or getattr(self.downloader, '_should_abort', False):
                    self.ui.root.after(0, lambda: self._completed(False, "Download aborted by user"))
                else:
                    display = msg if msg else "Unknown error"
                    self.ui.root.after(0, lambda: self._completed(False, f"Download failed: {display}"))

        import yt_dlp  # local import to avoid top-level dependency if not needed elsewhere
        self.thread = threading.Thread(target=worker, daemon=True)
        self.is_running = True
        self.thread.start()

    def abort(self):
        if self.is_running:
            try:
                self._aborted = True
                self.log("🛑 Abort requested...")
                self._set_progress_text_safe("⏹️ Aborting...")

                # Call downloader abort first
                self.downloader.abort_download()

                # Wait a short time for graceful shutdown
                import time
                time.sleep(0.5)

                # If thread is still alive after abort, try to force termination
                if self.thread and self.thread.is_alive():
                    self.log("⚠️ Thread still running, attempting force termination...")
                    try:
                        # Try to raise KeyboardInterrupt in the thread
                        import ctypes
                        if hasattr(ctypes, 'pythonapi'):
                            thread_id = self.thread.ident
                            if thread_id:
                                ctypes.pythonapi.PyThreadState_SetAsyncExc(
                                    ctypes.c_long(thread_id),
                                    ctypes.py_object(KeyboardInterrupt)
                                )
                                self.log("✅ Force termination signal sent to thread")
                    except Exception as e:
                        self.log(f"⚠️ Could not force terminate thread: {e}")

            except Exception as e:
                self.log(f"⚠️ Error during abort: {e}")

    def destroy(self):
        try:
            self._destroyed = True
            self.frame.destroy()
        except Exception:
            pass

    def _is_playlist_url(self, url: str) -> bool:
        import re
        patterns = [r'[?&]list=([^&]+)', r'playlist\?list=([^&]+)', r'watch\?v=[^&]+&list=([^&]+)']
        if any(re.search(p, url) for p in patterns):
            return True
        if 'youtube.com/playlist' in url or 'youtube.com/watch?list=' in url:
            return True
        return False

    def _update_progress(self, d):
        if not self._is_alive():
            return
        try:
            if d['status'] == 'downloading':
                # Compute progress safely off the UI thread
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

                filename = os.path.basename(d.get('filename', '')).rsplit('.', 1)[0]
                speed = d.get('speed', 0)
                eta = d.get('eta', 0)
                if speed and eta:
                    speed_mb = speed / 1024 / 1024
                    eta_str = f"{eta // 60}m {eta % 60}s" if eta > 60 else f"{eta}s"
                    status_text = f"Downloading: {filename} ({speed_mb:.1f} MB/s, ETA: {eta_str})"
                else:
                    status_text = f"Downloading: {filename}"

                # Apply UI updates on main thread
                self._run_on_ui(lambda: self.progress_bar.set(progress))
                self._set_progress_text_safe(status_text)

                # Throttled logging
                progress_percent = progress * 100
                if (progress_percent - self._last_logged_progress >= 5.0 or filename != self._last_logged_filename):
                    self.log(f"⏬ {status_text}")
                    self._last_logged_progress = progress_percent
                    self._last_logged_filename = filename

            elif d['status'] == 'finished':
                filename = os.path.basename(d.get('filename', '')).rsplit('.', 1)[0]
                self._set_progress_text_safe(f"Processing: {filename}")
                self.log(f"🔄 Processing: {filename}")
                self._last_logged_progress = 0
                self._last_logged_filename = ""

            elif d['status'] == 'error':
                error_msg = d.get('error', 'Unknown error')
                self._set_progress_text_safe(f"Error: {error_msg}")
                self.log(f"❌ Error: {error_msg}")
        except Exception as e:
            self.log(f"❌ Progress update error: {e}")

    def _completed(self, success: bool, message: str):
        if not self._is_alive():
            return
        try:
            error_summary = self.downloader.get_error_summary()
            if success:
                if error_summary:
                    self._set_progress_text_safe("⚠️ Completed with issues")
                    self.log(f"⚠️ Completed with issues: {error_summary}")
                    try:
                        messagebox.showwarning("Completed with Issues", f"Download completed but some videos had issues:\n{error_summary}\n\nCheck the error report in the output folder for details.")
                    except Exception:
                        pass
                else:
                    self._set_progress_text_safe("✅ Completed")
                    self.log(f"✅ {message}")
            else:
                if "aborted" in message.lower():
                    self._set_progress_text_safe("⏹️ Aborted")
                    self.log(f"⏹️ {message}")
                else:
                    if error_summary:
                        self._set_progress_text_safe("⚠️ Completed with errors")
                        self.log(f"⚠️ Completed with errors: {error_summary}")
                    else:
                        self._set_progress_text_safe("❌ Failed")
                        self.log(f"❌ {message}")
                    try:
                        messagebox.showerror("Error", message)
                    except Exception:
                        pass

            # Restore buttons/state
            try:
                self.abort_btn.configure(state="disabled")
                self.start_btn.configure(state="normal")
            except Exception:
                pass
            self.is_running = False
        except Exception:
            # If anything fails during completion (likely due to destroyed widgets), just exit quietly
            pass