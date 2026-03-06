"""
Source adapter registry.

Auto-discovers and manages all available source adapters. New adapters are
registered here and become available for use in the application without
any other code changes.
"""

from __future__ import annotations

from packages.shared.logging import get_logger
from packages.shared.schemas import AdapterInfo
from packages.sources.base import SourceAdapter
from packages.sources.daft import DaftAdapter
from packages.sources.myhome import MyHomeAdapter
from packages.sources.ppr import PPRAdapter
from packages.sources.propertypal import PropertyPalAdapter
from packages.sources.rss import RSSAdapter

logger = get_logger(__name__)

# ── Registry ──────────────────────────────────────────────────────────────────

_ADAPTERS: dict[str, type[SourceAdapter]] = {}


def _register_builtin_adapters() -> None:
    """Register all built-in adapters."""
    builtin = [
        DaftAdapter,
        MyHomeAdapter,
        PropertyPalAdapter,
        PPRAdapter,
        RSSAdapter,
    ]
    for adapter_cls in builtin:
        instance = adapter_cls()
        _ADAPTERS[instance.get_adapter_name()] = adapter_cls
        logger.debug("adapter_registered", name=instance.get_adapter_name())


def register_adapter(adapter_cls: type[SourceAdapter]) -> None:
    """
    Register a custom source adapter.

    Call this to add new adapters at runtime (e.g., from plugins).
    """
    instance = adapter_cls()
    name = instance.get_adapter_name()
    _ADAPTERS[name] = adapter_cls
    logger.info("custom_adapter_registered", name=name)


def get_adapter(adapter_name: str) -> SourceAdapter:
    """
    Get an adapter instance by name.

    Args:
        adapter_name: Registered adapter name (e.g., 'daft', 'myhome', 'ppr').

    Returns:
        A new instance of the requested adapter.

    Raises:
        KeyError: If no adapter with that name is registered.
    """
    if not _ADAPTERS:
        _register_builtin_adapters()

    if adapter_name not in _ADAPTERS:
        available = list(_ADAPTERS.keys())
        raise KeyError(
            f"Unknown adapter '{adapter_name}'. Available: {available}"
        )

    return _ADAPTERS[adapter_name]()


def list_adapters() -> list[AdapterInfo]:
    """List all registered adapters with their metadata."""
    if not _ADAPTERS:
        _register_builtin_adapters()

    result = []
    for name, adapter_cls in _ADAPTERS.items():
        instance = adapter_cls()
        result.append(
            AdapterInfo(
                name=name,
                description=instance.get_description(),
                adapter_type=instance.get_adapter_type(),
                config_schema=instance.get_config_schema(),
                supports_incremental=instance.supports_incremental(),
            )
        )
    return result


def get_adapter_names() -> list[str]:
    """Return list of all registered adapter names."""
    if not _ADAPTERS:
        _register_builtin_adapters()
    return list(_ADAPTERS.keys())


# Initialize on import
_register_builtin_adapters()
