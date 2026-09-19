"""
Capture Metadata Validation Service

Validates and normalizes capture metadata from mobile devices.
Ensures required fields are present and values are within acceptable ranges.
"""
import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum


class ValidationSeverity(Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationIssue:
    field: str
    message: str
    severity: ValidationSeverity
    value: Any = None


@dataclass
class CaptureMetadata:
    """Normalized capture metadata."""
    duration_seconds: float = 0.0
    resolution_width: int = 0
    resolution_height: int = 0
    fps: float = 30.0
    device_make: str = ""
    device_model: str = ""
    os_version: str = ""
    app_version: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude: Optional[float] = None
    gps_accuracy_m: Optional[float] = None
    heading: Optional[float] = None
    pitch: Optional[float] = None
    roll: Optional[float] = None
    focal_length_mm: Optional[float] = None
    sensor_width_mm: Optional[float] = None
    sensor_height_mm: Optional[float] = None

    @property
    def resolution_string(self) -> str:
        return f"{self.resolution_width}x{self.resolution_height}"

    @property
    def aspect_ratio(self) -> float:
        if self.resolution_height > 0:
            return self.resolution_width / self.resolution_height
        return 0.0

    @property
    def megapixels(self) -> float:
        return (self.resolution_width * self.resolution_height) / 1_000_000

    def to_dict(self) -> Dict[str, Any]:
        return {
            "duration_seconds": self.duration_seconds,
            "resolution": self.resolution_string,
            "fps": self.fps,
            "device": f"{self.device_make} {self.device_model}",
            "os_version": self.os_version,
            "app_version": self.app_version,
            "location": {
                "lat": self.latitude,
                "lon": self.longitude,
                "alt": self.altitude,
                "accuracy_m": self.gps_accuracy_m,
            } if self.latitude is not None else None,
            "orientation": {
                "heading": self.heading,
                "pitch": self.pitch,
                "roll": self.roll,
            },
            "camera": {
                "focal_length_mm": self.focal_length_mm,
                "sensor_width_mm": self.sensor_width_mm,
                "sensor_height_mm": self.sensor_height_mm,
            },
        }


class CaptureMetadataValidator:
    """Validates capture metadata from mobile devices."""

    SUPPORTED_RESOLUTIONS = [
        (3840, 2160),  # 4K
        (2560, 1440),  # 1440p
        (1920, 1080),  # 1080p
        (1280, 720),   # 720p
        (854, 480),    # 480p
    ]

    VALID_FPS = [24, 25, 30, 60, 120]
    MIN_DURATION = 1.0  # seconds
    MAX_DURATION = 300.0  # 5 minutes
    MAX_GPS_ACCURACY = 50.0  # meters

    def validate(self, raw_metadata: Dict[str, Any]) -> Tuple[CaptureMetadata, List[ValidationIssue]]:
        issues = []
        meta = CaptureMetadata()

        meta.duration_seconds = self._validate_duration(raw_metadata, issues)
        meta.resolution_width, meta.resolution_height = self._validate_resolution(raw_metadata, issues)
        meta.fps = self._validate_fps(raw_metadata, issues)
        meta.device_make = raw_metadata.get("device_make", "")
        meta.device_model = raw_metadata.get("device_model", "")
        meta.os_version = raw_metadata.get("os_version", "")
        meta.app_version = raw_metadata.get("app_version", "")

        meta.latitude = self._validate_coordinate(raw_metadata, "latitude", -90, 90, issues)
        meta.longitude = self._validate_coordinate(raw_metadata, "longitude", -180, 180, issues)
        meta.altitude = raw_metadata.get("altitude")
        meta.gps_accuracy_m = self._validate_gps_accuracy(raw_metadata, issues)

        meta.heading = self._validate_angle(raw_metadata, "heading", issues)
        meta.pitch = self._validate_angle(raw_metadata, "pitch", issues)
        meta.roll = self._validate_angle(raw_metadata, "roll", issues)

        meta.focal_length_mm = raw_metadata.get("focal_length_mm")
        meta.sensor_width_mm = raw_metadata.get("sensor_width_mm")
        meta.sensor_height_mm = raw_metadata.get("sensor_height_mm")

        return meta, issues

    def _validate_duration(self, raw: Dict, issues: List[ValidationIssue]) -> float:
        duration = raw.get("duration_seconds", 0)
        if not isinstance(duration, (int, float)) or duration <= 0:
            issues.append(ValidationIssue(
                "duration_seconds", "Missing or invalid duration",
                ValidationSeverity.ERROR, duration,
            ))
            return 0.0

        if duration < self.MIN_DURATION:
            issues.append(ValidationIssue(
                "duration_seconds", f"Duration too short (min {self.MIN_DURATION}s)",
                ValidationSeverity.WARNING, duration,
            ))
        elif duration > self.MAX_DURATION:
            issues.append(ValidationIssue(
                "duration_seconds", f"Duration too long (max {self.MAX_DURATION}s)",
                ValidationSeverity.WARNING, duration,
            ))

        return float(duration)

    def _validate_resolution(self, raw: Dict, issues: List[ValidationIssue]) -> Tuple[int, int]:
        res = raw.get("resolution", "")
        if isinstance(res, str) and "x" in res:
            parts = res.split("x")
            try:
                w, h = int(parts[0]), int(parts[1])
                if w > 0 and h > 0:
                    return w, h
            except (ValueError, IndexError):
                pass

        w = raw.get("resolution_width", 0)
        h = raw.get("resolution_height", 0)
        if isinstance(w, int) and isinstance(h, int) and w > 0 and h > 0:
            return w, h

        issues.append(ValidationIssue(
            "resolution", "Missing or invalid resolution",
            ValidationSeverity.WARNING, res,
        ))
        return 1920, 1080  # default

    def _validate_fps(self, raw: Dict, issues: List[ValidationIssue]) -> float:
        fps = raw.get("fps", 30.0)
        if not isinstance(fps, (int, float)) or fps <= 0:
            issues.append(ValidationIssue(
                "fps", "Invalid FPS value",
                ValidationSeverity.WARNING, fps,
            ))
            return 30.0

        if fps not in self.VALID_FPS:
            issues.append(ValidationIssue(
                "fps", f"Non-standard FPS: {fps}",
                ValidationSeverity.INFO, fps,
            ))

        return float(fps)

    def _validate_coordinate(
        self, raw: Dict, field: str, min_val: float, max_val: float,
        issues: List[ValidationIssue],
    ) -> Optional[float]:
        val = raw.get(field)
        if val is None:
            issues.append(ValidationIssue(
                field, f"Missing {field}",
                ValidationSeverity.WARNING, val,
            ))
            return None

        if not isinstance(val, (int, float)) or not (min_val <= val <= max_val):
            issues.append(ValidationIssue(
                field, f"Invalid {field}: {val}",
                ValidationSeverity.ERROR, val,
            ))
            return None

        return float(val)

    def _validate_gps_accuracy(self, raw: Dict, issues: List[ValidationIssue]) -> Optional[float]:
        accuracy = raw.get("gps_accuracy_m")
        if accuracy is None:
            return None

        if not isinstance(accuracy, (int, float)) or accuracy < 0:
            issues.append(ValidationIssue(
                "gps_accuracy_m", "Invalid GPS accuracy",
                ValidationSeverity.WARNING, accuracy,
            ))
            return None

        if accuracy > self.MAX_GPS_ACCURACY:
            issues.append(ValidationIssue(
                "gps_accuracy_m", f"GPS accuracy too low: {accuracy}m",
                ValidationSeverity.WARNING, accuracy,
            ))

        return float(accuracy)

    def _validate_angle(self, raw: Dict, field: str, issues: List[ValidationIssue]) -> Optional[float]:
        val = raw.get(field)
        if val is None:
            return None

        if not isinstance(val, (int, float)):
            issues.append(ValidationIssue(
                field, f"Invalid {field} value",
                ValidationSeverity.INFO, val,
            ))
            return None

        return float(val) % 360.0

    def get_quality_score(self, meta: CaptureMetadata) -> float:
        score = 100.0

        if meta.duration_seconds < 5:
            score -= 20
        elif meta.duration_seconds < 10:
            score -= 10

        if meta.resolution_width < 1920:
            score -= 15
        elif meta.resolution_width < 2560:
            score -= 5

        if meta.gps_accuracy_m and meta.gps_accuracy_m > 10:
            score -= 15
        elif meta.gps_accuracy_m and meta.gps_accuracy_m > 5:
            score -= 5

        if meta.focal_length_mm is None:
            score -= 10

        if meta.latitude is None:
            score -= 20

        return max(0.0, min(100.0, score))


# Module-level singleton
capture_validator = CaptureMetadataValidator()
