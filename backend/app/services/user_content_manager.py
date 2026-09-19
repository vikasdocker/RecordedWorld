"""
User Content Independence Service

Ensures user-generated content is stored and managed independently from the base map.
Provides isolation, versioning, and conflict resolution for user content.
"""
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from enum import Enum


class ContentStatus(Enum):
    ACTIVE = "active"
    STALE = "stale"
    CONFLICT = "conflict"
    DELETED = "deleted"


@dataclass
class UserContent:
    """A piece of user-generated content independent of the base map."""
    id: str
    user_id: int
    content_type: str  # reconstruction, modification, annotation
    geo_bounds: Dict[str, float]  # geographic bounding box
    base_map_version: str  # version of base map when content was created
    current_base_map_version: str  # current base map version
    status: ContentStatus = ContentStatus.ACTIVE
    version: int = 1
    parent_id: Optional[str] = None  # for edits of existing content
    children_ids: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    @property
    def is_stale(self) -> bool:
        return self.base_map_version != self.current_base_map_version

    @property
    def has_children(self) -> bool:
        return len(self.children_ids) > 0


class UserContentManager:
    """Manages user-generated content independently from the base map."""

    def __init__(self):
        self.contents: Dict[str, UserContent] = {}
        self.user_contents: Dict[int, Set[str]] = {}  # user_id -> content_ids
        self.spatial_index: Dict[str, List[str]] = {}  # grid_cell -> content_ids

    def create_content(
        self,
        content_id: str,
        user_id: int,
        content_type: str,
        geo_bounds: Dict[str, float],
        base_map_version: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> UserContent:
        content = UserContent(
            id=content_id,
            user_id=user_id,
            content_type=content_type,
            geo_bounds=geo_bounds,
            base_map_version=base_map_version,
            current_base_map_version=base_map_version,
            metadata=metadata or {},
        )

        self.contents[content_id] = content
        self.user_contents.setdefault(user_id, set()).add(content_id)
        self._update_spatial_index(content)

        return content

    def update_content(
        self,
        content_id: str,
        base_map_version: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[UserContent]:
        content = self.contents.get(content_id)
        if not content:
            return None

        if base_map_version:
            content.current_base_map_version = base_map_version
            if content.base_map_version != base_map_version:
                content.status = ContentStatus.STALE

        if metadata:
            content.metadata.update(metadata)

        content.version += 1
        content.updated_at = time.time()
        return content

    def delete_content(self, content_id: str) -> bool:
        content = self.contents.get(content_id)
        if not content:
            return False

        content.status = ContentStatus.DELETED
        if content.user_id in self.user_contents:
            self.user_contents[content.user_id].discard(content_id)
        return True

    def get_content(self, content_id: str) -> Optional[UserContent]:
        content = self.contents.get(content_id)
        if content and content.status == ContentStatus.DELETED:
            return None
        return content

    def get_user_content(self, user_id: int) -> List[UserContent]:
        ids = self.user_contents.get(user_id, set())
        return [self.contents[cid] for cid in ids if cid in self.contents]

    def get_content_in_bounds(
        self, min_lat: float, min_lon: float, max_lat: float, max_lon: float
    ) -> List[UserContent]:
        result = []
        for content in self.contents.values():
            if content.status == ContentStatus.DELETED:
                continue
            cb = content.geo_bounds
            if (cb.get("min_lat", 0) <= max_lat and
                cb.get("max_lat", 0) >= min_lat and
                cb.get("min_lon", 0) <= max_lon and
                cb.get("max_lon", 0) >= min_lon):
                result.append(content)
        return result

    def check_conflicts(
        self, content_id: str
    ) -> List[str]:
        """Check if content overlaps with other user content."""
        content = self.contents.get(content_id)
        if not content:
            return []

        conflicts = []
        for other_id, other in self.contents.items():
            if other_id == content_id or other.status == ContentStatus.DELETED:
                continue
            if other.user_id == content.user_id:
                continue
            if self._bounds_overlap(content.geo_bounds, other.geo_bounds):
                conflicts.append(other_id)

        return conflicts

    def resolve_stale_content(self, content_id: str) -> Optional[UserContent]:
        """Mark stale content as needing update."""
        content = self.contents.get(content_id)
        if not content:
            return None

        if content.is_stale:
            content.status = ContentStatus.CONFLICT
        return content

    def _update_spatial_index(self, content: UserContent):
        cell = self._compute_grid_cell(content.geo_bounds)
        self.spatial_index.setdefault(cell, []).append(content.id)

    def _compute_grid_cell(self, bounds: Dict[str, float]) -> str:
        center_lat = (bounds.get("min_lat", 0) + bounds.get("max_lat", 0)) / 2
        center_lon = (bounds.get("min_lon", 0) + bounds.get("max_lon", 0)) / 2
        return f"{int(center_lat * 10)}_{int(center_lon * 10)}"

    def _bounds_overlap(self, b1: Dict, b2: Dict) -> bool:
        return not (b1.get("max_lat", 0) < b2.get("min_lat", 0) or
                    b1.get("min_lat", 0) > b2.get("max_lat", 0) or
                    b1.get("max_lon", 0) < b2.get("min_lon", 0) or
                    b1.get("min_lon", 0) > b2.get("max_lon", 0))

    def get_stats(self) -> Dict[str, Any]:
        active = sum(1 for c in self.contents.values()
                     if c.status == ContentStatus.ACTIVE)
        stale = sum(1 for c in self.contents.values()
                    if c.status == ContentStatus.STALE)
        return {
            "total_content": len(self.contents),
            "active": active,
            "stale": stale,
            "unique_users": len(self.user_contents),
        }


# Module-level singleton
user_content_manager = UserContentManager()
