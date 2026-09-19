"""Tests for Phase 8: Geolocation — alignment, accuracy, transform, RANSAC."""

import pytest
import math
import numpy as np

from app.core.geospatial import WGS84Coordinate, haversine_distance
from app.services.geolocation import (
    GPSPoint,
    LocalPoint,
    AlignmentPair,
    GlobalTransform,
    AccuracyReport,
    AlignmentMetadata,
    compute_procrustes_alignment,
    estimate_accuracy,
    ransac_alignment,
    align_reconstruction_to_gps,
)


# Test data: NYC Central Park area
ORIGIN = WGS84Coordinate(latitude=40.785, longitude=-73.968, altitude=0.0)

# Create corresponding local/GPS point pairs
# Local points are in a simple coordinate system
# GPS points are real WGS84 coordinates
TEST_PAIRS = [
    (LocalPoint(0, 0, 0), GPSPoint(40.785, -73.968, 0, 5.0)),
    (LocalPoint(100, 0, 0), GPSPoint(40.785, -73.96687, 0, 5.0)),  # ~100m east
    (LocalPoint(0, 0, 100), GPSPoint(40.785899, -73.968, 0, 5.0)),  # ~100m north
    (LocalPoint(50, 10, 50), GPSPoint(40.785450, -73.96743, 10, 5.0)),
    (LocalPoint(200, 5, 150), GPSPoint(40.786349, -73.96574, 5, 5.0)),
]


class TestGlobalTransform:
    def test_transform_apply(self):
        """Transform correctly applies to local points."""
        transform = GlobalTransform(
            translation=np.array([0, 0, 0]),
            rotation=np.eye(3),
            scale=1.0,
            origin=ORIGIN,
        )
        point = LocalPoint(0, 0, 0)
        result = transform.apply(point)
        assert isinstance(result, WGS84Coordinate)
        assert abs(result.latitude - ORIGIN.latitude) < 0.001
        assert abs(result.longitude - ORIGIN.longitude) < 0.001

    def test_transform_to_dict(self):
        """Transform can be serialized to dict."""
        transform = GlobalTransform(
            translation=np.array([1.0, 2.0, 3.0]),
            rotation=np.eye(3),
            scale=1.0,
            origin=ORIGIN,
        )
        d = transform.to_dict()
        assert "translation" in d
        assert "rotation" in d
        assert "scale" in d
        assert d["origin"]["lat"] == ORIGIN.latitude


class TestProcrustesAlignment:
    def test_basic_alignment(self):
        """Can compute basic Procrustes alignment."""
        local = [p[0] for p in TEST_PAIRS]
        gps = [p[1] for p in TEST_PAIRS]
        transform, error = compute_procrustes_alignment(local, gps, ORIGIN)
        assert isinstance(transform, GlobalTransform)
        assert error >= 0

    def test_alignment_identity(self):
        """Alignment with identical local/GPS points produces near-identity."""
        # Create points where local = ENU (approximately)
        origin = WGS84Coordinate(latitude=40.0, longitude=-74.0, altitude=0.0)
        transform_origin = __import__('app.core.geospatial', fromlist=['create_transform']).create_transform(origin)

        local_points = [LocalPoint(0, 0, 0), LocalPoint(100, 0, 0), LocalPoint(0, 0, 100)]
        gps_points = []
        for lp in local_points:
            enu = __import__('app.core.geospatial', fromlist=['ENUVector']).ENUVector(
                east=lp.x, north=lp.z, up=lp.y
            )
            wgs = transform_origin.enu_to_wgs84(enu)
            gps_points.append(GPSPoint(wgs.latitude, wgs.longitude, wgs.altitude, 5.0))

        transform, error = compute_procrustes_alignment(local_points, gps_points, origin)
        # Error should be very small for near-identity case
        assert error < 10  # meters

    def test_alignment_too_few_points(self):
        """Alignment fails with fewer than 3 points."""
        local = [LocalPoint(0, 0, 0), LocalPoint(1, 0, 0)]
        gps = [GPSPoint(40.785, -73.968, 0), GPSPoint(40.785, -73.967, 0)]
        with pytest.raises(ValueError):
            compute_procrustes_alignment(local, gps, ORIGIN)


