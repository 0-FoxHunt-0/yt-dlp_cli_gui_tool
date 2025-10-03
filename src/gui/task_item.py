import os
import json
import threading
from tkinter import filedialog, messagebox
import customtkinter as ctk
from typing import TYPE_CHECKING

from ..core.downloader import Downloader

if TYPE_CHECKING:
    from .modern_ui import ModernUI


class TaskItem:
    """Represents a single download task with its own controls, progress, and terminal"""
    def __init__(self, ui: 'ModernUI', parent_frame, default_output: str):
        self.ui = ui
        self.frame = ctk.CTkFrame(parent_frame)
        self.frame.pack(fill="x", pady=(0, 10))

        # Per-task state
        self.downloader = Downloader()
        self.thread = None
        self.is_running = False
        self._aborted = False
        self._destroyed = False
        # M3U tracking for finalization
        self._m3u_playlist_dir = None
        self._m3u_playlist_title = None
        # Playlist context for clearer logs
        self._current_playlist_title = None
        self._current_playlist_total = 0
        self._is_playlist_task = False

        # Header row with title and remove button
        header = ctk.CTkFrame(self.frame, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(10, 5))

        self.title_label = ctk.CTkLabel(header, text="Task", font=ctk.CTkFont(size=13, weight="bold"))
        self.title_label.pack(side="left")

        header_btns = ctk.CTkFrame(header, fg_color="transparent")
        header_btns.pack(side="right")

        self.start_btn = ctk.CTkButton(header_btns, text="▶ Start", width=80, height=30, command=self.start)
        self.start_btn.pack(side="left", padx=(0, 6))

        self.abort_btn = ctk.CTkButton(header_btns, text="⏹ Abort", width=80, height=30,
                                       fg_color=("red", "darkred"), hover_color=("darkred", "red"),
                                       command=self.abort)
        self.abort_btn.pack(side="left", padx=(0, 6))
        self.abort_btn.configure(state="disabled")

        remove_btn = ctk.CTkButton(header_btns, text="🗑 Remove", width=90, height=30,
                                   fg_color=("gray70", "gray30"), hover_color=("gray60", "gray40"),
                                   command=lambda: self.ui.remove_task(self))
        remove_btn.pack(side="left")

        # URL row
        url_row = ctk.CTkFrame(self.frame, fg_color="transparent")
        url_row.pack(fill="x", padx=10, pady=5)

        url_label = ctk.CTkLabel(url_row, text="URL:")
        url_label.pack(side="left", padx=(0, 8))

        self.url_var = ctk.StringVar(value="")
        self.url_entry = ctk.CTkEntry(url_row, textvariable=self.url_var, placeholder_text="https://www.youtube.com/watch?v=...", height=32)
        self.url_entry.pack(side="left", fill="x", expand=True)

        # Format row (per task)
        fmt_row = ctk.CTkFrame(self.frame, fg_color="transparent")
        fmt_row.pack(fill="x", padx=10, pady=5)

        fmt_label = ctk.CTkLabel(fmt_row, text="Format:")
        fmt_label.pack(side="left", padx=(0, 8))

        # Use default format from config (global section removed)
        self.format_var = ctk.StringVar(value=self.ui.config.get("default_format", "audio"))
        fmt_radios = ctk.CTkFrame(fmt_row, fg_color="transparent")
        fmt_radios.pack(side="left")
        audio_radio = ctk.CTkRadioButton(fmt_radios, text="🎵 Audio (MP3)", variable=self.format_var, value="audio")
        video_radio = ctk.CTkRadioButton(fmt_radios, text="🎬 Video", variable=self.format_var, value="video")
        audio_radio.pack(side="left", padx=(0, 12))
        video_radio.pack(side="left")

        # Output row
        out_row = ctk.CTkFrame(self.frame, fg_color="transparent")
        out_row.pack(fill="x", padx=10, pady=5)

        out_label = ctk.CTkLabel(out_row, text="Output:")
        out_label.pack(side="left", padx=(0, 8))

        self.output_var = ctk.StringVar(value=default_output)
        self.output_entry = ctk.CTkEntry(out_row, textvariable=self.output_var, height=32)
        self.output_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        browse_btn = ctk.CTkButton(out_row, text="Browse", width=80, height=32, command=self._browse_output)
        browse_btn.pack(side="left")

        # Progress
        prog_row = ctk.CTkFrame(self.frame, fg_color="transparent")
        prog_row.pack(fill="x", padx=10, pady=(5, 5))

        self.progress_bar = ctk.CTkProgressBar(prog_row)
        self.progress_bar.pack(fill="x")
        self.progress_bar.set(0)

        self.progress_text = ctk.CTkLabel(self.frame, text="Waiting", font=ctk.CTkFont(size=12))
        self.progress_text.pack(anchor="w", padx=10)

        # Terminal / Status
        self.status_text = ctk.CTkTextbox(self.frame, height=130, font=ctk.CTkFont(size=11, family="Consolas"))
        self.status_text.pack(fill="x", padx=10, pady=(5, 6))

        clear_btn = ctk.CTkButton(self.frame, text="Clear Log", width=100, height=28, command=self._clear_status)
        clear_btn.pack(anchor="w", padx=10, pady=(0, 10))

        # Internal tracking for throttled logging
        self._last_logged_progress = 0
        self._last_logged_filename = ""
        self._logged_item_filenames = set()

    def _run_on_ui(self, fn):
        """Schedule a callable to run on the Tk main thread safely."""
        try:
            if not self._is_alive():
                return
            self.ui.root.after(0, lambda: fn() if self._is_alive() else None)
        except Exception:
            pass

    def update_title(self, text: str):
        self.title_label.configure(text=text)

    def get_url(self) -> str:
        return self.url_var.get().strip()

    def _browse_output(self):
        directory = filedialog.askdirectory(initialdir=self.output_var.get())
        if directory:
            self.output_var.set(directory)
            # Also store as default for future tasks
            self.ui._save_output_directory(directory)

    def _clear_status(self):
        try:
            self.status_text.delete("0.0", "end")
        except Exception:
            pass

    def _is_alive(self) -> bool:
        try:
            return (not self._destroyed) and self.frame.winfo_exists()
        except Exception:
            return False

    def _set_progress_text_safe(self, text: str):
        if not self._is_alive():
            return
        def _apply():
            try:
                if self._is_alive():
                    self.progress_text.configure(text=text)
            except Exception:
                pass
        self._run_on_ui(_apply)

    def log(self, message: str):
        if not self._is_alive():
            return
        def _append():
            try:
                if self._is_alive():
                    self.status_text.insert("end", f"{message}\n")
                    self.status_text.see("end")
            except Exception:
                pass
        self._run_on_ui(_append)

    def start(self):
        if self.is_running:
            return
        url = self.get_url()
        if not url or not url.startswith(("http://", "https://")):
            messagebox.showerror("Error", "Please enter a valid URL starting with http:// or https://")
            return
        output_dir = self.output_var.get().strip()
        if not output_dir:
            messagebox.showerror("Error", "Please choose an output directory")
            return
        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except Exception as e:
                messagebox.showerror("Error", f"Cannot create output directory: {e}")
                return

        # Detect playlist for early feedback
        is_playlist = self._is_playlist_url(url)
        self._is_playlist_task = bool(is_playlist)
        if is_playlist:
            self.progress_text.configure(text="📑 Detected playlist - preparing...")
            self.log("📑 Detected playlist URL - will download all videos")
        else:
            self.progress_text.configure(text="🎬 Detected single video - preparing...")
            self.log("🎬 Detected single video URL")

        # Build metadata options from global UI
        metadata_options = {key: var.get() for key, var in self.ui.metadata_vars.items()}
        is_audio = self.format_var.get() == "audio"

        # Switch buttons
        self.start_btn.configure(state="disabled")
        self.abort_btn.configure(state="normal")
        self.progress_bar.set(0)
        self._last_logged_progress = 0
        self._last_logged_filename = ""
        self._aborted = False
        # Context log for clarity across multiple tasks
        try:
            cookie_file_cfg = self.ui.config.get("cookie_file", "") or ""
            cookie_used = cookie_file_cfg.strip()
        except Exception:
            cookie_used = ""
        self.log(f"🚀 Starting download | URL: {url}\n   Format: {'audio' if is_audio else 'video'} | Output: {output_dir}\n   Cookies: {'yes' if cookie_used else 'no'}")

        def worker():
            try:
                # Try to get quick playlist size and title for UX
                if is_playlist:
                    try:
                        import yt_dlp
                        with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True}) as ydl:
                            info = ydl.extract_info(url, download=False)
                            if info and 'entries' in info:
                                valid_entries = [e for e in info['entries'] if e is not None]
                                total = len(valid_entries)
                                # Capture playlist title for clearer logs
                                pl_title = info.get('title', 'Unknown Playlist')
                                # Store for end-of-download logging
                                self._current_playlist_title = pl_title
                                self._current_playlist_total = total
                                # Log a clear start banner for the playlist
                                self.ui.root.after(0, lambda: self.log(f"📑 Playlist start: {pl_title} ({total} videos)"))
                                self.ui.root.after(0, lambda: self._set_progress_text_safe(f"📋 Playlist: {total} videos"))

                                # Pre-create playlist directory and reconcile existing M3U if requested
                                try:
                                    enabled_var = self.ui.metadata_vars.get('create_m3u', None)
                                    if enabled_var and enabled_var.get():
                                        playlist_dir = self._compute_playlist_directory(output_dir, pl_title)
                                        os.makedirs(playlist_dir, exist_ok=True)
                                        self._m3u_playlist_dir = playlist_dir
                                        self._m3u_playlist_title = pl_title
                                        expected = []
                                        for idx, entry in enumerate(valid_entries, start=1):
                                            try:
                                                expected.append({
                                                    'index': idx,
                                                    'id': entry.get('id'),
                                                    'title': entry.get('title')
                                                })
                                            except Exception:
                                                pass
                                        self._reconcile_existing_playlist_m3u(playlist_dir, pl_title, expected)
                                except Exception:
                                    pass
                    except Exception:
                        pass

                # Get cookie file from UI config
                cookie_file = self.ui.config.get("cookie_file", "")
                if cookie_file:
                    cookie_file = cookie_file.strip()

                result_code = self.downloader.download(
                    url=url,
                    output_path=output_dir,
                    is_audio=is_audio,
                    is_playlist=is_playlist,
                    metadata_options=metadata_options,
                    progress_callback=self._update_progress,
                    cookie_file=cookie_file if cookie_file else None,
                    force_playlist_redownload=metadata_options.get('force_playlist_redownload', False)
                )
                # Consider success only if yt-dlp returned 0 (no errors)
                is_success = (result_code == 0) or (is_playlist and result_code in (0, None))
                self.ui.root.after(0, lambda: self._completed(is_success, "Download completed successfully!" if is_success else "Download failed"))
            except Exception as e:
                # Normalize aborts vs errors
                msg = str(e) if e is not None else ""
                # Only treat as user abort if an explicit abort was requested
                if (msg and 'aborted' in msg.lower()) and getattr(self.downloader, '_user_abort_requested', False):
                    self.ui.root.after(0, lambda: self._completed(False, "Download aborted by user"))
                else:
                    display = msg if msg else "Unknown error"
                    self.ui.root.after(0, lambda: self._completed(False, f"Download failed: {display}"))

        self.thread = threading.Thread(target=worker, daemon=True)
        self.is_running = True
        self.thread.start()

    def abort(self):
        if self.is_running:
            try:
                self._aborted = True
                self.log("🛑 Abort requested...")
                self._set_progress_text_safe("⏹️ Aborting...")

                # Call downloader abort first
                self.downloader.abort_download()

                # Wait a short time for graceful shutdown
                import time
                time.sleep(0.5)

                # If thread is still alive after abort, try to force termination
                if self.thread and self.thread.is_alive():
                    self.log("⚠️ Thread still running, attempting force termination...")
                    try:
                        # Try to raise KeyboardInterrupt in the thread
                        import ctypes
                        if hasattr(ctypes, 'pythonapi'):
                            thread_id = self.thread.ident
                            if thread_id:
                                ctypes.pythonapi.PyThreadState_SetAsyncExc(
                                    ctypes.c_long(thread_id),
                                    ctypes.py_object(KeyboardInterrupt)
                                )
                                self.log("✅ Force termination signal sent to thread")
                    except Exception as e:
                        self.log(f"⚠️ Could not force terminate thread: {e}")

            except Exception as e:
                self.log(f"⚠️ Error during abort: {e}")

    def destroy(self):
        try:
            self._destroyed = True
            self.frame.destroy()
        except Exception:
            pass

    def _is_playlist_url(self, url: str) -> bool:
        import re
        patterns = [r'[?&]list=([^&]+)', r'playlist\?list=([^&]+)', r'watch\?v=[^&]+&list=([^&]+)']
        if any(re.search(p, url) for p in patterns):
            return True
        if 'youtube.com/playlist' in url or 'youtube.com/watch?list=' in url:
            return True
        return False

    def _update_progress(self, d):
        if not self._is_alive():
            return
        try:
            if d.get('status') == 'downloading':
                # Compute progress safely off the UI thread
                if d.get('total_bytes'):
                    downloaded = d.get('downloaded_bytes', 0)
                    total = d.get('total_bytes', 0)
                    progress = (downloaded / total) if total > 0 else 0
                else:
                    progress_str = d.get('_percent_str', '0%').replace('%', '')
                    try:
                        progress = float(progress_str) / 100
                    except ValueError:
                        progress = 0

                filename = os.path.basename(d.get('filename', '')).rsplit('.', 1)[0]
                speed = d.get('speed', 0)
                eta = d.get('eta', 0)
                if speed and eta:
                    speed_mb = speed / 1024 / 1024
                    eta_str = f"{eta // 60}m {eta % 60}s" if eta > 60 else f"{eta}s"
                    status_text = f"Downloading: {filename} ({speed_mb:.1f} MB/s, ETA: {eta_str})"
                else:
                    status_text = f"Downloading: {filename}"

                # Apply UI updates on main thread
                self._run_on_ui(lambda: self.progress_bar.set(progress))
                self._set_progress_text_safe(status_text)

                # Per-item start log (once per file)
                try:
                    if filename and filename not in self._logged_item_filenames:
                        info = d.get('info_dict', {}) or {}
                        pl_idx = info.get('playlist_index')
                        n_entries = info.get('n_entries') or info.get('playlist_count') or self._current_playlist_total or None
                        vid_title = info.get('title') or filename
                        pl_title = info.get('playlist_title') or info.get('playlist') or self._current_playlist_title or None
                        if pl_idx and n_entries:
                            self.log(f"▶ Starting: [{int(pl_idx)}/{int(n_entries)}] {vid_title}" + (f" — Playlist: {pl_title}" if pl_title else ""))
                        else:
                            self.log(f"▶ Starting: {vid_title}")
                        self._logged_item_filenames.add(filename)
                except Exception:
                    pass

                # Throttled logging
                progress_percent = progress * 100
                if (progress_percent - self._last_logged_progress >= 5.0 or filename != self._last_logged_filename):
                    self.log(f"⏬ {status_text}")
                    self._last_logged_progress = progress_percent
                    self._last_logged_filename = filename

            elif d.get('status') == 'finished':
                filename = os.path.basename(d.get('filename', '')).rsplit('.', 1)[0]
                self._set_progress_text_safe(f"Processing: {filename}")
                self.log(f"🔄 Processing: {filename}")
                # Per-item finish log with index if available
                try:
                    info = d.get('info_dict', {}) or {}
                    pl_idx = info.get('playlist_index')
                    n_entries = info.get('n_entries') or info.get('playlist_count') or self._current_playlist_total or None
                    vid_title = info.get('title') or filename
                    if pl_idx and n_entries:
                        self.log(f"✅ Finished item: [{int(pl_idx)}/{int(n_entries)}] {vid_title}")
                except Exception:
                    pass
                self._last_logged_progress = 0
                self._last_logged_filename = ""

                # Attempt M3U incremental update when a file finishes a stage
                try:
                    self._maybe_update_m3u(d)
                except Exception:
                    pass

            # Postprocessor hooks deliver final filepaths
            elif d.get('status') == 'postprocessor':
                try:
                    # Some postprocessors report 'filepath' field
                    if d.get('info_dict') or d.get('filepath'):
                        self._maybe_update_m3u(d)
                except Exception:
                    pass

            elif d.get('status') == 'error':
                error_msg = d.get('error', 'Unknown error')
                self._set_progress_text_safe(f"Error: {error_msg}")
                self.log(f"❌ Error: {error_msg}")
        except Exception as e:
            self.log(f"❌ Progress update error: {e}")

    def _completed(self, success: bool, message: str):
        if not self._is_alive():
            return
        try:
            # Final playlist banner for clarity
            try:
                if self._is_playlist_task:
                    pl_title = self._current_playlist_title or "Playlist"
                    # Attempt to summarize counts from downloader if available
                    progress = {}
                    try:
                        progress = self.downloader.get_playlist_progress() or {}
                    except Exception:
                        progress = {}
                    total = progress.get('total', self._current_playlist_total)
                    downloaded = progress.get('downloaded')
                    failed = progress.get('failed')
                    skipped = progress.get('skipped')
                    summary_bits = []
                    if downloaded is not None:
                        summary_bits.append(f"downloaded {downloaded}")
                    if skipped is not None:
                        summary_bits.append(f"skipped {skipped}")
                    if failed is not None:
                        summary_bits.append(f"failed {failed}")
                    summary = (", ".join(summary_bits)) if summary_bits else ""
                    if total:
                        self.log(f"📦 Playlist end: {pl_title} ({total} videos){' — ' + summary if summary else ''}")
                    else:
                        self.log(f"📦 Playlist end: {pl_title}{' — ' + summary if summary else ''}")
            except Exception:
                pass

            error_summary = self.downloader.get_error_summary()
            if success:
                if error_summary:
                    self._set_progress_text_safe("⚠️ Completed with issues")
                    self.log(f"⚠️ Completed with issues: {error_summary}")
                else:
                    self._set_progress_text_safe("✅ Completed")
                    self.log(f"✅ {message}")
            else:
                if "aborted" in message.lower():
                    self._set_progress_text_safe("⏹️ Aborted")
                    self.log(f"⏹️ {message}")
                else:
                    if error_summary:
                        self._set_progress_text_safe("⚠️ Completed with errors")
                        self.log(f"⚠️ Completed with errors: {error_summary}")
                    else:
                        self._set_progress_text_safe("❌ Failed")
                        self.log(f"❌ {message}")
                # Do not show modal error popups; errors are logged in the task terminal only

            # Restore buttons/state
            try:
                self.abort_btn.configure(state="disabled")
                self.start_btn.configure(state="normal")
            except Exception:
                pass
            self.is_running = False

        except Exception:
            # If anything fails during completion (likely due to destroyed widgets), just exit quietly
            pass

        # Finalize M3U: ensure file is written even if last hook missed
        try:
            enabled_var = self.ui.metadata_vars.get('create_m3u', None)
            if enabled_var and enabled_var.get():
                target_dir = self._m3u_playlist_dir
                if not target_dir:
                    try:
                        out_dir = self.output_var.get().strip()
                        if out_dir and os.path.isdir(out_dir):
                            target_dir = out_dir
                    except Exception:
                        pass
                if target_dir:
                    self._write_m3u_from_state(target_dir, self._m3u_playlist_title)
                    self.log("📄 M3U playlist updated.")
        except Exception:
            pass

    # ===== M3U helpers =====
    def _sanitize_name(self, name: str) -> str:
        try:
            if not name:
                return ""
            import re
            return re.sub(r'[<>:"/\\|?*]', '_', name)
        except Exception:
            return name or ""

    def _maybe_update_m3u(self, d: dict):
        # Check toggle
        try:
            enabled_var = self.ui.metadata_vars.get('create_m3u', None)
            if not enabled_var or not enabled_var.get():
                return
        except Exception:
            return

        info = d.get('info_dict', {}) or {}
        # Prefer final filepath reported by postprocessor; fallback to filename
        final_path = info.get('filepath') or d.get('filepath') or d.get('filename')
        if not final_path:
            return
        directory = os.path.dirname(final_path)
        playlist_title = info.get('playlist_title') or info.get('playlist') or ''
        total = info.get('n_entries') or info.get('playlist_count') or 0
        video_id = info.get('id')
        title = info.get('title')

        # Update state and M3U
        try:
            state = self._load_state(directory)
            if playlist_title:
                state['playlist_title'] = playlist_title
            if total:
                try:
                    state['total_entries'] = max(int(total), int(state.get('total_entries', 0) or 0))
                except Exception:
                    pass
            entries = state.setdefault('entries', {})
            pl_index = info.get('playlist_index')
            if pl_index:
                key = str(int(pl_index))
                entries[key] = {
                    'id': video_id,
                    'title': title,
                    'path': final_path
                }
            else:
                # No index available; temporarily store under a special key to be appended later
                tmp_key = f"_extra_{video_id or os.path.basename(final_path)}"
                entries[tmp_key] = {
                    'id': video_id,
                    'title': title,
                    'path': final_path
                }
            self._save_state(directory, state)
            self._write_m3u_from_state(directory, playlist_title)
        except Exception:
            pass

    def _compute_playlist_directory(self, output_dir: str, playlist_title: str) -> str:
        safe_title = self._sanitize_name(playlist_title or 'Unknown_Playlist')
        return os.path.join(output_dir, safe_title)

    def _state_path(self, directory: str) -> str:
        return os.path.join(directory, ".playlist_state.json")

    def _load_state(self, directory: str) -> dict:
        try:
            path = self._state_path(directory)
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return {"playlist_title": None, "total_entries": 0, "entries": {}}

    def _save_state(self, directory: str, state: dict):
        try:
            path = self._state_path(directory)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _m3u_path(self, directory: str, playlist_title: str = None) -> str:
        try:
            base = os.path.basename(directory).strip() or (playlist_title or "playlist")
        except Exception:
            base = (playlist_title or "playlist")
        safe = self._sanitize_name(base)
        # If user wants M3U in parent folder, place it there
        try:
            to_parent = self.ui.metadata_vars.get('m3u_to_parent', None)
            if to_parent and to_parent.get():
                parent_dir = os.path.dirname(directory.rstrip(os.sep)) or directory
                return os.path.join(parent_dir, f"{safe}.m3u")
        except Exception:
            pass
        return os.path.join(directory, f"{safe}.m3u")

    def _write_m3u_from_state(self, directory: str, playlist_title: str = None):
        state = self._load_state(directory)
        # Merge provided playlist_title
        if playlist_title and not state.get("playlist_title"):
            state["playlist_title"] = playlist_title

        # Build ordered list by playlist index
        try:
            entries = state.get("entries", {})
            ordered = []
            for k, v in entries.items():
                try:
                    ordered.append((int(k), v))
                except Exception:
                    pass
            ordered.sort(key=lambda x: x[0])

            # Prepare lines (relative paths)
            lines = []
            included_abs_paths = set()
            for _, meta in ordered:
                path = meta.get('path')
                if not path or not os.path.exists(path):
                    continue
                try:
                    abs_path = os.path.abspath(path)
                    included_abs_paths.add(abs_path)
                except Exception:
                    pass
                # For parent placement, keep paths relative to the M3U file location
                try:
                    target_m3u_dir = os.path.dirname(self._m3u_path(directory, state.get("playlist_title")))
                    rel = os.path.relpath(path, target_m3u_dir)
                except Exception:
                    rel = path
                lines.append(rel.replace('\\', '/'))

            # Also append any temp extras captured without an index
            try:
                for k, meta in list(state.get('entries', {}).items()):
                    if not isinstance(k, str) or not k.startswith('_extra_'):
                        continue
                    path = meta.get('path')
                    if not path or not os.path.exists(path):
                        continue
                    try:
                        abs_path = os.path.abspath(path)
                        if abs_path in included_abs_paths:
                            continue
                        included_abs_paths.add(abs_path)
                        target_m3u_dir = os.path.dirname(self._m3u_path(directory, state.get("playlist_title")))
                        rel = os.path.relpath(path, target_m3u_dir)
                    except Exception:
                        rel = path
                    lines.append(rel.replace('\\', '/'))
            except Exception:
                pass

            # Fallback: append any media files present in directory but missing from expected list
            try:
                media_exts = ('.mp3', '.m4a', '.flac', '.ogg', '.wav', '.mp4', '.mkv', '.webm')
                dir_entries = []
                for fn in os.listdir(directory):
                    fp = os.path.join(directory, fn)
                    if os.path.isfile(fp) and fn.lower().endswith(media_exts):
                        try:
                            abs_fp = os.path.abspath(fp)
                            if abs_fp not in included_abs_paths:
                                dir_entries.append(fp)
                        except Exception:
                            pass
                # Deterministic order for extras: alphabetical by filename
                dir_entries.sort(key=lambda p: os.path.basename(p).lower())
                for fp in dir_entries:
                    try:
                        target_m3u_dir = os.path.dirname(self._m3u_path(directory, state.get("playlist_title")))
                        rel = os.path.relpath(fp, target_m3u_dir)
                    except Exception:
                        rel = fp
                    lines.append(rel.replace('\\', '/'))
            except Exception:
                pass

            m3u_file = self._m3u_path(directory, state.get("playlist_title"))
            with open(m3u_file, 'w', encoding='utf-8') as f:
                f.write("#EXTM3U\n")
                for rel in lines:
                    # Basic M3U without EXTINF duration; Samsung Music accepts plain entries
                    f.write(f"{rel}\n")
        except Exception:
            pass

    def _reconcile_existing_playlist_m3u(self, directory: str, playlist_title: str, expected_entries: list):
        """Seed or fix M3U before download by matching existing files to expected order."""
        try:
            state = self._load_state(directory)
            state['playlist_title'] = playlist_title or state.get('playlist_title') or ''
            state['total_entries'] = max(state.get('total_entries', 0) or 0, len(expected_entries))

            # Build quick lookup by sanitized title stem
            expected_by_stem = {}
            for item in expected_entries:
                title = item.get('title') or ''
                stem = self._sanitize_name(title).lower()
                expected_by_stem[stem] = item

            # Scan directory for media files
            media_exts = ('.mp3', '.m4a', '.flac', '.ogg', '.wav', '.mp4', '.mkv', '.webm')
            for root, _, files in os.walk(directory):
                if os.path.abspath(root) != os.path.abspath(directory):
                    continue
                for fn in files:
                    if not fn.lower().endswith(media_exts):
                        continue
                    stem = os.path.splitext(fn)[0].lower()
                    # Find best match by prefix or equality
                    match = None
                    if stem in expected_by_stem:
                        match = expected_by_stem[stem]
                    else:
                        for key, item in expected_by_stem.items():
                            if stem.startswith(key[:50]):
                                match = item
                                break
                    if match:
                        idx = int(match.get('index') or 0)
                        if idx > 0:
                            path = os.path.join(directory, fn)
                            state.setdefault('entries', {})[str(idx)] = {
                                'id': match.get('id'),
                                'title': match.get('title'),
                                'path': path
                            }
            self._save_state(directory, state)
            self._write_m3u_from_state(directory, playlist_title)
        except Exception:
            pass

