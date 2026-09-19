"""
Tests for Depth Estimation and Reconstruction Metadata.
"""
import pytest
import uuid
import numpy as np
from app.core.database import SessionLocal, engine, Base
from app.models.user import User
from app.models.capture import Capture
from app.models.reconstruction_job import ReconstructionJob
from app.models.reconstruction_metadata import ReconstructionMetadata
from app.services.depth_estimation import DepthEstimator, DepthResult, depth_estimator


@pytest.fixture(scope="module")
def setup_db():
    """Create tables and test data."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        uid = uuid.uuid4().hex[:8]
        user = User(
            username=f"depth_test_{uid}",
            email=f"depth_{uid}@example.com",
            password_hash="salt:hash",
            display_name="Depth Test",
            location_sharing=True,
        )
        db.add(user)
        db.flush()

        job = ReconstructionJob(
            job_id=f"recon-{uuid.uuid4().hex[:8]}",
            user_id=user.id,
            status="completed",
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job.id
    finally:
        db.close()


class TestDepthEstimation:
    def test_estimate_from_image(self):
        estimator = DepthEstimator()
        # Create a simple test image
        image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        result = estimator.estimate_from_image(image)

        assert isinstance(result, DepthResult)
        assert result.depth_map.shape == (100, 100)
        assert result.min_depth > 0
        assert result.max_depth >= result.min_depth
        assert result.mean_depth > 0

    def test_estimate_from_single_frame(self):
        estimator = DepthEstimator()
        image = np.random.randint(0, 255, (80, 120, 3), dtype=np.uint8)
        result = estimator.estimate_from_frames([image])

        assert result.depth_map.shape == (80, 120)

    def test_estimate_invalid_image(self):
        estimator = DepthEstimator()
        with pytest.raises(ValueError):
            estimator.estimate_from_image(None)

    def test_gradient_heuristic_consistency(self):
        estimator = DepthEstimator()
        # Darker image (should estimate differently than bright)
        dark_image = np.zeros((100, 100, 3), dtype=np.uint8)
        bright_image = np.ones((100, 100, 3), dtype=np.uint8) * 255

        result_dark = estimator._estimate_gradient_heuristic(dark_image)
        result_bright = estimator._estimate_gradient_heuristic(bright_image)

        # Both should produce valid results
        assert result_dark.depth_map.shape == (100, 100)
        assert result_bright.depth_map.shape == (100, 100)

    def test_depth_result_fields(self):
        result = DepthResult(
            depth_map=np.ones((10, 10), dtype=np.float32),
            min_depth=1.0,
            max_depth=1.0,
            mean_depth=1.0,
        )
        assert result.depth_map.shape == (10, 10)
        assert result.min_depth == 1.0
        assert result.confidence_map is None


class TestReconstructionMetadata:
    def test_create_metadata(self, setup_db):
        db = SessionLocal()
        try:
            meta = ReconstructionMetadata(
                reconstruction_job_id=setup_db,
                feature_detector="sift",
                matcher_type="flann",
                input_frame_count=120,
                input_resolution="1920x1080",
                features_detected=50000,
                features_matched=35000,
                inlier_ratio=0.75,
                point_count=500000,
                vertex_count=100000,
                face_count=200000,
                overall_quality="high",
                total_time=45.2,
            )
            db.add(meta)
            db.commit()
            db.refresh(meta)

            assert meta.id is not None
            assert meta.feature_detector == "sift"
            assert meta.inlier_ratio == 0.75
            assert meta.total_time == 45.2
        finally:
            db.close()

    def test_metadata_model_fields(self):
        columns = {c.name for c in ReconstructionMetadata.__table__.columns}
        expected = {
            'id', 'reconstruction_job_id', 'feature_detector', 'matcher_type',
            'depth_method', 'input_frame_count', 'input_resolution',
            'input_duration_seconds', 'features_detected', 'features_matched',
            'inlier_ratio', 'camera_poses_estimated', 'mean_reprojection_error',
            'point_count', 'point_density', 'vertex_count', 'face_count',
            'mesh_volume', 'mesh_surface_area', 'texture_resolution',
            'texture_quality_score', 'overall_quality', 'alignment_confidence',
            'completeness_score', 'feature_detection_time', 'matching_time',
            'sfm_time', 'mesh_generation_time', 'texture_time',
            'optimization_time', 'total_time', 'errors', 'warnings', 'created_at'
        }
        assert expected.issubset(columns)
