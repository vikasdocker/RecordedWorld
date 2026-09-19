"""Tests for Phase 19: Real-World Visual Accuracy — error metrics, quality, confidence."""

import pytest
import math
import numpy as np

from app.core.geospatial import WGS84Coordinate, haversine_distance
from app.services.geolocation import LocalPoint, GPSPoint, GlobalTransform, create_transform
from app.services.visual_accuracy import (
    GeographicError,
    RotationError,
    ScaleError,
    QualityMetrics,
    AccuracyReport,
    calculate_geographic_error,
    calculate_rotation_error,
    calculate_scale_error,
    calculate_quality_metrics,
    compute_accuracy_report,
)


# Test data
ORIGIN = WGS84Coordinate(latitude=40.785, longitude=-73.968, altitude=0.0)

# Create aligned point pairs (predicted ≈ ground truth)
ALIGNED_PAIRS = [
    (WGS84Coordinate(40.785, -73.968, 0), WGS84Coordinate(40.785, -73.968, 0)),
    (WGS84Coordinate(40.786, -73.967, 10), WGS84Coordinate(40.786, -73.967, 10)),
    (WGS84Coordinate(40.787, -73.966, 20), WGS84Coordinate(40.787, -73.966, 20)),
    (WGS84Coordinate(40.784, -73.969, -5), WGS84Coordinate(40.784, -73.969, -5)),
    (WGS84Coordinate(40.788, -73.965, 15), WGS84Coordinate(40.788, -73.965, 15)),
]

# Create misaligned point pairs (predicted ≠ ground truth)
MISALIGNED_PAIRS = [
    (WGS84Coordinate(40.785, -73.968, 0), WGS84Coordinate(40.786, -73.967, 5)),
    (WGS84Coordinate(40.786, -73.967, 10), WGS84Coordinate(40.788, -73.965, 15)),
    (WGS84Coordinate(40.787, -73.966, 20), WGS84Coordinate(40.790, -73.962, 30)),
]


class TestGeographicError:
    def test_perfect_alignment(self):
        """Perfect alignment has zero error."""
        pred = [p[0] for p in ALIGNED_PAIRS]
        gt = [p[1] for p in ALIGNED_PAIRS]
        error = calculate_geographic_error(pred, gt)
        assert isinstance(error, GeographicError)
        assert error.horizontal_error_mean < 0.1
        assert error.vertical_error_mean < 0.1
        assert error.rmse < 0.1

    def test_misalignment(self):
        """Misaligned points have measurable error."""
        pred = [p[0] for p in MISALIGNED_PAIRS]
        gt = [p[1] for p in MISALIGNED_PAIRS]
        error = calculate_geographic_error(pred, gt)
        assert error.horizontal_error_mean > 0
        assert error.horizontal_error_max > error.horizontal_error_mean

    def test_error_serialization(self):
        """Error metrics serialize to dict."""
        pred = [p[0] for p in ALIGNED_PAIRS]
        gt = [p[1] for p in ALIGNED_PAIRS]
        error = calculate_geographic_error(pred, gt)
        d = error.to_dict()
        assert "horizontal_error_mean" in d
        assert "rmse" in d


class TestRotationError:
    def test_identity_rotation(self):
        """Identity rotation has zero error."""
        R_est = np.eye(3)
        R_gt = np.eye(3)
        error = calculate_rotation_error(R_est, R_gt)
        assert isinstance(error, RotationError)
        assert error.mean_angular_error < 0.1

    def test_90_degree_rotation(self):
        """90-degree rotation error."""
        R_est = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]])  # 90° around Z
        R_gt = np.eye(3)
        error = calculate_rotation_error(R_est, R_gt)
        assert error.mean_angular_error > 80  # close to 90 degrees

    def test_small_rotation_error(self):
        """Small rotation error."""
        angle = math.radians(5)  # 5 degrees
        R_est = np.array([
            [math.cos(angle), -math.sin(angle), 0],
            [math.sin(angle), math.cos(angle), 0],
            [0, 0, 1],
        ])
        R_gt = np.eye(3)
        error = calculate_rotation_error(R_est, R_gt)
        assert 4 < error.mean_angular_error < 6

    def test_error_serialization(self):
        """Error metrics serialize to dict."""
        error = calculate_rotation_error(np.eye(3), np.eye(3))
        d = error.to_dict()
        assert "yaw_error" in d
        assert "mean_angular_error" in d


class TestScaleError:
    def test_perfect_scale(self):
        """Scale factor of 1.0 has zero error."""
        error = calculate_scale_error(1.0, 1.0)
        assert isinstance(error, ScaleError)
        assert error.scale_error_percent < 0.1
        assert error.is_consistent

    def test_scale_deviation(self):
        """Scale factor different from 1.0 has error."""
        error = calculate_scale_error(1.1, 1.0)
        assert error.scale_error_percent > 9  # ~10% error
        assert error.scale_deviation > 9

    def test_consistency_check(self):
        """Consistent distances mark scale as consistent."""
        local = [100, 200, 300]
        gps = [100, 200, 300]  # same ratio
        error = calculate_scale_error(1.0, 1.0, local, gps)
        assert error.is_consistent

    def test_inconsistent_distances(self):
        """Inconsistent distances mark scale as inconsistent."""
        local = [100, 100, 100]
        gps = [100, 200, 300]  # different ratios
        error = calculate_scale_error(1.0, 1.0, local, gps)
        assert not error.is_consistent

    def test_error_serialization(self):
        """Error metrics serialize to dict."""
        error = calculate_scale_error(1.0, 1.0)
        d = error.to_dict()
        assert "scale_factor" in d
        assert "scale_error_percent" in d


