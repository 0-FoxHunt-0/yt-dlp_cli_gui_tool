from prompt_toolkit import Application
from prompt_toolkit.layout import Layout, HSplit, VSplit, Window
from prompt_toolkit.widgets import RadioList, TextArea, Button, Label, Checkbox, Box
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.dimension import D
from prompt_toolkit.layout.containers import WindowAlign
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.styles import Style
from prompt_toolkit.application.current import get_app
from ..core.downloader import Downloader
import os
import asyncio
import threading
import time


class TerminalUI:
    def __init__(self):
        self.downloader = Downloader()
        self.focusable_elements = []

        # Create header
        self.header = Label(HTML(
            '<style fg="ansiwhite" bg="ansiblue"> YouTube Downloader </style>'
        ))

        # Create URL input with better styling
        self.url_input = TextArea(
            height=1,
            prompt='URL › ',
            focusable=True,
            multiline=False,
            style='class:input-field'
        )
        self.focusable_elements.append(self.url_input)

        # Create format selection with better visual grouping
        self.format_select = RadioList([
            ('audio', '🎵 Audio Only'),
            ('video', '🎬 Video'),
        ])
        self.focusable_elements.append(self.format_select)

        # Add playlist toggle with icon
        self.playlist_toggle = Checkbox(
            text="📑 Treat as playlist"
        )
        self.focusable_elements.append(self.playlist_toggle)

        # Output path with icon
        self.output_path = TextArea(
            height=1,
            text=os.getcwd(),
            focusable=True,
            multiline=False,
            style='class:input-field'
        )
        self.focusable_elements.append(self.output_path)

        # Styled download button
        self.download_button = Button(
            text='⬇️  Download',
            handler=self.start_download
        )
        self.focusable_elements.append(self.download_button)

        # Status and progress with better styling
        self.status_text = Label(text='Ready...', style='class:status')
        self.progress_text = Label(
            text='[                    ] 0%',
            style='class:progress-bar'
        )

        # Create layout with better visual hierarchy and spacing
        self.container = HSplit([
            # Header
            Box(body=self.header, height=1, style='class:header'),
            Window(height=1),  # Spacing

            # Input section
            Box(
                body=HSplit([
                    Label(HTML('<style fg="ansiyellow">Enter YouTube URL:</style>')),
                    self.url_input,
                ]),
                padding=1,
                style='class:input-box'
            ),
            Window(height=1),  # Spacing

            # Options section
            Box(
                body=HSplit([
                    Label(HTML('<style fg="ansiyellow">Download Options:</style>')),
                    VSplit([
                        Box(
                            body=self.format_select,
                            padding=1,
                            style='class:options-box'
                        ),
                        Window(width=2),  # Horizontal spacing
                        Box(
                            body=self.playlist_toggle,
                            padding=1,
                            style='class:options-box'
                        ),
                    ]),
                ]),
                padding=1,
                style='class:options-section'
            ),
            Window(height=1),  # Spacing

            # Output section
            Box(
                body=HSplit([
                    Label(HTML('<style fg="ansiyellow">📂 Output Directory:</style>')),
                    self.output_path,
                ]),
                padding=1,
                style='class:output-box'
            ),
            Window(height=1),  # Spacing

            # Download button centered
            HSplit([
                Window(height=D.exact(1)),  # Top padding
                VSplit([
                    Window(width=D.exact(1)),  # Left padding
                    Box(
                        body=self.download_button,
                        height=3,
                        padding_top=1,
                        padding_bottom=1,
                    ),
                    Window(width=D.exact(1)),  # Right padding
                ]),
                Window(height=D.exact(1)),  # Bottom padding
            ]),

            # Status and progress section
            Box(
                body=HSplit([
                    self.status_text,
                    self.progress_text,
                ]),
                padding=1,
                style='class:status-box'
            ),
        ])

        # Key bindings
        kb = KeyBindings()

        @kb.add('c-c')
        def _(event):
            "Quit application on Ctrl+C"
            event.app.exit()

        @kb.add('tab')
        def _(event):
            "Focus next element"
            current_index = -1
            for i, element in enumerate(self.focusable_elements):
                if event.app.layout.has_focus(element):
                    current_index = i
                    break

            next_index = (current_index + 1) % len(self.focusable_elements)
            event.app.layout.focus(self.focusable_elements[next_index])

        @kb.add('s-tab')
        def _(event):
            "Focus previous element"
            current_index = -1
            for i, element in enumerate(self.focusable_elements):
                if event.app.layout.has_focus(element):
                    current_index = i
                    break

            prev_index = (current_index - 1) % len(self.focusable_elements)
            event.app.layout.focus(self.focusable_elements[prev_index])

        # Create application with proper Style object
        style = Style.from_dict({
            'header': 'bg:ansiblue fg:white bold',
            'input-box': 'bg:ansibrightblack',
            'input-field': 'bg:ansiblack',
            'options-box': 'bg:ansibrightblack',
            'output-box': 'bg:ansibrightblack',
            'status-box': 'bg:ansibrightblack',
            'button': 'bg:ansigreen fg:white bold',
            'progress-bar': 'fg:ansigreen',
            'status': 'fg:ansiyellow',
        })

        self.application = Application(
            layout=Layout(self.container, focused_element=self.url_input),
            key_bindings=kb,
            full_screen=True,
            mouse_support=True,
            style=style  # Use the Style object instead of dict
        )

        self.download_completed = False
        self.download_success = False

    def update_progress(self, d):
        """Update the progress text and status text"""
        try:
            if d['status'] == 'downloading':
                # Get full filename and extract info
                full_path = d.get('filename', '')
                filename = os.path.basename(full_path)
                if '.' in filename:  # Remove file extension for display
                    filename = filename.rsplit('.', 1)[0]

                # Extract download progress
                if d.get('total_bytes'):
                    # Known file size
                    downloaded = d.get('downloaded_bytes', 0)
                    total = d.get('total_bytes', 0)
                    progress = (downloaded / total * 100) if total > 0 else 0
                else:
                    # Unknown file size, use yt-dlp's estimate
                    progress_str = d.get('_percent_str', '0%').replace('%', '')
                    try:
                        progress = float(progress_str)
                    except ValueError:
                        progress = 0

                # Create progress bar
                filled = int((progress / 100) * 20)
                bar = '█' * filled + '░' * (20 - filled)

                # Calculate speed and format ETA
                speed = d.get('speed', 0)
                eta = d.get('eta', 0)

                if speed and eta:
                    speed_mb = speed / 1024 / 1024
                    if eta > 60:
                        eta_str = f"{eta // 60}m {eta % 60}s"
                    else:
                        eta_str = f"{eta}s"
                    status = f"⏬ {filename} ({speed_mb:.1f} MB/s, ETA: {eta_str})"
                else:
                    status = f"⏬ {filename}"

                # Update UI with new status
                self.status_text.text = status
                self.progress_text.text = f'[{bar}] {progress:.1f}%'
                get_app().invalidate()

            elif d['status'] == 'finished':
                filename = os.path.basename(
                    d.get('filename', '')).rsplit('.', 1)[0]
                self.status_text.text = f"🔄 Converting: {filename}"
                self.progress_text.text = '[██████████████████████] 100%'
                get_app().invalidate()

            elif d['status'] == 'error':
                error_msg = d.get('error', 'Unknown error')
                self.status_text.text = f"❌ Error: {error_msg}"
                self.progress_text.text = '[░░░░░░░░░░░░░░░░░░░░] 0%'
                get_app().invalidate()

        except Exception as e:
            self.status_text.text = f"❌ Status update error: {str(e)}"
            self.progress_text.text = '[░░░░░░░░░░░░░░░░░░░░] 0%'
            get_app().invalidate()

    def start_download(self):
        """Start the download process"""
        url = self.url_input.text.strip()
        if not url:
            self.status_text.text = "Please enter a URL"
            return

        self.status_text.text = "Starting download..."
        self.progress_text.text = '[                    ] 0%'
        get_app().invalidate()

        def download_thread():
            try:
                self.downloader.download(
                    url=url,
                    output_path=self.output_path.text,
                    is_audio=self.format_select.current_value == 'audio',
                    is_playlist=self.playlist_toggle.checked,
                    progress_callback=self.update_progress
                )
                self.status_text.text = "✅ Download completed!"
                self.download_completed = True
                self.download_success = True
            except Exception as e:
                self.status_text.text = f"❌ Download error: {str(e)}"
                self.download_completed = True
                self.download_success = False
            finally:
                get_app().invalidate()
                # Start auto-quit timer
                threading.Timer(5.0, lambda: get_app().exit()).start()

        # Start download in separate thread
        thread = threading.Thread(target=download_thread)
        thread.daemon = True
        thread.start()

    def run(self):
        self.application.run()
