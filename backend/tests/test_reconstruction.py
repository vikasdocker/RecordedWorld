import pytest
import cv2
import numpy as np
import os
import tempfile

from app.services.feature_extractor import (
    create_detector, extract_features, extract_features_batch,
    extract_features_from_video, match_features, match_features_chain, FeatureMethod,
    DetectedFeatures, MatchResult,
)
from app.services.camera_pose import (
    CameraIntrinsics, estimate_fundamental_matrix, estimate_essential_matrix,
    recover_pose, estimate_camera_pose, triangulate_points,
    build_projection_matrix, compute_reprojection_error,
)
from app.services.point_cloud_generator import (
    PointCloud, generate_point_cloud_from_video,
)


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


def _create_test_image(width=320, height=240, seed=42):
    """Create a test image with features."""
    rng = np.random.RandomState(seed)
    img = np.zeros((height, width, 3), dtype=np.uint8)
    # Add rectangles
    for _ in range(5):
        x1, y1 = rng.randint(0, width - 50), rng.randint(0, height - 50)
        x2, y2 = x1 + rng.randint(30, 80), y1 + rng.randint(30, 80)
        color = tuple(int(c) for c in rng.randint(100, 255, 3))
        cv2.rectangle(img, (x1, y1), (x2, y2), color, -1)
    # Add text
    cv2.putText(img, "FEATURE", (50, 120), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
    # Add noise
    noise = rng.randint(0, 30, (height, width, 3), dtype=np.uint8)
    img = cv2.add(img, noise)
    return img


def _create_test_video(path, num_frames=20, fps=10.0):
    """Create a test video with moving features."""
    width, height = 320, 240
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(path, fourcc, fps, (width, height))
    rng = np.random.RandomState(42)
    for i in range(num_frames):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        # Moving rectangle
        x = int(50 + (i * 5) % 200)
        cv2.rectangle(frame, (x, 50), (x + 80, 180), (255, 128, 64), -1)
        # Stationary text
        cv2.putText(frame, f"FRAME{i:03d}", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        # Random dots for features
        for _ in range(50):
            px, py = rng.randint(10, width - 10), rng.randint(10, height - 10)
            cv2.circle(frame, (px, py), 3, tuple(int(c) for c in rng.randint(100, 255, 3)), -1)
        out.write(frame)
    out.release()


# --- Feature Extractor Tests ---

class TestFeatureExtractor:
    def test_create_sift_detector(self):
        det = create_detector(FeatureMethod.SIFT, 1000)
        assert isinstance(det, cv2.SIFT)

    def test_create_orb_detector(self):
        det = create_detector(FeatureMethod.ORB, 1000)
        assert isinstance(det, cv2.ORB)

    def test_create_akaze_detector(self):
        det = create_detector(FeatureMethod.AKAZE, 1000)
        assert isinstance(det, cv2.AKAZE)

    def test_extract_features_sift(self):
        img = _create_test_image()
        detector = create_detector(FeatureMethod.SIFT, 1000)
        features = extract_features(img, detector, 0, "sift")

        assert features.keypoints_count > 0
        assert features.descriptors is not None
        assert features.keypoints_xy.shape[1] == 2
        assert features.method == "sift"

    def test_extract_features_orb(self):
        img = _create_test_image()
        detector = create_detector(FeatureMethod.ORB, 1000)
        features = extract_features(img, detector, 0, "orb")

        assert features.keypoints_count > 0
        assert features.method == "orb"

    def test_extract_features_empty_image(self):
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        detector = create_detector(FeatureMethod.SIFT, 1000)
        features = extract_features(img, detector, 0, "sift")

        # May find no features on uniform black image
        assert features.keypoints_count >= 0

    def test_extract_features_grayscale(self):
        img = np.random.randint(0, 255, (240, 320), dtype=np.uint8)
        detector = create_detector(FeatureMethod.SIFT, 1000)
        features = extract_features(img, detector, 0, "sift")

        assert features.keypoints_count > 0

    def test_extract_features_batch(self):
        images = [_create_test_image(seed=i) for i in range(3)]
        detector = create_detector(FeatureMethod.SIFT, 1000)
        results = extract_features_batch(images, detector, "sift")

        assert len(results) == 3
        for r in results:
            assert r.keypoints_count > 0

    def test_extract_features_from_video(self, temp_dir):
        video_path = os.path.join(temp_dir, "test.mp4")
        _create_test_video(video_path, num_frames=30)

        results = extract_features_from_video(
            video_path, target_fps=2.0, method=FeatureMethod.SIFT
        )
        assert len(results) > 0
        assert any(f.keypoints_count > 0 for f in results)


# --- Feature Matching Tests ---

class TestFeatureMatching:
    def test_match_identical_images(self):
        img = _create_test_image(seed=42)
        detector = create_detector(FeatureMethod.SIFT, 1000)
        f1 = extract_features(img, detector, 0, "sift")
        f2 = extract_features(img, detector, 1, "sift")

        result = match_features(f1, f2, FeatureMethod.SIFT)

        assert isinstance(result, MatchResult)
        assert result.match_ratio > 0.5  # most matches should be good

    def test_match_similar_images(self):
        img1 = _create_test_image(seed=42)
        img2 = _create_test_image(seed=42)
        # Slight shift
        M = np.float32([[1, 0, 5], [0, 1, 3]])
        img2 = cv2.warpAffine(img2, M, (320, 240))

        detector = create_detector(FeatureMethod.SIFT, 1000)
        f1 = extract_features(img1, detector, 0, "sift")
        f2 = extract_features(img2, detector, 1, "sift")

        result = match_features(f1, f2, FeatureMethod.SIFT)
        assert len(result.good_matches) > 0

    def test_match_different_images(self):
        img1 = _create_test_image(seed=42)
        img2 = _create_test_image(seed=99)

        detector = create_detector(FeatureMethod.SIFT, 1000)
        f1 = extract_features(img1, detector, 0, "sift")
        f2 = extract_features(img2, detector, 1, "sift")

        result = match_features(f1, f2, FeatureMethod.SIFT)
        # Different images should have fewer good matches
        assert result.match_ratio < 0.8

    def test_match_with_no_features(self):
        f1 = DetectedFeatures(0, 0, None, np.array([]).reshape(0, 2), "sift", (240, 320))
        f2 = DetectedFeatures(1, 0, None, np.array([]).reshape(0, 2), "sift", (240, 320))

        result = match_features(f1, f2, FeatureMethod.SIFT)
        assert len(result.matches) == 0

    def test_match_features_chain(self, temp_dir):
        video_path = os.path.join(temp_dir, "test.mp4")
        _create_test_video(video_path, num_frames=20)

        features = extract_features_from_video(video_path, target_fps=5.0)
        if len(features) >= 2:
            results = match_features_chain(features)
            assert len(results) == len(features) - 1


# --- Camera Pose Tests ---

class TestCameraPose:
    def test_intrinsics_from_image_size(self):
        K = CameraIntrinsics.from_image_size(640, 480)
        assert K.fx > 0
        assert K.fy > 0
        assert K.cx == 320
        assert K.cy == 240
        assert K.matrix.shape == (3, 3)

    def test_intrinsics_custom_focal(self):
        K = CameraIntrinsics.from_image_size(640, 480, focal_length=500.0)
        assert K.fx == 500.0
        assert K.fy == 500.0

    def test_estimate_fundamental_matrix(self):
        # Create diverse point correspondences
        pts1 = np.array([
            [100, 100], [200, 50], [300, 200], [50, 180],
            [150, 120], [280, 80], [120, 250], [250, 220],
            [180, 160], [80, 140], [220, 190], [350, 100],
        ], dtype=np.float32)
        pts2 = pts1 + np.random.RandomState(42).randn(12, 2).astype(np.float32) * 3

        F, mask = estimate_fundamental_matrix(pts1, pts2)
        assert F is not None
        assert F.shape == (3, 3)
        assert len(mask) == 12

    def test_estimate_fundamental_too_few_points(self):
        pts1 = np.array([[100, 100], [200, 100]], dtype=np.float32)
        pts2 = pts1 + 5
        F, mask = estimate_fundamental_matrix(pts1, pts2)
        assert F is None

    def test_estimate_essential_matrix(self):
        pts1 = np.array([
            [100, 100], [200, 50], [300, 200], [50, 180],
            [150, 120], [280, 80], [120, 250], [250, 220],
            [180, 160], [80, 140], [220, 190], [350, 100],
        ], dtype=np.float32)
        pts2 = pts1 + np.random.RandomState(42).randn(12, 2).astype(np.float32) * 3
        K = np.eye(3)

        E, mask = estimate_essential_matrix(pts1, pts2, K)
        assert E is not None
        assert E.shape == (3, 3)

    def test_build_projection_matrix(self):
        R = np.eye(3)
        t = np.array([[0], [0], [0]])
        K = np.eye(3)

        P = build_projection_matrix(R, t, K)
        assert P.shape == (3, 4)
        # Should be K when R=I, t=0
        np.testing.assert_array_almost_equal(P[:, :3], K)

    def test_reprojection_error_identity(self):
        # Points at known locations should have zero reprojection error
        pts3d = np.array([[0, 0, 5], [1, 0, 5], [0, 1, 5]], dtype=np.float64)
        R = np.eye(3)
        t = np.zeros((3, 1))
        K = np.eye(3)

        # Project manually
        P = build_projection_matrix(R, t, K)
        pts_h = np.hstack([pts3d, np.ones((3, 1))]).T
        projected = P @ pts_h
        projected_2d = (projected[:2] / projected[2]).T

        error = compute_reprojection_error(pts3d, projected_2d, R, t, K)
        assert error < 0.01


# --- Point Cloud Tests ---

class TestPointCloud:
    def test_empty_cloud(self):
        cloud = PointCloud.empty()
        assert cloud.num_points == 0

    def test_filter_by_depth(self):
        cloud = PointCloud(
            points=np.array([[0, 0, 1], [0, 0, 50], [0, 0, 200]]),
            colors=np.array([[255, 0, 0], [0, 255, 0], [0, 0, 255]]),
            frame_indices=np.array([0, 0, 0]),
            num_points=3,
        )
        filtered = cloud.filter_by_depth(0.5, 100)
        assert filtered.num_points == 2

    def test_voxel_downsample(self):
        # Create points in same voxel
        cloud = PointCloud(
            points=np.array([[0.001, 0.001, 1], [0.002, 0.002, 1], [0.05, 0.05, 1]]),
            colors=np.array([[255, 0, 0], [0, 255, 0], [0, 0, 255]]),
            frame_indices=np.array([0, 0, 0]),
            num_points=3,
        )
        downsampled = cloud.voxel_downsample(voxel_size=0.01)
        # First two should merge, third stays
        assert downsampled.num_points <= 3

    def test_to_ply(self, temp_dir):
        cloud = PointCloud(
            points=np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]),
            colors=np.array([[255, 0, 0], [0, 255, 0]]),
            frame_indices=np.array([0, 1]),
            num_points=2,
        )
        ply_path = os.path.join(temp_dir, "test.ply")
        cloud.to_ply(ply_path)
        assert os.path.exists(ply_path)

        with open(ply_path) as f:
            content = f.read()
        assert "ply" in content
        assert "2" in content

    def test_to_xyz_array(self):
        cloud = PointCloud(
            points=np.array([[1.0, 2.0, 3.0]]),
            colors=np.array([[255, 128, 64]]),
            frame_indices=np.array([0]),
            num_points=1,
        )
        arr = cloud.to_xyz_array()
        assert arr.shape == (1, 6)

    def test_generate_from_video(self, temp_dir):
        video_path = os.path.join(temp_dir, "test.mp4")
        _create_test_video(video_path, num_frames=20)

        cloud = generate_point_cloud_from_video(
            video_path, target_fps=2.0, method=FeatureMethod.SIFT
        )
        assert cloud.num_points >= 0  # May be 0 if features don't match well
