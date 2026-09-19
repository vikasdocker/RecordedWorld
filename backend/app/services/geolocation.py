"""
Geolocation Service

Aligns 3D reconstructions to real-world GPS coordinates:
- Global transform computation (local → GPS aligned)
- Accuracy estimation (reprojection + GPS error)
- Alignment metadata storage
- Map matching (GPS to reconstruction alignment)

Pipeline:
  GPS Track + Local 3D Model → Procrustes Alignment → Global Transform → Accuracy Report
"""

import math
import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict
from datetime import datetime, timezone

from app.core.geospatial import (
    WGS84Coordinate,
    ENUVector,
    GeoTransform,
    create_transform,
    haversine_distance,
)
from app.core.world_precision import (
    HighPrecisionPosition,
    deterministic_round,
)


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class GPSPoint:
    """A GPS observation with optional accuracy."""
    latitude: float
    longitude: float
    altitude: float = 0.0
    accuracy_meters: float = 10.0  # horizontal accuracy
    timestamp: Optional[datetime] = None


@dataclass
class LocalPoint:
    """A point in the local reconstruction coordinate system."""
    x: float  # East
    y: float  # Up
    z: float  # North


@dataclass
class AlignmentPair:
    """A matched pair of local and GPS points."""
    local: LocalPoint
    gps: GPSPoint


@dataclass
class GlobalTransform:
    """
    Transform from local reconstruction coordinates to GPS-aligned coordinates.

    The transform consists of:
    - Translation: offset from local origin to GPS-aligned origin
    - Rotation: alignment of local axes to geographic axes
    - Scale: conversion factor from local units to meters
    """
    translation: np.ndarray  # 3x1
    rotation: np.ndarray     # 3x3
    scale: float = 1.0
    origin: Optional[WGS84Coordinate] = None

    def apply(self, point: LocalPoint) -> WGS84Coordinate:
        """Apply transform to convert local point to GPS."""
        local = np.array([point.x, point.y, point.z])
        transformed = self.scale * (self.rotation @ local) + self.translation
        # Convert ENU to WGS84
        enu = ENUVector(east=transformed[0], north=transformed[2], up=transformed[1])
        if self.origin:
            transform = create_transform(self.origin)
            return transform.enu_to_wgs84(enu)
        return WGS84Coordinate(latitude=0, longitude=0, altitude=0)

    def to_dict(self) -> dict:
        return {
            "translation": self.translation.tolist(),
            "rotation": self.rotation.tolist(),
            "scale": self.scale,
            "origin": {
                "lat": self.origin.latitude,
                "lon": self.origin.longitude,
                "alt": self.origin.altitude,
            } if self.origin else None,
        }


@dataclass
class AccuracyReport:
    """Accuracy metrics for an alignment."""
    mean_reprojection_error: float  # pixels
    mean_gps_error: float  # meters
    max_gps_error: float  # meters
    horizontal_accuracy: float  # meters (estimated)
    vertical_accuracy: float  # meters (estimated)
    confidence: float  # 0.0 to 1.0
    num_aligned_points: int
    num_rejected_points: int
    quality: str  # "high", "medium", "low"

    def to_dict(self) -> dict:
        return {
            "mean_reprojection_error": round(self.mean_reprojection_error, 4),
            "mean_gps_error": round(self.mean_gps_error, 4),
            "max_gps_error": round(self.max_gps_error, 4),
            "horizontal_accuracy": round(self.horizontal_accuracy, 4),
            "vertical_accuracy": round(self.vertical_accuracy, 4),
            "confidence": round(self.confidence, 4),
            "num_aligned_points": self.num_aligned_points,
            "num_rejected_points": self.num_rejected_points,
            "quality": self.quality,
        }


@dataclass
class AlignmentMetadata:
    """Complete alignment result with transform and accuracy."""
    location_id: Optional[int] = None
    transform: Optional[GlobalTransform] = None
    accuracy: Optional[AccuracyReport] = None
    gps_points_used: int = 0
    local_points_used: int = 0
    alignment_method: str = "procrustes"  # procrustes, ransac, least_squares
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "location_id": self.location_id,
            "transform": self.transform.to_dict() if self.transform else None,
            "accuracy": self.accuracy.to_dict() if self.accuracy else None,
            "gps_points_used": self.gps_points_used,
            "local_points_used": self.local_points_used,
            "alignment_method": self.alignment_method,
            "created_at": self.created_at.isoformat(),
        }


# =============================================================================
# Core Alignment Algorithms
# =============================================================================

