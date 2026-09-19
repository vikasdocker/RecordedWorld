"""
Tests for Visual Landmark service and model.
"""
import pytest
import uuid
import numpy as np
from app.core.database import SessionLocal, engine, Base
from app.models.user import User
from app.models.capture import Capture
from app.models.location import Location
from app.models.visual_landmark import VisualLandmark, LandmarkMatch
from app.services.visual_landmark_service import VisualLandmarkService, LandmarkMatchResult


@pytest.fixture(scope="module")
def setup_db():
    """Create tables and test data."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        uid = uuid.uuid4().hex[:8]
        user = User(
            username=f"landmark_test_{uid}",
            email=f"landmark_{uid}@example.com",
            password_hash="salt:hash",
            display_name="Landmark Test",
            location_sharing=True,
        )
        db.add(user)
        db.flush()

        capture = Capture(
            user_id=user.id,
            title="Test Capture",
            video_path="/tmp/test.mp4",
            status="uploaded",
        )
        db.add(capture)
        db.commit()
        db.refresh(capture)

        return {"user_id": user.id, "capture_id": capture.id}
    finally:
        db.close()


class TestVisualLandmarkModel:
    def test_create_landmark(self, setup_db):
        db = SessionLocal()
        try:
            landmark = VisualLandmark(
                capture_id=setup_db["capture_id"],
                latitude=37.7749,
                longitude=-122.4194,
                altitude=16.0,
                feature_type="sift",
                descriptor_count=128,
                quality_score=0.85,
            )
            db.add(landmark)
            db.commit()
            db.refresh(landmark)

            assert landmark.id is not None
            assert landmark.latitude == 37.7749
            assert landmark.feature_type == "sift"
            assert landmark.quality_score == 0.85
        finally:
            db.close()

    def test_landmark_model_fields(self):
        columns = {c.name for c in VisualLandmark.__table__.columns}
        expected = {
            'id', 'capture_id', 'location_id', 'latitude', 'longitude',
            'altitude', 'feature_type', 'descriptor_count', 'descriptor_data',
            'keypoint_data', 'image_path', 'image_hash', 'quality_score',
            'uniqueness_score', 'visibility_range', 'match_count',
            'last_matched_at', 'device_info', 'capture_conditions',
            'created_at', 'updated_at'
        }
        assert expected.issubset(columns)


class TestLandmarkMatchModel:
    def test_create_match(self, setup_db):
        db = SessionLocal()
        try:
            landmark = VisualLandmark(
                capture_id=setup_db["capture_id"],
                latitude=37.7749,
                longitude=-122.4194,
                feature_type="sift",
            )
            db.add(landmark)
            db.flush()

            match = LandmarkMatch(
                matched_landmark_id=landmark.id,
                match_score=0.85,
                match_distance=15.0,
                inlier_count=50,
                status="confirmed",
            )
            db.add(match)
            db.commit()
            db.refresh(match)

            assert match.id is not None
            assert match.match_score == 0.85
            assert match.status == "confirmed"
        finally:
            db.close()

    def test_match_model_fields(self):
        columns = {c.name for c in LandmarkMatch.__table__.columns}
        expected = {
            'id', 'query_capture_id', 'query_image_hash',
            'matched_landmark_id', 'match_score', 'match_distance',
            'inlier_count', 'outlier_ratio', 'status', 'created_at'
        }
        assert expected.issubset(columns)


class TestVisualLandmarkService:
    def test_find_nearby_landmarks(self, setup_db):
        db = SessionLocal()
        try:
            # Create landmarks
            for i in range(5):
                landmark = VisualLandmark(
                    capture_id=setup_db["capture_id"],
                    latitude=37.7749 + i * 0.001,
                    longitude=-122.4194 + i * 0.001,
                    feature_type="sift",
                    quality_score=0.5 + i * 0.1,
                )
                db.add(landmark)
            db.commit()

            service = VisualLandmarkService(db)
            nearby = service.find_nearby_landmarks(
                latitude=37.7749,
                longitude=-122.4194,
                radius_meters=1000,
            )
            assert len(nearby) >= 5
        finally:
            db.close()

    def test_match_score_computation(self):
        service = VisualLandmarkService(None)

        # Create test descriptors
        query = np.random.rand(100, 128).astype(np.float32)
        stored = np.random.rand(50, 128).astype(np.float32)

        score = service._compute_match_score(query, stored)
        assert 0.0 <= score <= 1.0

    def test_match_score_empty(self):
        service = VisualLandmarkService(None)
        query = np.array([])
        stored = np.random.rand(50, 128).astype(np.float32)

        score = service._compute_match_score(query, stored)
        assert score == 0.0

    def test_get_landmark_stats(self, setup_db):
        db = SessionLocal()
        try:
            # Create landmarks of different types
            for ft in ["sift", "orb", "sift"]:
                landmark = VisualLandmark(
                    capture_id=setup_db["capture_id"],
                    latitude=37.7749,
                    longitude=-122.4194,
                    feature_type=ft,
                )
                db.add(landmark)
            db.commit()

            service = VisualLandmarkService(db)
            stats = service.get_landmark_stats()
            assert stats["total_landmarks"] >= 3
            assert "sift" in stats["by_feature_type"]
            assert "orb" in stats["by_feature_type"]
        finally:
            db.close()
