"""Base domain models and abstractions."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class Entity(BaseModel):
    """Base entity with identity."""

    model_config = ConfigDict(frozen=False)

    id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Last update timestamp"
    )

    @field_serializer("id")
    def serialize_id(self, value: UUID) -> str:
        """Serialize UUID to string."""
        return str(value)

    @field_serializer("created_at", "updated_at")
    def serialize_datetime(self, value: datetime) -> str:
        """Serialize datetime to ISO format."""
        return value.isoformat()

    def __eq__(self, other: Any) -> bool:
        """Entities are equal if they have the same ID."""
        if not isinstance(other, Entity):
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        """Hash based on entity ID."""
        return hash(self.id)


class ValueObject(BaseModel):
    """Base value object - immutable and compared by value."""

    model_config = ConfigDict(frozen=True)
