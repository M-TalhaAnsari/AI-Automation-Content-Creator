"""
config/ -- Public interface
===================================
Single source of truth for all settings, API keys, and constants.
Every other module imports from here. This module never imports from
any other TrendForge module (like core/).

Usage:
    from config import CONFIG, PLATFORM_SETTINGS, SUPPORTED_PLATFORMS, SOURCE_MAP

What lives here:
    settings.py -- TrendForgeConfig singleton (CONFIG), ModelConfig, SourceConfig, SystemConfig
    platforms.py -- PLATFORM_SETTINGS dict, SUPPORTED_PLATFORMS list
    sources.py   -- SOURCE_MAP (category -> list of source names)

Current state: everything lives in one config.py at the project root.
Future: split into config/settings.py, config/platforms.py, config/sources.py
as each grows. The public interface stays identical either way.
"""
from .config import CONFIG, PLATFORM_SETTINGS, SUPPORTED_PLATFORMS, SOURCE_MAP