"""
Memory Manager for World Streaming

Tracks and manages memory usage for loaded world content.
Implements budget-based eviction and memory pools.
"""
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from enum import Enum


class MemoryPool(Enum):
    TERRAIN = "terrain"
    MESHES = "meshes"
    TEXTURES = "textures"
    AUDIO = "audio"
    SCRIPTS = "scripts"
    GENERAL = "general"


@dataclass
class MemoryBlock:
    """A block of allocated memory."""
    id: str
    pool: MemoryPool
    size_bytes: int
    owner_id: str  # chunk or asset ID
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    pinned: bool = False

    @property
    def age_seconds(self) -> float:
        return time.time() - self.created_at

    @property
    def idle_seconds(self) -> float:
        return time.time() - self.last_accessed


@dataclass
class MemoryBudget:
    """Memory budget configuration."""
    total_mb: float = 512.0
    pool_budgets: Dict[MemoryPool, float] = field(default_factory=lambda: {
        MemoryPool.TERRAIN: 128.0,
        MemoryPool.MESHES: 128.0,
        MemoryPool.TEXTURES: 256.0,
        MemoryPool.AUDIO: 32.0,
        MemoryPool.SCRIPTS: 16.0,
        MemoryPool.GENERAL: 64.0,
    })


class MemoryManager:
    """Tracks and manages memory for world content."""

    def __init__(self, budget: Optional[MemoryBudget] = None):
        self.budget = budget or MemoryBudget()
        self.blocks: Dict[str, MemoryBlock] = {}
        self.pool_usage: Dict[MemoryPool, int] = {p: 0 for p in MemoryPool}

    def allocate(
        self,
        block_id: str,
        pool: MemoryPool,
        size_bytes: int,
        owner_id: str,
        pinned: bool = False,
    ) -> bool:
        """Allocate memory block if within budget."""
        if self.pool_usage[pool] + size_bytes > self.budget.pool_budgets.get(pool, 0) * 1024 * 1024:
            self._evict_from_pool(pool, size_bytes)

        if self.pool_usage[pool] + size_bytes > self.budget.pool_budgets.get(pool, 0) * 1024 * 1024:
            return False

        block = MemoryBlock(
            id=block_id,
            pool=pool,
            size_bytes=size_bytes,
            owner_id=owner_id,
            pinned=pinned,
        )
        self.blocks[block_id] = block
        self.pool_usage[pool] += size_bytes
        return True

    def free(self, block_id: str) -> bool:
        block = self.blocks.pop(block_id, None)
        if block:
            self.pool_usage[block.pool] -= block.size_bytes
            return True
        return False

    def touch(self, block_id: str):
        if block_id in self.blocks:
            self.blocks[block_id].last_accessed = time.time()

    def get_usage(self) -> Dict[str, Any]:
        total = sum(self.pool_usage.values())
        return {
            "total_mb": total / (1024 * 1024),
            "budget_mb": self.budget.total_mb,
            "usage_pct": total / (self.budget.total_mb * 1024 * 1024) * 100,
            "by_pool": {
                p.value: usage / (1024 * 1024)
                for p, usage in self.pool_usage.items()
            },
            "block_count": len(self.blocks),
        }

    def get_eviction_candidates(
        self, pool: MemoryPool, needed_bytes: int
    ) -> List[MemoryBlock]:
        candidates = [
            b for b in self.blocks.values()
            if b.pool == pool and not b.pinned
        ]
        candidates.sort(key=lambda b: (b.idle_seconds, b.age_seconds), reverse=True)

        result = []
        freed = 0
        for block in candidates:
            if freed >= needed_bytes:
                break
            result.append(block)
            freed += block.size_bytes
        return result

    def _evict_from_pool(self, pool: MemoryPool, needed_bytes: int):
        candidates = self.get_eviction_candidates(pool, needed_bytes)
        for block in candidates:
            self.free(block.id)

    def get_total_usage_bytes(self) -> int:
        return sum(self.pool_usage.values())

    def get_stats(self) -> Dict[str, Any]:
        usage = self.get_usage()
        pinned = sum(1 for b in self.blocks.values() if b.pinned)
        return {
            **usage,
            "pinned_blocks": pinned,
            "evictable_blocks": len(self.blocks) - pinned,
        }


# Module-level singleton
memory_manager = MemoryManager()
