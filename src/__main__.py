#!/usr/bin/env python3
"""
Entry point for yt-dlp-gui command line tool
"""

import argparse
import sys
import signal
from .core.downloader import Downloader
from .gui.terminal_ui import TerminalUI
from .gui.modern_ui import ModernUI


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