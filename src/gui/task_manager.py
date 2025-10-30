"""
Task Manager Module

Manages task creation, operations, and state.
Handles task persistence and restoration from configuration.
"""

import os


class TaskManager:
    """Manages task creation, operations, and state"""

    def __init__(self, ui, config, widget_factory):
        self.ui = ui
        self.config = config
        self.widget_factory = widget_factory
        self.tasks = []
        self._restoring_tasks = False
        self._persist_after_id = None  # For debouncing task persistence

    def add_task(self, url="", parent_frame=None):
        """Add a new task"""
        if parent_frame is None:
            parent_frame = self.ui.ui_manager.get_tasks_list_frame()

        # Default to the process current working directory for newly added tasks
        # but keep config-based defaults when restoring from saved state
        if not self._restoring_tasks:
            try:
                default_output = os.getcwd()
            except Exception:
                default_output = self.config.get("output_directory", self.config.get_default_output_directory())
        else:
            default_output = self.config.get("output_directory", self.config.get_default_output_directory())

        # Import here to avoid circular imports
        from .task_item import TaskItem
        task = TaskItem(self.ui, parent_frame=parent_frame, default_output=default_output)
        self.tasks.append(task)

        # Defer color updates and bindings during bulk restoration for better performance
        if not self._restoring_tasks:
            # Update task colors to match current theme
            task.update_colors()
            # Attach bindings for persistence BEFORE setting URL
            self.ui._attach_task_bindings(task)
        else:
            # During restoration, defer these operations to avoid blocking UI
            # They will be applied after all tasks are created
            pass

        # Set URL if provided (this will trigger persistence if not restoring)
        try:
            if url:
                task.url_var.set(url)
                # Update video info for new tasks (not during restoration)
                if not self._restoring_tasks and hasattr(task, 'update_video_info'):
                    task.update_video_info(url, force=True)
        except Exception:
            pass

        # Re-number task titles
        for idx, t in enumerate(self.tasks, start=1):
            t.update_title(f"Task {idx}")

        return task

    def remove_task(self, task):
        """Remove a task"""
        try:
            if task in self.tasks:
                # Abort if running
                if task.is_running:
                    task.abort()
                task.destroy()
                self.tasks.remove(task)
                # Re-number remaining tasks
                for idx, t in enumerate(self.tasks, start=1):
                    t.update_title(f"Task {idx}")
        except Exception:
            pass

    def restore_tasks_from_config(self):
        """Restore tasks from configuration"""
        try:
            self._restoring_tasks = True
            tasks_data = self.config.get("tasks", []) or []

            if tasks_data:
                # New structured storage path
                for item in tasks_data:
                    try:
                        url_value = (item.get("url") or "").strip()
                        fmt_value = (item.get("format") or self.config.get("default_format", "audio")).strip()
                        output_value = item.get("output") or self.config.get("output_directory", self.config.get_default_output_directory())

                        # Extract video/playlist info
                        video_name = item.get("video_name", "")
                        playlist_name = item.get("playlist_name", "")
                        is_playlist = item.get("is_playlist", False)

                        task = self.add_task(url=url_value)

                        # Set video/playlist info
                        if hasattr(task, 'video_name'):
                            task.video_name = video_name
                        if hasattr(task, 'playlist_name'):
                            task.playlist_name = playlist_name
                        if hasattr(task, 'is_playlist'):
                            task.is_playlist = is_playlist

                        # Update subtitle with video/playlist name (skip URL analysis during restoration)
                        display_name = playlist_name if is_playlist and playlist_name else video_name
                        if display_name:
                            task.update_subtitle(display_name)
                        # Skip URL analysis during restoration to avoid crashes
                        # elif url_value:
                        #     if hasattr(task, 'update_video_info'):
                        #         task.update_video_info(url_value, force=True)

                        try:
                            task.format_var.set(fmt_value if fmt_value in ("audio", "video") else self.config.get("default_format", "audio"))
                        except Exception:
                            pass
                        try:
                            if output_value:
                                task.output_var.set(output_value)
                        except Exception:
                            pass
                    except Exception as e:
                        # Log error but continue with other tasks
                        print(f"Error restoring task: {e}")
                        # Fallback: add an empty task if malformed
                        try:
                            self.add_task(url="")
                        except Exception:
                            pass
            else:
                # Backwards compatibility with older settings
                urls = self.config.get("task_urls", []) or []
                count = self.config.get("tasks_count", 1)
                try:
                    count = int(count)
                except Exception:
                    count = 1
                if count < 1:
                    count = 1

                for i in range(count):
                    url_value = urls[i] if i < len(urls) else ""
                    try:
                        self.add_task(url=url_value)
                    except Exception as e:
                        print(f"Error adding task {i}: {e}")
                        try:
                            self.add_task(url="")
                        except Exception:
                            pass
        except Exception as e:
            # Critical error in restoration - log and continue with empty task
            print(f"Critical error during task restoration: {e}")
            try:
                self.add_task(url="")
            except Exception:
                pass
        finally:
            self._restoring_tasks = False

            # Apply deferred operations after all tasks are created for better performance
            if tasks_data:
                try:
                    # Batch apply colors and bindings to all tasks
                    for task in self.tasks:
                        try:
                            task.finalize_gui_setup()  # Finalize GUI setup first
                            task.update_colors()
                            self.ui._attach_task_bindings(task)
                        except Exception as e:
                            print(f"Error applying deferred operations to task: {e}")
                except Exception as e:
                    print(f"Error during deferred task operations: {e}")

            # Don't persist immediately after restore to avoid overwriting restored data

    def _attach_task_bindings(self, task):
        """Attach listeners to task inputs for persistence"""
        try:
            # Create a closure that captures the task reference
            def make_url_callback(t):
                return lambda *args: self._on_task_changed(t, "url")

            def make_output_callback(t):
                return lambda *args: self._on_task_changed(t, "output")

            def make_format_callback(t):
                return lambda *args: self._on_task_changed(t, "format")

            task.url_var.trace_add("write", make_url_callback(task))
            task.output_var.trace_add("write", make_output_callback(task))
            task.format_var.trace_add("write", make_format_callback(task))
        except Exception:
            pass

    def _on_task_changed(self, task, change_type):
        """Handle changes to task variables"""
        if getattr(self, '_restoring_tasks', False):
            return

        # Update video info if URL changed
        if change_type == "url":
            url = task.get_url()
            if url and hasattr(task, 'update_video_info'):
                task.update_video_info(url, force=True)

        # Schedule persistence for all changes
        self._schedule_persist_tasks()

    def _schedule_persist_tasks(self):
        """Schedule task persistence to avoid too frequent writes"""
        try:
            if self._persist_after_id is not None:
                try:
                    self.ui.root.after_cancel(self._persist_after_id)
                except Exception:
                    pass
            # Debounce saves to avoid excessive disk writes
            self._persist_after_id = self.ui.root.after(300, self._persist_tasks_to_config)
        except Exception:
            # Fallback to immediate persist
            self._persist_tasks_to_config()

    def _persist_tasks_to_config(self):
        """Save current tasks count and URLs to config"""
        try:
            # Build structured tasks array
            tasks_array = []
            for t in self.tasks:
                try:
                    tasks_array.append({
                        "url": t.get_url(),
                        "format": t.format_var.get() if hasattr(t, 'format_var') else self.config.get("default_format", "audio"),
                        "output": t.output_var.get() if hasattr(t, 'output_var') else self.config.get("output_directory", self.config.get_default_output_directory()),
                        "video_name": getattr(t, 'video_name', ""),
                        "playlist_name": getattr(t, 'playlist_name', ""),
                        "is_playlist": getattr(t, 'is_playlist', False)
                    })
                except Exception:
                    tasks_array.append({
                        "url": "",
                        "format": self.config.get("default_format", "audio"),
                        "output": self.config.get("output_directory", self.config.get_default_output_directory()),
                        "video_name": "",
                        "playlist_name": "",
                        "is_playlist": False
                    })

            # Store new structure
            self.config.settings["tasks"] = tasks_array
            # Maintain backwards-compatible fields
            self.config.settings["task_urls"] = [t.get("url", "") for t in tasks_array]
            self.config.settings["tasks_count"] = len(tasks_array)
            self.config.save_settings()

        except Exception as e:
            print(f"Error persisting tasks: {e}")

    def run_all_tasks(self):
        """Start all tasks that are not yet running and have a URL"""
        for task in self.tasks:
            if not task.is_running and task.get_url():
                task.start()

    def scram_all_tasks(self):
        """Abort all running tasks"""
        for task in self.tasks:
            if task.is_running:
                task.abort()
