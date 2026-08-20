"""
imaging/storage/base.py — Abstract Base Class for Asset Storage.

Design intent:
─────────────
Decouples image persistence from the filesystem and database.
Operations:
  - save(key, data, content_type) -> key/path
  - get(key) -> bytes
  - delete(key) -> bool
  - exists(key) -> bool
  - build_key(user_id, asset_id, extension) -> standard key format

Storage implementations (LocalStorage, S3Storage, GCSStorage) inherit
from AssetStorage. Business logic interacts ONLY with this interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, Union


class AssetStorage(ABC):
    """Abstract object storage interface for image assets."""

    @property
    @abstractmethod
    def backend_name(self) -> str:
        """Storage backend name, e.g. 'local', 's3', 'gcs'."""
        raise NotImplementedError

    @abstractmethod
    def save(self, key: str, data: bytes, content_type: str = "image/png") -> str:
        """
        Store raw bytes under the given key.
        Returns the canonical storage identifier / key.
        """
        raise NotImplementedError

    @abstractmethod
    def get(self, key: str) -> Optional[bytes]:
        """
        Retrieve raw bytes for the given storage key.
        Returns None if not found.
        """
        raise NotImplementedError

    @abstractmethod
    def delete(self, key: str) -> bool:
        """
        Delete asset at key.
        Returns True if deleted, False if not found or error.
        """
        raise NotImplementedError

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check whether an asset exists at key."""
        raise NotImplementedError

    def build_key(
        self,
        user_id: Optional[Union[int, str]],
        asset_id: str,
        extension: str = "png",
    ) -> str:
        """
        Build standard storage key/path.
        Default format: images/{user_id}/{asset_id}.{extension}
        (where user_id defaults to 'anon' for guests)
        """
        uid_str = str(user_id) if user_id is not None else "anon"
        clean_ext = extension.lstrip(".")
        return f"images/{uid_str}/{asset_id}.{clean_ext}"
