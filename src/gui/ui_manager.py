"""
UI Manager Module

Manages the main UI layout and window.
Handles window setup, layout creation, and scrollable content management.
"""

import customtkinter as ctk


class UIManager:
    """Manages the main UI layout and window"""

    def __init__(self, root, config, theme_manager, widget_factory, task_manager):
        # Store references to existing components
        self.root = root
        self.config = config
        self.theme = theme_manager
        self.widget_factory = widget_factory
        self.task_manager = task_manager

        # UI state
        self.tasks_list_frame = None
        self.settings_vars = {}
        self.metadata_vars = {}
        self.cookie_var = None  # Will be set by create_cookie_section

    def get_tasks_list_frame(self):
        """Get the tasks list frame"""
        return self.tasks_list_frame


    def create_main_layout(self):
        """Create the main UI layout"""
        # Create main container with scrollbar
        self.create_scrollable_container()
        self.create_scrollable_content()

    def create_scrollable_container(self):
        """Create the scrollable main container"""
        # Main container frame
        self.main_container = self.widget_factory.create_frame(self.root)
        self.main_container.pack(fill="both", expand=True, padx=0, pady=0)

        # Create canvas and scrollbar for scrolling
        self.canvas = ctk.CTkCanvas(
            self.main_container,
            bg=self.theme.get_color('background'),
            highlightthickness=0
        )
        self.canvas.pack(side="left", fill="both", expand=True)

        # Scrollbar
        self.scrollbar = ctk.CTkScrollbar(
            self.main_container,
            orientation="vertical",
            command=self.canvas.yview,
            fg_color=self.theme.get_color('surface')
        )
        self.scrollbar.pack(side="right", fill="y")

        # Connect scrollbar to canvas
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # Create scrollable frame inside canvas
        self.scrollable_frame = self.widget_factory.create_frame(self.canvas)
        self.canvas_window = self.canvas.create_window(
            (0, 0),
            window=self.scrollable_frame,
            anchor="nw"
        )

        # Configure scrolling
        def configure_scroll_region(event=None):
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))

        def configure_window_size(event=None):
            canvas_width = self.canvas.winfo_width()
            self.canvas.itemconfig(self.canvas_window, width=canvas_width)

        self.scrollable_frame.bind("<Configure>", configure_scroll_region)
        self.canvas.bind("<Configure>", configure_window_size)

        # Mouse wheel scrolling
        def mouse_wheel(event):
            if event.delta > 0:
                self.canvas.yview_scroll(-1, "units")
            else:
                self.canvas.yview_scroll(1, "units")

        self.canvas.bind("<MouseWheel>", mouse_wheel)

    def create_scrollable_content(self):
        """Create the content inside the scrollable frame in the correct order"""
        # Header section
        self.create_header()

        # Welcome/Ready section
        self.create_welcome_section()

        # Settings section (should appear before tasks)
        self.create_settings_section()

        # Cookie section
        self.create_cookie_section()

        # Tasks section
        self.create_tasks_section()

    def create_header(self):
        """Create the header section"""
        # Header frame
        header_frame = self.widget_factory.create_frame(self.scrollable_frame)
        header_frame.pack(fill="x", padx=20, pady=(20, 10))

        # Title
        title_label = self.widget_factory.create_label(
            header_frame,
            "🎬 YouTube Media Downloader",
            font_size=24
        )
        title_label.pack(pady=(0, 10))

        # Subtitle
        subtitle_label = self.widget_factory.create_label(
            header_frame,
            "Download videos and playlists with advanced options",
            font_size=14
        )
        subtitle_label.pack()

    def create_tasks_section(self):
        """Create the tasks section"""
        # Tasks section frame
        tasks_frame = self.widget_factory.create_frame(self.scrollable_frame)
        tasks_frame.pack(fill="x", padx=20, pady=(20, 10))

        # Tasks header
        tasks_header = self.widget_factory.create_frame(tasks_frame)
        tasks_header.pack(fill="x", pady=(0, 15))

        tasks_title = self.widget_factory.create_label(
            tasks_header,
            "📋 Download Tasks",
            font_size=18
        )
        tasks_title.pack(side="left")

        # Add task button
        add_task_btn = self.widget_factory.create_button(
            tasks_header,
            "➕ Add Task",
            command=self.task_manager.add_task,
            width=100,
            height=32
        )
        add_task_btn.pack(side="right")

        # Tasks container
        self.tasks_list_frame = self.widget_factory.create_frame(tasks_frame)
        self.tasks_list_frame.pack(fill="x")

    def create_settings_section(self):
        """Create the settings section"""
        # Settings section frame (using card styling for consistency)
        settings_frame = self.widget_factory.create_card_frame(self.scrollable_frame)
        settings_frame.pack(fill="x", padx=20, pady=(0, 25))

        # Settings header
        settings_header = self.widget_factory.create_frame(settings_frame, fg_color="transparent")
        settings_header.pack(fill="x", pady=(15, 15))

        settings_title = self.widget_factory.create_label(
            settings_header,
            "⚙️ Settings",
            font_size=18
        )
        settings_title.pack(side="left")

        # Create settings categories with proper padding
        settings_content = self.widget_factory.create_frame(settings_frame, fg_color="transparent")
        settings_content.pack(fill="x", padx=25, pady=(5, 20))
        self.create_settings_categories(settings_content)

    def create_settings_categories(self, parent_frame):
        """Create settings categories with checkboxes for metadata and download options"""
        # Check FFmpeg availability for disabling certain options
        ffmpeg_disabled = not hasattr(self.task_manager.ui, 'downloader') or not self.task_manager.ui.downloader.ffmpeg_available

        # Create two columns for settings
        left_column = self.widget_factory.create_frame(parent_frame, fg_color="transparent")
        left_column.pack(side="left", fill="both", expand=True, padx=(0, 10))

        right_column = self.widget_factory.create_frame(parent_frame, fg_color="transparent")
        right_column.pack(side="right", fill="both", expand=True, padx=(10, 0))

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

    def _create_settings_category(self, parent, title, options, ffmpeg_disabled=False, disabled_keys=None):
        """Create a settings category with title and checkboxes"""
        if disabled_keys is None:
            disabled_keys = []

        # Category frame
        category_frame = self.widget_factory.create_frame(parent, fg_color="transparent")
        category_frame.pack(fill="x", pady=(0, 15))

        # Category title
        title_label = ctk.CTkLabel(
            category_frame,
            text=title,
            font=ctk.CTkFont(size=14, weight="bold", family="Segoe UI"),
            text_color=(self.theme.get_color('text_primary'), self.theme.get_color('text_primary'))
        )
        title_label.pack(anchor="w", pady=(0, 10))

        # Checkboxes container
        checkboxes_frame = self.widget_factory.create_frame(category_frame, fg_color="transparent")
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
                text_color=(self.theme.get_color('text_primary'), self.theme.get_color('text_primary')),
                hover_color=(self.theme.get_color('primary'), self.theme.get_color('primary_hover'))
            )
            checkbox.pack(anchor="w", pady=2)

        return category_frame

    def _load_metadata_setting(self, key, default):
        """Load a metadata setting from config with fallback to default"""
        return self.config.get(key, default)

    def create_welcome_section(self):
        """Create the welcome/ready to download section"""
        # Welcome card container
        welcome_card = self.widget_factory.create_card_frame(self.scrollable_frame)
        welcome_card.pack(fill="x", padx=20, pady=(0, 25))

        # Welcome content
        welcome_content = self.widget_factory.create_frame(welcome_card, fg_color="transparent")
        welcome_content.pack(fill="x", padx=25, pady=20)

        # Welcome title
        welcome_title = self.widget_factory.create_label(
            welcome_content,
            "🎯 Ready to Download",
            font_size=18
        )
        welcome_title.pack(anchor="w", pady=(0, 10))

        # Welcome description
        welcome_desc = self.widget_factory.create_label(
            welcome_content,
            "Configure your download settings below, then add tasks to start downloading YouTube content.\nSupports playlists, individual videos, and various quality options.",
            font_size=12
        )
        welcome_desc.pack(anchor="w")

    def create_cookie_section(self):
        """Create cookie file section for browser authentication"""
        # Cookie card container
        cookie_card = self.widget_factory.create_card_frame(self.scrollable_frame)
        cookie_card.pack(fill="x", padx=20, pady=(0, 25))

        # Cookie header
        cookie_header = self.widget_factory.create_frame(cookie_card, fg_color="transparent")
        cookie_header.pack(fill="x", padx=25, pady=(20, 15))

        # Cookie title with icon
        cookie_title = self.widget_factory.create_label(
            cookie_header,
            "🍪 Browser Authentication",
            font_size=18
        )
        cookie_title.pack(anchor="w")

        # Cookie description
        cookie_desc = self.widget_factory.create_label(
            cookie_header,
            "Optional: Use browser cookies for accessing restricted content",
            font_size=12
        )
        cookie_desc.pack(anchor="w", pady=(2, 0))

        # Cookie file input row
        cookie_row = self.widget_factory.create_frame(cookie_card, fg_color="transparent")
        cookie_row.pack(fill="x", padx=25, pady=(0, 15))

        # Cookie file entry
        self.cookie_var = ctk.StringVar(value=self.config.get("cookie_file", ""))
        cookie_entry = ctk.CTkEntry(
            cookie_row,
            textvariable=self.cookie_var,
            placeholder_text="Path to YouTube cookies.txt file",
            height=38,
            font=ctk.CTkFont(size=13, family="Segoe UI"),
            corner_radius=8,
            border_width=2,
            border_color=(self.theme.get_color('border'), self.theme.get_color('border'))
        )
        cookie_entry.pack(side="left", fill="x", expand=True)

        # Browse button for cookie file
        browse_btn = self.widget_factory.create_button(
            cookie_row,
            "Browse",
            command=self._browse_cookie_file,
            width=85,
            height=38
        )
        browse_btn.pack(side="left", padx=(10, 0))

        # Info text
        info_frame = self.widget_factory.create_frame(cookie_card, fg_color="transparent")
        info_frame.pack(fill="x", padx=25, pady=(5, 20))

        info_text = self.widget_factory.create_label(
            info_frame,
            "💡 Use browser cookies for accessing age-restricted or region-blocked content.\nExport cookies from your browser or use a cookie extractor extension.",
            font_size=11
        )
        info_text.pack(anchor="w")

    def _browse_cookie_file(self):
        """Browse for cookie file"""
        from tkinter import filedialog
        file_path = filedialog.askopenfilename(
            title="Select Cookie File",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialdir=self.config.get("cookie_file", "")
        )
        if file_path:
            self.cookie_var.set(file_path)
            self.config.set("cookie_file", file_path)


    def restore_settings_to_ui(self):
        """Restore metadata settings from config into UI elements"""
        try:
            # Restore metadata settings
            for key, var in self.metadata_vars.items():
                saved_value = self.config.get(key, False)
                var.set(saved_value)

        except Exception as e:
            print(f"Error restoring settings to UI: {e}")
