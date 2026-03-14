"""Unit tests for base domain models."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from pydantic import Field, ValidationError

from copinanceos.domain.models.base import Entity, ValueObject
from copinanceos.domain.models.market import MarketDataPoint
from copinanceos.domain.models.stock import Stock


# Sample entity class for direct testing - must be defined at module level
class SampleEntity(Entity):
    """Sample entity for unit testing."""

    name: str = Field(..., description="Test name")


# Sample value object class for direct testing - must be defined at module level
class SampleValueObject(ValueObject):
    """Sample value object for unit testing."""

    value: str = Field(..., description="Test value")


@pytest.mark.unit
class SampleEntityClass:
    """Test Entity base class."""

    def test_entity_has_default_id(self) -> None:
        """Test that entity gets a default UUID ID."""
        entity = SampleEntity(name="test")
        assert isinstance(entity.id, UUID)
        assert entity.id is not None

    def test_entity_can_have_custom_id(self) -> None:
        """Test that entity can be created with a custom ID."""
        custom_id = uuid4()
        entity = SampleEntity(id=custom_id, name="test")
        assert entity.id == custom_id

    def test_entity_has_default_timestamps(self) -> None:
        """Test that entity gets default timestamps."""
        before = datetime.now(UTC)
        entity = SampleEntity(name="test")
        after = datetime.now(UTC)

        assert isinstance(entity.created_at, datetime)
        assert isinstance(entity.updated_at, datetime)
        assert before <= entity.created_at <= after
        assert before <= entity.updated_at <= after

    def test_entity_can_have_custom_timestamps(self) -> None:
        """Test that entity can be created with custom timestamps."""
        custom_created = datetime(2023, 1, 1, tzinfo=UTC)
        custom_updated = datetime(2023, 1, 2, tzinfo=UTC)
        entity = SampleEntity(name="test", created_at=custom_created, updated_at=custom_updated)
        assert entity.created_at == custom_created
        assert entity.updated_at == custom_updated

    def test_entity_is_mutable(self) -> None:
        """Test that entity is mutable (frozen=False)."""
        entity = SampleEntity(name="test")
        original_name = entity.name
        entity.name = "updated"
        assert entity.name == "updated"
        assert entity.name != original_name

    def test_entity_equality_same_id(self) -> None:
        """Test that entities with same ID are equal."""
        entity_id = uuid4()
        entity1 = SampleEntity(id=entity_id, name="test1")
        entity2 = SampleEntity(id=entity_id, name="test2")

        assert entity1 == entity2
        assert hash(entity1) == hash(entity2)

    def test_entity_equality_different_id(self) -> None:
        """Test that entities with different IDs are not equal."""
        entity1 = SampleEntity(name="test1")
        entity2 = SampleEntity(name="test2")

        assert entity1 != entity2

    def test_entity_equality_different_type(self) -> None:
        """Test that entity is not equal to non-Entity objects."""
        entity = SampleEntity(name="test")
        assert entity != "not an entity"
        assert entity != 123
        assert entity != None  # noqa: E711

    def test_entity_hash(self) -> None:
        """Test that entities can be hashed by ID."""
        entity = SampleEntity(name="test")
        entity_set = {entity}
        assert entity in entity_set

    def test_entity_hash_same_id(self) -> None:
        """Test that entities with same ID have same hash."""
        entity_id = uuid4()
        entity1 = SampleEntity(id=entity_id, name="test1")
        entity2 = SampleEntity(id=entity_id, name="test2")

        assert hash(entity1) == hash(entity2)

    def test_entity_hash_different_id(self) -> None:
        """Test that entities with different IDs have different hashes."""
        entity1 = SampleEntity(name="test1")
        entity2 = SampleEntity(name="test2")

        # Hashes might collide, but should be different for different IDs
        if entity1.id != entity2.id:
            assert hash(entity1) != hash(entity2)

    def test_entity_id_serialization(self) -> None:
        """Test that entity ID is serialized to string."""
        entity = SampleEntity(name="test")
        serialized = entity.model_dump()
        assert isinstance(serialized["id"], str)
        assert serialized["id"] == str(entity.id)

    def test_entity_datetime_serialization(self) -> None:
        """Test that entity datetimes are serialized to ISO format."""
        entity = SampleEntity(name="test")
        serialized = entity.model_dump()
        assert isinstance(serialized["created_at"], str)
        assert isinstance(serialized["updated_at"], str)
        # Verify ISO format
        datetime.fromisoformat(serialized["created_at"].replace("Z", "+00:00"))
        datetime.fromisoformat(serialized["updated_at"].replace("Z", "+00:00"))

    def test_entity_json_serialization(self) -> None:
        """Test that entity can be serialized to JSON."""
        entity = SampleEntity(name="test")
        json_str = entity.model_dump_json()
        assert isinstance(json_str, str)
        assert "test" in json_str
        assert str(entity.id) in json_str

    def test_entity_through_stock_model(self) -> None:
        """Test entity behavior through Stock model."""
        stock1 = Stock(symbol="AAPL", name="Apple Inc.", exchange="NASDAQ")
        stock2 = Stock(symbol="MSFT", name="Microsoft", exchange="NASDAQ")
        stock2.id = stock1.id

        assert stock1 == stock2
        assert hash(stock1) == hash(stock2)

    def test_entity_hash_through_stock_model(self) -> None:
        """Test entity hashing through Stock model."""
        stock = Stock(symbol="AAPL", name="Apple Inc.", exchange="NASDAQ")
        stock_set = {stock}
        assert stock in stock_set


@pytest.mark.unit
class SampleValueObjectClass:
    """Test ValueObject base class."""

    def test_value_object_is_immutable(self) -> None:
        """Test that value objects are immutable (frozen=True)."""
        value_obj = SampleValueObject(value="test")
        with pytest.raises(ValidationError):
            value_obj.value = "updated"  # type: ignore

    def test_value_object_immutability_through_market_data(self) -> None:
        """Test value object immutability through MarketDataPoint model."""
        stock_data = MarketDataPoint(
            symbol="AAPL",
            timestamp=datetime.now(UTC),
            open_price=Decimal("150.00"),
            close_price=Decimal("151.00"),
            high_price=Decimal("152.00"),
            low_price=Decimal("149.00"),
            volume=1000000,
        )

        with pytest.raises(ValidationError):
            stock_data.symbol = "MSFT"  # type: ignore

    def test_value_object_equality_by_value(self) -> None:
        """Test that value objects are equal if all values are equal."""
        value_obj1 = SampleValueObject(value="test")
        value_obj2 = SampleValueObject(value="test")

        # Pydantic models with frozen=True compare by value
        assert value_obj1 == value_obj2

    def test_value_object_inequality_different_values(self) -> None:
        """Test that value objects with different values are not equal."""
        value_obj1 = SampleValueObject(value="test1")
        value_obj2 = SampleValueObject(value="test2")

        assert value_obj1 != value_obj2

    def test_value_object_can_be_serialized(self) -> None:
        """Test that value objects can be serialized."""
        value_obj = SampleValueObject(value="test")
        serialized = value_obj.model_dump()
        assert serialized["value"] == "test"

    def test_value_object_can_be_json_serialized(self) -> None:
        """Test that value objects can be JSON serialized."""
        value_obj = SampleValueObject(value="test")
        json_str = value_obj.model_dump_json()
        assert isinstance(json_str, str)
        assert "test" in json_str

    def test_value_object_has_no_id(self) -> None:
        """Test that value objects don't have ID field."""
        value_obj = SampleValueObject(value="test")
        assert not hasattr(value_obj, "id")
        serialized = value_obj.model_dump()
        assert "id" not in serialized

    def test_value_object_has_no_timestamps(self) -> None:
        """Test that value objects don't have timestamp fields."""
        value_obj = SampleValueObject(value="test")
        assert not hasattr(value_obj, "created_at")
        assert not hasattr(value_obj, "updated_at")
        serialized = value_obj.model_dump()
        assert "created_at" not in serialized
        assert "updated_at" not in serialized


@pytest.mark.unit
class TestBaseModelsIntegration:
    """Integration tests for base models through domain models."""

    def test_entity_equality_through_stock(self) -> None:
        """Test entity equality through Stock model."""
        stock1 = Stock(symbol="AAPL", name="Apple Inc.", exchange="NASDAQ")
        stock2 = Stock(symbol="MSFT", name="Microsoft", exchange="NASDAQ")
        stock2.id = stock1.id

        assert stock1 == stock2

    def test_entity_hash_through_stock(self) -> None:
        """Test entity hashing through Stock model."""
        stock = Stock(symbol="AAPL", name="Apple Inc.", exchange="NASDAQ")
        stock_set = {stock}
        assert stock in stock_set

    def test_value_object_immutability_through_market_data(self) -> None:
        """Test value object immutability through MarketDataPoint model."""
        stock_data = MarketDataPoint(
            symbol="AAPL",
            timestamp=datetime.now(UTC),
            open_price=Decimal("150.00"),
            close_price=Decimal("151.00"),
            high_price=Decimal("152.00"),
            low_price=Decimal("149.00"),
            volume=1000000,
        )

        with pytest.raises(ValidationError):
            stock_data.symbol = "MSFT"  # type: ignore
