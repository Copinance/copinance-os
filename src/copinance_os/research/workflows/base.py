"""Use case interfaces and base classes."""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from pydantic import BaseModel

TRequest = TypeVar("TRequest", bound=BaseModel)
TResponse = TypeVar("TResponse", bound=BaseModel)


class UseCase(ABC, Generic[TRequest, TResponse]):
    """Base use case interface."""

    @abstractmethod
    async def execute(self, request: TRequest) -> TResponse:
        """Execute the use case."""
        pass
