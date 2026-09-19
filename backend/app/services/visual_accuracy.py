"""
Visual Accuracy Service

Explicit accuracy measurement and reporting for 3D reconstructions:
- Geographic error calculation (horizontal + vertical)
- Rotation error calculation (yaw, pitch, roll deviations)
- Scale error calculation (deviation from ground truth)
- Quality metrics (comprehensive scoring)
- Confidence scoring (based on error distribution)
- Accuracy report generation

Metrics Format:
  Position Accuracy: X.Xm
  Rotation Accuracy: ±X.X°
  Scale Accuracy: ±X.X%
  Vertical Accuracy: X.Xm
  Reconstruction Quality: HIGH/MEDIUM/LOW
  Alignment Confidence: XX%
"""

import math
import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from datetime import datetime, timezone

from app.core.geospatial import WGS84Coordinate, haversine_distance
from app.services.geolocation import (
    LocalPoint,
    GPSPoint,
    GlobalTransform,
    AccuracyReport,
)


# =============================================================================
# Accuracy Metrics
# =============================================================================

@dataclass
class GeographicError:
    """Error in geographic positioning."""
    horizontal_error_mean: float  # meters
    horizontal_error_max: float  # meters
    horizontal_error_std: float  # meters
    vertical_error_mean: float  # meters
    vertical_error_max: float  # meters
    vertical_error_std: float  # meters
    rmse: float  # root mean square error (meters)

    def to_dict(self) -> dict:
        return {
            "horizontal_error_mean": round(self.horizontal_error_mean, 4),
            "horizontal_error_max": round(self.horizontal_error_max, 4),
            "horizontal_error_std": round(self.horizontal_error_std, 4),
            "vertical_error_mean": round(self.vertical_error_mean, 4),
            "vertical_error_max": round(self.vertical_error_max, 4),
            "vertical_error_std": round(self.vertical_error_std, 4),
            "rmse": round(self.rmse, 4),
        }


@dataclass
class RotationError:
    """Error in rotation alignment."""
    yaw_error: float  # degrees
    pitch_error: float  # degrees
    roll_error: float  # degrees
    mean_angular_error: float  # degrees
    max_angular_error: float  # degrees

    def to_dict(self) -> dict:
        return {
            "yaw_error": round(self.yaw_error, 4),
            "pitch_error": round(self.pitch_error, 4),
            "roll_error": round(self.roll_error, 4),
            "mean_angular_error": round(self.mean_angular_error, 4),
            "max_angular_error": round(self.max_angular_error, 4),
        }


@dataclass
class ScaleError:
    """Error in scale estimation."""
    scale_factor: float  # estimated scale (should be ~1.0)
    scale_deviation: float  # |scale - 1.0| * 100 (percentage)
    scale_error_percent: float  # percentage error
    is_consistent: bool  # whether scale is uniform across the model

    def to_dict(self) -> dict:
        return {
            "scale_factor": round(self.scale_factor, 6),
            "scale_deviation": round(self.scale_deviation, 4),
            "scale_error_percent": round(self.scale_error_percent, 4),
            "is_consistent": self.is_consistent,
        }


@dataclass
class QualityMetrics:
    """Comprehensive quality assessment."""
    overall_score: float  # 0-100
    position_score: float  # 0-100
    rotation_score: float  # 0-100
    scale_score: float  # 0-100
    completeness_score: float  # 0-100
    quality_label: str  # "high", "medium", "low"
    confidence: float  # 0-1

    def to_dict(self) -> dict:
        return {
            "overall_score": round(self.overall_score, 2),
            "position_score": round(self.position_score, 2),
            "rotation_score": round(self.rotation_score, 2),
            "scale_score": round(self.scale_score, 2),
            "completeness_score": round(self.completeness_score, 2),
            "quality_label": self.quality_label,
            "confidence": round(self.confidence, 4),
        }


