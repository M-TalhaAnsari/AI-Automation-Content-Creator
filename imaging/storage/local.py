"""
imaging/storage/local.py — Local File System Asset Storage.

Stores files on disk under a configurable root directory (defaults to `storage/`).
Serves files through backend service methods, NOT directly via static file mounts.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from imaging.storage.base import AssetStorage

logger = logging.getLogger("trendforge.imaging.storage.local")


class LocalStorage(AssetStorage):
    """
    Local filesystem storage backend.
    Saves assets under base_directory / key.
    """

    def __init__(self, base_directory: Optional[str] = None):
        # Default to "storage" directory in project root if not specified
        if base_directory is None:
            project_root = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            base_directory = os.path.join(project_root, "storage")
        
        self.base_directory = os.path.abspath(base_directory)
        os.makedirs(self.base_directory, exist_ok=True)
        logger.info("LocalStorage initialized with base directory: %s", self.base_directory)

    @property
    def backend_name(self) -> str:
        return "local"

    def _resolve_path(self, key: str) -> str:
        """Resolve storage key to safe local absolute filepath."""
        normalized_key = os.path.normpath(key.replace("/", os.sep)).lstrip(os.sep)
        full_path = os.path.abspath(os.path.join(self.base_directory, normalized_key))

        # Guard against path traversal
        if not full_path.startswith(self.base_directory):
            raise ValueError(f"Security error: key '{key}' resolves outside storage base directory")

        return full_path

    def save(self, key: str, data: bytes, content_type: str = "image/png") -> str:
        full_path = self._resolve_path(key)
        parent_dir = os.path.dirname(full_path)
        os.makedirs(parent_dir, exist_ok=True)

        with open(full_path, "wb") as f:
            f.write(data)

        logger.debug("Saved asset to local storage: %s (%d bytes)", key, len(data))
        return key

    def get(self, key: str) -> Optional[bytes]:
        full_path = self._resolve_path(key)
        if not os.path.exists(full_path) or not os.path.isfile(full_path):
            return None

        try:
            with open(full_path, "rb") as f:
                return f.read()
        except OSError as e:
            logger.error("Error reading file %s: %s", full_path, e)
            return None

    def delete(self, key: str) -> bool:
        full_path = self._resolve_path(key)
        if not os.path.exists(full_path):
            return False

        try:
            os.remove(full_path)
            logger.info("Deleted asset from local storage: %s", key)
            return True
        except OSError as e:
            logger.error("Failed to delete %s: %s", full_path, e)
            return False

    def exists(self, key: str) -> bool:
        full_path = self._resolve_path(key)
        return os.path.exists(full_path) and os.path.isfile(full_path)
