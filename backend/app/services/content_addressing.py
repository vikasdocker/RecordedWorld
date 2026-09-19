"""
Content Addressability Service

Provides content-hash-based addressing for world assets.
Ensures deduplication and integrity of shared content.
"""
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ContentAddress:
    """Content-addressed reference to an asset."""
    hash: str  # SHA-256 hex digest
    size_bytes: int
    content_type: str  # mesh, texture, terrain, metadata
    mime_type: str = "application/octet-stream"

    @property
    def short_hash(self) -> str:
        return self.hash[:12]


@dataclass
class ContentRecord:
    """Record of a content-addressed asset."""
    address: ContentAddress
    locations: List[str] = field(default_factory=list)  # storage paths/URLs
    references: int = 0  # number of references
    metadata: Dict[str, Any] = field(default_factory=dict)


class ContentAddressableStore:
    """Content-addressed storage for world assets."""

    def __init__(self):
        self.records: Dict[str, ContentRecord] = {}  # hash -> record

    def compute_hash(self, data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def compute_hash_json(self, obj: Any) -> str:
        serialized = json.dumps(obj, sort_keys=True, default=str)
        return self.compute_hash(serialized.encode())

    def store(
        self,
        data: bytes,
        content_type: str,
        locations: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ContentAddress:
        h = self.compute_hash(data)

        if h in self.records:
            self.records[h].references += 1
            return self.records[h].address

        address = ContentAddress(
            hash=h,
            size_bytes=len(data),
            content_type=content_type,
        )

        self.records[h] = ContentRecord(
            address=address,
            locations=locations or [],
            references=1,
            metadata=metadata or {},
        )

        return address

    def store_json(
        self,
        obj: Any,
        content_type: str,
        locations: Optional[List[str]] = None,
    ) -> ContentAddress:
        serialized = json.dumps(obj, sort_keys=True, default=str)
        return self.store(serialized.encode(), content_type, locations)

    def get(self, content_hash: str) -> Optional[ContentRecord]:
        return self.records.get(content_hash)

    def exists(self, content_hash: str) -> bool:
        return content_hash in self.records

    def dereference(self, content_hash: str) -> bool:
        if content_hash in self.records:
            self.records[content_hash].references += 1
            return True
        return False

    def release(self, content_hash: str) -> bool:
        if content_hash in self.records:
            self.records[content_hash].references -= 1
            return True
        return False

    def unreferenced(self) -> List[str]:
        return [h for h, r in self.records.items() if r.references <= 0]

    def gc(self) -> int:
        """Remove unreferenced content. Returns count removed."""
        to_remove = self.unreferenced()
        for h in to_remove:
            del self.records[h]
        return len(to_remove)

    def deduplicate(self) -> int:
        """Find and merge duplicate content. Returns count merged."""
        # Already content-addressed, so duplicates are naturally merged
        return 0

    def get_stats(self) -> Dict[str, Any]:
        total_size = sum(r.address.size_bytes for r in self.records.values())
        return {
            "total_objects": len(self.records),
            "total_size_mb": total_size / (1024 * 1024),
            "total_references": sum(r.references for r in self.records.values()),
            "content_types": {
                ct: sum(1 for r in self.records.values()
                        if r.address.content_type == ct)
                for ct in set(r.address.content_type for r in self.records.values())
            } if self.records else {},
        }


# Module-level singleton
content_store = ContentAddressableStore()
