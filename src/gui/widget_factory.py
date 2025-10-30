"""
Widget Factory Module

Factory class for creating common UI widgets with consistent styling.
"""

import customtkinter as ctk


class WidgetFactory:
    """Factory class for creating common UI widgets with consistent styling"""

    def __init__(self, theme_manager):
        self.theme = theme_manager

    def create_button(self, parent, text, command=None, width=None, height=None, **kwargs):
        """Create a styled button"""
        colors = self.theme.get_current_colors()
        return ctk.CTkButton(
            parent,
            text=text,
            command=command,
            width=width,
            height=height,
            font=ctk.CTkFont(size=12, family="Segoe UI"),
            fg_color=(colors['primary'], colors['primary_hover']),
            hover_color=(colors['primary_hover'], colors['primary']),
            corner_radius=8,
            **kwargs
        )

    def create_entry(self, parent, textvariable=None, placeholder_text=None, **kwargs):
        """Create a styled entry field"""
        colors = self.theme.get_current_colors()
        return ctk.CTkEntry(
            parent,
            textvariable=textvariable,
            placeholder_text=placeholder_text,
            height=36,
            font=ctk.CTkFont(size=12, family="Segoe UI"),
            corner_radius=8,
            border_width=2,
            border_color=(colors['border'], colors['border']),
            **kwargs
        )

    def create_label(self, parent, text, font_size=12, **kwargs):
        """Create a styled label"""
        colors = self.theme.get_current_colors()
        return ctk.CTkLabel(
            parent,
            text=text,
            font=ctk.CTkFont(size=font_size, family="Segoe UI"),
            text_color=(colors['text_primary'], colors['text_primary']),
            **kwargs
        )

    def create_frame(self, parent, **kwargs):
        """Create a styled frame"""
        colors = self.theme.get_current_colors()
        # Use provided fg_color if given, otherwise use default
        fg_color = kwargs.pop('fg_color', (colors['surface'], colors['surface']))
        return ctk.CTkFrame(
            parent,
            fg_color=fg_color,
            **kwargs
        )

    def create_card_frame(self, parent, **kwargs):
        """Create a card-style frame"""
        colors = self.theme.get_current_colors()
        # Extract fg_color if provided, otherwise use default
        fg_color = kwargs.pop('fg_color', (colors['card'], colors['card']))

        return ctk.CTkFrame(
            parent,
            fg_color=fg_color,
            corner_radius=10,
            border_width=1,
            border_color=(colors['border'], colors['border']),
            **kwargs
        )
