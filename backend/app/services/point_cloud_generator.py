"""
Point Cloud Generation

Generates 3D point clouds from video frames using:
- Multi-view triangulation
- Depth estimation from camera poses
- Point filtering and cleanup

Output: XYZ points with RGB color for mesh generation.
"""

import cv2
import numpy as np
from dataclasses import dataclass
from typing import List, Optional, Tuple

from app.services.feature_extractor import (
    DetectedFeatures, MatchResult, extract_features, extract_features_from_video,
    match_features, create_detector, FeatureMethod
)
from app.services.camera_pose import (
    CameraPose, CameraIntrinsics, TriangulationResult,
    estimate_camera_pose, triangulate_points, build_projection_matrix,
)


@dataclass
class PointCloud:
    """A 3D point cloud with colors."""
    points: np.ndarray  # Nx3
    colors: np.ndarray  # Nx3 (RGB, 0-255)
    frame_indices: np.ndarray  # N (which frame each point came from)
    num_points: int

    @classmethod
    def empty(cls) -> "PointCloud":
        return cls(
            points=np.array([]).reshape(0, 3),
            colors=np.array([]).reshape(0, 3),
            frame_indices=np.array([], dtype=int),
            num_points=0,
        )

    def filter_by_depth(self, min_depth: float = 0.1, max_depth: float = 100.0) -> "PointCloud":
        """Remove points outside depth range."""
        depths = self.points[:, 2]
        mask = (depths >= min_depth) & (depths <= max_depth)
        return PointCloud(
            points=self.points[mask],
            colors=self.colors[mask],
            frame_indices=self.frame_indices[mask],
            num_points=int(np.sum(mask)),
        )

    def filter_by_statistical_outlier(self, k: int = 20, std_ratio: float = 2.0) -> "PointCloud":
        """Remove statistical outliers."""
        if self.num_points < k:
            return self

        from scipy.spatial import cKDTree
        tree = cKDTree(self.points)
        distances, _ = tree.query(self.points, k=k + 1)
        mean_dist = np.mean(distances[:, 1:], axis=1)
        threshold = np.mean(mean_dist) + std_ratio * np.std(mean_dist)
        mask = mean_dist < threshold

        return PointCloud(
            points=self.points[mask],
            colors=self.colors[mask],
            frame_indices=self.frame_indices[mask],
            num_points=int(np.sum(mask)),
        )

    def voxel_downsample(self, voxel_size: float = 0.01) -> "PointCloud":
        """Downsample using voxel grid."""
        if self.num_points == 0:
            return self

        # Quantize to voxel grid
        quantized = np.floor(self.points / voxel_size).astype(np.int32)

        # Unique voxels
        _, unique_indices = np.unique(
            quantized, axis=0, return_index=True
        )

        return PointCloud(
            points=self.points[unique_indices],
            colors=self.colors[unique_indices],
            frame_indices=self.frame_indices[unique_indices],
            num_points=len(unique_indices),
        )

    def to_ply(self, path: str):
        """Export to PLY format."""
        with open(path, "w") as f:
            f.write("ply\n")
            f.write("format ascii 1.0\n")
            f.write(f"element vertex {self.num_points}\n")
            f.write("property float x\n")
            f.write("property float y\n")
            f.write("property float z\n")
            f.write("property uchar red\n")
            f.write("property uchar green\n")
            f.write("property uchar blue\n")
            f.write("end_header\n")
            for i in range(self.num_points):
                p = self.points[i]
                c = self.colors[i]
                f.write(f"{p[0]:.6f} {p[1]:.6f} {p[2]:.6f} {int(c[0])} {int(c[1])} {int(c[2])}\n")

    def to_xyz_array(self) -> np.ndarray:
        """Return Nx6 array: [x, y, z, r, g, b]."""
        return np.hstack([self.points, self.colors])


