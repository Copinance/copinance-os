"""Unit tests for container cache_enabled and cache_manager injection."""

from unittest.mock import patch

import pytest

from copinance_os.data.cache import CacheManager
from copinance_os.infra.di import get_container, reset_container


@pytest.mark.unit
class TestContainerCacheConfig:
    """Validate that get_container() respects cache_enabled and cache_manager."""

    def teardown_method(self) -> None:
        """Reset global container after each test to avoid affecting other tests."""
        reset_container()

    def test_get_container_with_cache_enabled_false_disables_cache(self) -> None:
        """Passing cache_enabled=False returns a container whose cache_manager() is None."""
        reset_container()
        container = get_container(cache_enabled=False, load_from_env=False)

        assert container.cache_manager() is None

    def test_get_container_with_cache_enabled_true_uses_builtin_cache(self) -> None:
        """Passing cache_enabled=True returns a container with a CacheManager instance."""
        reset_container()
        container = get_container(cache_enabled=True, load_from_env=False)

        cache = container.cache_manager()
        assert cache is not None
        assert isinstance(cache, CacheManager)

    def test_get_container_default_uses_builtin_cache(self) -> None:
        """When cache_enabled is not passed, default container has cache enabled."""
        reset_container()
        container = get_container(load_from_env=False)

        cache = container.cache_manager()
        assert cache is not None
        assert isinstance(cache, CacheManager)

    def test_get_container_cache_disable_applied_when_container_already_exists(
        self,
    ) -> None:
        """When global container already exists, get_container(cache_enabled=False) still disables cache."""
        reset_container()
        # Create container first (e.g. another module did container.something())
        get_container(load_from_env=False)
        # Library user then calls with cache disabled; override must apply
        container = get_container(cache_enabled=False, load_from_env=False)

        assert container.cache_manager() is None

    def test_get_container_with_custom_cache_manager_uses_provided_instance(
        self,
    ) -> None:
        """Passing cache_manager to get_container() uses that instance."""
        reset_container()
        custom = CacheManager()
        container = get_container(
            cache_manager=custom,
            load_from_env=False,
        )

        assert container.cache_manager() is custom

    def test_get_container_respects_settings_cache_enabled_when_none(self) -> None:
        """When cache_enabled=None, get_container() uses settings (e.g. COPINANCEOS_CACHE_ENABLED)."""
        reset_container()
        with patch(
            "copinance_os.infra.di.container.get_settings",
        ) as get_settings:
            get_settings.return_value.cache_enabled = False
            container = get_container(cache_enabled=None, load_from_env=False)

        assert container.cache_manager() is None