class TestAccuracyEstimation:
    def test_accuracy_perfect(self):
        """Perfect alignment gives high confidence."""
        local = [p[0] for p in TEST_PAIRS]
        gps = [p[1] for p in TEST_PAIRS]
        transform, _ = compute_procrustes_alignment(local, gps, ORIGIN)
        accuracy = estimate_accuracy(local, gps, transform)
        assert isinstance(accuracy, AccuracyReport)
        assert accuracy.num_aligned_points == len(TEST_PAIRS)
        assert accuracy.quality in ("high", "medium", "low")

    def test_accuracy_to_dict(self):
        """Accuracy report serializes to dict."""
        local = [p[0] for p in TEST_PAIRS]
        gps = [p[1] for p in TEST_PAIRS]
        transform, _ = compute_procrustes_alignment(local, gps, ORIGIN)
        accuracy = estimate_accuracy(local, gps, transform)
        d = accuracy.to_dict()
        assert "confidence" in d
        assert "quality" in d
        assert 0 <= d["confidence"] <= 1


class TestRANSACAlignment:
    def test_ransac_basic(self):
        """RANSAC alignment works."""
        local = [p[0] for p in TEST_PAIRS]
        gps = [p[1] for p in TEST_PAIRS]
        transform, accuracy = ransac_alignment(local, gps, ORIGIN, num_iterations=50)
        assert isinstance(transform, GlobalTransform)
        assert isinstance(accuracy, AccuracyReport)

    def test_ransac_with_outliers(self):
        """RANSAC handles outliers gracefully."""
        local = [p[0] for p in TEST_PAIRS]
        gps = [p[1] for p in TEST_PAIRS]
        # Add outlier pair
        local.append(LocalPoint(500, 500, 500))
        gps.append(GPSPoint(41.0, -74.0, 100, 5.0))  # far away

        transform, accuracy = ransac_alignment(
            local, gps, ORIGIN, num_iterations=100, inlier_threshold=20.0
        )
        # Should have rejected the outlier
        assert accuracy.num_rejected_points >= 1

    def test_ransac_too_few_points(self):
        """RANSAC fails with fewer than 3 points."""
        local = [LocalPoint(0, 0, 0)]
        gps = [GPSPoint(40.785, -73.968, 0)]
        with pytest.raises(ValueError):
            ransac_alignment(local, gps, ORIGIN)


class TestHighLevelAPI:
    def test_align_reconstruction(self):
        """High-level API produces complete metadata."""
        local = [p[0] for p in TEST_PAIRS]
        gps = [p[1] for p in TEST_PAIRS]
        metadata = align_reconstruction_to_gps(
            local, gps, ORIGIN, method="ransac", location_id=42
        )
        assert isinstance(metadata, AlignmentMetadata)
        assert metadata.location_id == 42
        assert metadata.transform is not None
        assert metadata.accuracy is not None
        assert metadata.gps_points_used == len(TEST_PAIRS)

    def test_align_mismatched_lengths(self):
        """API rejects mismatched point lists."""
        local = [LocalPoint(0, 0, 0), LocalPoint(1, 0, 0)]
        gps = [GPSPoint(40.785, -73.968, 0)]
        with pytest.raises(ValueError):
            align_reconstruction_to_gps(local, gps, ORIGIN)

    def test_align_too_few_points(self):
        """API rejects fewer than 3 points."""
        local = [LocalPoint(0, 0, 0), LocalPoint(1, 0, 0)]
        gps = [GPSPoint(40.785, -73.968, 0), GPSPoint(40.785, -73.967, 0)]
        with pytest.raises(ValueError):
            align_reconstruction_to_gps(local, gps, ORIGIN)


class TestMetadataSerialization:
    def test_metadata_to_dict(self):
        """Metadata serializes completely."""
        local = [p[0] for p in TEST_PAIRS]
        gps = [p[1] for p in TEST_PAIRS]
        metadata = align_reconstruction_to_gps(local, gps, ORIGIN)
        d = metadata.to_dict()
        assert "transform" in d
        assert "accuracy" in d
        assert "alignment_method" in d

    def test_metadata_to_dict_empty(self):
        """Empty metadata serializes without error."""
        metadata = AlignmentMetadata()
        d = metadata.to_dict()
        assert d["transform"] is None
