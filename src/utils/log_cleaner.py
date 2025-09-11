import os
import logging
from pathlib import Path
from typing import List, Optional
import re
from datetime import datetime


class LogCleaner:
    """Utility class for cleaning up old log files"""

    def __init__(self, logs_dir: str, max_logs_to_keep: int = 5):
        """
        Initialize the log cleaner

        Args:
            logs_dir: Path to the logs directory
            max_logs_to_keep: Maximum number of log files to keep
        """
        self.logs_dir = Path(logs_dir)
        self.max_logs_to_keep = max_logs_to_keep
        self.log_pattern = re.compile(r'yt-dlp_(\d{8}_\d{6})\.log')

    def get_log_files(self) -> List[Path]:
        """
        Get all log files in the logs directory, sorted by creation time (newest first)

        Returns:
            List of log file paths sorted by creation time
        """
        if not self.logs_dir.exists():
            return []

        log_files = []
        for file_path in self.logs_dir.iterdir():
            if file_path.is_file() and self.log_pattern.match(file_path.name):
                log_files.append(file_path)

        # Sort by creation time (newest first)
        log_files.sort(key=lambda x: x.stat().st_ctime, reverse=True)
        return log_files

    def clean_old_logs(self, exclude_current: bool = False) -> dict:
        """
        Clean up old log files, keeping only the most recent ones

        Args:
            exclude_current: If True, exclude the most recent log file from cleanup

        Returns:
            Dictionary with cleanup results
        """
        try:
            log_files = self.get_log_files()

            if not log_files:
                return {
                    "cleaned_count": 0,
                    "total_files": 0,
                    "message": "No log files found"
                }

            # Determine how many files to keep
            keep_count = self.max_logs_to_keep
            if exclude_current:
                keep_count -= 1  # Keep one extra slot for the current log

            # Files to keep and files to delete
            files_to_keep = log_files[:keep_count] if keep_count > 0 else []
            files_to_delete = log_files[keep_count:]

            # Clean up old files
            cleaned_count = 0
            cleaned_files = []

            for file_path in files_to_delete:
                try:
                    # Get file size before deletion for logging
                    file_size = file_path.stat().st_size
                    file_path.unlink()
                    cleaned_count += 1
                    cleaned_files.append(file_path.name)
                    logging.info(f"Cleaned up old log file: {file_path.name} ({file_size} bytes)")
                except Exception as e:
                    logging.warning(f"Failed to delete log file {file_path.name}: {e}")

            # Log summary
            if cleaned_count > 0:
                logging.info(f"Log cleanup completed: removed {cleaned_count} old log files")

            return {
                "cleaned_count": cleaned_count,
                "total_files": len(log_files),
                "files_kept": len(files_to_keep),
                "files_cleaned": cleaned_files,
                "message": f"Kept {len(files_to_keep)} most recent log files, removed {cleaned_count} old files"
            }

        except Exception as e:
            error_msg = f"Error during log cleanup: {e}"
            logging.error(error_msg)
            return {
                "cleaned_count": 0,
                "total_files": 0,
                "error": error_msg
            }

    def get_cleanup_info(self) -> dict:
        """
        Get information about current log files and cleanup status

        Returns:
            Dictionary with log file information
        """
        try:
            log_files = self.get_log_files()

            if not log_files:
                return {
                    "total_files": 0,
                    "oldest_file": None,
                    "newest_file": None,
                    "would_clean": 0,
                    "message": "No log files found"
                }

            # Get file information
            oldest_file = log_files[-1]  # Last in sorted list (oldest)
            newest_file = log_files[0]   # First in sorted list (newest)

            # Calculate how many would be cleaned
            would_clean = max(0, len(log_files) - self.max_logs_to_keep)

            return {
                "total_files": len(log_files),
                "oldest_file": {
                    "name": oldest_file.name,
                    "size": oldest_file.stat().st_size,
                    "created": datetime.fromtimestamp(oldest_file.stat().st_ctime).isoformat()
                },
                "newest_file": {
                    "name": newest_file.name,
                    "size": newest_file.stat().st_size,
                    "created": datetime.fromtimestamp(newest_file.stat().st_ctime).isoformat()
                },
                "would_clean": would_clean,
                "message": f"Found {len(log_files)} log files, would clean {would_clean} if cleanup is enabled"
            }

        except Exception as e:
            error_msg = f"Error getting log cleanup info: {e}"
            logging.error(error_msg)
            return {
                "total_files": 0,
                "error": error_msg
            }


def cleanup_logs(logs_dir: str, max_logs_to_keep: int = 5, exclude_current: bool = False) -> dict:
    """
    Convenience function to clean up old log files

    Args:
        logs_dir: Path to the logs directory
        max_logs_to_keep: Maximum number of log files to keep
        exclude_current: If True, exclude the most recent log file from cleanup

    Returns:
        Dictionary with cleanup results
    """
    cleaner = LogCleaner(logs_dir, max_logs_to_keep)
    return cleaner.clean_old_logs(exclude_current=exclude_current)


def get_log_cleanup_info(logs_dir: str, max_logs_to_keep: int = 5) -> dict:
    """
    Convenience function to get log cleanup information

    Args:
        logs_dir: Path to the logs directory
        max_logs_to_keep: Maximum number of log files to keep

    Returns:
        Dictionary with log file information
    """
    cleaner = LogCleaner(logs_dir, max_logs_to_keep)
    return cleaner.get_cleanup_info()
