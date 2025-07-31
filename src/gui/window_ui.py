import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
from ..core.downloader import Downloader
from ..utils.config import Config


class WindowUI:
    def __init__(self):
        self.downloader = Downloader()
        self.download_thread = None
        self.config = Config()
        
        # Create the main window
        self.root = tk.Tk()
        self.root.title("YouTube Downloader")
        
        # Load window size from config
        window_size = self.config.get("window_size", "600x500")
        self.root.geometry(window_size)
        self.root.resizable(True, True)
        
        # Set window icon (if available)
        try:
            self.root.iconbitmap("icon.ico")
        except:
            pass
        
        # Configure style and theme
        self.setup_styles()
        
        # Create and pack the GUI elements
        self.create_widgets()
        
        # Apply theme
        self.apply_theme()
        
        # Center the window
        self.center_window()
        
        # Bind window close event
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def setup_styles(self):
        """Configure modern styling for the application"""
        self.style = ttk.Style()
        
        # Configure modern theme
        try:
            self.style.theme_use('clam')
        except:
            pass
        
        # Configure fonts
        self.style.configure('Title.TLabel', font=('Arial', 14, 'bold'))
        self.style.configure('Header.TLabel', font=('Arial', 10, 'bold'))
        self.style.configure('Status.TLabel', font=('Arial', 9))
        
        # Theme colors will be applied in apply_theme()

    def create_widgets(self):
        """Create all GUI widgets"""
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill="both", expand=True)
        
        # Header with title and theme toggle
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill="x", pady=(0, 20))
        
        # Title
        title_label = ttk.Label(header_frame, text="YouTube Downloader", style='Title.TLabel')
        title_label.pack(side="left")
        
        # Theme toggle button
        self.theme_button = ttk.Button(
            header_frame, 
            text="🌙", 
            command=self.toggle_theme,
            width=4
        )
        self.theme_button.pack(side="right", padx=(10, 0))
        
        # URL input section
        self.create_url_section(main_frame)
        
        # Options section
        self.create_options_section(main_frame)
        
        # Output section
        self.create_output_section(main_frame)
        
        # Download button
        self.create_download_section(main_frame)
        
        # Progress section
        self.create_progress_section(main_frame)
        
        # Status section
        self.create_status_section(main_frame)

    def create_url_section(self, parent):
        """Create URL input section"""
        url_frame = ttk.LabelFrame(parent, text="YouTube URL", padding="10")
        url_frame.pack(fill="x", pady=(0, 10))
        
        # URL entry with placeholder
        self.url_var = tk.StringVar()
        self.url_entry = ttk.Entry(url_frame, textvariable=self.url_var, width=60, font=('Arial', 10))
        self.url_entry.pack(fill="x", pady=(0, 5))
        
        # Placeholder text
        self.url_entry.insert(0, "https://www.youtube.com/watch?v=...")
        self.url_entry.bind('<FocusIn>', self.on_url_focus_in)
        self.url_entry.bind('<FocusOut>', self.on_url_focus_out)
        
        # URL validation label
        self.url_validation_label = ttk.Label(url_frame, text="", style='Info.TLabel')
        self.url_validation_label.pack()

    def create_options_section(self, parent):
        """Create download options section"""
        options_frame = ttk.LabelFrame(parent, text="Download Options", padding="10")
        options_frame.pack(fill="x", pady=(0, 10))
        
        # Format selection
        format_frame = ttk.Frame(options_frame)
        format_frame.pack(fill="x", pady=(0, 10))
        
        ttk.Label(format_frame, text="Format:", style='Header.TLabel').pack(anchor="w")
        
        self.format_var = tk.StringVar(value=self.config.get("default_format", "audio"))
        format_radio_frame = ttk.Frame(format_frame)
        format_radio_frame.pack(fill="x", pady=(5, 0))
        
        ttk.Radiobutton(format_radio_frame, text="🎵 Audio Only (MP3)", 
                       variable=self.format_var, value="audio").pack(side="left", padx=(0, 20))
        ttk.Radiobutton(format_radio_frame, text="🎬 Video + Audio", 
                       variable=self.format_var, value="video").pack(side="left")
        
        # Playlist option
        playlist_frame = ttk.Frame(options_frame)
        playlist_frame.pack(fill="x")
        
        self.playlist_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(playlist_frame, text="📑 Download as playlist", 
                       variable=self.playlist_var).pack(anchor="w")

    def create_output_section(self, parent):
        """Create output directory section"""
        output_frame = ttk.LabelFrame(parent, text="Output Directory", padding="10")
        output_frame.pack(fill="x", pady=(0, 10))
        
        # Output path
        output_path_frame = ttk.Frame(output_frame)
        output_path_frame.pack(fill="x")
        
        self.output_var = tk.StringVar(value=self.config.get("output_directory", os.getcwd()))
        self.output_entry = ttk.Entry(output_path_frame, textvariable=self.output_var, width=50)
        self.output_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        ttk.Button(output_path_frame, text="Browse", command=self.browse_output).pack(side="right")

    def create_download_section(self, parent):
        """Create download button section"""
        download_frame = ttk.Frame(parent)
        download_frame.pack(fill="x", pady=10)
        
        self.download_button = ttk.Button(download_frame, text="⬇️ Download", 
                                        command=self.start_download, style='Accent.TButton')
        self.download_button.pack(pady=10)

    def create_progress_section(self, parent):
        """Create progress bar section"""
        progress_frame = ttk.LabelFrame(parent, text="Progress", padding="10")
        progress_frame.pack(fill="x", pady=(0, 10))
        
        # Progress bar
        self.progress_bar = ttk.Progressbar(progress_frame, length=400, mode='determinate')
        self.progress_bar.pack(fill="x", pady=(0, 5))
        
        # Progress text
        self.progress_text = ttk.Label(progress_frame, text="Ready to download", style='Status.TLabel')
        self.progress_text.pack()

    def create_status_section(self, parent):
        """Create status section"""
        status_frame = ttk.LabelFrame(parent, text="Status", padding="10")
        status_frame.pack(fill="both", expand=True)
        
        # Status text
        self.status_text = tk.Text(status_frame, height=6, wrap="word", font=('Consolas', 9))
        status_scrollbar = ttk.Scrollbar(status_frame, orient="vertical", command=self.status_text.yview)
        self.status_text.configure(yscrollcommand=status_scrollbar.set)
        
        self.status_text.pack(side="left", fill="both", expand=True)
        status_scrollbar.pack(side="right", fill="y")
        
        # Clear status button
        clear_button = ttk.Button(status_frame, text="Clear Log", command=self.clear_status)
        clear_button.pack(pady=(5, 0))

    def on_url_focus_in(self, event):
        """Handle URL entry focus in"""
        if self.url_var.get() == "https://www.youtube.com/watch?v=...":
            self.url_entry.delete(0, tk.END)
            self.url_validation_label.config(text="")

    def on_url_focus_out(self, event):
        """Handle URL entry focus out"""
        if not self.url_var.get():
            self.url_entry.insert(0, "https://www.youtube.com/watch?v=...")

    def browse_output(self):
        """Browse for output directory"""
        directory = filedialog.askdirectory(initialdir=self.output_var.get())
        if directory:
            self.output_var.set(directory)
            # Save to config
            self.config.set("output_directory", directory)

    def update_progress(self, d):
        """Update progress bar and status"""
        try:
            if d['status'] == 'downloading':
                # Extract progress percentage
                if d.get('total_bytes'):
                    downloaded = d.get('downloaded_bytes', 0)
                    total = d.get('total_bytes', 0)
                    progress = (downloaded / total * 100) if total > 0 else 0
                else:
                    progress_str = d.get('_percent_str', '0%').replace('%', '')
                    try:
                        progress = float(progress_str)
                    except ValueError:
                        progress = 0
                
                # Update progress bar
                self.progress_bar['value'] = progress
                
                # Update progress text
                filename = os.path.basename(d.get('filename', '')).rsplit('.', 1)[0]
                speed = d.get('speed', 0)
                eta = d.get('eta', 0)
                
                if speed and eta:
                    speed_mb = speed / 1024 / 1024
                    if eta > 60:
                        eta_str = f"{eta // 60}m {eta % 60}s"
                    else:
                        eta_str = f"{eta}s"
                    status_text = f"Downloading: {filename} ({speed_mb:.1f} MB/s, ETA: {eta_str})"
                else:
                    status_text = f"Downloading: {filename}"
                
                self.progress_text.config(text=status_text)
                
                # Update status log
                self.log_status(f"⏬ {status_text}")
                
            elif d['status'] == 'finished':
                filename = os.path.basename(d.get('filename', '')).rsplit('.', 1)[0]
                self.progress_text.config(text=f"Processing: {filename}")
                self.log_status(f"🔄 Processing: {filename}")
                
            elif d['status'] == 'error':
                error_msg = d.get('error', 'Unknown error')
                self.progress_text.config(text=f"Error: {error_msg}")
                self.log_status(f"❌ Error: {error_msg}")
                
        except Exception as e:
            self.log_status(f"❌ Progress update error: {str(e)}")

    def log_status(self, message):
        """Add message to status log"""
        self.status_text.insert(tk.END, f"{message}\n")
        self.status_text.see(tk.END)
        self.root.update_idletasks()

    def clear_status(self):
        """Clear status log"""
        self.status_text.delete(1.0, tk.END)

    def start_download(self):
        """Start the download process"""
        url = self.url_var.get().strip()
        
        # Validate URL
        if not url or url == "https://www.youtube.com/watch?v=...":
            messagebox.showerror("Error", "Please enter a valid YouTube URL")
            return
        
        if not url.startswith(('http://', 'https://')):
            messagebox.showerror("Error", "Please enter a valid URL starting with http:// or https://")
            return
        
        # Validate output directory
        output_dir = self.output_var.get()
        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except Exception as e:
                messagebox.showerror("Error", f"Cannot create output directory: {str(e)}")
                return
        
        # Disable download button
        self.download_button.config(state='disabled')
        self.progress_bar['value'] = 0
        self.progress_text.config(text="Starting download...")
        self.log_status("🚀 Starting download...")
        
        # Start download in separate thread
        self.download_thread = threading.Thread(target=self.download_worker, args=(url,))
        self.download_thread.daemon = True
        self.download_thread.start()

    def download_worker(self, url):
        """Worker thread for download"""
        try:
            self.downloader.download(
                url=url,
                output_path=self.output_var.get(),
                is_audio=self.format_var.get() == "audio",
                is_playlist=self.playlist_var.get(),
                progress_callback=self.update_progress
            )
            
            # Update UI on completion
            self.root.after(0, self.download_completed, True, "Download completed successfully!")
            
        except Exception as e:
            # Update UI on error
            self.root.after(0, self.download_completed, False, f"Download failed: {str(e)}")

    def download_completed(self, success, message):
        """Handle download completion"""
        if success:
            self.progress_text.config(text="✅ Download completed!")
            self.log_status(f"✅ {message}")
            messagebox.showinfo("Success", "Download completed successfully!")
        else:
            self.progress_text.config(text="❌ Download failed")
            self.log_status(f"❌ {message}")
            messagebox.showerror("Error", message)
        
        # Re-enable download button
        self.download_button.config(state='normal')
        self.progress_bar['value'] = 0

    def center_window(self):
        """Center the window on screen"""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')

    def apply_theme(self):
        """Apply the current theme colors"""
        colors = self.config.get_theme_colors()
        
        # Configure style colors
        self.style.configure('TFrame', background=colors['bg'])
        self.style.configure('TLabel', background=colors['bg'], foreground=colors['fg'])
        self.style.configure('TButton', background=colors['button_bg'], foreground=colors['button_fg'])
        self.style.configure('TEntry', fieldbackground=colors['entry_bg'], foreground=colors['entry_fg'])
        self.style.configure('TRadiobutton', background=colors['bg'], foreground=colors['fg'])
        self.style.configure('TCheckbutton', background=colors['bg'], foreground=colors['fg'])
        self.style.configure('TLabelframe', background=colors['frame_bg'])
        self.style.configure('TLabelframe.Label', background=colors['frame_bg'], foreground=colors['fg'])
        self.style.configure('Horizontal.TProgressbar', 
                           background=colors['progress_fg'], 
                           troughcolor=colors['progress_bg'])
        
        # Configure custom styles
        self.style.configure('Success.TLabel', foreground=colors['success_fg'])
        self.style.configure('Error.TLabel', foreground=colors['error_fg'])
        self.style.configure('Warning.TLabel', foreground=colors['warning_fg'])
        self.style.configure('Info.TLabel', foreground=colors['info_fg'])
        
        # Apply colors to root window
        self.root.configure(bg=colors['bg'])
        
        # Update theme button text and ensure proper centering
        current_theme = self.config.get("theme", "dark")
        icon_text = "☀️" if current_theme == "dark" else "🌙"
        self.theme_button.configure(text=icon_text)
        
        # Force update to ensure proper rendering
        self.theme_button.update_idletasks()

    def toggle_theme(self):
        """Toggle between dark and light themes"""
        current_theme = self.config.get("theme", "dark")
        new_theme = "light" if current_theme == "dark" else "dark"
        
        # Save new theme to config
        self.config.set("theme", new_theme)
        
        # Apply the new theme
        self.apply_theme()
        
        # Update all widgets with new colors
        self.update_widget_colors()

    def update_widget_colors(self):
        """Update all widget colors to match current theme"""
        colors = self.config.get_theme_colors()
        
        # Update text widgets
        if hasattr(self, 'status_text'):
            self.status_text.configure(
                bg=colors['text_bg'],
                fg=colors['text_fg'],
                insertbackground=colors['fg']
            )
        
        # Note: ttk.Entry widgets don't support fieldbackground directly
        # The colors are handled by the style configuration in apply_theme()

    def on_closing(self):
        """Handle window closing"""
        # Save window size to config
        geometry = self.root.geometry()
        self.config.set("window_size", geometry)
        
        if self.download_thread and self.download_thread.is_alive():
            if messagebox.askokcancel("Quit", "Download in progress. Are you sure you want to quit?"):
                self.root.destroy()
        else:
            self.root.destroy()

    def run(self):
        """Start the GUI application"""
        self.root.mainloop() 