class TestQualityMetrics:
    def test_high_quality(self):
        """Low errors produce high quality score."""
        geo = GeographicError(
            horizontal_error_mean=0.5,
            horizontal_error_max=1.0,
            horizontal_error_std=0.2,
            vertical_error_mean=0.3,
            vertical_error_max=0.5,
            vertical_error_std=0.1,
            rmse=0.6,
        )
        rot = RotationError(
            yaw_error=0.5,
            pitch_error=0.3,
            roll_error=0.2,
            mean_angular_error=0.4,
            max_angular_error=0.5,
        )
        scale = ScaleError(
            scale_factor=1.0,
            scale_deviation=0.1,
            scale_error_percent=0.1,
            is_consistent=True,
        )
        quality = calculate_quality_metrics(geo, rot, scale, num_points=100)
        assert isinstance(quality, QualityMetrics)
        assert quality.quality_label == "high"
        assert quality.confidence > 0.8

    def test_low_quality(self):
        """High errors produce low quality score."""
        geo = GeographicError(
            horizontal_error_mean=100,
            horizontal_error_max=200,
            horizontal_error_std=50,
            vertical_error_mean=50,
            vertical_error_max=100,
            vertical_error_std=25,
            rmse=120,
        )
        rot = RotationError(
            yaw_error=30,
            pitch_error=20,
            roll_error=15,
            mean_angular_error=25,
            max_angular_error=30,
        )
        scale = ScaleError(
            scale_factor=2.0,
            scale_deviation=100,
            scale_error_percent=100,
            is_consistent=False,
        )
        quality = calculate_quality_metrics(geo, rot, scale, num_points=10)
        assert quality.quality_label == "low"
        assert quality.confidence < 0.5

    def test_medium_quality(self):
        """Moderate errors produce medium quality score."""
        geo = GeographicError(
            horizontal_error_mean=15,
            horizontal_error_max=25,
            horizontal_error_std=5,
            vertical_error_mean=10,
            vertical_error_max=15,
            vertical_error_std=3,
            rmse=18,
        )
        rot = RotationError(
            yaw_error=10,
            pitch_error=8,
            roll_error=5,
            mean_angular_error=8,
            max_angular_error=10,
        )
        scale = ScaleError(
            scale_factor=1.1,
            scale_deviation=10,
            scale_error_percent=10,
            is_consistent=True,
        )
        quality = calculate_quality_metrics(geo, rot, scale, num_points=50)
        assert quality.quality_label == "medium"

    def test_quality_serialization(self):
        """Quality metrics serialize to dict."""
        geo = GeographicError(1, 2, 0.5, 0.5, 1, 0.2, 1.1)
        rot = RotationError(1, 0.5, 0.3, 0.6, 1)
        scale = ScaleError(1.0, 0.1, 0.1, True)
        quality = calculate_quality_metrics(geo, rot, scale, num_points=100)
        d = quality.to_dict()
        assert "overall_score" in d
        assert "quality_label" in d


class TestAccuracyReport:
    def test_complete_report(self):
        """Can generate complete accuracy report."""
        local_points = [LocalPoint(0, 0, 0), LocalPoint(100, 0, 0), LocalPoint(0, 0, 100)]
        gps_points = [
            GPSPoint(40.785, -73.968, 0, 5),
            GPSPoint(40.785, -73.96687, 0, 5),
            GPSPoint(40.785899, -73.968, 0, 5),
        ]
        transform = GlobalTransform(
            translation=np.array([0, 0, 0]),
            rotation=np.eye(3),
            scale=1.0,
            origin=ORIGIN,
        )
        report = compute_accuracy_report(
            local_points, gps_points, transform,
            location_id=42, alignment_method="ransac",
        )
        assert isinstance(report, AccuracyReport)
        assert report.location_id == 42
        assert report.geographic_error is not None
        assert report.quality_metrics is not None

    def test_report_serialization(self):
        """Report serializes to dict."""
        local_points = [LocalPoint(0, 0, 0), LocalPoint(100, 0, 0)]
        gps_points = [GPSPoint(40.785, -73.968, 0, 5), GPSPoint(40.785, -73.96687, 0, 5)]
        transform = GlobalTransform(
            translation=np.array([0, 0, 0]),
            rotation=np.eye(3),
            scale=1.0,
            origin=ORIGIN,
        )
        report = compute_accuracy_report(local_points, gps_points, transform)
        d = report.to_dict()
        assert "geographic_error" in d
        assert "quality_metrics" in d

    def test_report_summary(self):
        """Report generates human-readable summary."""
        local_points = [LocalPoint(0, 0, 0), LocalPoint(100, 0, 0)]
        gps_points = [GPSPoint(40.785, -73.968, 0, 5), GPSPoint(40.785, -73.96687, 0, 5)]
        transform = GlobalTransform(
            translation=np.array([0, 0, 0]),
            rotation=np.eye(3),
            scale=1.0,
            origin=ORIGIN,
        )
        report = compute_accuracy_report(local_points, gps_points, transform)
        summary = report.summary()
        assert "Position Accuracy" in summary
        assert "Rotation Accuracy" in summary

    def test_report_serialization_empty(self):
        """Empty report serializes without error."""
        report = AccuracyReport()
        d = report.to_dict()
        assert d["geographic_error"] is None
