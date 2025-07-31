import argparse
import tkinter as tk
from tkinter import ttk, filedialog
import sys
import signal
from src.core.downloader import Downloader
from src.gui.terminal_ui import TerminalUI
from src.gui.modern_ui import ModernUI


class YouTubeDownloaderApp:
    def __init__(self):
        self.downloader = Downloader()

        # Create the main window
        self.root = tk.Tk()
        self.root.title("YouTube Downloader")

        # Create and pack the GUI elements
        self.create_widgets()

        # Center the window
        self.center_window()

    def create_widgets(self):
        # URL input
        url_frame = ttk.LabelFrame(self.root, text="YouTube URL")
        url_frame.pack(padx=5, pady=5, fill="x")

        self.url_entry = ttk.Entry(url_frame, width=50)
        self.url_entry.pack(padx=5, pady=5)

        # Format Selection
        format_frame = ttk.LabelFrame(self.root, text="Format")
        format_frame.pack(padx=5, pady=5, fill="x")

        self.format_var = tk.StringVar(value="audio")
        ttk.Radiobutton(format_frame, text="Audio", variable=self.format_var,
                        value="audio").pack(side="left", padx=5, pady=5)
        ttk.Radiobutton(format_frame, text="Video", variable=self.format_var,
                        value="video").pack(side="left", padx=5, pady=5)

        # Output Directory
        output_frame = ttk.LabelFrame(self.root, text="Output Directory")
        output_frame.pack(padx=5, pady=5, fill="x")

        self.output_var = tk.StringVar(value=".")
        self.output_entry = ttk.Entry(
            output_frame, textvariable=self.output_var, width=40)
        self.output_entry.pack(side="left", padx=5, pady=5)

        ttk.Button(output_frame, text="Browse", command=self.browse_output).pack(
            side="left", padx=5, pady=5)

        # Download Button
        self.download_button = ttk.Button(
            self.root, text="Download", command=self.start_download)
        self.download_button.pack(pady=10)

        # Progress Bar
        self.progress_bar = ttk.Progressbar(
            self.root, length=300, mode='determinate')
        self.progress_bar.pack(pady=5)

        # Status Label
        self.status_label = ttk.Label(self.root, text="")
        self.status_label.pack(pady=5)

    def center_window(self):
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')

    def browse_output(self):
        directory = filedialog.askdirectory()
        if directory:
            self.output_var.set(directory)

    def update_progress(self, d):
        if d['status'] == 'downloading':
            percent = d.get('_percent_str', '0%').replace('%', '')
            self.progress_bar['value'] = float(percent)
            self.status_label['text'] = f"Downloading: {percent}%"
        elif d['status'] == 'finished':
            self.status_label['text'] = "Processing..."

    def start_download(self):
        url = self.url_entry.get()
        if not url:
            self.status_label['text'] = "Please enter a URL"
            return

        self.download_button['state'] = 'disabled'
        self.status_label['text'] = "Starting download..."
        self.progress_bar['value'] = 0

        try:
            self.downloader.download(
                url=url,
                output_path=self.output_var.get(),
                is_audio=self.format_var.get() == "audio",
                progress_callback=self.update_progress
            )
            self.status_label['text'] = "Download completed!"
        except Exception as e:
            self.status_label['text'] = f"Error: {str(e)}"
        finally:
            self.download_button['state'] = 'normal'
            self.progress_bar['value'] = 0


def setup_global_signal_handlers():
    """Set up global signal handlers"""
    def signal_handler(signum, frame):
        print("\n👋 Exiting gracefully...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, signal_handler)

def main():
    # Set up global signal handlers first
    setup_global_signal_handlers()
    
    parser = argparse.ArgumentParser(description='YouTube Downloader')
    parser.add_argument(
        '--url', help='YouTube URL to download directly (skips UI)')
    parser.add_argument('--audio-only', action='store_true',
                        help='Download audio only')
    parser.add_argument('--output', default='.', help='Output directory')
    parser.add_argument('--terminal', action='store_true',
                        help='Use terminal UI instead of modern GUI')

    args = parser.parse_args()

    if args.url:
        # Direct download mode
        downloader = Downloader()
        try:
            downloader.download(args.url, args.output, args.audio_only)
        except KeyboardInterrupt:
            print("\n🛑 Download interrupted. Cleaning up incomplete files...")
            downloader.abort_download()
            print("✅ Cleanup completed. Exiting...")
        except Exception as e:
            print(f"Error: {e}")
    elif args.terminal:
        # Terminal UI mode
        try:
            ui = TerminalUI()
            ui.run()
        except KeyboardInterrupt:
            print("\n👋 Exiting gracefully...")
    else:
        # Default: Modern GUI mode
        try:
            ui = ModernUI()
            ui.run()
        except KeyboardInterrupt:
            print("\n👋 Exiting gracefully...")
        except Exception as e:
            print(f"Error: {e}")


if __name__ == '__main__':
    main()
