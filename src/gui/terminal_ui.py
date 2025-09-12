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
from ..utils.config import Config
import os
import threading


class TerminalUI:
    def __init__(self):
        self.downloader = Downloader()
        self.config = Config()
        self.focusable_elements = []
        self.download_thread = None

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

        # Metadata options
        self.metadata_checkboxes = {}
        metadata_options = [
            ('embed_metadata', '📝 Embed Metadata', True),
            ('embed_thumbnail', '🖼️ Embed Thumbnail', True),
            ('write_thumbnail', '💾 Save Thumbnail', True),
            ('include_author', '👤 Include Author', False),
            ('force_playlist_redownload', '🔄 Force Re-download All', False),
        ]
        
        for key, text, default in metadata_options:
            checkbox = Checkbox(text=text, checked=default)
            self.metadata_checkboxes[key] = checkbox
            self.focusable_elements.append(checkbox)

        # Output path with icon
        self.output_path = TextArea(
            height=1,
            text=self.config.get("output_directory", self.config.get_default_output_directory()),
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
                    Box(
                        body=self.format_select,
                        padding=1,
                        style='class:options-box'
                    ),
                ]),
                padding=1,
                style='class:options-section'
            ),
            Window(height=1),  # Spacing

            # Metadata section
            Box(
                body=HSplit([
                    Label(HTML('<style fg="ansiyellow">Metadata Options:</style>')),
                    VSplit([
                        HSplit([checkbox for checkbox in list(self.metadata_checkboxes.values())[:2]]),
                        Window(width=2),
                        HSplit([checkbox for checkbox in list(self.metadata_checkboxes.values())[2:]]),
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
            "Quit application on Ctrl+C or abort download"
            if self.download_thread and self.download_thread.is_alive():
                # Abort download
                self.downloader.abort_download()
                self.status_text.text = "🛑 Aborting and cleaning up incomplete files..."
                get_app().invalidate()
            else:
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
                # Auto-detect if this is a playlist
                is_playlist = self.is_playlist_url(url)
                
                # Update status with detection result
                if is_playlist:
                    self.status_text.text = "📑 Detected playlist - downloading all videos..."
                else:
                    self.status_text.text = "🎬 Detected single video - downloading..."
                get_app().invalidate()
                
                # Collect metadata options
                metadata_options = {
                    key: checkbox.checked for key, checkbox in self.metadata_checkboxes.items()
                }
                
                # Save output directory to config
                self.config.set("output_directory", self.output_path.text)
                
                self.downloader.download(
                    url=url,
                    output_path=self.output_path.text,
                    is_audio=self.format_select.current_value == 'audio',
                    is_playlist=is_playlist,
                    metadata_options=metadata_options,
                    progress_callback=self.update_progress,
                    force_playlist_redownload=metadata_options.get('force_playlist_redownload', False)
                )
                # Check for error summary
                error_summary = self.downloader.get_error_summary()
                if error_summary:
                    self.status_text.text = f"⚠️ Download completed with issues: {error_summary}"
                else:
                    self.status_text.text = "✅ Download completed!"
                self.download_completed = True
                self.download_success = True
            except Exception as e:
                error_msg = str(e)
                if "aborted" in error_msg.lower():
                    self.status_text.text = "⏹️ Download aborted - incomplete files cleaned up"
                else:
                    # Check for error summary
                    error_summary = self.downloader.get_error_summary()
                    if error_summary:
                        self.status_text.text = f"⚠️ Download completed with errors: {error_summary}"
                    else:
                        self.status_text.text = f"❌ Download error: {error_msg}"
                self.download_completed = True
                self.download_success = False
            finally:
                get_app().invalidate()
                # Start auto-quit timer
                threading.Timer(5.0, lambda: get_app().exit()).start()

        # Start download in separate thread
        self.download_thread = threading.Thread(target=download_thread)
        self.download_thread.daemon = True
        self.download_thread.start()

    def run(self):
        self.application.run()
