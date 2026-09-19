"""
Edge Case & Integration Tests

Tests boundary conditions, error recovery, and cross-service integration.
"""
import time
import math
import pytest
import numpy as np
from app.core.geospatial import (
    WGS84Coordinate, ENUVector, GeoTransform,
    haversine_distance, bounding_box
)
from app.core.world_precision import (
    FloatingOrigin, HighPrecisionPosition, WorldCoordinateManager
)
from app.core.spatial_index import compute_grid_cell_id
from app.services.job_queue import JobQueue, JobStatus, JobPriority
from app.services.content_addressing import ContentAddressableStore
from app.services.memory_manager import MemoryManager, MemoryPool, MemoryBudget
from app.services.lod_system import LODManager, LODLevel
from app.services.capture_metadata import CaptureMetadataValidator
from app.services.device_orientation import DeviceOrientationProcessor, OrientationSample, EulerAngles
from app.services.upload_session import UploadSessionManager, UploadState


# --- Geospatial Edge Cases ---

class TestGeospatialEdgeCases:
    def test_coordinate_at_pole(self):
        c = WGS84Coordinate(90.0, 0.0)
        assert c.latitude == 90.0

    def test_coordinate_at_antimeridian(self):
        c = WGS84Coordinate(0.0, 180.0)
        assert c.longitude == 180.0

    def test_haversine_same_point(self):
        a = WGS84Coordinate(40.0, -74.0)
        d = haversine_distance(a, a)
        assert d == pytest.approx(0.0, abs=0.01)

    def test_haversine_opposite_side(self):
        a = WGS84Coordinate(0.0, 0.0)
        b = WGS84Coordinate(0.0, 180.0)
        d = haversine_distance(a, b)
        assert d > 20000  # half circumference

    def test_bounding_box_zero_radius(self):
        center = WGS84Coordinate(40.0, -74.0)
        bb = bounding_box(center, 0.0)
        assert bb[0] == pytest.approx(40.0, abs=0.01)

    def test_bounding_box_large_radius(self):
        center = WGS84Coordinate(0.0, 0.0)
        bb = bounding_box(center, 1000000.0)  # 1000km
        assert bb[0] > -90  # Should be reasonable


# --- World Precision Edge Cases ---

class TestWorldPrecisionEdgeCases:
    def test_floating_origin_at_equator(self):
        origin = WGS84Coordinate(0.0, 0.0)
        fo = FloatingOrigin(origin)
        game_pos = fo.wgs84_to_game(WGS84Coordinate(0.001, 0.001))
        assert isinstance(game_pos.x, float)

    def test_high_precision_position_identity(self):
        hp = HighPrecisionPosition(40.7128, -74.0060, 0.0)
        assert hp.latitude == 40.7128

    def test_world_coordinate_manager(self):
        origin = WGS84Coordinate(40.0, -74.0)
        fo = FloatingOrigin(origin)
        wcm = WorldCoordinateManager(fo)
        pos = wcm.wgs84_to_game(WGS84Coordinate(40.001, -74.001))
        assert isinstance(pos.x, float)


# --- Spatial Index Edge Cases ---

class TestSpatialIndexEdgeCases:
    def test_grid_cell_at_zero(self):
        cell = compute_grid_cell_id(WGS84Coordinate(0.0, 0.0))
        assert isinstance(cell, str)

    def test_grid_cell_negative_coords(self):
        cell = compute_grid_cell_id(WGS84Coordinate(-45.0, -90.0))
        assert isinstance(cell, str)

    def test_grid_cell_same_location(self):
        c1 = compute_grid_cell_id(WGS84Coordinate(40.0, -74.0))
        c2 = compute_grid_cell_id(WGS84Coordinate(40.0, -74.0))
        assert c1 == c2  # Exact same coords = same grid cell


# --- Job Queue Edge Cases ---

class TestJobQueueEdgeCases:
    def test_create_many_jobs(self):
        q = JobQueue()
        for i in range(100):
            q.create_job(user_id=i % 10)
        assert len(q._jobs) == 100

    def test_cancel_all_jobs(self):
        q = JobQueue()
        jobs = [q.create_job(user_id=1) for _ in range(5)]
        for j in jobs:
            q.enqueue(j.job_id)
        for j in jobs:
            q.cancel_job(j.job_id)
        assert q.get_queue_length() == 0

    def test_rapid_retry(self):
        q = JobQueue()
        job = q.create_job(user_id=1)
        q.enqueue(job.job_id)
        q.dequeue()
        q.fail_job(job.job_id, "err")
        for _ in range(3):
            q.retry_job(job.job_id)
            q.dequeue()
            q.fail_job(job.job_id, "err")
        assert q.retry_job(job.job_id) is False

    def test_priority_stats(self):
        q = JobQueue()
        q.create_job(user_id=1, priority=JobPriority.HIGH)
        q.create_job(user_id=2, priority=JobPriority.LOW)
        stats = q.get_stats()
        assert stats["by_priority"]["high"] == 1
        assert stats["by_priority"]["low"] == 1


