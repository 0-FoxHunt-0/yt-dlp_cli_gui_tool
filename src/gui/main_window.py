import tkinter as tk
from tkinter import ttk, filedialog
import threading
from ..core.downloader import Downloader

class YoutubeDownloaderGUI:
    def __init__(self, master):
        self.master = master
        self.master.title("YouTube Downloader")
        self.downloader = Downloader()
        
        self.create_widgets()
        self.center_window()

    def create_widgets(self):
        # URL input
        self.url_frame = ttk.LabelFrame(self.master, text="Video URL")
        self.url_frame.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        
        self.url_entry = ttk.Entry(self.url_frame, width=50)
        self.url_entry.grid(row=0, column=0, padx=5, pady=5)

        # Format selection
        self.format_frame = ttk.LabelFrame(self.master, text="Download Options")
        self.format_frame.grid(row=1, column=0, padx=5, pady=5, sticky="ew")
        
        self.format_var = tk.StringVar(value="video")
        self.video_radio = ttk.Radiobutton(self.format_frame, text="Video", 
                                         variable=self.format_var, value="video")
        self.audio_radio = ttk.Radiobutton(self.format_frame, text="Audio Only", 
                                         variable=self.format_var, value="audio")
        
        self.video_radio.grid(row=0, column=0, padx=5, pady=5)
        self.audio_radio.grid(row=0, column=1, padx=5, pady=5)

        # Output directory
        self.output_frame = ttk.LabelFrame(self.master, text="Output Directory")
        self.output_frame.grid(row=2, column=0, padx=5, pady=5, sticky="ew")
        
        self.output_var = tk.StringVar(value=".")
        self.output_entry = ttk.Entry(self.output_frame, 
                                    textvariable=self.output_var, width=40)
        self.browse_button = ttk.Button(self.output_frame, text="Browse", 
                                      command=self.browse_output)
        
        self.output_entry.grid(row=0, column=0, padx=5, pady=5)
        self.browse_button.grid(row=0, column=1, padx=5, pady=5)

        # Download button and progress
        self.download_button = ttk.Button(self.master, text="Download", 
                                        command=self.start_download)
        self.download_button.grid(row=3, column=0, pady=10)

        self.progress_bar = ttk.Progressbar(self.master, length=300, 
                                          mode='determinate')
        self.progress_bar.grid(row=4, column=0, pady=5)

        self.status_label = ttk.Label(self.master, text="")
        self.status_label.grid(row=5, column=0, pady=5)

    def center_window(self):
        self.master.update_idletasks()
        width = self.master.winfo_width()
        height = self.master.winfo_height()
        x = (self.master.winfo_screenwidth() // 2) - (width // 2)
        y = (self.master.winfo_screenheight() // 2) - (height // 2)
        self.master.geometry(f'{width}x{height}+{x}+{y}')

    def browse_output(self):
        directory = filedialog.askdirectory()
        if directory:
            self.output_var.set(directory)

    def start_download(self):
        url = self.url_entry.get()
        if not url:
            self.status_label.config(text="Please enter a URL")
            return

        self.download_button.config(state=tk.DISABLED)
        self.status_label.config(text="Starting download...")
        self.progress_bar['value'] = 0

        thread = threading.Thread(target=self._download_thread, args=(url,))
        thread.daemon = True
        thread.start()

    def _download_thread(self, url):
        try:
            self.downloader.download(
                url=url,
                output_path=self.output_var.get(),
                format_option='bestvideo+bestaudio/best' if self.format_var.get() == 'video' else 'bestaudio/best',
                progress_callback=self.update_progress,
                is_audio_only=self.format_var.get() == 'audio'
            )
            self.master.after(0, lambda: self.status_label.config(text="Download completed!"))
        except Exception as e:
            self.master.after(0, lambda: self.status_label.config(text=f"Error: {str(e)}"))
        finally:
            self.master.after(0, lambda: self.download_button.config(state=tk.NORMAL))

    def update_progress(self, d):
        if d['status'] == 'downloading':
            percent = d.get('_percent_str', '0%').replace('%', '')
            self.master.after(0, lambda: self.progress_bar.configure(value=float(percent)))
            self.master.after(0, lambda: self.status_label.config(text=f"Downloading: {d.get('_percent_str', '0%')}"))
        elif d['status'] == 'finished':
            self.master.after(0, lambda: self.status_label.config(text="Processing..."))