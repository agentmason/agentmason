from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
import os


class FileStorage(ABC):
    """Abstract base class for file storage implementations."""

    @abstractmethod
    async def save(self, file_id: str, content: bytes, organization_id: str) -> str:
        """
        Save a file and return the storage location.
        
        Args:
            file_id: Unique identifier for the file
            content: File content as bytes
            organization_id: Organization ID for multi-tenancy
            
        Returns:
            Storage location path/key
        """
        pass

    @abstractmethod
    async def get(self, storage_location: str) -> bytes:
        """
        Retrieve a file from storage.
        
        Args:
            storage_location: Path/key to the stored file
            
        Returns:
            File content as bytes
        """
        pass

    @abstractmethod
    async def delete(self, storage_location: str) -> None:
        """
        Delete a file from storage.
        
        Args:
            storage_location: Path/key to the stored file
        """
        pass

    @abstractmethod
    async def exists(self, storage_location: str) -> bool:
        """
        Check if a file exists in storage.
        
        Args:
            storage_location: Path/key to the stored file
            
        Returns:
            True if file exists, False otherwise
        """
        pass


class LocalFileStorage(FileStorage):
    """Local file storage implementation for development."""

    def __init__(self, base_path: str = "./storage") -> None:
        """
        Initialize local file storage.
        
        Args:
            base_path: Base directory for storing files
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _get_file_path(self, storage_location: str) -> Path:
        """Get the full file path from storage location."""
        return self.base_path / storage_location

    async def save(self, file_id: str, content: bytes, organization_id: str) -> str:
        """Save file to local storage and return relative path."""
        # Create organization-specific directory
        org_path = self.base_path / organization_id
        org_path.mkdir(parents=True, exist_ok=True)

        # Save file
        file_path = org_path / file_id
        file_path.write_bytes(content)

        # Return relative path for storage
        return str(file_path.relative_to(self.base_path))

    async def get(self, storage_location: str) -> bytes:
        """Retrieve file from local storage."""
        file_path = self._get_file_path(storage_location)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {storage_location}")
        return file_path.read_bytes()

    async def delete(self, storage_location: str) -> None:
        """Delete file from local storage."""
        file_path = self._get_file_path(storage_location)
        if file_path.exists():
            file_path.unlink()
        # Clean up empty directories
        try:
            file_path.parent.rmdir()
        except OSError:
            pass

    async def exists(self, storage_location: str) -> bool:
        """Check if file exists in local storage."""
        file_path = self._get_file_path(storage_location)
        return file_path.exists()