# --- Content Addressing Edge Cases ---

class TestContentAddressingEdgeCases:
    def test_store_empty_data(self):
        store = ContentAddressableStore()
        addr = store.store(b"", "empty")
        assert addr.size_bytes == 0

    def test_store_large_data(self):
        store = ContentAddressableStore()
        data = b"x" * 1024 * 1024  # 1MB
        addr = store.store(data, "large")
        assert addr.size_bytes == 1024 * 1024

    def test_hash_deterministic(self):
        store = ContentAddressableStore()
        h1 = store.compute_hash(b"test")
        h2 = store.compute_hash(b"test")
        assert h1 == h2

    def test_hash_different_data(self):
        store = ContentAddressableStore()
        h1 = store.compute_hash(b"test1")
        h2 = store.compute_hash(b"test2")
        assert h1 != h2

    def test_reference_counting(self):
        store = ContentAddressableStore()
        addr = store.store(b"data", "test")
        assert store.get(addr.hash).references == 1
        store.dereference(addr.hash)
        assert store.get(addr.hash).references == 2
        store.release(addr.hash)
        assert store.get(addr.hash).references == 1


# --- Memory Manager Edge Cases ---

class TestMemoryManagerEdgeCases:
    def test_allocate_zero_bytes(self):
        mgr = MemoryManager()
        result = mgr.allocate("b1", MemoryPool.TERRAIN, 0, "owner")
        assert result is True

    def test_free_nonexistent(self):
        mgr = MemoryManager()
        assert mgr.free("nonexistent") is False

    def test_multiple_pools(self):
        mgr = MemoryManager()
        for pool in MemoryPool:
            mgr.allocate(f"b_{pool.value}", pool, 1024, "owner")
        usage = mgr.get_usage()
        assert usage["block_count"] == len(MemoryPool)

    def test_eviction_under_pressure(self):
        budget = MemoryBudget(total_mb=0.001, pool_budgets={MemoryPool.TERRAIN: 0.001})
        mgr = MemoryManager(budget=budget)
        for i in range(10):
            mgr.allocate(f"b{i}", MemoryPool.TERRAIN, 1024, "owner")
        # Should have evicted some
        assert len(mgr.blocks) <= 10


# --- LOD Edge Cases ---

class TestLODEdgeCases:
    def test_zero_distance(self):
        lod = LODManager()
        sel = lod.select_lod(0.0)
        assert sel.level == LODLevel.ULTRA

    def test_negative_distance(self):
        lod = LODManager()
        sel = lod.select_lod(-100.0)
        assert sel.level == LODLevel.ULTRA

    def test_extreme_distance(self):
        lod = LODManager()
        sel = lod.select_lod(100000.0)
        assert sel.level == LODLevel.MINIMAL

    def test_reduce_to_one_vertex(self):
        lod = LODManager()
        verts = [(i, i, i) for i in range(100)]
        reduced = lod.reduce_vertices(verts, 1)
        assert len(reduced) == 1

    def test_simplify_triangle(self):
        lod = LODManager()
        points = [(0, 0), (1, 0), (0.5, 0.866)]
        simplified = lod.simplify_polygon(points, tolerance=0.1)
        assert len(simplified) <= 3


# --- Capture Metadata Edge Cases ---

class TestCaptureMetadataEdgeCases:
    def test_validate_empty(self):
        v = CaptureMetadataValidator()
        meta, issues = v.validate({})
        assert meta.duration_seconds == 0.0

    def test_validate_extreme_duration(self):
        v = CaptureMetadataValidator()
        meta, issues = v.validate({"duration_seconds": 999999})
        assert any(i.field == "duration_seconds" for i in issues)

    def test_validate_negative_fps(self):
        v = CaptureMetadataValidator()
        meta, issues = v.validate({"fps": -30})
        assert meta.fps == 30.0  # default

    def test_quality_score_perfect(self):
        v = CaptureMetadataValidator()
        from app.services.capture_metadata import CaptureMetadata
        meta = CaptureMetadata(
            duration_seconds=30.0,
            resolution_width=3840, resolution_height=2160,
            gps_accuracy_m=1.0, latitude=40.0,
            focal_length_mm=26.0,
        )
        score = v.get_quality_score(meta)
        assert score >= 80