@dataclass
class AccuracyReport:
    """Complete accuracy report for a reconstruction."""
    location_id: Optional[int] = None
    geographic_error: Optional[GeographicError] = None
    rotation_error: Optional[RotationError] = None
    scale_error: Optional[ScaleError] = None
    quality_metrics: Optional[QualityMetrics] = None
    num_control_points: int = 0
    num_test_points: int = 0
    alignment_method: str = "unknown"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "location_id": self.location_id,
            "geographic_error": self.geographic_error.to_dict() if self.geographic_error else None,
            "rotation_error": self.rotation_error.to_dict() if self.rotation_error else None,
            "scale_error": self.scale_error.to_dict() if self.scale_error else None,
            "quality_metrics": self.quality_metrics.to_dict() if self.quality_metrics else None,
            "num_control_points": self.num_control_points,
            "num_test_points": self.num_test_points,
            "alignment_method": self.alignment_method,
            "created_at": self.created_at.isoformat(),
        }

    def summary(self) -> str:
        """Human-readable summary of accuracy."""
        lines = []
        if self.geographic_error:
            lines.append(f"Position Accuracy: {self.geographic_error.horizontal_error_mean:.1f}m")
        if self.rotation_error:
            lines.append(f"Rotation Accuracy: ±{self.rotation_error.mean_angular_error:.1f}°")
        if self.scale_error:
            lines.append(f"Scale Accuracy: ±{self.scale_error.scale_error_percent:.1f}%")
        if self.quality_metrics:
            lines.append(f"Reconstruction Quality: {self.quality_metrics.quality_label.upper()}")
            lines.append(f"Alignment Confidence: {self.quality_metrics.confidence * 100:.0f}%")
        return "\n".join(lines)


# =============================================================================
# Error Calculation Functions
# =============================================================================

def calculate_geographic_error(
    predicted_points: List[WGS84Coordinate],
    ground_truth_points: List[WGS84Coordinate],
) -> GeographicError:
    """
    Calculate geographic error between predicted and ground truth positions.
    """
    horizontal_errors = []
    vertical_errors = []

    for pred, gt in zip(predicted_points, ground_truth_points):
        # Horizontal error (haversine)
        h_error = haversine_distance(pred, gt)
        horizontal_errors.append(h_error)

        # Vertical error
        v_error = abs(pred.altitude - gt.altitude)
        vertical_errors.append(v_error)

    h_arr = np.array(horizontal_errors)
    v_arr = np.array(vertical_errors)

    # RMSE
    rmse = float(np.sqrt(np.mean(h_arr ** 2 + v_arr ** 2)))

    return GeographicError(
        horizontal_error_mean=float(np.mean(h_arr)),
        horizontal_error_max=float(np.max(h_arr)),
        horizontal_error_std=float(np.std(h_arr)),
        vertical_error_mean=float(np.mean(v_arr)),
        vertical_error_max=float(np.max(v_arr)),
        vertical_error_std=float(np.std(v_arr)),
        rmse=rmse,
    )


def calculate_rotation_error(
    estimated_rotation: np.ndarray,
    ground_truth_rotation: np.ndarray,
) -> RotationError:
    """
    Calculate rotation error between estimated and ground truth rotations.

    Both rotations are 3x3 matrices. Error is computed as the
    angular deviation of the rotation difference.
    """
    # Rotation difference
    R_diff = estimated_rotation @ ground_truth_rotation.T

    # Convert to axis-angle
    angle = math.acos(np.clip((np.trace(R_diff) - 1) / 2, -1, 1))
    angle_deg = math.degrees(angle)

    # Extract Euler angles (approximate)
    # Yaw (rotation around Y axis)
    yaw_error = math.degrees(math.atan2(R_diff[0, 2], R_diff[0, 0]))
    # Pitch (rotation around X axis)
    pitch_error = math.degrees(math.atan2(-R_diff[1, 2], R_diff[2, 2]))
    # Roll (rotation around Z axis)
    roll_error = math.degrees(math.atan2(R_diff[1, 0], R_diff[1, 1]))

    return RotationError(
        yaw_error=abs(yaw_error),
        pitch_error=abs(pitch_error),
        roll_error=abs(roll_error),
        mean_angular_error=angle_deg,
        max_angular_error=max(abs(yaw_error), abs(pitch_error), abs(roll_error)),
    )


def calculate_scale_error(
    estimated_scale: float,
    ground_truth_scale: float = 1.0,
    local_distances: Optional[List[float]] = None,
    gps_distances: Optional[List[float]] = None,
) -> ScaleError:
    """
    Calculate scale error.
    """
    scale_deviation = abs(estimated_scale - ground_truth_scale) * 100
    scale_error_percent = abs(estimated_scale - ground_truth_scale) / ground_truth_scale * 100

    # Check consistency if distances provided
    is_consistent = True
    if local_distances and gps_distances and len(local_distances) == len(gps_distances):
        ratios = [gps / local for local, gps in zip(local_distances, gps_distances) if local > 0]
        if ratios:
            ratio_std = float(np.std(ratios))
            is_consistent = ratio_std < 0.1  # less than 10% variation

    return ScaleError(
        scale_factor=estimated_scale,
        scale_deviation=scale_deviation,
        scale_error_percent=scale_error_percent,
        is_consistent=is_consistent,
    )


