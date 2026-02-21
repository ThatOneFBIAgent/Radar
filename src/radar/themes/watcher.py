"""
Theme file watcher — hot-reload themes when JSON files change.

Uses watchdog to monitor the themes directory. On modification,
signals the application to reload the active theme.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Callable

from watchdog.events import FileModifiedEvent, FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)


class _ThemeFileHandler(FileSystemEventHandler):
    """Watchdog handler that triggers reload on .json changes."""

    def __init__(self, callback: Callable[[str], None]) -> None:
        super().__init__()
        self._callback = callback
        self._debounce_lock = threading.Lock()

    def on_modified(self, event: FileModifiedEvent) -> None:
        if event.is_directory:
            return
        path = Path(str(event.src_path))
        if path.suffix.lower() != ".json":
            return

        # Debounce: watchdog can fire multiple events per save
        if not self._debounce_lock.acquire(blocking=False):
            return
        try:
            theme_name = path.stem
            logger.info("Theme file changed: %s — triggering reload", theme_name)
            self._callback(theme_name)
        finally:
            self._debounce_lock.release()


class ThemeWatcher:
    """Watches a directory for theme file changes and triggers reloads.

    Usage:
        watcher = ThemeWatcher(themes_dir, on_theme_change)
        watcher.start()
        ...
        watcher.stop()
    """

    def __init__(
        self,
        themes_dir: Path,
        on_change: Callable[[str], None],
    ) -> None:
        self._themes_dir = themes_dir
        self._on_change = on_change
        self._observer: Observer | None = None

    def start(self) -> None:
        """Start watching the themes directory in a background thread."""
        if self._observer is not None:
            return

        if not self._themes_dir.exists():
            logger.warning("Themes directory does not exist: %s", self._themes_dir)
            return

        handler = _ThemeFileHandler(self._on_change)
        self._observer = Observer()
        self._observer.schedule(handler, str(self._themes_dir), recursive=False)
        self._observer.daemon = True
        self._observer.start()
        logger.info("Theme watcher started — monitoring %s", self._themes_dir)

    def stop(self) -> None:
        """Stop the file watcher."""
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=2.0)
            self._observer = None
            logger.info("Theme watcher stopped")
