"""
Asset Service

3D asset storage, retrieval, and delivery.
"""

from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime, timezone

from app.core.config import settings


class AssetService:
    """Manages 3D asset storage and delivery."""

    _assets: Dict[str, dict] = {}

    @classmethod
    def register_asset(
        cls,
        asset_id: str,
        file_path: Path,
        format: str = "glb",
        vertex_count: int = 0,
        face_count: int = 0,
        file_size_bytes: int = 0,
    ) -> dict:
        """Register an asset in the registry."""
        asset = {
            "id": asset_id,
            "file_path": str(file_path),
            "format": format,
            "vertex_count": vertex_count,
            "face_count": face_count,
            "file_size_bytes": file_size_bytes,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        cls._assets[asset_id] = asset
        return asset

    @classmethod
    def get_asset(cls, asset_id: str) -> Optional[dict]:
        """Get asset info by ID."""
        return cls._assets.get(asset_id)

    @classmethod
    def delete_asset(cls, asset_id: str) -> bool:
        """Delete an asset from registry and disk."""
        asset = cls._assets.pop(asset_id, None)
        if not asset:
            return False
        file_path = Path(asset["file_path"])
        if file_path.exists():
            file_path.unlink()
        return True

    @classmethod
    def get_asset_path(cls, asset_id: str) -> Optional[Path]:
        """Get the file path for an asset."""
        asset = cls._assets.get(asset_id)
        if not asset:
            return None
        return Path(asset["file_path"])

    @classmethod
    def get_asset_url(cls, asset_id: str) -> Optional[str]:
        """Get the delivery URL for an asset."""
        asset = cls._assets.get(asset_id)
        if not asset:
            return None
        fmt = asset.get("format", "glb")
        prefix = asset_id[:2] if len(asset_id) >= 2 else "aa"
        return f"/assets/{prefix}/{asset_id}_lod0.{fmt}"

    @classmethod
    def get_user_assets(cls, user_id: int) -> List[dict]:
        """Get all assets for a user (by directory convention)."""
        user_assets = []
        for asset_id, asset in cls._assets.items():
            if f"/{user_id}/" in asset.get("file_path", ""):
                user_assets.append(asset)
        return user_assets

    @classmethod
    def get_total_size(cls) -> int:
        """Get total size of all registered assets in bytes."""
        return sum(a.get("file_size_bytes", 0) for a in cls._assets.values())

    @classmethod
    def get_asset_count(cls) -> int:
        """Get number of registered assets."""
        return len(cls._assets)
