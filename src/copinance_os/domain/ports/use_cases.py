"""Generic use case interface (base contract for all application use cases)."""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from pydantic import BaseModel

TRequest = TypeVar("TRequest", bound=BaseModel)
TResponse = TypeVar("TResponse", bound=BaseModel)


class UseCase(ABC, Generic[TRequest, TResponse]):
    """Base use case interface. Implementations live in research/workflows/."""

    @abstractmethod
    async def execute(self, request: TRequest) -> TResponse:
        """Execute the use case."""
        pass
