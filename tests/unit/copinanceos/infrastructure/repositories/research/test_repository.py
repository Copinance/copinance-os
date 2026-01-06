"""Unit tests for research repository implementation."""

from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from copinanceos.domain.models.research import Research, ResearchStatus, ResearchTimeframe
from copinanceos.domain.ports.storage import Storage
from copinanceos.infrastructure.repositories.research.repository import ResearchRepositoryImpl


@pytest.mark.unit
class TestResearchRepositoryImpl:
    """Test ResearchRepositoryImpl."""

    def test_initialization_with_default_storage(self) -> None:
        """Test initialization with default storage."""
        with patch(
            "copinanceos.infrastructure.repositories.research.repository.create_storage"
        ) as mock_create_storage:
            mock_storage = MagicMock(spec=Storage)
            mock_storage.get_collection = MagicMock(return_value={})
            mock_create_storage.return_value = mock_storage

            repository = ResearchRepositoryImpl()

            assert repository._storage is mock_storage
            mock_storage.get_collection.assert_called_once_with("research", Research)

    def test_initialization_with_custom_storage(self) -> None:
        """Test initialization with custom storage."""
        mock_storage = MagicMock(spec=Storage)
        mock_storage.get_collection = MagicMock(return_value={})

        repository = ResearchRepositoryImpl(storage=mock_storage)

        assert repository._storage is mock_storage
        mock_storage.get_collection.assert_called_once_with("research", Research)

    def test_initialization_with_base_path(self) -> None:
        """Test initialization with base_path when storage is None."""
        with patch(
            "copinanceos.infrastructure.repositories.research.repository.create_storage"
        ) as mock_create_storage:
            mock_storage = MagicMock(spec=Storage)
            mock_storage.get_collection = MagicMock(return_value={})
            mock_create_storage.return_value = mock_storage

            base_path = Path("/tmp/test")
            repository = ResearchRepositoryImpl(base_path=base_path)

            mock_create_storage.assert_called_once_with(base_path=base_path)
            assert repository._storage is mock_storage

    def test_initialization_with_base_path_and_storage_ignores_base_path(self) -> None:
        """Test that base_path is ignored when storage is provided."""
        mock_storage = MagicMock(spec=Storage)
        mock_storage.get_collection = MagicMock(return_value={})

        base_path = Path("/tmp/test")
        repository = ResearchRepositoryImpl(storage=mock_storage, base_path=base_path)

        assert repository._storage is mock_storage
        # base_path should be ignored when storage is provided

    @pytest.mark.asyncio
    async def test_get_by_id_found(self) -> None:
        """Test getting research by ID when it exists."""
        mock_storage = MagicMock(spec=Storage)
        research = Research(
            stock_symbol="AAPL",
            timeframe=ResearchTimeframe.SHORT_TERM,
            workflow_type="stock",
        )
        mock_storage.get_collection = MagicMock(return_value={research.id: research})

        repository = ResearchRepositoryImpl(storage=mock_storage)
        result = await repository.get_by_id(research.id)

        assert result is not None
        assert result.id == research.id
        assert result.stock_symbol == "AAPL"

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self) -> None:
        """Test getting research by ID when it doesn't exist."""
        mock_storage = MagicMock(spec=Storage)
        mock_storage.get_collection = MagicMock(return_value={})

        repository = ResearchRepositoryImpl(storage=mock_storage)
        result = await repository.get_by_id(uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_save_research(self) -> None:
        """Test saving a research."""
        mock_storage = MagicMock(spec=Storage)
        research_dict: dict = {}
        mock_storage.get_collection = MagicMock(return_value=research_dict)
        mock_storage.save = MagicMock()

        repository = ResearchRepositoryImpl(storage=mock_storage)
        research = Research(
            stock_symbol="AAPL",
            timeframe=ResearchTimeframe.SHORT_TERM,
            workflow_type="stock",
        )

        result = await repository.save(research)

        assert result is research
        assert research_dict[research.id] is research
        mock_storage.save.assert_called_once_with("research")

    @pytest.mark.asyncio
    async def test_save_research_updates_existing(self) -> None:
        """Test that save updates an existing research."""
        mock_storage = MagicMock(spec=Storage)
        research = Research(
            stock_symbol="AAPL",
            timeframe=ResearchTimeframe.SHORT_TERM,
            workflow_type="stock",
        )
        research_dict = {research.id: research}
        mock_storage.get_collection = MagicMock(return_value=research_dict)
        mock_storage.save = MagicMock()

        repository = ResearchRepositoryImpl(storage=mock_storage)

        # Update the research
        research.status = ResearchStatus.COMPLETED
        research.results = {"summary": "Test results"}
        result = await repository.save(research)

        assert result is research
        assert research_dict[research.id].status == ResearchStatus.COMPLETED
        assert research_dict[research.id].results == {"summary": "Test results"}
        mock_storage.save.assert_called_once_with("research")

    @pytest.mark.asyncio
    async def test_save_multiple_research(self) -> None:
        """Test saving multiple research items."""
        mock_storage = MagicMock(spec=Storage)
        research_dict: dict = {}
        mock_storage.get_collection = MagicMock(return_value=research_dict)
        mock_storage.save = MagicMock()

        repository = ResearchRepositoryImpl(storage=mock_storage)
        research1 = Research(
            stock_symbol="AAPL",
            timeframe=ResearchTimeframe.SHORT_TERM,
            workflow_type="stock",
        )
        research2 = Research(
            stock_symbol="MSFT",
            timeframe=ResearchTimeframe.LONG_TERM,
            workflow_type="agent",
        )

        await repository.save(research1)
        await repository.save(research2)

        assert len(research_dict) == 2
        assert research_dict[research1.id] is research1
        assert research_dict[research2.id] is research2
        assert mock_storage.save.call_count == 2

    @pytest.mark.asyncio
    async def test_delete_research_found(self) -> None:
        """Test deleting research when it exists."""
        mock_storage = MagicMock(spec=Storage)
        research = Research(
            stock_symbol="AAPL",
            timeframe=ResearchTimeframe.SHORT_TERM,
            workflow_type="stock",
        )
        research_dict = {research.id: research}
        mock_storage.get_collection = MagicMock(return_value=research_dict)
        mock_storage.save = MagicMock()

        repository = ResearchRepositoryImpl(storage=mock_storage)
        result = await repository.delete(research.id)

        assert result is True
        assert research.id not in research_dict
        mock_storage.save.assert_called_once_with("research")

    @pytest.mark.asyncio
    async def test_delete_research_not_found(self) -> None:
        """Test deleting research when it doesn't exist."""
        mock_storage = MagicMock(spec=Storage)
        research_dict: dict = {}
        mock_storage.get_collection = MagicMock(return_value=research_dict)
        mock_storage.save = MagicMock()

        repository = ResearchRepositoryImpl(storage=mock_storage)
        result = await repository.delete(uuid4())

        assert result is False
        mock_storage.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_list_all_research(self) -> None:
        """Test listing all research."""
        mock_storage = MagicMock(spec=Storage)
        research_items = [
            Research(
                stock_symbol=f"STOCK{i}",
                timeframe=ResearchTimeframe.SHORT_TERM,
                workflow_type="stock",
            )
            for i in range(5)
        ]
        research_dict = {r.id: r for r in research_items}
        mock_storage.get_collection = MagicMock(return_value=research_dict)

        repository = ResearchRepositoryImpl(storage=mock_storage)
        result = await repository.list_all()

        assert len(result) == 5
        assert all(isinstance(r, Research) for r in result)

    @pytest.mark.asyncio
    async def test_list_all_research_with_limit(self) -> None:
        """Test listing research with limit."""
        mock_storage = MagicMock(spec=Storage)
        research_items = [
            Research(
                stock_symbol=f"STOCK{i}",
                timeframe=ResearchTimeframe.SHORT_TERM,
                workflow_type="stock",
            )
            for i in range(10)
        ]
        research_dict = {r.id: r for r in research_items}
        mock_storage.get_collection = MagicMock(return_value=research_dict)

        repository = ResearchRepositoryImpl(storage=mock_storage)
        result = await repository.list_all(limit=3)

        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_list_all_research_with_offset(self) -> None:
        """Test listing research with offset."""
        mock_storage = MagicMock(spec=Storage)
        research_items = [
            Research(
                stock_symbol=f"STOCK{i}",
                timeframe=ResearchTimeframe.SHORT_TERM,
                workflow_type="stock",
            )
            for i in range(5)
        ]
        research_dict = {r.id: r for r in research_items}
        mock_storage.get_collection = MagicMock(return_value=research_dict)

        repository = ResearchRepositoryImpl(storage=mock_storage)
        all_research = await repository.list_all()
        offset_research = await repository.list_all(limit=10, offset=2)

        assert len(offset_research) == 3  # 5 total - 2 offset = 3
        assert offset_research[0].id != all_research[0].id

    @pytest.mark.asyncio
    async def test_list_all_research_with_limit_and_offset(self) -> None:
        """Test listing research with both limit and offset."""
        mock_storage = MagicMock(spec=Storage)
        research_items = [
            Research(
                stock_symbol=f"STOCK{i}",
                timeframe=ResearchTimeframe.SHORT_TERM,
                workflow_type="stock",
            )
            for i in range(10)
        ]
        research_dict = {r.id: r for r in research_items}
        mock_storage.get_collection = MagicMock(return_value=research_dict)

        repository = ResearchRepositoryImpl(storage=mock_storage)
        result = await repository.list_all(limit=3, offset=2)

        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_list_all_research_empty(self) -> None:
        """Test listing research when none exist."""
        mock_storage = MagicMock(spec=Storage)
        mock_storage.get_collection = MagicMock(return_value={})

        repository = ResearchRepositoryImpl(storage=mock_storage)
        result = await repository.list_all()

        assert result == []

    @pytest.mark.asyncio
    async def test_list_all_research_offset_exceeds_total(self) -> None:
        """Test listing research when offset exceeds total count."""
        mock_storage = MagicMock(spec=Storage)
        research_items = [
            Research(
                stock_symbol=f"STOCK{i}",
                timeframe=ResearchTimeframe.SHORT_TERM,
                workflow_type="stock",
            )
            for i in range(3)
        ]
        research_dict = {r.id: r for r in research_items}
        mock_storage.get_collection = MagicMock(return_value=research_dict)

        repository = ResearchRepositoryImpl(storage=mock_storage)
        result = await repository.list_all(limit=10, offset=5)

        assert result == []

    @pytest.mark.asyncio
    async def test_research_persistence(
        self,
        isolated_storage: Storage,
    ) -> None:
        """Test that research persists across repository instances."""
        # Create first repository instance and save research
        repo1 = ResearchRepositoryImpl(storage=isolated_storage)
        research = Research(
            stock_symbol="AAPL",
            timeframe=ResearchTimeframe.SHORT_TERM,
            workflow_type="stock",
        )
        saved_research = await repo1.save(research)

        # Create second repository instance with same storage
        repo2 = ResearchRepositoryImpl(storage=isolated_storage)

        # Verify research can be retrieved from new instance
        retrieved_research = await repo2.get_by_id(saved_research.id)

        assert retrieved_research is not None
        assert retrieved_research.id == saved_research.id
        assert retrieved_research.stock_symbol == "AAPL"

    @pytest.mark.asyncio
    async def test_save_research_with_all_fields(self) -> None:
        """Test saving research with all fields populated."""
        mock_storage = MagicMock(spec=Storage)
        research_dict: dict = {}
        mock_storage.get_collection = MagicMock(return_value=research_dict)
        mock_storage.save = MagicMock()

        repository = ResearchRepositoryImpl(storage=mock_storage)
        profile_id = uuid4()
        research = Research(
            stock_symbol="AAPL",
            timeframe=ResearchTimeframe.LONG_TERM,
            workflow_type="agent",
            profile_id=profile_id,
            status=ResearchStatus.IN_PROGRESS,
            parameters={"key": "value"},
            results={"summary": "Test"},
            error_message=None,
        )

        result = await repository.save(research)

        assert result is research
        assert research_dict[research.id].profile_id == profile_id
        assert research_dict[research.id].status == ResearchStatus.IN_PROGRESS
        assert research_dict[research.id].parameters == {"key": "value"}
        assert research_dict[research.id].results == {"summary": "Test"}

    @pytest.mark.asyncio
    async def test_save_preserves_research_id(self) -> None:
        """Test that save preserves the research ID."""
        mock_storage = MagicMock(spec=Storage)
        research_dict: dict = {}
        mock_storage.get_collection = MagicMock(return_value=research_dict)
        mock_storage.save = MagicMock()

        repository = ResearchRepositoryImpl(storage=mock_storage)
        research = Research(
            stock_symbol="AAPL",
            timeframe=ResearchTimeframe.SHORT_TERM,
            workflow_type="stock",
        )
        original_id = research.id

        result = await repository.save(research)

        assert result.id == original_id
        assert research_dict[original_id].id == original_id
