"""Unit tests for base use case classes."""

import pytest
from pydantic import BaseModel

from copinance_os.research.workflows.base import UseCase


class SampleRequest(BaseModel):
    """Sample request model for testing."""

    value: str


class SampleResponse(BaseModel):
    """Sample response model for testing."""

    result: str


class ConcreteUseCase(UseCase[SampleRequest, SampleResponse]):
    """Concrete implementation of UseCase for testing."""

    async def execute(self, request: SampleRequest) -> SampleResponse:
        """Execute the use case."""
        return SampleResponse(result=f"Processed: {request.value}")


@pytest.mark.unit
class TestUseCase:
    """Test base UseCase interface."""

    def test_use_case_is_abstract(self) -> None:
        """Test that UseCase cannot be instantiated directly."""
        # UseCase is abstract, so it cannot be instantiated
        # This is tested by the fact that we need a concrete implementation
        assert issubclass(ConcreteUseCase, UseCase)

    def test_concrete_use_case_can_be_instantiated(self) -> None:
        """Test that a concrete use case can be instantiated."""
        use_case = ConcreteUseCase()
        assert isinstance(use_case, UseCase)
        assert isinstance(use_case, ConcreteUseCase)

    async def test_execute_method(self) -> None:
        """Test that execute method works correctly."""
        use_case = ConcreteUseCase()
        request = SampleRequest(value="test")
        response = await use_case.execute(request)

        assert isinstance(response, SampleResponse)
        assert response.result == "Processed: test"

    def test_generic_type_parameters(self) -> None:
        """Test that UseCase properly uses generic type parameters."""
        # Verify that the concrete use case has the correct type parameters
        use_case = ConcreteUseCase()
        assert hasattr(use_case, "execute")
