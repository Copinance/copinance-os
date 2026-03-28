"""Unit tests for CLI utility functions."""

import asyncio

import pytest

from copinance_os.interfaces.cli.utils import async_command


@pytest.mark.unit
class TestAsyncCommand:
    """Test async_command decorator."""

    def test_async_command_decorator(self) -> None:
        """Test that async_command decorator works correctly."""

        @async_command
        async def async_function(value: str) -> str:
            """Test async function."""
            await asyncio.sleep(0.01)  # Simulate async work
            return f"Result: {value}"

        # The decorated function should be synchronous
        result = async_function("test")
        assert result == "Result: test"

    def test_async_command_with_exception(self) -> None:
        """Test that async_command handles exceptions correctly."""

        @async_command
        async def async_function_that_raises() -> None:
            """Test async function that raises."""
            await asyncio.sleep(0.01)
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            async_function_that_raises()

    def test_async_command_with_return_value(self) -> None:
        """Test that async_command preserves return values."""

        @async_command
        async def async_function_with_return() -> dict[str, str]:
            """Test async function with return value."""
            await asyncio.sleep(0.01)
            return {"key": "value"}

        result = async_function_with_return()
        assert result == {"key": "value"}

    def test_async_command_with_arguments(self) -> None:
        """Test that async_command works with function arguments."""

        @async_command
        async def async_function_with_args(a: int, b: int, c: str = "default") -> str:
            """Test async function with arguments."""
            await asyncio.sleep(0.01)
            return f"{a}+{b}={c}"

        result = async_function_with_args(1, 2, c="test")
        assert result == "1+2=test"

    def test_async_command_only_works_with_async_functions(self) -> None:
        """Test that async_command raises TypeError for non-async functions."""

        with pytest.raises(
            TypeError, match="async_command decorator can only be used on async functions"
        ):

            @async_command
            def sync_function() -> str:  # type: ignore[misc]
                """This should fail."""
                return "test"
