import json
import os
import shutil
from pathlib import Path


class Config:
    def __init__(self):
        # Resolve project root independent of current working directory
        # src/utils/config.py -> utils -> src -> project root
        self.project_root = Path(__file__).resolve().parent.parent.parent

        # Store config adjacent to the app so it persists regardless of CWD
        self.config_dir = self.project_root / "config"
        self.config_file = self.config_dir / "settings.json"

        # One-time migration: move legacy config stored in CWD (older versions)
        self._migrate_legacy_config_locations()
        self.default_settings = {
            "theme": "auto",
            "window_size": "700x600",
            "output_directory": self._get_default_output_directory(),
            "default_format": "audio",
            "cookie_file": "",  # Path to YouTube cookies file
            "use_cookies_from_browser": True,
            "cookies_from_browser": "brave",  # Default to Brave if available
            "auto_clear_logs": True,
            "max_logs_to_keep": 5,
            "download_history": True,
            # Persist open tasks state
            "tasks_count": 1,
            "task_urls": [],
            # New structured tasks (list of {url, format, output})
            "tasks": [],
            # Metadata options
            "embed_metadata": True,
            "embed_thumbnail": True,
            "embed_chapters": True,
            "write_thumbnail": True,
            "include_author": False,
            "write_description": False,
            "write_info_json": False,
            "embed_subs": False,
            "playlist_album_override": False,
            "create_m3u": False,
            "m3u_to_parent": False,
            # Import dialog defaults
            "last_import_input_dir": "",
            "last_import_output_dir": "",
            "import_override_existing": False
            ,
            # Proof-of-Origin (POT) provider via Docker (bgutil)
            "pot_provider": {
                "enabled": True,
                "method": "docker",  # docker | script (not implemented yet)
                "docker_image": "brainicism/bgutil-ytdlp-pot-provider",
                "docker_container_name": "bgutil-provider",
                "docker_port": 4416,
                "base_url": "http://127.0.0.1:4416",
                "disable_innertube": True,
                "stop_on_exit": True,
                "readiness_timeout_secs": 45
            }
        }
        self.settings = self.load_settings()
        # Ensure default output directory exists
        self._ensure_default_output_directory()

    def load_settings(self):
        """Load settings from config file or create with defaults"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_settings = json.load(f)
                    # Merge with defaults to handle missing keys
                    settings = self.default_settings.copy()
                    settings.update(loaded_settings)
                    return settings
            else:
                # Create config directory and file with defaults
                self.config_dir.mkdir(exist_ok=True)
                self.save_settings(self.default_settings)
                return self.default_settings.copy()
        except Exception as e:
            print(f"Error loading config: {e}")
            return self.default_settings.copy()

    def save_settings(self, settings=None):
        """Save current settings to config file"""
        if settings is None:
            settings = self.settings
        
        try:
            self.config_dir.mkdir(exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving config: {e}")

    def get(self, key, default=None):
        """Get a setting value"""
        return self.settings.get(key, default)

    def set(self, key, value):
        """Set a setting value and save"""
        self.settings[key] = value
        self.save_settings()

    def get_theme_colors(self, theme=None):
        """Get color scheme for specified theme"""
        if theme is None:
            theme = self.settings.get("theme", "dark")
        
        if theme == "dark":
            return {
                "bg": "#2b2b2b",
                "fg": "#ffffff",
                "button_bg": "#404040",
                "button_fg": "#ffffff",
                "entry_bg": "#404040",
                "entry_fg": "#ffffff",
                "frame_bg": "#3c3c3c",
                "progress_bg": "#404040",
                "progress_fg": "#4CAF50",
                "text_bg": "#404040",
                "text_fg": "#ffffff",
                "success_fg": "#4CAF50",
                "error_fg": "#f44336",
                "warning_fg": "#ff9800",
                "info_fg": "#2196F3"
            }
        else:  # light mode
            return {
                "bg": "#f5f5f5",
                "fg": "#000000",
                "button_bg": "#e0e0e0",
                "button_fg": "#000000",
                "entry_bg": "#ffffff",
                "entry_fg": "#000000",
                "frame_bg": "#ffffff",
                "progress_bg": "#e0e0e0",
                "progress_fg": "#4CAF50",
                "text_bg": "#ffffff",
                "text_fg": "#000000",
                "success_fg": "#4CAF50",
                "error_fg": "#f44336",
                "warning_fg": "#ff9800",
                "info_fg": "#2196F3"
            }

    def _get_default_output_directory(self):
        """Get the default output directory path"""
        # Create an 'output' folder in the project root directory
        try:
            project_root = self.project_root
        except Exception:
            project_root = Path(__file__).resolve().parent.parent.parent
        default_dir = project_root / "output"
        return str(default_dir)

    def _ensure_default_output_directory(self):
        """Ensure the default output directory exists"""
        try:
            default_dir = Path(self._get_default_output_directory())
            default_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"Warning: Could not create default output directory: {e}")

    def get_default_output_directory(self):
        """Get the default output directory path"""
        return self._get_default_output_directory()

    def reset_output_directory(self):
        """Reset output directory to default and ensure it exists"""
        default_dir = self._get_default_output_directory()
        self.set("output_directory", default_dir)
        self._ensure_default_output_directory()
        return default_dir

    def _migrate_legacy_config_locations(self):
        """Migrate settings from legacy CWD-based config folder to project-root config."""
        try:
            legacy_dir = Path.cwd() / "config"
            legacy_file = legacy_dir / "settings.json"

            # Skip if legacy equals new location or legacy doesn't exist
            if not legacy_file.exists():
                return
            try:
                if legacy_file.resolve() == self.config_file.resolve():
                    return
            except Exception:
                # If resolve fails, continue with best-effort migration
                pass

            # Only migrate if target doesn't already exist
            if self.config_file.exists():
                return

            self.config_dir.mkdir(parents=True, exist_ok=True)
            try:
                # Prefer moving to avoid duplicates
                shutil.move(str(legacy_file), str(self.config_file))
            except Exception:
                # Fallback to copy if move fails (e.g., cross-device)
                shutil.copy2(str(legacy_file), str(self.config_file))
        except Exception:
            # Non-fatal; continue without blocking app startup
            pass