"""JSON file-based storage backend for repositories."""

import json
import sys
from pathlib import Path
from typing import Any
from uuid import UUID

from copinanceos.domain.ports.storage import Storage
from copinanceos.infrastructure.persistence import PERSISTENCE_SCHEMA_VERSION, get_data_dir


class JsonFileStorage(Storage):
    """JSON file-based storage backend.

    This storage backend persists data to JSON files on disk.
    Data persists between process invocations. Suitable for CLI
    applications and development.
    """

    def __init__(self, base_path: Path | str = ".copinance") -> None:
        """Initialize JSON file storage.

        Args:
            base_path: Base directory for storing JSON files
        """
        self._root_path = Path(base_path)
        self._root_path.mkdir(parents=True, exist_ok=True)
        self._base_path = self._root_path
        self._data_path = get_data_dir(self._root_path)
        self._collections: dict[str, dict[UUID, Any]] = {}
        self._file_paths: dict[str, Path] = {}

    def _get_file_path(self, collection_name: str) -> Path:
        """Get file path for a collection.

        Args:
            collection_name: Name of the collection

        Returns:
            Path to JSON file for this collection
        """
        if collection_name not in self._file_paths:
            normalized = collection_name.replace("\\", "/").strip("/")
            if not normalized:
                normalized = "default"
            parts = [part.replace("..", "_").replace("/", "_") for part in normalized.split("/")]
            directory = self._data_path.joinpath(*parts[:-1]) if len(parts) > 1 else self._data_path
            directory.mkdir(parents=True, exist_ok=True)
            self._file_paths[collection_name] = directory / f"{parts[-1]}.json"
        return self._file_paths[collection_name]

    def get_collection(self, collection_name: str, entity_type: type[Any]) -> dict[UUID, Any]:
        """Get or create a collection by name.

        Args:
            collection_name: Name of the collection
            entity_type: Pydantic model type for deserialization

        Returns:
            Dictionary mapping UUIDs to entities
        """
        if collection_name not in self._collections:
            self._collections[collection_name] = {}
            self._load_collection(collection_name, entity_type)
        return self._collections[collection_name]

    def _load_collection(self, collection_name: str, entity_type: type[Any]) -> None:
        """Load collection from JSON file.

        Args:
            collection_name: Name of the collection
            entity_type: Pydantic model type for deserialization
        """
        file_path = self._get_file_path(collection_name)
        if file_path.exists():
            try:
                with open(file_path) as f:
                    data = json.load(f)
                    entities = data.get("entities", {})
                    for entity_id_str, entity_data in entities.items():
                        entity_id = UUID(entity_id_str)
                        entity = entity_type.model_validate(entity_data)
                        self._collections[collection_name][entity_id] = entity
            except (json.JSONDecodeError, ValueError, KeyError, TypeError) as e:
                # If file is corrupted, start fresh
                print(
                    f"Warning: Could not load {collection_name} data: {e}. Starting fresh.",
                    file=sys.stderr,
                )
                self._collections[collection_name] = {}

    def _save_collection(self, collection_name: str) -> None:
        """Save collection to JSON file.

        Args:
            collection_name: Name of the collection
        """
        if collection_name not in self._collections:
            return

        file_path = self._get_file_path(collection_name)
        entities = {
            str(entity_id): entity.model_dump(mode="json")
            for entity_id, entity in self._collections[collection_name].items()
        }
        data = {
            "schema_version": PERSISTENCE_SCHEMA_VERSION,
            "collection_name": collection_name,
            "entities": entities,
        }
        with open(file_path, "w") as f:
            json.dump(data, f, indent=2)

    def save(self, collection_name: str) -> None:
        """Save collection to disk.

        Args:
            collection_name: Name of the collection to save
        """
        if collection_name in self._collections:
            self._save_collection(collection_name)

    def clear(self, collection_name: str | None = None) -> None:
        """Clear storage.

        Args:
            collection_name: If provided, clear only this collection.
                           If None, clear all collections.
        """
        if collection_name:
            if collection_name in self._collections:
                self._collections[collection_name].clear()
                file_path = self._get_file_path(collection_name)
                if file_path.exists():
                    file_path.unlink()
        else:
            self._collections.clear()
            for file_path in self._data_path.rglob("*.json"):
                if file_path.exists():
                    file_path.unlink()
