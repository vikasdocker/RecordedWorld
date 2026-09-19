"""
Video Quality Settings Service

Manages video capture quality presets and adaptive quality selection
based on device capabilities and storage constraints.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum


class QualityPreset(Enum):
    ULTRA = "ultra"  # 4K 60fps
    HIGH = "high"  # 4K 30fps or 1080p 60fps
    MEDIUM = "medium"  # 1080p 30fps
    LOW = "low"  # 720p 30fps
    MINIMAL = "minimal"  # 480p 24fps


@dataclass
class QualityProfile:
    """A quality profile with capture settings."""
    preset: QualityPreset
    resolution_width: int
    resolution_height: int
    fps: float
    bitrate_mbps: float
    codec: str = "h264"
    keyframe_interval: int = 2
    stabilization: bool = True
    hdr: bool = False

    @property
    def resolution_string(self) -> str:
        return f"{self.resolution_width}x{self.resolution_height}"

    @property
    def pixels_per_frame(self) -> int:
        return self.resolution_width * self.resolution_height

    @property
    def estimated_mb_per_minute(self) -> float:
        return self.bitrate_mbps * 60 / 8

    def to_dict(self) -> Dict[str, Any]:
        return {
            "preset": self.preset.value,
            "resolution": self.resolution_string,
            "fps": self.fps,
            "bitrate_mbps": self.bitrate_mbps,
            "codec": self.codec,
            "stabilization": self.stabilization,
            "hdr": self.hdr,
        }


QUALITY_PROFILES: Dict[QualityPreset, QualityProfile] = {
    QualityPreset.ULTRA: QualityProfile(
        preset=QualityPreset.ULTRA,
        resolution_width=3840, resolution_height=2160,
        fps=60.0, bitrate_mbps=100.0, hdr=True,
    ),
    QualityPreset.HIGH: QualityProfile(
        preset=QualityPreset.HIGH,
        resolution_width=3840, resolution_height=2160,
        fps=30.0, bitrate_mbps=50.0,
    ),
    QualityPreset.MEDIUM: QualityProfile(
        preset=QualityPreset.MEDIUM,
        resolution_width=1920, resolution_height=1080,
        fps=30.0, bitrate_mbps=20.0,
    ),
    QualityPreset.LOW: QualityProfile(
        preset=QualityPreset.LOW,
        resolution_width=1280, resolution_height=720,
        fps=30.0, bitrate_mbps=8.0,
    ),
    QualityPreset.MINIMAL: QualityProfile(
        preset=QualityPreset.MINIMAL,
        resolution_width=854, resolution_height=480,
        fps=24.0, bitrate_mbps=3.0, stabilization=False,
    ),
}


@dataclass
class DeviceCapabilities:
    """Device capability constraints."""
    device_id: str
    max_resolution_width: int = 3840
    max_resolution_height: int = 2160
    max_fps: float = 60.0
    supports_hdr: bool = False
    supports_4k: bool = True
    storage_free_mb: float = 10000.0
    battery_percent: float = 100.0


class VideoQualityService:
    """Manages video quality settings and adaptive selection."""

    def __init__(self):
        self.profiles = dict(QUALITY_PROFILES)
        self.device_capabilities: Dict[str, DeviceCapabilities] = {}

    def get_profile(self, preset: QualityPreset) -> Optional[QualityProfile]:
        return self.profiles.get(preset)

    def get_all_profiles(self) -> List[QualityProfile]:
        return list(self.profiles.values())

    def register_device(self, caps: DeviceCapabilities):
        self.device_capabilities[caps.device_id] = caps

    def select_optimal_quality(
        self,
        device_id: str,
        duration_minutes: float = 1.0,
        storage_reserve_mb: float = 500.0,
    ) -> QualityProfile:
        caps = self.device_capabilities.get(device_id)
        if not caps:
            return self.profiles[QualityPreset.MEDIUM]

        available_mb = caps.storage_free_mb - storage_reserve_mb
        sorted_profiles = sorted(
            self.profiles.values(),
            key=lambda p: p.pixels_per_frame * p.fps,
            reverse=True,
        )

        for profile in sorted_profiles:
            if profile.resolution_width > caps.max_resolution_width:
                continue
            if profile.resolution_height > caps.max_resolution_height:
                continue
            if profile.fps > caps.max_fps:
                continue
            if profile.hdr and not caps.supports_hdr:
                continue
            if profile.resolution_width >= 3840 and not caps.supports_4k:
                continue
            if profile.estimated_mb_per_minute * duration_minutes > available_mb:
                continue
            return profile

        return self.profiles[QualityPreset.MINIMAL]

    def get_recommended_for_3d(self) -> QualityProfile:
        return self.profiles[QualityPreset.HIGH]

    def get_storage_estimate(
        self, preset: QualityPreset, duration_minutes: float
    ) -> float:
        profile = self.profiles.get(preset)
        if not profile:
            return 0.0
        return profile.estimated_mb_per_minute * duration_minutes

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_profiles": len(self.profiles),
            "registered_devices": len(self.device_capabilities),
            "presets": [p.value for p in self.profiles],
        }


# Module-level singleton
video_quality_service = VideoQualityService()
