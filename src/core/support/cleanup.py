import os
from pathlib import Path
import logging


def collect_incomplete_files(output_directory: str, cleanup_type: str = "general"):
    if not output_directory:
        return set()
    output_path = Path(output_directory)
    if not output_path.exists():
        return set()
    cleanup_files = set()

    partial_patterns = [
        "*.part",
        "*.f*",
        "*.temp",
        "*.tmp",
        "*.temp.mp3",
        "*.temp.mp4",
        "*.temp.webm",
        "*.temp.mkv",
        "*.ytdl",
        "*.ytdl.meta",
        "*.meta",
        "*.webm.part",
        "*.mp4.part",
        "*.mkv.part",
        "*.m4a.part",
        "*.frag",
        "*.fragment*",
        "*.incomplete",
        "*.downloading",
        "*.webp",
    ]

    try:
        import time
        for pattern in partial_patterns:
            for file_path in output_path.rglob(pattern):
                if file_path.is_file():
                    try:
                        file_age = time.time() - file_path.stat().st_mtime
                        if pattern == "*.webp":
                            time_limit = 7200
                        else:
                            time_limit = 3600
                        if file_age < time_limit:
                            cleanup_files.add(str(file_path))
                    except Exception:
                        pass
    except Exception as e:
        logging.warning(f"Error scanning for cleanup files: {e}")
    return cleanup_files


def remove_files(file_paths: set):
    cleaned_count = 0
    cleaned_files = []
    for file_path in file_paths:
        try:
            if os.path.exists(file_path):
                size = os.path.getsize(file_path)
                os.remove(file_path)
                cleaned_count += 1
                cleaned_files.append((file_path, size))
        except Exception as e:
            logging.warning(f"Failed to clean up file {file_path}: {e}")
    return cleaned_count, cleaned_files