def generate_point_cloud_from_video(
    video_path: str,
    target_fps: float = 1.0,
    method: FeatureMethod = FeatureMethod.SIFT,
    max_features: int = 5000,
) -> PointCloud:
    """
    Generate a point cloud from a video using SfM pipeline.

    Pipeline:
    1. Extract features from sampled frames
    2. Match features between consecutive frames
    3. Estimate camera poses
    4. Triangulate 3D points
    5. Merge into single point cloud

    Args:
        video_path: Path to video file
        target_fps: Frame sampling rate
        method: Feature detection method
        max_features: Max features per frame

    Returns:
        PointCloud with all triangulated points
    """
    # Step 1: Extract features
    features_list = extract_features_from_video(
        video_path, target_fps, max_features, method
    )

    if len(features_list) < 2:
        return PointCloud.empty()

    # Get image dimensions from first frame
    h, w = features_list[0].image_shape
    intrinsics = CameraIntrinsics.from_image_size(w, h)
    K = intrinsics.matrix

    # Step 2-4: Match features, estimate poses, triangulate
    all_points = []
    all_colors = []
    all_frame_indices = []

    # Read video for color sampling
    cap = cv2.VideoCapture(video_path)
    video_fps = cap.get(cv2.CAP_PROP_FPS)
    if video_fps <= 0:
        video_fps = 30.0
    frame_interval = max(1, int(video_fps / target_fps))

    # Accumulate poses
    poses = [CameraPose(
        rotation=np.eye(3),
        translation=np.zeros((3, 1)),
        fundamental_matrix=np.zeros((3, 3)),
        essential_matrix=np.zeros((3, 3)),
        inlier_mask=np.array([], dtype=bool),
        num_inliers=0,
        pose_valid=True,
    )]

    # Estimate poses for each consecutive pair
    for i in range(len(features_list) - 1):
        f1 = features_list[i]
        f2 = features_list[i + 1]

        if f1.descriptors is None or f2.descriptors is None:
            continue

        # Match features
        match_result = match_features(f1, f2, method)

        if len(match_result.good_matches) < 10:
            continue

        # Get matched point coordinates
        pts1 = np.array([
            f1.keypoints_xy[m.query_idx] for m in match_result.good_matches
        ])
        pts2 = np.array([
            f2.keypoints_xy[m.train_idx] for m in match_result.good_matches
        ])

        # Estimate relative pose
        pose = estimate_camera_pose(pts1, pts2, (h, w))

        if not pose.pose_valid:
            continue

        # Accumulate global pose
        global_R = poses[-1].rotation @ pose.rotation
        global_t = poses[-1].translation + poses[-1].rotation @ pose.translation
        poses.append(CameraPose(
            rotation=global_R,
            translation=global_t,
            fundamental_matrix=pose.fundamental_matrix,
            essential_matrix=pose.essential_matrix,
            inlier_mask=pose.inlier_mask,
            num_inliers=pose.num_inliers,
            pose_valid=True,
        ))

    cap.release()

    # Step 4: Triangulate points between consecutive frame pairs
    cap = cv2.VideoCapture(video_path)
    frame_idx = 0
    sample_idx = 0

    while sample_idx < len(features_list) - 1:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % frame_interval == 0 and sample_idx < len(poses) - 1:
            f1 = features_list[sample_idx]
            f2 = features_list[sample_idx + 1]

            if f1.descriptors is not None and f2.descriptors is not None:
                match_result = match_features(f1, f2, method)

                if len(match_result.good_matches) >= 10:
                    pts1 = np.array([
                        f1.keypoints_xy[m.query_idx] for m in match_result.good_matches
                    ])
                    pts2 = np.array([
                        f2.keypoints_xy[m.train_idx] for m in match_result.good_matches
                    ])

                    # Build projection matrices
                    R1 = poses[sample_idx].rotation
                    t1 = poses[sample_idx].translation
                    R2 = poses[sample_idx + 1].rotation
                    t2 = poses[sample_idx + 1].translation

                    P1 = build_projection_matrix(R1, t1, K)
                    P2 = build_projection_matrix(R2, t2, K)

                    # Triangulate
                    tri_result = triangulate_points(pts1, pts2, P1, P2)

                    if tri_result.num_valid > 0:
                        valid_pts = tri_result.points_3d[tri_result.inlier_mask]

                        # Sample colors from frame
                        colors = []
                        for pt in pts1[tri_result.inlier_mask]:
                            x, y = int(pt[0]), int(pt[1])
                            x = max(0, min(x, frame.shape[1] - 1))
                            y = max(0, min(y, frame.shape[0] - 1))
                            bgr = frame[y, x]
                            colors.append([bgr[2], bgr[1], bgr[0]])  # BGR to RGB

                        all_points.append(valid_pts)
                        all_colors.append(np.array(colors))
                        all_frame_indices.append(
                            np.full(len(valid_pts), sample_idx)
                        )

            sample_idx += 1

        frame_idx += 1

    cap.release()

    if not all_points:
        return PointCloud.empty()

    # Merge all points
    merged_points = np.vstack(all_points)
    merged_colors = np.vstack(all_colors)
    merged_indices = np.concatenate(all_frame_indices)

    cloud = PointCloud(
        points=merged_points,
        colors=merged_colors,
        frame_indices=merged_indices,
        num_points=len(merged_points),
    )

    # Filter outliers
    cloud = cloud.filter_by_depth(0.1, 500.0)
    if cloud.num_points > 100:
        cloud = cloud.voxel_downsample(voxel_size=0.02)

    return cloud