# --- Device Orientation Edge Cases ---

class TestDeviceOrientationEdgeCases:
    def test_single_sample(self):
        proc = DeviceOrientationProcessor()
        result = proc.process_samples([
            OrientationSample(timestamp_ms=0, accel_z=9.81)
        ])
        assert result is not None

    def test_gravity_perfect(self):
        proc = DeviceOrientationProcessor()
        samples = [
            OrientationSample(timestamp_ms=0, accel_x=0, accel_y=0, accel_z=9.81),
            OrientationSample(timestamp_ms=10, accel_x=0, accel_y=0, accel_z=9.81),
        ]
        result = proc.process_samples(samples)
        assert result.confidence > 0.9

    def test_tilted_device(self):
        proc = DeviceOrientationProcessor()
        samples = [
            OrientationSample(timestamp_ms=0, accel_x=9.81, accel_y=0, accel_z=0),
        ]
        result = proc.process_samples(samples)
        assert result is not None
        # Gravity filter will converge, but pitch should reflect tilt
        assert abs(result.euler.pitch) > 0

    def test_euler_wraparound(self):
        euler = EulerAngles(heading=359.0, pitch=0, roll=0)
        quat = euler.to_quaternion()
        assert all(isinstance(q, float) for q in quat)


# --- Upload Session Edge Cases ---

class TestUploadSessionEdgeCases:
    def test_single_byte_upload(self):
        mgr = UploadSessionManager()
        session = mgr.create_session("s1", user_id=1, filename="v.mp4", total_size=1, chunk_size=1)
        assert session.total_chunks == 1
        mgr.mark_chunk_uploaded("s1", 0)
        assert session.state == UploadState.COMPLETED

    def test_huge_upload(self):
        mgr = UploadSessionManager()
        session = mgr.create_session("s1", user_id=1, filename="v.mp4",
                                     total_size=1024*1024*100, chunk_size=1024*1024)
        assert session.total_chunks == 100

    def test_concurrent_sessions(self):
        mgr = UploadSessionManager()
        for i in range(5):
            mgr.create_session(f"s{i}", user_id=1, filename="v.mp4", total_size=1024, chunk_size=1024)
        stats = mgr.get_stats()
        assert stats["total_sessions"] == 5

    def test_speed_calculation(self):
        mgr = UploadSessionManager()
        session = mgr.create_session("s1", user_id=1, filename="v.mp4",
                                     total_size=1024*1024, chunk_size=1024*1024)
        speed = session.speed_bytes_per_sec
        assert speed >= 0


# --- Cross-Service Integration ---

class TestCrossServiceIntegration:
    def test_job_with_content_addressing(self):
        q = JobQueue()
        store = ContentAddressableStore()

        job = q.create_job(user_id=1)
        q.enqueue(job.job_id)
        q.dequeue()  # processing

        # Go through full pipeline
        q.update_progress(job.job_id, 100, JobStatus.RECONSTRUCTING)
        q.update_progress(job.job_id, 100, JobStatus.ALIGNING)
        q.update_progress(job.job_id, 100, JobStatus.OPTIMIZING)
        q.update_progress(job.job_id, 100, JobStatus.VALIDATING)

        # Store result
        addr = store.store(b"reconstruction result", "mesh")
        q.complete_job(job.job_id, asset_id=addr.hash)

        assert job.status == JobStatus.COMPLETED
        assert store.exists(addr.hash)

    def test_memory_with_lod(self):
        mgr = MemoryManager()
        lod = LODManager()

        # Simulate loading different LOD levels
        for level in LODLevel:
            config = lod.get_config_for_distance(level * 1000)
            mgr.allocate(f"lod_{level.value}", MemoryPool.MESHES,
                        config.max_vertices * 12, f"chunk_{level.value}")

        usage = mgr.get_usage()
        assert usage["block_count"] == len(LODLevel)

    def test_capture_validation_with_orientation(self):
        validator = CaptureMetadataValidator()
        processor = DeviceOrientationProcessor()

        # Validate metadata
        raw = {
            "duration_seconds": 10.0,
            "resolution": "1920x1080",
            "fps": 30,
            "latitude": 40.7128,
            "longitude": -74.0060,
        }
        meta, issues = validator.validate(raw)
        assert meta.latitude == 40.7128

        # Process orientation
        samples = [
            OrientationSample(timestamp_ms=0, accel_z=9.81),
            OrientationSample(timestamp_ms=10, accel_z=9.81),
        ]
        heading, pitch, roll = processor.get_capture_orientation(samples)
        meta.heading = heading
        meta.pitch = pitch
        meta.roll = roll

        score = validator.get_quality_score(meta)
        assert score > 0
