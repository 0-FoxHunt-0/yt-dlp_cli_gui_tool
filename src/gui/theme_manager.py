"""
Theme Manager Module

Manages color themes and styling for the application.
Currently supports dark mode only (light mode removed per requirements).
"""


class ThemeManager:
    """Manages color themes and styling for the application"""

    # Dark mode color palette only (light mode removed per requirements)
    COLORS = {
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
    }

    def __init__(self):
        self.colors = self.COLORS.copy()

    def get_current_colors(self):
        """Get current color scheme"""
        return self.colors

    def get_color(self, key):
        """Get a specific color by key"""
        return self.colors.get(key, '#000000')