def compute_procrustes_alignment(
    local_points: List[LocalPoint],
    gps_points: List[GPSPoint],
    origin: WGS84Coordinate,
) -> Tuple[GlobalTransform, float]:
    """
    Compute alignment using Procrustes analysis.

    Finds optimal rotation, translation, and scale to align
    local points to GPS-derived ENU coordinates.

    Returns:
        (transform, mean_error)
    """
    if len(local_points) < 3:
        raise ValueError("Need at least 3 point pairs for alignment")

    # Convert GPS points to ENU relative to origin
    transform_origin = create_transform(origin)
    gps_enu = []
    for gps in gps_points:
        wgs = WGS84Coordinate(gps.latitude, gps.longitude, gps.altitude)
        enu = transform_origin.wgs84_to_enu(wgs)
        gps_enu.append(np.array([enu.east, enu.up, enu.north]))  # Y-up for game coords

    local_arr = np.array([[p.x, p.y, p.z] for p in local_points])
    gps_arr = np.array(gps_enu)

    # Center both sets
    local_center = local_arr.mean(axis=0)
    gps_center = gps_arr.mean(axis=0)
    local_centered = local_arr - local_center
    gps_centered = gps_arr - gps_center

    # Procrustes: find R, t, s that minimizes ||s * R @ local + t - gps||
    # Step 1: Compute cross-covariance
    H = local_centered.T @ gps_centered

    # Step 2: SVD
    U, S, Vt = np.linalg.svd(H)

    # Step 3: Rotation
    R = Vt.T @ U.T
    # Ensure proper rotation (det = +1)
    if np.linalg.det(R) < 0:
        Vt[-1, :] *= -1
        R = Vt.T @ U.T

    # Step 4: Scale
    scale_local = np.sqrt(np.sum(local_centered ** 2))
    scale_gps = np.sqrt(np.sum(gps_centered ** 2))
    scale = scale_gps / scale_local if scale_local > 0 else 1.0

    # Step 5: Translation
    t = gps_center - scale * R @ local_center

    transform = GlobalTransform(
        translation=t.reshape(3),
        rotation=R,
        scale=scale,
        origin=origin,
    )

    # Compute mean error
    errors = []
    for local, gps in zip(local_points, gps_points):
        predicted = transform.apply(local)
        actual = WGS84Coordinate(gps.latitude, gps.longitude, gps.altitude)
        error = haversine_distance(predicted, actual)
        errors.append(error)

    mean_error = float(np.mean(errors)) if errors else 0.0
    return transform, mean_error


def estimate_accuracy(
    local_points: List[LocalPoint],
    gps_points: List[GPSPoint],
    transform: GlobalTransform,
    gps_accuracy_default: float = 10.0,
) -> AccuracyReport:
    """
    Estimate alignment accuracy.

    Computes:
    - GPS error: distance between transformed local points and GPS points
    - Horizontal/vertical accuracy estimates
    - Confidence score based on error distribution
    """
    errors = []
    gps_errors = []

    for local, gps in zip(local_points, gps_points):
        predicted = transform.apply(local)
        actual = WGS84Coordinate(gps.latitude, gps.longitude, gps.altitude)

        # Haversine error (horizontal)
        h_error = haversine_distance(predicted, actual)
        gps_errors.append(h_error)

        # Vertical error
        v_error = abs(predicted.altitude - gps.altitude)
        errors.append(math.sqrt(h_error ** 2 + v_error ** 2))

    if not errors:
        return AccuracyReport(
            mean_reprojection_error=0,
            mean_gps_error=0,
            max_gps_error=0,
            horizontal_accuracy=0,
            vertical_accuracy=0,
            confidence=0,
            num_aligned_points=0,
            num_rejected_points=0,
            quality="low",
        )

    mean_error = float(np.mean(errors))
    mean_gps_error = float(np.mean(gps_errors))
    max_gps_error = float(np.max(gps_errors))

    # Accuracy estimates (based on GPS accuracy and alignment quality)
    gps_accuracies = [gps.accuracy_meters for gps in gps_points]
    mean_gps_accuracy = float(np.mean(gps_accuracies)) if gps_accuracies else gps_accuracy_default

    horizontal_accuracy = math.sqrt(mean_gps_error ** 2 + mean_gps_accuracy ** 2)
    vertical_accuracy = horizontal_accuracy * 1.5  # vertical typically worse

    # Confidence score (0-1, based on error relative to GPS accuracy)
    if mean_gps_error < mean_gps_accuracy * 0.5:
        confidence = 0.95
    elif mean_gps_error < mean_gps_accuracy:
        confidence = 0.80
    elif mean_gps_error < mean_gps_accuracy * 2:
        confidence = 0.60
    elif mean_gps_error < mean_gps_accuracy * 5:
        confidence = 0.40
    else:
        confidence = 0.20

    # Quality label
    if confidence >= 0.8 and mean_gps_error < 5:
        quality = "high"
    elif confidence >= 0.5 and mean_gps_error < 20:
        quality = "medium"
    else:
        quality = "low"

    return AccuracyReport(
        mean_reprojection_error=mean_error,
        mean_gps_error=mean_gps_error,
        max_gps_error=max_gps_error,
        horizontal_accuracy=horizontal_accuracy,
        vertical_accuracy=vertical_accuracy,
        confidence=confidence,
        num_aligned_points=len(local_points),
        num_rejected_points=0,
        quality=quality,
    )


