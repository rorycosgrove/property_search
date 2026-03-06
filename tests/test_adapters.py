"""Tests for the source adapter registry."""
import pytest

from packages.sources.registry import get_adapter, get_adapter_names, list_adapters


class TestAdapterRegistry:
    def test_list_adapters_returns_all_builtin(self):
        adapters = list_adapters()
        names = {a.name for a in adapters}
        assert "daft" in names
        assert "myhome" in names
        assert "propertypal" in names
        assert "ppr" in names
        assert "rss" in names

    def test_get_adapter_daft(self):
        adapter = get_adapter("daft")
        assert adapter is not None
        assert adapter.get_adapter_name() == "daft"

    def test_get_adapter_unknown_raises(self):
        with pytest.raises(KeyError):
            get_adapter("nonexistent_adapter")

    def test_get_adapter_names(self):
        names = get_adapter_names()
        assert len(names) >= 5
        assert "daft" in names
