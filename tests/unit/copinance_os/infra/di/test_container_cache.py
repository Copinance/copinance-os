"""Tests for explicit, side-effect-free container cache composition."""

from pathlib import Path

import pytest

from copinance_os.data.cache import CacheManager, InMemoryCacheBackend
from copinance_os.infra.di import create_container


@pytest.mark.unit
class TestContainerCacheConfig:
    def test_independent_container_defaults_to_noop_cache(self) -> None:
        container = create_container()

        cache = container.cache_manager()
        assert isinstance(cache, CacheManager)
        assert cache.enabled is False
        assert cache.get_backend().get_backend_name() == "none"

    def test_custom_cache_manager_is_shared_with_edgar_provider_graph(self) -> None:
        custom = CacheManager(InMemoryCacheBackend())
        container = create_container(cache_manager=custom)

        assert container.cache_manager() is custom
        assert container.sec_filings_provider()._cache_manager is custom

    def test_host_owned_data_providers_can_replace_bundled_adapters(self) -> None:
        market = object()
        fundamentals = object()
        filings = object()
        macro = object()

        container = create_container(
            market_data_provider=market,
            fundamental_data_provider=fundamentals,
            sec_filings_provider=filings,
            macro_data_provider=macro,
        )

        assert container.market_data_provider() is market
        assert container.fundamental_data_provider() is fundamentals
        assert container.sec_filings_provider() is filings
        assert container.macro_data_provider() is macro

    def test_container_construction_creates_no_files(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)

        container = create_container()
        container.storage_backend()
        container.cache_manager()
        container.current_profile().get_current_profile_id()
        container.research_orchestrator()

        assert list(tmp_path.iterdir()) == []