def ransac_alignment(
    local_points: List[LocalPoint],
    gps_points: List[GPSPoint],
    origin: WGS84Coordinate,
    num_iterations: int = 100,
    inlier_threshold: float = 5.0,  # meters
) -> Tuple[GlobalTransform, AccuracyReport]:
    """
    RANSAC-based alignment for robustness to outliers.

    Repeatedly samples minimal point sets, computes alignment,
    and counts inliers. Best alignment is refined using all inliers.
    """
    if len(local_points) < 3:
        raise ValueError("Need at least 3 point pairs for RANSAC")

    best_transform = None
    best_inliers = 0
    best_error = float("inf")

    n = len(local_points)

    for _ in range(num_iterations):
        # Sample 3 random points
        indices = np.random.choice(n, 3, replace=False)
        sample_local = [local_points[i] for i in indices]
        sample_gps = [gps_points[i] for i in indices]

        try:
            transform, _ = compute_procrustes_alignment(sample_local, sample_gps, origin)
        except Exception:
            continue

        # Count inliers
        inliers = 0
        total_error = 0
        for local, gps in zip(local_points, gps_points):
            predicted = transform.apply(local)
            actual = WGS84Coordinate(gps.latitude, gps.longitude, gps.altitude)
            error = haversine_distance(predicted, actual)
            if error < inlier_threshold:
                inliers += 1
                total_error += error

        if inliers > best_inliers or (inliers == best_inliers and total_error < best_error):
            best_inliers = inliers
            best_error = total_error
            best_transform = transform

    if best_transform is None:
        # Fallback to simple alignment
        best_transform, best_error = compute_procrustes_alignment(
            local_points, gps_points, origin
        )

    # Refine with all inliers
    inlier_local = []
    inlier_gps = []
    for local, gps in zip(local_points, gps_points):
        predicted = best_transform.apply(local)
        actual = WGS84Coordinate(gps.latitude, gps.longitude, gps.altitude)
        error = haversine_distance(predicted, actual)
        if error < inlier_threshold:
            inlier_local.append(local)
            inlier_gps.append(gps)

    if len(inlier_local) >= 3:
        final_transform, final_error = compute_procrustes_alignment(
            inlier_local, inlier_gps, origin
        )
    else:
        final_transform = best_transform

    accuracy = estimate_accuracy(inlier_local, inlier_gps, final_transform)
    accuracy.num_rejected_points = n - len(inlier_local)

    return final_transform, accuracy


# =============================================================================
# High-Level API
# =============================================================================

def align_reconstruction_to_gps(
    local_points: List[LocalPoint],
    gps_points: List[GPSPoint],
    origin: WGS84Coordinate,
    method: str = "ransac",
    location_id: Optional[int] = None,
) -> AlignmentMetadata:
    """
    High-level API: align a reconstruction to GPS coordinates.

    Args:
        local_points: Points in local reconstruction space
        gps_points: Corresponding GPS observations
        origin: WGS84 origin for ENU conversion
        method: "procrustes" or "ransac"
        location_id: Optional location ID for metadata

    Returns:
        AlignmentMetadata with transform and accuracy
    """
    if len(local_points) != len(gps_points):
        raise ValueError("local_points and gps_points must have same length")

    if len(local_points) < 3:
        raise ValueError("Need at least 3 point pairs for alignment")

    if method == "ransac":
        transform, accuracy = ransac_alignment(local_points, gps_points, origin)
    else:
        transform, error = compute_procrustes_alignment(local_points, gps_points, origin)
        accuracy = estimate_accuracy(local_points, gps_points, transform)

    return AlignmentMetadata(
        location_id=location_id,
        transform=transform,
        accuracy=accuracy,
        gps_points_used=len(gps_points),
        local_points_used=len(local_points),
        alignment_method=method,
    )
