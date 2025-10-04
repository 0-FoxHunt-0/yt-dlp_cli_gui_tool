import customtkinter as ctk
import threading
import os
import signal
import sys
import json
import re
import difflib
import math
from pathlib import Path
from tkinter import filedialog, messagebox
from ..core.downloader import Downloader
from ..utils.config import Config
from .task_item import TaskItem

# Try to import darkdetect, fallback to system detection
try:
    import darkdetect
    DARKDETECT_AVAILABLE = True
except ImportError:
    DARKDETECT_AVAILABLE = False


class ModernUI:
    # Modern color palette for both light and dark themes
    COLORS = {
        'dark': {
            'primary': '#6366f1',      # Indigo
            'primary_hover': '#5856d6', # Darker indigo
            'secondary': '#10b981',    # Emerald
            'accent': '#f59e0b',       # Amber
            'danger': '#ef4444',       # Red
            'warning': '#f97316',      # Orange
            'success': '#22c55e',      # Green
            'surface': '#1f2937',      # Dark surface
            'surface_light': '#374151', # Light surface
            'background': '#111827',    # Dark background
            'card': '#1f2937',         # Card background
            'text_primary': '#f9fafb',  # Light text
            'text_secondary': '#d1d5db', # Muted text
            'border': '#374151',       # Border color
        },
        'light': {
            'primary': '#6366f1',      # Indigo (same for consistency)
            'primary_hover': '#5856d6', # Darker indigo
            'secondary': '#10b981',    # Emerald
            'accent': '#f59e0b',       # Amber
            'danger': '#dc2626',       # Red
            'warning': '#ea580c',      # Orange
            'success': '#16a34a',      # Green
            'surface': '#f8fafc',      # Light surface
            'surface_light': '#f1f5f9', # Lighter surface
            'background': '#ffffff',    # White background
            'card': '#ffffff',         # White card background
            'text_primary': '#0f172a',  # Dark text
            'text_secondary': '#64748b', # Muted text
            'border': '#e2e8f0',       # Light border color
        }
    }

    # Animation constants
    ANIMATION_DURATION = 300
    EASING_FUNCTIONS = {
        'ease_out': lambda t: 1 - math.pow(1 - t, 3),
        'ease_in_out': lambda t: 3 * t * t - 2 * t * t * t if t < 0.5 else 1 - math.pow(-2 * t + 2, 3) / 2
    }

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
        
        # Create the main window with modern styling
        self.root = ctk.CTk()
        self.root.title("🎬 YouTube Media Downloader")

        # Set minimum size
        self.root.minsize(800, 600)

        # Maximize window to fill entire screen (but keep it windowed)
        try:
            # Try modern maximized state first
            self.root.state('zoomed')
            # Ensure window is not minimized and is visible
            self.root.update()
            self.root.deiconify()
            self.root.focus_force()
        except:
            try:
                # Fallback for older Tkinter versions
                self.root.attributes('-zoomed', True)
                self.root.update()
                self.root.deiconify()
                self.root.focus_force()
            except:
                # Final fallback - set large geometry
                screen_width = self.root.winfo_screenwidth()
                screen_height = self.root.winfo_screenheight()
                self.root.geometry(f"{screen_width}x{screen_height}+0+0")
                self.root.update()
                self.root.deiconify()
                self.root.focus_force()

        # Modern window appearance (no transparency for better visibility)
        pass
        
        # Set window icon (resolve relative to project root with fallback)
        try:
            project_root = Path(__file__).resolve().parent.parent.parent
            icon_candidates = [
                project_root / "icon.ico",
                project_root / "assets" / "icon.ico",
                Path.cwd() / "icon.ico",
            ]
            for candidate in icon_candidates:
                if candidate.exists():
                    self.root.iconbitmap(str(candidate))
                    break
        except Exception:
            pass
        
        # Track debounced persistence and restoration state
        self._persist_after_id = None
        self._restoring_tasks = False

        # Create and pack the GUI elements
        self.create_widgets()

        # Restore tasks state (count and URLs) from config after UI is created
        self.restore_tasks_from_config()

        # Note: Window is launched maximized to fill screen
        
        # Bind window close event and maximize toggle
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.bind("<Escape>", self.toggle_maximize)
        self.root.bind("<F11>", self.toggle_maximize)
        
        # Set up signal handlers for graceful exit
        self.setup_signal_handlers()
        
        # Debouncing for output directory changes
        self._output_dir_save_after_id = None

    def setup_appearance(self):
        """Configure CustomTkinter appearance with modern styling"""
        # Set appearance mode based on system or config
        if DARKDETECT_AVAILABLE:
            system_mode = darkdetect.theme()
        else:
            # Fallback: assume dark mode for modern look
            system_mode = "dark"

        config_mode = self.config.get("theme", system_mode)

        if config_mode == "auto":
            ctk.set_appearance_mode("system")
        else:
            ctk.set_appearance_mode(config_mode)

        # Configure modern styling
        self._apply_modern_styling()

    def get_current_colors(self):
        """Get the current color palette based on the theme mode"""
        current_mode = ctk.get_appearance_mode().lower()
        return self.COLORS.get(current_mode, self.COLORS['dark'])

    def _apply_modern_styling(self):
        """Apply modern styling and custom colors to the app"""
        try:
            # Get current colors based on theme mode
            current_colors = self.get_current_colors()

            # Create custom color theme for current mode
            colors = [
                ("CTk", {"fg_color": [current_colors['background'], current_colors['surface']]}),
                ("CTkToplevel", {"fg_color": [current_colors['background'], current_colors['surface']]}),
                ("CTkFrame", {"fg_color": [current_colors['surface'], current_colors['surface_light']]}),
                ("CTkButton", {
                    "fg_color": [current_colors['primary'], current_colors['primary_hover']],
                    "hover_color": [current_colors['primary_hover'], current_colors['primary']],
                    "border_color": [current_colors['primary'], current_colors['primary_hover']],
                    "text_color": [current_colors['text_primary'], current_colors['text_primary']],
                    "border_width": [1, 1]
                }),
                ("CTkLabel", {
                    "fg_color": "transparent",
                    "text_color": [current_colors['text_primary'], current_colors['text_secondary']]
                }),
                ("CTkEntry", {
                    "fg_color": [current_colors['surface_light'], current_colors['surface']],
                    "border_color": [current_colors['border'], current_colors['border']],
                    "text_color": [current_colors['text_primary'], current_colors['text_primary']],
                    "placeholder_text_color": [current_colors['text_secondary'], current_colors['text_secondary']]
                }),
                ("CTkTextbox", {
                    "fg_color": [current_colors['surface_light'], current_colors['surface']],
                    "border_color": [current_colors['border'], current_colors['border']],
                    "text_color": [current_colors['text_primary'], current_colors['text_primary']]
                }),
                ("CTkScrollableFrame", {
                    "fg_color": [current_colors['surface'], current_colors['surface_light']],
                    "scrollbar_fg_color": [current_colors['surface_light'], current_colors['surface']],
                    "scrollbar_button_color": [current_colors['primary'], current_colors['primary_hover']],
                    "scrollbar_button_hover_color": [current_colors['primary_hover'], current_colors['primary']]
                }),
                ("CTkProgressBar", {
                    "fg_color": [current_colors['surface_light'], current_colors['surface']],
                    "progress_color": [current_colors['secondary'], current_colors['secondary']],
                    "border_color": [current_colors['border'], current_colors['border']]
                }),
                ("CTkCheckBox", {
                    "fg_color": [current_colors['surface_light'], current_colors['surface']],
                    "border_color": [current_colors['border'], current_colors['border']],
                    "hover_color": [current_colors['primary'], current_colors['primary_hover']],
                    "checkmark_color": [current_colors['text_primary'], current_colors['text_primary']],
                    "text_color": [current_colors['text_primary'], current_colors['text_primary']]
                }),
                ("CTkRadioButton", {
                    "fg_color": [current_colors['surface_light'], current_colors['surface']],
                    "border_color": [current_colors['border'], current_colors['border']],
                    "hover_color": [current_colors['primary'], current_colors['primary_hover']],
                    "checkmark_color": [current_colors['text_primary'], current_colors['text_primary']],
                    "text_color": [current_colors['text_primary'], current_colors['text_primary']]
                }),
                ("CTkOptionMenu", {
                    "fg_color": [current_colors['surface_light'], current_colors['surface']],
                    "button_color": [current_colors['primary'], current_colors['primary_hover']],
                    "button_hover_color": [current_colors['primary_hover'], current_colors['primary']],
                    "text_color": [current_colors['text_primary'], current_colors['text_primary']],
                    "dropdown_fg_color": [current_colors['surface'], current_colors['surface_light']],
                    "dropdown_text_color": [current_colors['text_primary'], current_colors['text_primary']],
                    "dropdown_hover_color": [current_colors['primary'], current_colors['primary_hover']]
                })
            ]

            # Apply custom theme
            for widget, color_dict in colors:
                try:
                    ctk.CTkAppearanceModeTracker(widget, color_dict)
                except:
                    pass

        except Exception as e:
            print(f"Warning: Could not apply custom styling: {e}")
            # Fallback to default theme
            pass

    def create_widgets(self):
        """Create all GUI widgets"""
        # Header with title and theme toggle (outside scrollable area)
        self.create_header()
        
        # Create scrollable main container
        self.create_scrollable_container()
        
        # Create scrollable content
        self.create_scrollable_content()

        # Restore settings from config into UI
        self.restore_settings_to_ui()

    def _create_settings_category(self, parent, title, options, ffmpeg_disabled=False, disabled_keys=None):
        """Create a settings category with title and checkboxes"""
        if disabled_keys is None:
            disabled_keys = []

        # Category frame
        category_frame = ctk.CTkFrame(parent, fg_color="transparent")
        category_frame.pack(fill="x", pady=(0, 15))

        # Category title
        title_label = ctk.CTkLabel(
            category_frame,
            text=title,
            font=ctk.CTkFont(size=14, weight="bold", family="Segoe UI"),
            text_color=(self.get_current_colors()['text_primary'], self.get_current_colors()['text_primary'])
        )
        title_label.pack(anchor="w", pady=(0, 10))

        # Checkboxes container
        checkboxes_frame = ctk.CTkFrame(category_frame, fg_color="transparent")
        checkboxes_frame.pack(fill="x", pady=(0, 10))

        # Create checkboxes for this category
        for key, text, default in options:
            var = ctk.BooleanVar(value=default)
            self.metadata_vars[key] = var

            checkbox = ctk.CTkCheckBox(
                checkboxes_frame,
                text=text,
                variable=var,
                font=ctk.CTkFont(size=12, family="Segoe UI"),
                state="disabled" if ffmpeg_disabled and key in disabled_keys else "normal",
                command=lambda k=key, v=var: self._save_metadata_setting(k, v.get()),
                text_color=(self.get_current_colors()['text_primary'], self.get_current_colors()['text_primary']),
                hover_color=(self.get_current_colors()['primary'], self.get_current_colors()['primary_hover'])
            )
            checkbox.pack(anchor="w", pady=2)

        return category_frame

    def restore_settings_to_ui(self):
        """Restore all settings from config into UI elements"""
        try:
            # Restore metadata settings
            for key, var in self.metadata_vars.items():
                saved_value = self.config.get(key, False)
                var.set(saved_value)

            # Restore cookie file setting
            cookie_file = self.config.get("cookie_file", "")
            self.cookie_var.set(cookie_file)

            # Restore theme (already handled in setup_appearance)
            # Restore output directory (handled per-task)

        except Exception as e:
            print(f"Error restoring settings to UI: {e}")

    def create_scrollable_container(self):
        """Create modern scrollable container for the main content"""
        # Main container with modern styling
        self.main_container = ctk.CTkFrame(
            self.root,
            fg_color="transparent"
        )
        self.main_container.pack(fill="both", expand=True, padx=0, pady=(0, 30))

        # Create modern scrollable frame with card-like appearance
        current_colors = self.get_current_colors()
        self.scrollable_frame = ctk.CTkScrollableFrame(
            self.main_container,
            fg_color=(current_colors['surface'], current_colors['surface_light']),
            corner_radius=16,
            border_width=2,
            border_color=(current_colors['border'], current_colors['border'])
        )
        self.scrollable_frame.pack(fill="both", expand=True, padx=30, pady=0)

    def create_scrollable_content(self):
        """Create all content within the scrollable frame with modern card layouts"""
        # Content container with padding
        content_frame = ctk.CTkFrame(self.scrollable_frame, fg_color="transparent")
        content_frame.pack(fill="both", expand=True, padx=25, pady=25)

        # Welcome card at the top
        self.create_welcome_card(content_frame)

        # Metadata section with modern card design
        self.create_metadata_section(content_frame)

        # Cookie file section with modern card design
        self.create_cookie_section(content_frame)

        # Tasks section (multi-task support) with modern card design
        self.create_tasks_section(content_frame)

    def create_welcome_card(self, parent):
        """Create a modern welcome card at the top"""
        current_colors = self.get_current_colors()
        welcome_card = ctk.CTkFrame(
            parent,
            fg_color=(current_colors['card'], current_colors['card']),
            corner_radius=12,
            border_width=1,
            border_color=(current_colors['border'], current_colors['border'])
        )
        welcome_card.pack(fill="x", pady=(0, 25))

        # Welcome content
        welcome_content = ctk.CTkFrame(welcome_card, fg_color="transparent")
        welcome_content.pack(fill="x", padx=25, pady=20)

        # Welcome title
        welcome_title = ctk.CTkLabel(
            welcome_content,
            text="🚀 Ready to Download",
            font=ctk.CTkFont(size=20, weight="bold", family="Segoe UI"),
            text_color=(current_colors['text_primary'], current_colors['text_primary'])
        )
        welcome_title.pack(anchor="w", pady=(0, 8))

        # Welcome description
        welcome_desc = ctk.CTkLabel(
            welcome_content,
            text="Configure your download settings below, then add tasks to start downloading YouTube content.\n"
                 "Supports playlists, individual videos, and various quality options.",
            font=ctk.CTkFont(size=13, family="Segoe UI"),
            text_color=(current_colors['text_secondary'], current_colors['text_secondary']),
            justify="left"
        )
        welcome_desc.pack(anchor="w")

    def restore_tasks_from_config(self):
        """Restore number of tasks and their URLs from config"""
        try:
            self._restoring_tasks = True
            tasks_data = self.config.get("tasks", []) or []

            if tasks_data:
                # New structured storage path
                for item in tasks_data:
                    try:
                        url_value = (item.get("url") or "").strip()
                        fmt_value = (item.get("format") or self.config.get("default_format", "audio")).strip()
                        output_value = item.get("output") or self.config.get("output_directory", self.config.get_default_output_directory())

                        # Extract video/playlist info
                        video_name = item.get("video_name", "")
                        playlist_name = item.get("playlist_name", "")
                        is_playlist = item.get("is_playlist", False)

                        task = self.add_task(url=url_value)

                        # Set video/playlist info
                        if hasattr(task, 'video_name'):
                            task.video_name = video_name
                        if hasattr(task, 'playlist_name'):
                            task.playlist_name = playlist_name
                        if hasattr(task, 'is_playlist'):
                            task.is_playlist = is_playlist

                        # Update subtitle with video/playlist name (skip URL analysis during restoration)
                        display_name = playlist_name if is_playlist and playlist_name else video_name
                        if display_name:
                            task.update_subtitle(display_name)
                        # Skip URL analysis during restoration to avoid crashes
                        # elif url_value:
                        #     if hasattr(task, 'update_video_info'):
                        #         task.update_video_info(url_value, force=True)

                        try:
                            task.format_var.set(fmt_value if fmt_value in ("audio", "video") else self.config.get("default_format", "audio"))
                        except Exception:
                            pass
                        try:
                            if output_value:
                                task.output_var.set(output_value)
                        except Exception:
                            pass
                    except Exception as e:
                        # Log error but continue with other tasks
                        print(f"Error restoring task: {e}")
                        # Fallback: add an empty task if malformed
                        try:
                            self.add_task(url="")
                        except Exception:
                            pass
            else:
                # Backwards compatibility with older settings
                urls = self.config.get("task_urls", []) or []
                count = self.config.get("tasks_count", 1)
                try:
                    count = int(count)
                except Exception:
                    count = 1
                if count < 1:
                    count = 1

                for i in range(count):
                    url_value = urls[i] if i < len(urls) else ""
                    try:
                        self.add_task(url=url_value)
                    except Exception as e:
                        print(f"Error adding task {i}: {e}")
                        try:
                            self.add_task(url="")
                        except Exception:
                            pass
        except Exception as e:
            # Critical error in restoration - log and continue with empty task
            print(f"Critical error during task restoration: {e}")
            try:
                self.add_task(url="")
            except Exception:
                pass
        finally:
            self._restoring_tasks = False

            # Apply deferred operations after all tasks are created for better performance
            if tasks_data:
                try:
                    # Batch apply colors and bindings to all tasks
                    for task in self.tasks:
                        try:
                            task.finalize_gui_setup()  # Finalize GUI setup first
                            task.update_colors()
                            self._attach_task_bindings(task)
                        except Exception as e:
                            print(f"Error applying deferred operations to task: {e}")
                except Exception as e:
                    print(f"Error during deferred task operations: {e}")

            # Don't persist immediately after restore to avoid overwriting restored data

    def _attach_task_bindings(self, task):
        """Attach listeners to task inputs for persistence"""
        try:
            # Create a closure that captures the task reference
            def make_url_callback(t):
                return lambda *args: self._on_task_changed(t, "url")

            def make_output_callback(t):
                return lambda *args: self._on_task_changed(t, "output")

            def make_format_callback(t):
                return lambda *args: self._on_task_changed(t, "format")

            task.url_var.trace_add("write", make_url_callback(task))
            task.output_var.trace_add("write", make_output_callback(task))
            task.format_var.trace_add("write", make_format_callback(task))
        except Exception:
            pass

    def _on_task_changed(self, task, change_type):
        """Handle changes to task variables"""
        if getattr(self, '_restoring_tasks', False):
            return

        # Update video info if URL changed
        if change_type == "url":
            url = task.get_url()
            if url and hasattr(task, 'update_video_info'):
                task.update_video_info(url, force=True)

        # Schedule persistence for all changes
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
            # Build structured tasks array
            tasks_array = []
            for t in getattr(self, 'tasks', []):
                try:
                    tasks_array.append({
                        "url": t.get_url(),
                        "format": t.format_var.get() if hasattr(t, 'format_var') else self.config.get("default_format", "audio"),
                        "output": t.output_var.get() if hasattr(t, 'output_var') else self.config.get("output_directory", self.config.get_default_output_directory()),
                        "video_name": getattr(t, 'video_name', ""),
                        "playlist_name": getattr(t, 'playlist_name', ""),
                        "is_playlist": getattr(t, 'is_playlist', False)
                    })
                except Exception:
                    tasks_array.append({
                        "url": "",
                        "format": self.config.get("default_format", "audio"),
                        "output": self.config.get("output_directory", self.config.get_default_output_directory()),
                        "video_name": "",
                        "playlist_name": "",
                        "is_playlist": False
                    })

            # Store new structure
            self.config.settings["tasks"] = tasks_array
            # Maintain backwards-compatible fields
            self.config.settings["task_urls"] = [t.get("url", "") for t in tasks_array]
            self.config.settings["tasks_count"] = len(tasks_array)
            self.config.save_settings()
        except Exception:
            pass

    def create_header(self):
        """Create modern header with animated title and controls"""
        # Main header frame with gradient-like background effect
        current_colors = self.get_current_colors()
        header_frame = ctk.CTkFrame(
            self.root,
            fg_color=(current_colors['surface'], current_colors['surface_light']),
            corner_radius=0
        )
        header_frame.pack(fill="x", padx=0, pady=(0, 20))

        # Create inner header with padding
        inner_header = ctk.CTkFrame(
            header_frame,
            fg_color="transparent"
        )
        inner_header.pack(fill="x", padx=30, pady=25)

        # Left section: Logo and title with animations
        left_section = ctk.CTkFrame(inner_header, fg_color="transparent")
        left_section.pack(side="left", fill="y")

        # Animated logo/title area
        self.title_frame = ctk.CTkFrame(
            left_section,
            fg_color="transparent"
        )
        self.title_frame.pack(side="left")

        # Logo icon (animated)
        self.logo_label = ctk.CTkLabel(
            self.title_frame,
            text="🎬",
            font=ctk.CTkFont(size=32, weight="bold")
        )
        self.logo_label.pack(side="left", padx=(0, 10))

        # Main title with modern typography
        self.title_label = ctk.CTkLabel(
            self.title_frame,
            text="YouTube Media Downloader",
            font=ctk.CTkFont(size=28, weight="bold", family="Segoe UI"),
            text_color=(current_colors['text_primary'], current_colors['text_primary'])
        )
        self.title_label.pack(side="left")

        # Subtitle
        self.subtitle_label = ctk.CTkLabel(
            self.title_frame,
            text="Professional media extraction tool",
            font=ctk.CTkFont(size=12, family="Segoe UI"),
            text_color=(current_colors['text_secondary'], current_colors['text_secondary'])
        )
        self.subtitle_label.pack(side="left", padx=(15, 0))

        # Right section: Action buttons
        right_section = ctk.CTkFrame(inner_header, fg_color="transparent")
        right_section.pack(side="right", fill="y")

        # Button container with modern styling
        button_container = ctk.CTkFrame(
            right_section,
            fg_color="transparent"
        )
        button_container.pack(side="right")

        # Modern theme toggle with hover effects
        self.theme_button = ctk.CTkButton(
            button_container,
            text="🌙",
            width=50,
            height=45,
            command=self.toggle_theme,
            fg_color=(current_colors['surface_light'], current_colors['surface']),
            hover_color=(current_colors['primary'], current_colors['primary_hover']),
            text_color=(current_colors['text_primary'], current_colors['text_primary']),
            font=ctk.CTkFont(size=20),
            corner_radius=12,
            border_width=2,
            border_color=(current_colors['border'], current_colors['border'])
        )
        self.theme_button.pack(side="left", padx=(0, 10))

        # Import button with modern styling
        self.import_button = ctk.CTkButton(
            button_container,
            text="📥 Import Files",
            width=140,
            height=45,
            command=self.show_import_dialog,
            fg_color=(current_colors['secondary'], current_colors['secondary']),
            hover_color=(current_colors['secondary'], current_colors['secondary']),
            text_color=(current_colors['text_primary'], current_colors['text_primary']),
            font=ctk.CTkFont(size=14, weight="bold", family="Segoe UI"),
            corner_radius=12
        )
        self.import_button.pack(side="left")

        # Add hover animations
        self._setup_hover_animations()

    def _setup_hover_animations(self):
        """Setup smooth hover animations for interactive elements"""
        current_colors = self.get_current_colors()

        # Theme button hover effect
        def theme_hover_in(e):
            current_colors = self.get_current_colors()
            self.theme_button.configure(
                fg_color=(current_colors['primary'], current_colors['primary_hover']),
                border_color=(current_colors['primary'], current_colors['primary_hover'])
            )

        def theme_hover_out(e):
            current_colors = self.get_current_colors()
            self.theme_button.configure(
                fg_color=(current_colors['surface_light'], current_colors['surface']),
                border_color=(current_colors['border'], current_colors['border'])
            )

        self.theme_button.bind("<Enter>", theme_hover_in)
        self.theme_button.bind("<Leave>", theme_hover_out)

        # Import button hover effect (already styled)
        def import_hover_in(e):
            current_colors = self.get_current_colors()
            self.import_button.configure(
                fg_color=(current_colors['accent'], current_colors['accent'])
            )

        def import_hover_out(e):
            current_colors = self.get_current_colors()
            self.import_button.configure(
                fg_color=(current_colors['secondary'], current_colors['secondary'])
            )

        self.import_button.bind("<Enter>", import_hover_in)
        self.import_button.bind("<Leave>", import_hover_out)

    def show_import_dialog(self):
        """Show a modal dialog to import files from one directory to another."""
        try:
            # Create modal window
            dialog = ctk.CTkToplevel(self.root)
        except Exception:
            # Fallback to standard Toplevel if CTkToplevel not available
            import tkinter as tk
            dialog = tk.Toplevel(self.root)
        dialog.title("Import Files")
        try:
            dialog.grab_set()
        except Exception:
            pass

        # Variables with defaults from config
        last_in = self.config.get("last_import_input_dir", "") or ""
        last_out = self.config.get("last_import_output_dir", self.config.get("output_directory", self.config.get_default_output_directory())) or ""
        override_default = bool(self.config.get("import_override_existing", False))

        input_var = ctk.StringVar(value=last_in)
        output_var = ctk.StringVar(value=last_out)
        override_var = ctk.BooleanVar(value=override_default)

        # Layout frames
        container = ctk.CTkFrame(dialog)
        container.pack(fill="both", expand=True, padx=20, pady=20)

        # Input directory row
        in_row = ctk.CTkFrame(container, fg_color="transparent")
        in_row.pack(fill="x", pady=(0, 10))
        in_label = ctk.CTkLabel(in_row, text="Input directory:")
        in_label.pack(side="left", padx=(0, 8))
        in_entry = ctk.CTkEntry(in_row, textvariable=input_var, height=32)
        in_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        in_browse = ctk.CTkButton(in_row, text="Browse", width=80, height=32, command=lambda: self._browse_dir_into_var(input_var, title="Select Input Directory"))
        in_browse.pack(side="left")

        # Output directory row
        out_row = ctk.CTkFrame(container, fg_color="transparent")
        out_row.pack(fill="x", pady=(0, 10))
        out_label = ctk.CTkLabel(out_row, text="Output directory:")
        out_label.pack(side="left", padx=(0, 8))
        out_entry = ctk.CTkEntry(out_row, textvariable=output_var, height=32)
        out_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        out_browse = ctk.CTkButton(out_row, text="Browse", width=80, height=32, command=lambda: self._browse_dir_into_var(output_var, title="Select Output Directory"))
        out_browse.pack(side="left")

        # Options row
        options_row = ctk.CTkFrame(container, fg_color="transparent")
        options_row.pack(fill="x", pady=(0, 10))
        override_chk = ctk.CTkCheckBox(options_row, text="Override existing", variable=override_var)
        override_chk.pack(anchor="w")

        # Duplicate detection options (mutually exclusive)
        dup_row = ctk.CTkFrame(container, fg_color="transparent")
        dup_row.pack(fill="x", pady=(0, 10))

        # Filename similarity option
        name_sim_var = ctk.BooleanVar(value=False)
        name_sim_chk = ctk.CTkCheckBox(dup_row, text="Skip if filename similarity >= (%)", variable=name_sim_var)
        name_sim_chk.pack(side="left")
        name_thresh_var = ctk.StringVar(value="70")
        name_thresh_entry = ctk.CTkEntry(dup_row, textvariable=name_thresh_var, width=60, height=28)
        name_thresh_entry.pack(side="left", padx=(8, 0))

        # Content similarity option
        content_sim_var = ctk.BooleanVar(value=False)
        content_sim_chk = ctk.CTkCheckBox(dup_row, text="Skip if first Xs content matches", variable=content_sim_var)
        content_sim_chk.pack(side="left", padx=(16, 0))
        content_secs_var = ctk.StringVar(value="10")
        content_secs_entry = ctk.CTkEntry(dup_row, textvariable=content_secs_var, width=60, height=28)
        content_secs_entry.pack(side="left", padx=(8, 0))

        # Initialize entry states (disabled until checked)
        name_thresh_entry.configure(state="disabled")
        content_secs_entry.configure(state="disabled")

        def _enforce_exclusive(source: str):
            try:
                if source == 'name' and name_sim_var.get():
                    # Disable content option
                    content_sim_var.set(False)
                    content_secs_entry.configure(state="disabled")
                    # Enable name entry
                    name_thresh_entry.configure(state="normal")
                elif source == 'content' and content_sim_var.get():
                    # Disable name option
                    name_sim_var.set(False)
                    name_thresh_entry.configure(state="disabled")
                    # Enable content entry
                    content_secs_entry.configure(state="normal")
                else:
                    # If unchecked, disable its entry
                    if source == 'name':
                        name_thresh_entry.configure(state="disabled")
                    else:
                        content_secs_entry.configure(state="disabled")
            except Exception:
                pass

        name_sim_chk.configure(command=lambda: _enforce_exclusive('name'))
        content_sim_chk.configure(command=lambda: _enforce_exclusive('content'))

        # Progress UI
        progress_row = ctk.CTkFrame(container, fg_color="transparent")
        progress_row.pack(fill="x", pady=(10, 10))
        prog = ctk.CTkProgressBar(progress_row)
        prog.pack(fill="x")
        prog.set(0)
        prog_label = ctk.CTkLabel(container, text="")
        prog_label.pack(anchor="w", pady=(6, 0))

        log_box = ctk.CTkTextbox(container, height=140, font=ctk.CTkFont(size=11, family="Consolas"))
        log_box.pack(fill="both", expand=True, pady=(8, 8))

        # Buttons row
        btn_row = ctk.CTkFrame(container, fg_color="transparent")
        btn_row.pack(fill="x", pady=(4, 0))
        # Shared state for undo
        import_state = {"actions": [], "backup_root": None}

        start_btn = ctk.CTkButton(btn_row, text="Start Import", height=34,
                                  command=lambda: self._start_import_worker(
                                      dialog,
                                      input_var.get().strip(),
                                      output_var.get().strip(),
                                      bool(override_var.get()),
                                      bool(name_sim_var.get()),
                                      name_thresh_var.get().strip(),
                                      bool(content_sim_var.get()),
                                      content_secs_var.get().strip(),
                                      prog, prog_label, log_box, start_btn, undo_btn, import_state
                                  ))
        start_btn.pack(side="left")
        undo_btn = ctk.CTkButton(btn_row, text="Undo Last Import", height=34,
                                 fg_color=("orange", "#b87333"), hover_color=("#e69500", "#996633"),
                                 state="disabled",
                                 command=lambda: self._start_undo_worker(dialog, prog, prog_label, log_box, undo_btn, start_btn, import_state))
        undo_btn.pack(side="left", padx=(8, 0))
        close_btn = ctk.CTkButton(btn_row, text="Close", height=34, fg_color=("gray70", "gray30"), hover_color=("gray60", "gray40"),
                                  command=lambda: self._close_dialog_safe(dialog))
        close_btn.pack(side="right")

    def _close_dialog_safe(self, dialog):
        try:
            dialog.destroy()
        except Exception:
            pass

    def _browse_dir_into_var(self, var, title="Select Directory"):
        try:
            directory = filedialog.askdirectory(title=title, initialdir=var.get() or self.config.get("output_directory", self.config.get_default_output_directory()))
            if directory:
                var.set(directory)
        except Exception:
            pass

    def _start_import_worker(self, dialog, input_dir, output_dir, override_existing,
                             use_name_similarity, name_threshold_str,
                             use_content_similarity, content_seconds_str,
                             prog, prog_label, log_box, start_btn, undo_btn, import_state):
        # Validate
        if not input_dir or not os.path.isdir(input_dir):
            try:
                messagebox.showerror("Import", "Please select a valid input directory")
            except Exception:
                pass
            return
        if not output_dir:
            try:
                messagebox.showerror("Import", "Please select an output directory")
            except Exception:
                pass
            return
        if os.path.abspath(input_dir) == os.path.abspath(output_dir):
            try:
                messagebox.showerror("Import", "Input and output directories must be different")
            except Exception:
                pass
            return

        # Persist last used settings
        try:
            self.config.set("last_import_input_dir", input_dir)
            self.config.set("last_import_output_dir", output_dir)
            self.config.set("import_override_existing", bool(override_existing))
        except Exception:
            pass

        # Validate mutual exclusivity
        if use_name_similarity and use_content_similarity:
            try:
                messagebox.showerror("Import", "Only one similarity option can be active at a time.")
            except Exception:
                pass
            return

        # Parse thresholds
        name_threshold = None
        content_seconds = None
        try:
            if use_name_similarity:
                name_threshold = float(name_threshold_str)
                if name_threshold < 0 or name_threshold > 100:
                    raise ValueError()
        except Exception:
            try:
                messagebox.showerror("Import", "Please enter a valid filename similarity percentage (0-100).")
            except Exception:
                pass
            return

        try:
            if use_content_similarity:
                content_seconds = float(content_seconds_str)
                if content_seconds <= 0 or content_seconds > 3600:
                    raise ValueError()
        except Exception:
            try:
                messagebox.showerror("Import", "Please enter a valid number of seconds (1-3600) for content match.")
            except Exception:
                pass
            return

        # Ensure output dir exists
        try:
            os.makedirs(output_dir, exist_ok=True)
        except Exception as e:
            try:
                messagebox.showerror("Import", f"Cannot create output directory: {e}")
            except Exception:
                pass
            return

        # Reset undo state and disable buttons during import
        try:
            start_btn.configure(state="disabled")
            undo_btn.configure(state="disabled")
        except Exception:
            pass

        def log(msg):
            try:
                log_box.insert("end", f"{msg}\n")
                log_box.see("end")
            except Exception:
                pass

        def set_status(text):
            try:
                prog_label.configure(text=text)
            except Exception:
                pass

        def set_progress(value):
            try:
                prog.set(value)
            except Exception:
                pass

        def _filenames_similar(src_path, dst_path, threshold_percent):
            try:
                src_name = os.path.splitext(os.path.basename(src_path))[0]
                dst_name = os.path.splitext(os.path.basename(dst_path))[0]
                ratio = difflib.SequenceMatcher(None, src_name.lower(), dst_name.lower()).ratio() * 100.0
                return ratio >= threshold_percent, ratio
            except Exception:
                return False, 0.0

        def _content_similar(src_path, dst_path, seconds):
            try:
                # Compare first N bytes proportional to seconds as a heuristic when duration unknown.
                # Read a fixed byte window per second (e.g., 256KB/s) capped at 8MB
                bytes_per_sec = 262144  # 256 KB
                max_bytes = int(min(8 * 1024 * 1024, max(1, seconds) * bytes_per_sec))
                size_src = os.path.getsize(src_path) if os.path.exists(src_path) else 0
                size_dst = os.path.getsize(dst_path) if os.path.exists(dst_path) else 0
                if size_src == 0 or size_dst == 0:
                    return False
                to_read = min(max_bytes, size_src, size_dst)
                with open(src_path, 'rb') as f1, open(dst_path, 'rb') as f2:
                    chunk1 = f1.read(to_read)
                    chunk2 = f2.read(to_read)
                if not chunk1 or not chunk2:
                    return False
                # Use a quick hash-based check
                import hashlib
                h1 = hashlib.blake2s(chunk1, digest_size=16).digest()
                h2 = hashlib.blake2s(chunk2, digest_size=16).digest()
                return h1 == h2
            except Exception:
                return False

        def worker():
            try:
                # Collect files to copy (recursive)
                files = []
                for root, _, filenames in os.walk(input_dir):
                    for name in filenames:
                        src_path = os.path.join(root, name)
                        rel = os.path.relpath(src_path, input_dir)
                        dest_path = os.path.join(output_dir, rel)
                        files.append((src_path, dest_path))

                total = len(files)
                copied = 0
                skipped = 0
                errors = 0

                if total == 0:
                    set_status("No files found in input directory")
                    return

                set_status(f"Preparing to import {total} file(s)...")

                # Prepare backup directory for overwritten files
                backup_root = None
                import_state["actions"] = []
                import_state["backup_root"] = None

                for idx, (src, dst) in enumerate(files, start=1):
                    try:
                        # Make sure destination directory exists
                        os.makedirs(os.path.dirname(dst), exist_ok=True)

                        if os.path.exists(dst):
                            # Similarity-based duplicate checks
                            if use_name_similarity and name_threshold is not None:
                                similar, ratio = _filenames_similar(src, dst, name_threshold)
                                if similar:
                                    skipped += 1
                                    log(f"Skipped by name similarity ({ratio:.1f}% >= {name_threshold:.1f}%): {os.path.relpath(dst, output_dir)}")
                                    continue
                            if use_content_similarity and content_seconds is not None:
                                try:
                                    if _content_similar(src, dst, content_seconds):
                                        skipped += 1
                                        log(f"Skipped by content similarity (first {int(content_seconds)}s match): {os.path.relpath(dst, output_dir)}")
                                        continue
                                except Exception as e:
                                    log(f"Content similarity check error, proceeding: {e}")
                            if override_existing:
                                import shutil
                                # Overwrite without creating backups per user preference
                                shutil.copy2(src, dst)
                                # Track overwrite (no backup available to restore)
                                import_state["actions"].append(("overwritten", dst, None))
                                copied += 1
                                log(f"Overwritten: {os.path.relpath(dst, output_dir)}")
                            else:
                                # Prioritize existing output file; skip duplicate
                                skipped += 1
                                log(f"Skipped (exists): {os.path.relpath(dst, output_dir)}")
                        else:
                            import shutil
                            shutil.copy2(src, dst)
                            # Track creation for undo
                            import_state["actions"].append(("created", dst))
                            copied += 1
                            log(f"Copied: {os.path.relpath(dst, output_dir)}")
                    except Exception as e:
                        errors += 1
                        log(f"Error copying {src} -> {dst}: {e}")

                    # Update progress
                    try:
                        set_progress(idx / total)
                        if idx % 10 == 0 or idx == total:
                            set_status(f"Imported {copied}, skipped {skipped}, errors {errors} ({idx}/{total})")
                    except Exception:
                        pass

                # Final status
                set_status(f"Done. Imported {copied}, skipped {skipped}, errors {errors}.")
                try:
                    messagebox.showinfo("Import", f"Completed. Imported {copied}, skipped {skipped}, errors {errors}.")
                except Exception:
                    pass
            finally:
                try:
                    start_btn.configure(state="normal")
                    # Enable undo if there were any actions to revert
                    if import_state.get("actions"):
                        undo_btn.configure(state="normal")
                    else:
                        undo_btn.configure(state="disabled")
                except Exception:
                    pass

        # Run worker in background
        try:
            th = threading.Thread(target=worker, daemon=True)
            th.start()
        except Exception as e:
            try:
                messagebox.showerror("Import", f"Failed to start import: {e}")
            except Exception:
                pass

    def _start_undo_worker(self, dialog, prog, prog_label, log_box, undo_btn, start_btn, import_state):
        actions = list(import_state.get("actions") or [])
        backup_root = import_state.get("backup_root")
        if not actions:
            try:
                messagebox.showinfo("Undo", "Nothing to undo.")
            except Exception:
                pass
            return

        # Disable buttons during undo
        try:
            undo_btn.configure(state="disabled")
            start_btn.configure(state="disabled")
        except Exception:
            pass

        def log(msg):
            try:
                log_box.insert("end", f"{msg}\n")
                log_box.see("end")
            except Exception:
                pass

        def set_status(text):
            try:
                prog_label.configure(text=text)
            except Exception:
                pass

        def set_progress(value):
            try:
                prog.set(value)
            except Exception:
                pass

        def safe_rmdir_empty_dirs(path, stop_at):
            try:
                path = os.path.abspath(path)
                stop_at = os.path.abspath(stop_at)
                while path.startswith(stop_at) and path != stop_at:
                    try:
                        os.rmdir(path)
                    except OSError:
                        break
                    path = os.path.dirname(path)
            except Exception:
                pass

        def worker():
            try:
                total = len(actions)
                undone = 0
                errors = 0
                set_status(f"Undoing last import ({total} action(s))...")

                # Undo in reverse order
                for idx, action in enumerate(reversed(actions), start=1):
                    try:
                        if not action:
                            continue
                        if action[0] == "created":
                            _, dst = action
                            if os.path.isfile(dst):
                                try:
                                    os.remove(dst)
                                    log(f"Removed created file: {dst}")
                                except Exception as e:
                                    errors += 1
                                    log(f"Error removing {dst}: {e}")
                                # Attempt to clean up empty directories up to dialog's output dir if known
                                safe_rmdir_empty_dirs(os.path.dirname(dst), stop_at=os.path.dirname(dst))
                        elif action[0] == "overwritten":
                            _, dst, backup_path = action
                            try:
                                # Without backups, we cannot restore originals; just inform the user
                                log(f"Cannot restore overwritten file (no backup): {dst}")
                            except Exception as e:
                                errors += 1
                                log(f"Error handling overwritten entry {dst}: {e}")
                        undone += 1
                    finally:
                        # Progress update
                        try:
                            set_progress(idx / total)
                            if idx % 10 == 0 or idx == total:
                                set_status(f"Undo progress: {undone}/{total}, errors {errors}")
                        except Exception:
                            pass

                # No backup root management needed if no backups created

                set_status(f"Undo completed. Undone {undone} action(s), errors {errors}.")
                # Clear state
                import_state["actions"] = []
                import_state["backup_root"] = None
                try:
                    messagebox.showinfo("Undo", f"Undo completed. Undone {undone} action(s), errors {errors}.")
                except Exception:
                    pass
            finally:
                try:
                    start_btn.configure(state="normal")
                    undo_btn.configure(state="disabled")
                except Exception:
                    pass

        try:
            th = threading.Thread(target=worker, daemon=True)
            th.start()
        except Exception as e:
            try:
                messagebox.showerror("Undo", f"Failed to start undo: {e}")
            except Exception:
                pass

    def create_tasks_section(self, parent):
        """Create the tasks management section with modern card design"""
        current_colors = self.get_current_colors()
        # Tasks card container
        tasks_card = ctk.CTkFrame(
            parent,
            fg_color=(current_colors['card'], current_colors['card']),
            corner_radius=12,
            border_width=1,
            border_color=(current_colors['border'], current_colors['border'])
        )
        tasks_card.pack(fill="both", expand=True, pady=(0, 0))

        # Tasks header
        tasks_header = ctk.CTkFrame(tasks_card, fg_color="transparent")
        tasks_header.pack(fill="x", padx=25, pady=(20, 15))

        # Tasks title with icon
        tasks_title = ctk.CTkLabel(
            tasks_header,
            text="📋 Download Tasks",
            font=ctk.CTkFont(size=18, weight="bold", family="Segoe UI"),
            text_color=(current_colors['text_primary'], current_colors['text_primary'])
        )
        tasks_title.pack(side="left")

        # Tasks description
        tasks_desc = ctk.CTkLabel(
            tasks_header,
            text="Add multiple download tasks and manage them independently",
            font=ctk.CTkFont(size=12, family="Segoe UI"),
            text_color=(current_colors['text_secondary'], current_colors['text_secondary'])
        )
        tasks_desc.pack(side="left", padx=(15, 0))

        # Controls section
        controls_section = ctk.CTkFrame(tasks_header, fg_color="transparent")
        controls_section.pack(side="right")

        # Modern control buttons
        add_btn = ctk.CTkButton(
            controls_section,
            text="➕ Add Task",
            width=120,
            height=38,
            command=self.add_task,
            font=ctk.CTkFont(size=12, family="Segoe UI"),
            fg_color=(current_colors['primary'], current_colors['primary_hover']),
            hover_color=(current_colors['primary_hover'], current_colors['primary']),
            corner_radius=8
        )
        add_btn.pack(side="left", padx=(0, 8))

        run_all_btn = ctk.CTkButton(
            controls_section,
            text="▶ Run All",
            width=110,
            height=38,
            command=self.run_all_tasks,
            font=ctk.CTkFont(size=12, family="Segoe UI"),
            fg_color=(current_colors['secondary'], current_colors['secondary']),
            hover_color=(current_colors['secondary'], current_colors['secondary']),
            corner_radius=8
        )
        run_all_btn.pack(side="left", padx=(0, 8))

        scram_btn = ctk.CTkButton(
            controls_section,
            text="🛑 Stop All",
            width=110,
            height=38,
            command=self.scram_all_tasks,
            font=ctk.CTkFont(size=12, family="Segoe UI"),
            fg_color=(current_colors['danger'], current_colors['danger']),
            hover_color=(current_colors['danger'], current_colors['danger']),
            corner_radius=8
        )
        scram_btn.pack(side="left")

        # Container for task items (stacked vertically) with modern styling
        self.tasks_list_frame = ctk.CTkFrame(
            tasks_card,
            fg_color="transparent"
        )
        self.tasks_list_frame.pack(fill="both", expand=True, padx=25, pady=(15, 25))

        # Initial tasks are restored from config in __init__

    # Global Download Options section removed; per-task format controls are used instead.

    def create_metadata_section(self, parent):
        """Create metadata options section with modern card design"""
        current_colors = self.get_current_colors()
        # Metadata card container
        metadata_card = ctk.CTkFrame(
            parent,
            fg_color=(current_colors['card'], current_colors['card']),
            corner_radius=12,
            border_width=1,
            border_color=(current_colors['border'], current_colors['border'])
        )
        metadata_card.pack(fill="x", pady=(0, 25))

        # Metadata header
        metadata_header = ctk.CTkFrame(metadata_card, fg_color="transparent")
        metadata_header.pack(fill="x", padx=25, pady=(20, 15))

        # Metadata title with icon
        metadata_title = ctk.CTkLabel(
            metadata_header,
            text="⚙️ Download Settings",
            font=ctk.CTkFont(size=18, weight="bold", family="Segoe UI"),
            text_color=(current_colors['text_primary'], current_colors['text_primary'])
        )
        metadata_title.pack(anchor="w")

        # Metadata description
        metadata_desc = ctk.CTkLabel(
            metadata_header,
            text="Configure how your downloads are processed and saved",
            font=ctk.CTkFont(size=12, family="Segoe UI"),
            text_color=(current_colors['text_secondary'], current_colors['text_secondary'])
        )
        metadata_desc.pack(anchor="w", pady=(2, 0))
        
        # Initialize metadata variables
        self.metadata_vars = {}

        # Organize settings into logical categories using columns
        ffmpeg_disabled = not self.downloader.ffmpeg_available

        # Create main categories container with columns
        categories_container = ctk.CTkFrame(metadata_card, fg_color="transparent")
        categories_container.pack(fill="x", padx=25, pady=(0, 15))

        # Left column
        left_column = ctk.CTkFrame(categories_container, fg_color="transparent")
        left_column.pack(side="left", fill="both", expand=True, padx=(0, 15))

        # Right column
        right_column = ctk.CTkFrame(categories_container, fg_color="transparent")
        right_column.pack(side="left", fill="both", expand=True, padx=(15, 0))

        # Category 1: Metadata Embedding (Left Column)
        self._create_settings_category(
            left_column, "📝 Metadata Embedding",
            [
                ("embed_metadata", "Embed Metadata", self._load_metadata_setting("embed_metadata", True and not ffmpeg_disabled)),
                ("embed_thumbnail", "Embed Thumbnail", self._load_metadata_setting("embed_thumbnail", True and not ffmpeg_disabled)),
                ("embed_chapters", "Embed Chapters", self._load_metadata_setting("embed_chapters", True and not ffmpeg_disabled)),
            ],
            ffmpeg_disabled, ["embed_metadata", "embed_thumbnail", "embed_chapters"]
        )

        # Category 2: File Options (Left Column)
        self._create_settings_category(
            left_column, "💾 File Options",
            [
                ("write_thumbnail", "Save Thumbnail", self._load_metadata_setting("write_thumbnail", True)),
                ("include_author", "Include Author", self._load_metadata_setting("include_author", False)),
                ("write_description", "Save Description", self._load_metadata_setting("write_description", False)),
                ("write_info_json", "Save Info JSON", self._load_metadata_setting("write_info_json", False)),
            ]
        )

        # Category 3: Playlist Options (Right Column)
        self._create_settings_category(
            right_column, "📀 Playlist Options",
            [
                ("playlist_album_override", "Use Playlist as Album", self._load_metadata_setting("playlist_album_override", False)),
                ("create_m3u", "Create M3U", self._load_metadata_setting("create_m3u", False)),
                ("m3u_to_parent", "Place M3U in parent folder", self._load_metadata_setting("m3u_to_parent", False)),
            ]
        )

        # Category 4: Download Options (Right Column)
        self._create_settings_category(
            right_column, "📥 Download Options",
            [
                ("embed_subs", "Download Subtitles", self._load_metadata_setting("embed_subs", False)),
                ("force_playlist_redownload", "Force Re-download All", self._load_metadata_setting("force_playlist_redownload", False)),
            ]
        )

        # Performance note with modern styling
        perf_frame = ctk.CTkFrame(metadata_card, fg_color="transparent")
        perf_frame.pack(fill="x", padx=25, pady=(15, 15))

        perf_note = ctk.CTkLabel(
            perf_frame,
            text="🚀 Optimized for maximum speed using all available CPU cores",
            font=ctk.CTkFont(size=11, family="Segoe UI"),
            text_color=(current_colors['text_secondary'], current_colors['text_secondary']),
            justify="left"
        )
        perf_note.pack(anchor="w")

        # Add button for updating existing files with modern styling
        update_existing_btn = ctk.CTkButton(
            perf_frame,
            text="🔄 Update Existing Files Album",
            font=ctk.CTkFont(size=12, family="Segoe UI"),
            height=36,
            command=self.update_existing_files_album,
            fg_color=(current_colors['accent'], current_colors['accent']),
            hover_color=(current_colors['warning'], current_colors['warning']),
            text_color=(current_colors['text_primary'], current_colors['text_primary']),
            corner_radius=8
        )
        update_existing_btn.pack(anchor="w", pady=(10, 0))

        # Info text about the update existing files feature with modern styling
        update_info = ctk.CTkLabel(
            metadata_card,
            text="💡 Use this to update album metadata on already downloaded playlist files",
            font=ctk.CTkFont(size=11, family="Segoe UI"),
            text_color=(current_colors['text_secondary'], current_colors['text_secondary']),
            justify="left"
        )
        update_info.pack(anchor="w", padx=25, pady=(5, 20))

    def update_existing_files_album(self):
        """Update album metadata for existing playlist files"""
        from tkinter import simpledialog, messagebox

        # Check FFmpeg availability
        if not self.downloader.ffmpeg_available:
            messagebox.showerror("Error", "FFmpeg is required for metadata updates but is not available.\n\nPlease install FFmpeg and ensure it's on your PATH.")
            return

        # Ask for output directory
        output_dir = filedialog.askdirectory(
            title="Select Directory with Playlist Files",
            initialdir=self.config.get("output_directory", self.config.get_default_output_directory())
        )
        if not output_dir:
            return

        # Ask for playlist name
        playlist_name = simpledialog.askstring(
            "Playlist Name",
            "Enter the playlist name to use as album metadata:",
            parent=self.root
        )
        if not playlist_name or not playlist_name.strip():
            return

        playlist_name = playlist_name.strip()

        # Ask for format type
        from tkinter import messagebox
        format_choice = messagebox.askquestion(
            "File Format",
            "Are the files audio files? (Select 'No' for video files)",
            icon='question'
        )
        is_audio = format_choice == 'yes'

        # Confirm operation
        file_types = "audio" if is_audio else "video"
        confirm = messagebox.askyesno(
            "Confirm Update",
            f"This will update the album metadata of all {file_types} files in:\n{output_dir}\n\n"
            f"Album name: '{playlist_name}'\n\n"
            f"Continue?",
            icon='warning'
        )

        if not confirm:
            return

        # Disable button during operation
        # Note: We can't easily access the button reference here, so we'll proceed

        def update_worker():
            try:
                self.downloader.update_existing_playlist_files_album(
                    output_path=output_dir,
                    playlist_title=playlist_name,
                    is_audio=is_audio
                )
                messagebox.showinfo("Success", "Album metadata update completed!\n\nCheck the logs for details.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update album metadata:\n\n{str(e)}")

        # Run in background thread
        import threading
        thread = threading.Thread(target=update_worker, daemon=True)
        thread.start()

    def create_cookie_section(self, parent):
        """Create cookie file section with modern card design"""
        current_colors = self.get_current_colors()
        # Cookie card container
        cookie_card = ctk.CTkFrame(
            parent,
            fg_color=(current_colors['card'], current_colors['card']),
            corner_radius=12,
            border_width=1,
            border_color=(current_colors['border'], current_colors['border'])
        )
        cookie_card.pack(fill="x", pady=(0, 25))

        # Cookie header
        cookie_header = ctk.CTkFrame(cookie_card, fg_color="transparent")
        cookie_header.pack(fill="x", padx=25, pady=(20, 15))

        # Cookie title with icon
        cookie_title = ctk.CTkLabel(
            cookie_header,
            text="🍪 Browser Authentication",
            font=ctk.CTkFont(size=18, weight="bold", family="Segoe UI"),
            text_color=(current_colors['text_primary'], current_colors['text_primary'])
        )
        cookie_title.pack(anchor="w")

        # Cookie description
        cookie_desc = ctk.CTkLabel(
            cookie_header,
            text="Optional: Use browser cookies for accessing restricted content",
            font=ctk.CTkFont(size=12, family="Segoe UI"),
            text_color=(current_colors['text_secondary'], current_colors['text_secondary'])
        )
        cookie_desc.pack(anchor="w", pady=(2, 0))

        # Cookie file input row with modern styling
        cookie_row = ctk.CTkFrame(cookie_card, fg_color="transparent")
        cookie_row.pack(fill="x", padx=25, pady=(0, 15))

        self.cookie_var = ctk.StringVar(value=self.config.get("cookie_file", ""))
        self.cookie_entry = ctk.CTkEntry(
            cookie_row,
            textvariable=self.cookie_var,
            placeholder_text="Path to YouTube cookies.txt file",
            height=38,
            font=ctk.CTkFont(size=13, family="Segoe UI"),
            corner_radius=8,
            border_width=2,
            border_color=(current_colors['border'], current_colors['border'])
        )
        self.cookie_entry.pack(side="left", fill="x", expand=True, padx=(0, 12))

        browse_cookie_btn = ctk.CTkButton(
            cookie_row,
            text="Browse",
            width=90,
            height=38,
            command=self.browse_cookie_file,
            font=ctk.CTkFont(size=12, family="Segoe UI"),
            corner_radius=8,
            fg_color=(current_colors['primary'], current_colors['primary_hover']),
            hover_color=(current_colors['primary_hover'], current_colors['primary'])
        )
        browse_cookie_btn.pack(side="left")

        # Cookie info text with modern styling
        cookie_info = ctk.CTkLabel(
            cookie_card,
            text="🎯 Use for age-restricted or region-blocked content.\n"
                 "Export cookies from your browser or use a cookie extractor extension.",
            font=ctk.CTkFont(size=11, family="Segoe UI"),
            text_color=(current_colors['text_secondary'], current_colors['text_secondary']),
            justify="left"
        )
        cookie_info.pack(anchor="w", padx=25, pady=(0, 20))

        # Bind to save on change (with debouncing)
        self.cookie_var.trace_add("write", self._on_cookie_file_changed)
        self._cookie_save_after_id = None

    def _save_metadata_setting(self, key, value):
        """Save a metadata setting to config"""
        try:
            self.config.set(key, value)
        except Exception as e:
            print(f"Error saving metadata setting {key}: {e}")

    def _load_metadata_setting(self, key, default=False):
        """Load a metadata setting from config"""
        try:
            return self.config.get(key, default)
        except Exception as e:
            print(f"Error loading metadata setting {key}: {e}")
            return default

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
        # Default to the process current working directory for newly added tasks
        # but keep config-based defaults when restoring from saved state
        if not getattr(self, '_restoring_tasks', False):
            try:
                default_output = os.getcwd()
            except Exception:
                default_output = self.config.get("output_directory", self.config.get_default_output_directory())
        else:
            default_output = self.config.get("output_directory", self.config.get_default_output_directory())
        task = TaskItem(self, parent_frame=self.tasks_list_frame, default_output=default_output)
        self.tasks.append(task)

        # Defer color updates and bindings during bulk restoration for better performance
        if not getattr(self, '_restoring_tasks', False):
            # Update task colors to match current theme
            task.update_colors()
            # Attach bindings for persistence BEFORE setting URL
            self._attach_task_bindings(task)
        else:
            # During restoration, defer these operations to avoid blocking UI
            # They will be applied after all tasks are created
            pass

        # Set URL if provided (this will trigger persistence if not restoring)
        try:
            if url:
                task.url_var.set(url)
                # Update video info for new tasks (not during restoration)
                if not getattr(self, '_restoring_tasks', False) and hasattr(task, 'update_video_info'):
                    task.update_video_info(url, force=True)
        except Exception:
            pass
        # Re-number task titles
        for idx, t in enumerate(self.tasks, start=1):
            t.update_title(f"Task {idx}")
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

        # Save to config first
        self.config.set("theme", new_mode.lower())

        # Update CustomTkinter appearance
        ctk.set_appearance_mode(new_mode)

        # Reapply modern styling for the new theme
        self._apply_modern_styling()

        # Update theme button text
        self.update_theme_button()

        # Update all existing task items
        for task in self.tasks:
            task.update_colors()
    

    def update_theme_button(self):
        """Update theme button text and styling"""
        current_mode = ctk.get_appearance_mode()
        current_colors = self.get_current_colors()

        # Use better contrast icons that work in both themes
        if current_mode == "Dark":
            icon_text = "☀️"  # Sun for switching to light mode
            # Use bright yellow for dark mode
            text_color = "#fbbf24"
        else:
            icon_text = "🌙"  # Moon for switching to dark mode
            # Use dark color for light mode
            text_color = current_colors['text_primary']

        self.theme_button.configure(
            text=icon_text,
            text_color=text_color,
            fg_color=(current_colors['surface_light'], current_colors['surface']),
            border_color=(current_colors['border'], current_colors['border'])
        )

    def toggle_maximize(self, event=None):
        """Toggle maximized window state"""
        try:
            # Check current state
            try:
                current_state = self.root.state()
                is_zoomed = 'zoomed' in current_state
            except:
                try:
                    is_zoomed = self.root.attributes('-zoomed')
                except:
                    # Fallback: check if window is approximately screen size
                    screen_width = self.root.winfo_screenwidth()
                    screen_height = self.root.winfo_screenheight()
                    window_width = self.root.winfo_width()
                    window_height = self.root.winfo_height()
                    is_zoomed = (window_width >= screen_width - 50 and window_height >= screen_height - 50)

            if is_zoomed:
                # Restore to normal window and center it
                try:
                    self.root.state('normal')
                except:
                    try:
                        self.root.attributes('-zoomed', False)
                    except:
                        # Fallback: set smaller size and center
                        self.root.geometry("1000x800")
                self.center_window()
            else:
                # Maximize window to fill screen
                try:
                    self.root.state('zoomed')
                except:
                    try:
                        self.root.attributes('-zoomed', True)
                    except:
                        # Final fallback - set to screen size
                        screen_width = self.root.winfo_screenwidth()
                        screen_height = self.root.winfo_screenheight()
                        self.root.geometry(f"{screen_width}x{screen_height}+0+0")
        except Exception as e:
            print(f"Error toggling maximize: {e}")

    def center_window(self):
        """Center the window on screen (only works when in normal windowed mode)"""
        try:
            # Check if we're in maximized/zoomed state
            try:
                current_state = self.root.state()
                if 'zoomed' in current_state:
                    return  # Don't try to center when maximized
            except:
                try:
                    if self.root.attributes('-zoomed'):
                        return  # Don't try to center when maximized
                except:
                    pass

            self.root.update_idletasks()
            width = self.root.winfo_width()
            height = self.root.winfo_height()
            x = (self.root.winfo_screenwidth() // 2) - (width // 2)
            y = (self.root.winfo_screenheight() // 2) - (height // 2)
            self.root.geometry(f'{width}x{height}+{x}+{y}')
        except Exception as e:
            print(f"Error centering window: {e}")

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
            
            # Save config before exit (only if not maximized)
            try:
                if not self.is_maximized():
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
        # Save window size to config (only if not maximized)
        try:
            if not self.is_maximized():
                geometry = self.root.geometry()
                self.config.set("window_size", geometry)
        except Exception:
            pass

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

    def is_maximized(self):
        """Check if the window is in maximized/zoomed state"""
        try:
            current_state = self.root.state()
            return 'zoomed' in current_state
        except:
            try:
                return self.root.attributes('-zoomed')
            except:
                # Fallback: check if window is approximately screen size
                try:
                    screen_width = self.root.winfo_screenwidth()
                    screen_height = self.root.winfo_screenheight()
                    window_width = self.root.winfo_width()
                    window_height = self.root.winfo_height()
                    return (window_width >= screen_width - 50 and window_height >= screen_height - 50)
                except:
                    return False
    
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
        self._is_playlist_task = bool(is_playlist)
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
        # Context log for clarity across multiple tasks
        try:
            cookie_file_cfg = self.ui.config.get("cookie_file", "") or ""
            cookie_used = cookie_file_cfg.strip()
        except Exception:
            cookie_used = ""
        self.log(f"🚀 Starting download | URL: {url}\n   Format: {'audio' if is_audio else 'video'} | Output: {output_dir}\n   Cookies: {'yes' if cookie_used else 'no'}")

        def worker():
            try:
                # Try to get quick playlist size and title for UX
                if is_playlist:
                    try:
                        with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True}) as ydl:
                            info = ydl.extract_info(url, download=False)
                            if info and 'entries' in info:
                                valid_entries = [e for e in info['entries'] if e is not None]
                                total = len(valid_entries)
                                # Capture playlist title for clearer logs
                                pl_title = info.get('title', 'Unknown Playlist')
                                # Store for end-of-download logging
                                self._current_playlist_title = pl_title
                                self._current_playlist_total = total
                                # Log a clear start banner for the playlist
                                self.ui.root.after(0, lambda: self.log(f"📑 Playlist start: {pl_title} ({total} videos)"))
                                self.ui.root.after(0, lambda: self._set_progress_text_safe(f"📋 Playlist: {total} videos"))

                                # Pre-create playlist directory and reconcile existing M3U if requested
                                try:
                                    if self.ui.metadata_vars.get('create_m3u', None) and self.ui.metadata_vars['create_m3u'].get():
                                        playlist_title = info.get('title', 'Unknown_Playlist')
                                        playlist_dir = self._compute_playlist_directory(output_dir, playlist_title)
                                        os.makedirs(playlist_dir, exist_ok=True)
                                        # Remember for finalization
                                        self._m3u_playlist_dir = playlist_dir
                                        self._m3u_playlist_title = playlist_title
                                        # Build expected mapping (index -> title, id)
                                        expected = []
                                        for idx, entry in enumerate(valid_entries, start=1):
                                            try:
                                                expected.append({
                                                    'index': idx,
                                                    'id': entry.get('id'),
                                                    'title': entry.get('title')
                                                })
                                            except Exception:
                                                pass
                                        # Reconcile existing M3U and seed state
                                        self._reconcile_existing_playlist_m3u(playlist_dir, playlist_title, expected)
                                except Exception:
                                    pass
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
                    cookie_file=cookie_file if cookie_file else None,
                    force_playlist_redownload=metadata_options.get('force_playlist_redownload', False)
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
            if d.get('status') == 'downloading':
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

                # Per-item start log (once per file)
                try:
                    if filename and filename not in self._logged_item_filenames:
                        info = d.get('info_dict', {}) or {}
                        pl_idx = info.get('playlist_index')
                        n_entries = info.get('n_entries') or info.get('playlist_count') or self._current_playlist_total or None
                        vid_title = info.get('title') or filename
                        pl_title = info.get('playlist_title') or info.get('playlist') or self._current_playlist_title or None
                        if pl_idx and n_entries:
                            self.log(f"▶ Starting: [{int(pl_idx)}/{int(n_entries)}] {vid_title}" + (f" — Playlist: {pl_title}" if pl_title else ""))
                        else:
                            self.log(f"▶ Starting: {vid_title}")
                        self._logged_item_filenames.add(filename)
                except Exception:
                    pass

                # Throttled logging
                progress_percent = progress * 100
                if (progress_percent - self._last_logged_progress >= 5.0 or filename != self._last_logged_filename):
                    self.log(f"⏬ {status_text}")
                    self._last_logged_progress = progress_percent
                    self._last_logged_filename = filename

            elif d.get('status') == 'finished':
                filename = os.path.basename(d.get('filename', '')).rsplit('.', 1)[0]
                self._set_progress_text_safe(f"Processing: {filename}")
                self.log(f"🔄 Processing: {filename}")
                # Per-item finish log with index if available
                try:
                    info = d.get('info_dict', {}) or {}
                    pl_idx = info.get('playlist_index')
                    n_entries = info.get('n_entries') or info.get('playlist_count') or self._current_playlist_total or None
                    vid_title = info.get('title') or filename
                    if pl_idx and n_entries:
                        self.log(f"✅ Finished item: [{int(pl_idx)}/{int(n_entries)}] {vid_title}")
                except Exception:
                    pass
                self._last_logged_progress = 0
                self._last_logged_filename = ""

                # Attempt M3U incremental update when a file finishes a stage
                try:
                    self._maybe_update_m3u(d)
                except Exception:
                    pass

            # Postprocessor hooks deliver final filepaths
            elif d.get('status') == 'postprocessor':
                try:
                    # Some postprocessors report 'filepath' field
                    if d.get('info_dict') or d.get('filepath'):
                        self._maybe_update_m3u(d)
                except Exception:
                    pass

            elif d.get('status') == 'error':
                error_msg = d.get('error', 'Unknown error')
                self._set_progress_text_safe(f"Error: {error_msg}")
                self.log(f"❌ Error: {error_msg}")
        except Exception as e:
            self.log(f"❌ Progress update error: {e}")

    def _completed(self, success: bool, message: str):
        if not self._is_alive():
            return
        try:
            # Final playlist banner for clarity
            try:
                if self._is_playlist_task:
                    pl_title = self._current_playlist_title or "Playlist"
                    # Attempt to summarize counts from downloader if available
                    progress = {}
                    try:
                        progress = self.downloader.get_playlist_progress() or {}
                    except Exception:
                        progress = {}
                    total = progress.get('total', self._current_playlist_total)
                    downloaded = progress.get('downloaded')
                    failed = progress.get('failed')
                    skipped = progress.get('skipped')
                    summary_bits = []
                    if downloaded is not None:
                        summary_bits.append(f"downloaded {downloaded}")
                    if skipped is not None:
                        summary_bits.append(f"skipped {skipped}")
                    if failed is not None:
                        summary_bits.append(f"failed {failed}")
                    summary = (", ".join(summary_bits)) if summary_bits else ""
                    if total:
                        self.log(f"📦 Playlist end: {pl_title} ({total} videos){' — ' + summary if summary else ''}")
                    else:
                        self.log(f"📦 Playlist end: {pl_title}{' — ' + summary if summary else ''}")
            except Exception:
                pass

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

            # Finalize M3U: ensure file is written even if last hook missed
            try:
                enabled_var = self.ui.metadata_vars.get('create_m3u', None)
                if enabled_var and enabled_var.get():
                    # If we had a playlist dir precomputed use it; otherwise, attempt to infer from output_path
                    target_dir = self._m3u_playlist_dir
                    if not target_dir:
                        try:
                            # Infer from the chosen output directory for this task
                            out_dir = self.output_var.get().strip()
                            if out_dir and os.path.isdir(out_dir):
                                target_dir = out_dir
                        except Exception:
                            pass
                    if target_dir:
                        self._write_m3u_from_state(target_dir, self._m3u_playlist_title)
                        self.log("📄 M3U playlist updated.")
            except Exception:
                pass
        except Exception:
            # If anything fails during completion (likely due to destroyed widgets), just exit quietly
            pass

    # ===== M3U helpers =====
    def _sanitize_name(self, name: str) -> str:
        try:
            if not name:
                return ""
            return re.sub(r'[<>:"/\\|?*]', '_', name)
        except Exception:
            return name or ""

    def _compute_playlist_directory(self, output_dir: str, playlist_title: str) -> str:
        safe_title = self._sanitize_name(playlist_title or 'Unknown_Playlist')
        return os.path.join(output_dir, safe_title)

    def _state_path(self, directory: str) -> str:
        return os.path.join(directory, ".playlist_state.json")

    def _load_state(self, directory: str) -> dict:
        try:
            path = self._state_path(directory)
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return {"playlist_title": None, "total_entries": 0, "entries": {}}

    def _save_state(self, directory: str, state: dict):
        try:
            path = self._state_path(directory)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _m3u_path(self, directory: str, playlist_title: str = None) -> str:
        try:
            base = os.path.basename(directory).strip() or (playlist_title or "playlist")
        except Exception:
            base = (playlist_title or "playlist")
        safe = self._sanitize_name(base)
        # If user wants M3U in parent folder, place it there
        try:
            to_parent = self.ui.metadata_vars.get('m3u_to_parent', None)
            if to_parent and to_parent.get():
                parent_dir = os.path.dirname(directory.rstrip(os.sep)) or directory
                return os.path.join(parent_dir, f"{safe}.m3u")
        except Exception:
            pass
        return os.path.join(directory, f"{safe}.m3u")

    def _write_m3u_from_state(self, directory: str, playlist_title: str = None):
        state = self._load_state(directory)
        # Merge provided playlist_title
        if playlist_title and not state.get("playlist_title"):
            state["playlist_title"] = playlist_title

        # Build ordered list by playlist index
        try:
            entries = state.get("entries", {})
            ordered = []
            for k, v in entries.items():
                try:
                    ordered.append((int(k), v))
                except Exception:
                    pass
            ordered.sort(key=lambda x: x[0])

            # Prepare lines (relative paths)
            lines = []
            included_abs_paths = set()
            for _, meta in ordered:
                path = meta.get('path')
                if not path or not os.path.exists(path):
                    continue
                try:
                    abs_path = os.path.abspath(path)
                    included_abs_paths.add(abs_path)
                except Exception:
                    pass
                # For parent placement, keep paths relative to the M3U file location
                try:
                    target_m3u_dir = os.path.dirname(self._m3u_path(directory, state.get("playlist_title")))
                    rel = os.path.relpath(path, target_m3u_dir)
                except Exception:
                    rel = path
                lines.append(rel.replace('\\', '/'))

            # Also append any temp extras captured without an index
            try:
                for k, meta in list(state.get('entries', {}).items()):
                    if not isinstance(k, str) or not k.startswith('_extra_'):
                        continue
                    path = meta.get('path')
                    if not path or not os.path.exists(path):
                        continue
                    try:
                        abs_path = os.path.abspath(path)
                        if abs_path in included_abs_paths:
                            continue
                        included_abs_paths.add(abs_path)
                        target_m3u_dir = os.path.dirname(self._m3u_path(directory, state.get("playlist_title")))
                        rel = os.path.relpath(path, target_m3u_dir)
                    except Exception:
                        rel = path
                    lines.append(rel.replace('\\', '/'))
            except Exception:
                pass

            # Fallback: append any media files present in directory but missing from expected list
            try:
                media_exts = ('.mp3', '.m4a', '.flac', '.ogg', '.wav', '.mp4', '.mkv', '.webm')
                dir_entries = []
                for fn in os.listdir(directory):
                    fp = os.path.join(directory, fn)
                    if os.path.isfile(fp) and fn.lower().endswith(media_exts):
                        try:
                            abs_fp = os.path.abspath(fp)
                            if abs_fp not in included_abs_paths:
                                dir_entries.append(fp)
                        except Exception:
                            pass
                # Deterministic order for extras: alphabetical by filename
                dir_entries.sort(key=lambda p: os.path.basename(p).lower())
                for fp in dir_entries:
                    try:
                        target_m3u_dir = os.path.dirname(self._m3u_path(directory, state.get("playlist_title")))
                        rel = os.path.relpath(fp, target_m3u_dir)
                    except Exception:
                        rel = fp
                    lines.append(rel.replace('\\', '/'))
            except Exception:
                pass

            m3u_file = self._m3u_path(directory, state.get("playlist_title"))
            with open(m3u_file, 'w', encoding='utf-8') as f:
                f.write("#EXTM3U\n")
                for rel in lines:
                    # Basic M3U without EXTINF duration; Samsung Music accepts plain entries
                    f.write(f"{rel}\n")
        except Exception:
            pass

    def _reconcile_existing_playlist_m3u(self, directory: str, playlist_title: str, expected_entries: list):
        """Seed or fix M3U before download by matching existing files to expected order."""
        try:
            state = self._load_state(directory)
            state['playlist_title'] = playlist_title or state.get('playlist_title') or ''
            state['total_entries'] = max(state.get('total_entries', 0) or 0, len(expected_entries))

            # Build quick lookup by sanitized title stem
            expected_by_stem = {}
            for item in expected_entries:
                title = item.get('title') or ''
                stem = self._sanitize_name(title).lower()
                expected_by_stem[stem] = item

            # Scan directory for media files
            media_exts = ('.mp3', '.m4a', '.flac', '.ogg', '.wav', '.mp4', '.mkv', '.webm')
            for root, _, files in os.walk(directory):
                if os.path.abspath(root) != os.path.abspath(directory):
                    continue
                for fn in files:
                    if not fn.lower().endswith(media_exts):
                        continue
                    stem = os.path.splitext(fn)[0].lower()
                    # Find best match by prefix or equality
                    match = None
                    if stem in expected_by_stem:
                        match = expected_by_stem[stem]
                    else:
                        for key, item in expected_by_stem.items():
                            if stem.startswith(key[:50]):
                                match = item
                                break
                    if match:
                        idx = int(match.get('index') or 0)
                        if idx > 0:
                            path = os.path.join(directory, fn)
                            state.setdefault('entries', {})[str(idx)] = {
                                'id': match.get('id'),
                                'title': match.get('title'),
                                'path': path
                            }
            self._save_state(directory, state)
            self._write_m3u_from_state(directory, playlist_title)
        except Exception:
            pass

    def _maybe_update_m3u(self, d: dict):
        # Check toggle
        try:
            enabled_var = self.ui.metadata_vars.get('create_m3u', None)
            if not enabled_var or not enabled_var.get():
                return
        except Exception:
            return

        info = d.get('info_dict', {}) or {}
        pl_index = info.get('playlist_index')
        # Accept zero/None indices in postprocessor stage, but prefer explicit playlist_index
        # If no playlist_index, try to derive from state later; for now, still record the path
        # Prefer final filepath reported by postprocessor; fallback to filename
        final_path = info.get('filepath') or d.get('filepath') or d.get('filename')
        if not final_path:
            return
        directory = os.path.dirname(final_path)
        playlist_title = info.get('playlist_title') or info.get('playlist') or ''
        total = info.get('n_entries') or info.get('playlist_count') or 0
        video_id = info.get('id')
        title = info.get('title')

        # Update state and M3U
        try:
            state = self._load_state(directory)
            if playlist_title:
                state['playlist_title'] = playlist_title
            if total:
                try:
                    state['total_entries'] = max(int(total), int(state.get('total_entries', 0) or 0))
                except Exception:
                    pass
            entries = state.setdefault('entries', {})
            if pl_index:
                key = str(int(pl_index))
                entries[key] = {
                    'id': video_id,
                    'title': title,
                    'path': final_path
                }
            else:
                # No index available; temporarily store under a special key to be appended later
                tmp_key = f"_extra_{video_id or os.path.basename(final_path)}"
                entries[tmp_key] = {
                    'id': video_id,
                    'title': title,
                    'path': final_path
                }
            self._save_state(directory, state)
            self._write_m3u_from_state(directory, playlist_title)
        except Exception:
            pass