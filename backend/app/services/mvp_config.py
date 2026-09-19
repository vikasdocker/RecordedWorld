"""
MVP Configuration

Defines the MVP scope, components, and validation.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class MVPComponent:
    """A component of the MVP."""
    name: str
    description: str
    phase: int
    status: str  # complete, partial, missing
    test_file: Optional[str] = None
    test_count: int = 0


# MVP Components
MVP_COMPONENTS = [
    MVPComponent(
        name="Geospatial Foundation",
        description="WGS84, ENU, GeoTransform, haversine",
        phase=1,
        status="complete",
        test_file="test_geolocation.py",
        test_count=15,
    ),
    MVPComponent(
        name="Media Ingestion",
        description="Video upload, validation, frame extraction",
        phase=5,
        status="complete",
    ),
    MVPComponent(
        name="3D Reconstruction",
        description="Mesh generation, optimization, LOD",
        phase=6,
        status="partial",
    ),
    MVPComponent(
        name="Geolocation & Alignment",
        description="Procrustes, RANSAC, global transform",
        phase=8,
        status="complete",
        test_file="test_geolocation.py",
        test_count=15,
    ),
    MVPComponent(
        name="Location Discovery",
        description="Nearby search, spatial indexing",
        phase=11,
        status="complete",
        test_file="test_location_discovery.py",
    ),
    MVPComponent(
        name="Player Avatars",
        description="Color picker, labels, animation",
        phase=12,
        status="complete",
        test_file="test_avatar.py",
        test_count=11,
    ),
    MVPComponent(
        name="Real-Time Multiplayer",
        description="WebSocket server, position sync",
        phase=13,
        status="complete",
        test_file="test_multiplayer.py",
    ),
    MVPComponent(
        name="Friend System",
        description="Friendship, blocking, visibility",
        phase=14,
        status="complete",
    ),
    MVPComponent(
        name="Location Tags",
        description="Tag CRUD, display",
        phase=15,
        status="complete",
        test_file="test_tags.py",
        test_count=14,
    ),
    MVPComponent(
        name="Privacy & Safety",
        description="Soft delete, restore, reporting",
        phase=16,
        status="complete",
        test_file="test_privacy.py",
        test_count=20,
    ),
    MVPComponent(
        name="Content Moderation",
        description="Policy, queue, approve/reject",
        phase=17,
        status="complete",
        test_file="test_moderation.py",
        test_count=18,
    ),
    MVPComponent(
        name="Asset Optimization",
        description="LOD, glTF export, CDN paths",
        phase=18,
        status="partial",
        test_file="test_asset_optimization.py",
        test_count=21,
    ),
    MVPComponent(
        name="World Precision",
        description="Floating origin, chunk coordinates",
        phase=20,
        status="complete",
        test_file="test_world_precision.py",
        test_count=25,
    ),
    MVPComponent(
        name="Backend Services",
        description="Auth, player, location, world, media, etc.",
        phase=21,
        status="complete",
        test_file="test_services.py",
        test_count=51,
    ),
    MVPComponent(
        name="Database",
        description="PostgreSQL/SQLite, indexes, health",
        phase=22,
        status="complete",
        test_file="test_database.py",
        test_count=23,
    ),
    MVPComponent(
        name="Job Queue",
        description="Reconstruction job processing",
        phase=23,
        status="complete",
        test_file="test_job_queue.py",
        test_count=23,
    ),
    MVPComponent(
        name="Gameplay",
        description="Exploration, quests, achievements",
        phase=24,
        status="complete",
        test_file="test_gameplay.py",
        test_count=22,
    ),
    MVPComponent(
        name="Performance",
        description="Monitoring, caching, optimization",
        phase=25,
        status="complete",
        test_file="test_performance.py",
        test_count=24,
    ),
    MVPComponent(
        name="Security",
        description="Rate limiting, validation, audit, signed URLs",
        phase=26,
        status="complete",
        test_file="test_security.py",
        test_count=39,
    ),
    MVPComponent(
        name="Testing",
        description="API integration, unit tests, WebSocket tests",
        phase=27,
        status="complete",
        test_file="test_api_integration.py",
        test_count=22,
    ),
    MVPComponent(
        name="Observability",
        description="Tracing, error tracking, metrics",
        phase=28,
        status="complete",
        test_file="test_observability.py",
        test_count=16,
    ),
]


def get_mvp_status() -> Dict:
    """Get overall MVP status."""
    total = len(MVP_COMPONENTS)
    complete = sum(1 for c in MVP_COMPONENTS if c.status == "complete")
    partial = sum(1 for c in MVP_COMPONENTS if c.status == "partial")
    missing = sum(1 for c in MVP_COMPONENTS if c.status == "missing")
    total_tests = sum(c.test_count for c in MVP_COMPONENTS)

    return {
        "total_components": total,
        "complete": complete,
        "partial": partial,
        "missing": missing,
        "completion_percent": round(complete / total * 100, 1),
        "total_tests": total_tests,
        "components": [
            {"name": c.name, "phase": c.phase, "status": c.status}
            for c in MVP_COMPONENTS
        ],
    }


def validate_mvp_readiness() -> Dict:
    """Validate MVP readiness."""
    issues = []
    for c in MVP_COMPONENTS:
        if c.status == "missing":
            issues.append(f"MISSING: {c.name} (Phase {c.phase})")
        elif c.status == "partial":
            issues.append(f"PARTIAL: {c.name} (Phase {c.phase})")

    return {
        "ready": len(issues) == 0,
        "issues": issues,
        "readiness_score": round(
            sum(1 for c in MVP_COMPONENTS if c.status == "complete") /
            len(MVP_COMPONENTS) * 100, 1
        ),
    }