def calculate_quality_metrics(
    geo_error: GeographicError,
    rot_error: RotationError,
    scale_error: ScaleError,
    num_points: int,
    expected_points: int = 100,
) -> QualityMetrics:
    """
    Calculate comprehensive quality metrics.
    """
    # Position score (0-100, lower error = higher score)
    if geo_error.horizontal_error_mean < 1:
        position_score = 100
    elif geo_error.horizontal_error_mean < 5:
        position_score = 90 - (geo_error.horizontal_error_mean - 1) * 5
    elif geo_error.horizontal_error_mean < 20:
        position_score = 70 - (geo_error.horizontal_error_mean - 5) * 2
    elif geo_error.horizontal_error_mean < 50:
        position_score = 40 - (geo_error.horizontal_error_mean - 20)
    else:
        position_score = max(0, 30 - geo_error.horizontal_error_mean / 5)

    # Rotation score (0-100)
    if rot_error.mean_angular_error < 1:
        rotation_score = 100
    elif rot_error.mean_angular_error < 5:
        rotation_score = 90 - (rot_error.mean_angular_error - 1) * 5
    elif rot_error.mean_angular_error < 15:
        rotation_score = 70 - (rot_error.mean_angular_error - 5) * 2
    else:
        rotation_score = max(0, 50 - rot_error.mean_angular_error)

    # Scale score (0-100)
    if scale_error.scale_error_percent < 1:
        scale_score = 100
    elif scale_error.scale_error_percent < 5:
        scale_score = 90 - (scale_error.scale_error_percent - 1) * 5
    elif scale_error.scale_error_percent < 20:
        scale_score = 70 - (scale_error.scale_error_percent - 5) * 2
    else:
        scale_score = max(0, 50 - scale_error.scale_error_percent)

    # Completeness score
    completeness_score = min(100, (num_points / expected_points) * 100)

    # Overall score (weighted average)
    overall_score = (
        position_score * 0.4 +
        rotation_score * 0.2 +
        scale_score * 0.2 +
        completeness_score * 0.2
    )

    # Quality label
    if overall_score >= 80:
        quality_label = "high"
    elif overall_score >= 50:
        quality_label = "medium"
    else:
        quality_label = "low"

    # Confidence
    confidence = min(1.0, overall_score / 100)

    return QualityMetrics(
        overall_score=overall_score,
        position_score=position_score,
        rotation_score=rotation_score,
        scale_score=scale_score,
        completeness_score=completeness_score,
        quality_label=quality_label,
        confidence=confidence,
    )


# =============================================================================
# High-Level API
# =============================================================================

def compute_accuracy_report(
    local_points: List[LocalPoint],
    gps_points: List[GPSPoint],
    transform: GlobalTransform,
    estimated_rotation: Optional[np.ndarray] = None,
    ground_truth_rotation: Optional[np.ndarray] = None,
    estimated_scale: float = 1.0,
    location_id: Optional[int] = None,
    alignment_method: str = "unknown",
) -> AccuracyReport:
    """
    Compute a complete accuracy report for a reconstruction alignment.

    Args:
        local_points: Points in local reconstruction space
        gps_points: Corresponding GPS ground truth
        transform: Computed alignment transform
        estimated_rotation: Optional estimated rotation matrix
        ground_truth_rotation: Optional ground truth rotation matrix
        estimated_scale: Estimated scale factor
        location_id: Optional location ID
        alignment_method: Method used for alignment

    Returns:
        Complete AccuracyReport
    """
    # Geographic error
    predicted = [transform.apply(lp) for lp in local_points]
    gt = [WGS84Coordinate(gp.latitude, gp.longitude, gp.altitude) for gp in gps_points]
    geo_error = calculate_geographic_error(predicted, gt)

    # Rotation error
    rot_error = None
    if estimated_rotation is not None and ground_truth_rotation is not None:
        rot_error = calculate_rotation_error(estimated_rotation, ground_truth_rotation)
    else:
        # Default rotation error
        rot_error = RotationError(
            yaw_error=0, pitch_error=0, roll_error=0,
            mean_angular_error=0, max_angular_error=0,
        )

    # Scale error
    scale_error = calculate_scale_error(estimated_scale)

    # Quality metrics
    quality = calculate_quality_metrics(
        geo_error, rot_error, scale_error,
        num_points=len(local_points),
    )

    return AccuracyReport(
        location_id=location_id,
        geographic_error=geo_error,
        rotation_error=rot_error,
        scale_error=scale_error,
        quality_metrics=quality,
        num_control_points=len(local_points),
        alignment_method=alignment_method,
    )
