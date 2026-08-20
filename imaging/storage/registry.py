"""
imaging/storage/registry.py — Pluggable Storage Registry.

Allows registering, discovering, and obtaining storage backends at runtime.
"""

from __future__ import annotations

import logging
from typing import Dict, Type

from imaging.storage.base import AssetStorage
from imaging.storage.local import LocalStorage

logger = logging.getLogger("trendforge.imaging.storage")

_STORAGE_REGISTRY: Dict[str, Type[AssetStorage]] = {
    "local": LocalStorage,
}

_STORAGE_INSTANCES: Dict[str, AssetStorage] = {}


def register_storage(name: str, storage_cls: Type[AssetStorage]) -> None:
    """Register a new storage backend class."""
    _STORAGE_REGISTRY[name.lower()] = storage_cls
    logger.info("Registered storage backend: %s (%s)", name, storage_cls.__name__)


def get_storage(name: str = "local", **kwargs) -> AssetStorage:
    """Get or instantiate an AssetStorage by name."""
    normalized = name.lower()
    if normalized not in _STORAGE_REGISTRY:
        logger.warning(
            "Storage backend '%s' not registered. Available: %s. Falling back to 'local'.",
            name,
            list(_STORAGE_REGISTRY.keys()),
        )
        normalized = "local"

    if normalized not in _STORAGE_INSTANCES or kwargs:
        storage_cls = _STORAGE_REGISTRY[normalized]
        instance = storage_cls(**kwargs)
        if not kwargs:
            _STORAGE_INSTANCES[normalized] = instance
        return instance

    return _STORAGE_INSTANCES[normalized]
