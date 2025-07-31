import json
import os
from pathlib import Path


class Config:
    def __init__(self):
        self.config_dir = Path("config")
        self.config_file = self.config_dir / "settings.json"
        self.default_settings = {
            "theme": "dark",
            "window_size": "600x500",
            "output_directory": ".",
            "default_format": "audio",
            "auto_clear_logs": False,
            "download_history": True
        }
        self.settings = self.load_settings()

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