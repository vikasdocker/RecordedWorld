"""
Camera Pose Estimation

Estimates camera motion between frames using:
- Fundamental matrix estimation
- Essential matrix decomposition
- Camera pose recovery (R, t)
- Triangulation for 3D point recovery

Pipeline:
  Matched Features → Fundamental Matrix → Essential Matrix → R, t → Triangulation → 3D Points
"""

import cv2
import numpy as np
from dataclasses import dataclass
from typing import Optional, Tuple, List


@dataclass
class CameraPose:
    """Estimated camera pose relative to a reference frame."""
    rotation: np.ndarray  # 3x3 rotation matrix
    translation: np.ndarray  # 3x1 translation vector
    fundamental_matrix: np.ndarray  # 3x3
    essential_matrix: np.ndarray  # 3x3
    inlier_mask: np.ndarray  # boolean mask
    num_inliers: int
    pose_valid: bool


@dataclass
class CameraIntrinsics:
    """Camera intrinsic parameters."""
    fx: float  # focal length x
    fy: float  # focal length y
    cx: float  # principal point x
    cy: float  # principal point y
    width: int
    height: int

    @property
    def matrix(self) -> np.ndarray:
        """3x3 camera intrinsic matrix."""
        return np.array([
            [self.fx, 0, self.cx],
            [0, self.fy, self.cy],
            [0, 0, 1],
        ], dtype=np.float64)

    @classmethod
    def from_image_size(
        cls, width: int, height: int,
        focal_length: Optional[float] = None,
    ) -> "CameraIntrinsics":
        """
        Create intrinsics with estimated focal length.
        Assumes focal length ≈ 1.2 * max(width, height) for typical phone cameras.
        """
        if focal_length is None:
            focal_length = 1.2 * max(width, height)
        return cls(
            fx=focal_length,
            fy=focal_length,
            cx=width / 2.0,
            cy=height / 2.0,
            width=width,
            height=height,
        )


@dataclass
class Point3D:
    """A 3D point with color."""
    x: float
    y: float
    z: float
    r: int = 255
    g: int = 255
    b: int = 255


@dataclass
class TriangulationResult:
    """Result of triangulating matched features."""
    points_3d: np.ndarray  # Nx4 or Nx3 points (homogeneous or xyz)
    inlier_mask: np.ndarray  # boolean mask for valid points
    num_points: int
    num_valid: int
    mean_depth: float


def estimate_fundamental_matrix(
    pts1: np.ndarray,
    pts2: np.ndarray,
    method: int = cv2.FM_RANSAC,
    ransac_reproj_threshold: float = 3.0,
) -> Tuple[Optional[np.ndarray], np.ndarray]:
    """
    Estimate fundamental matrix from matched point pairs.

    Args:
        pts1: Nx2 points in first image
        pts2: Nx2 points in second image
        method: Estimation method
        ransac_reproj_threshold: RANSAC threshold in pixels

    Returns:
        (fundamental_matrix, inlier_mask) or (None, empty_mask)
    """
    if len(pts1) < 8:
        return None, np.array([], dtype=bool)

    F, mask = cv2.findFundamentalMat(
        pts1, pts2,
        method=method,
        ransacReprojThreshold=ransac_reproj_threshold,
    )

    if F is None:
        return None, np.array([], dtype=bool)

    return F, mask.ravel().astype(bool)


def estimate_essential_matrix(
    pts1: np.ndarray,
    pts2: np.ndarray,
    camera_matrix: np.ndarray,
    method: int = cv2.FM_RANSAC,
    ransac_reproj_threshold: float = 3.0,
) -> Tuple[Optional[np.ndarray], np.ndarray]:
    """
    Estimate essential matrix using camera intrinsics.

    Args:
        pts1: Nx2 points in first image
        pts2: Nx2 points in second image
        camera_matrix: 3x3 intrinsic matrix
        method: Estimation method
        ransac_reproj_threshold: RANSAC threshold

    Returns:
        (essential_matrix, inlier_mask) or (None, empty_mask)
    """
    if len(pts1) < 8:
        return None, np.array([], dtype=bool)

    E, mask = cv2.findEssentialMat(
        pts1, pts2,
        camera_matrix,
        method=method,
        threshold=ransac_reproj_threshold,
    )

    if E is None:
        return None, np.array([], dtype=bool)

    return E, mask.ravel().astype(bool)


def recover_pose(
    essential_matrix: np.ndarray,
    pts1: np.ndarray,
    pts2: np.ndarray,
    camera_matrix: np.ndarray,
) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], np.ndarray]:
    """
    Recover camera pose from essential matrix.

    Returns:
        (rotation, translation, inlier_mask)
        rotation: 3x3 matrix
        translation: 3x1 vector (unit length)
    """
    if len(pts1) < 5:
        return None, None, np.array([], dtype=bool)

    num_inlier, R, t, mask = cv2.recoverPose(
        essential_matrix, pts1, pts2,
        cameraMatrix=camera_matrix,
    )

    if num_inlier < 5:
        return None, None, mask.ravel().astype(bool)

    return R, t, mask.ravel().astype(bool)


def estimate_camera_pose(
    pts1: np.ndarray,
    pts2: np.ndarray,
    image_shape: Tuple[int, int],
    focal_length: Optional[float] = None,
) -> CameraPose:
    """
    Full camera pose estimation pipeline.

    Args:
        pts1: Nx2 matched points in first image
        pts2: Nx2 matched points in second image
        image_shape: (height, width) of images
        focal_length: Optional focal length override

    Returns:
        CameraPose with R, t, and metadata
    """
    h, w = image_shape
    intrinsics = CameraIntrinsics.from_image_size(w, h, focal_length)
    K = intrinsics.matrix

    # Step 1: Essential matrix
    E, e_mask = estimate_essential_matrix(pts1, pts2, K)

    if E is None:
        return CameraPose(
            rotation=np.eye(3),
            translation=np.zeros((3, 1)),
            fundamental_matrix=np.zeros((3, 3)),
            essential_matrix=np.zeros((3, 3)),
            inlier_mask=np.zeros(len(pts1), dtype=bool),
            num_inliers=0,
            pose_valid=False,
        )

    # Step 2: Recover pose
    R, t, pose_mask = recover_pose(E, pts1, pts2, K)

    if R is None:
        return CameraPose(
            rotation=np.eye(3),
            translation=np.zeros((3, 1)),
            fundamental_matrix=np.zeros((3, 3)),
            essential_matrix=E,
            inlier_mask=np.zeros(len(pts1), dtype=bool),
            num_inliers=0,
            pose_valid=False,
        )

    # Step 3: Fundamental matrix (for reference)
    F, _ = estimate_fundamental_matrix(pts1, pts2)

    if F is None:
        F = np.zeros((3, 3))

    # Combine masks
    combined_mask = e_mask & pose_mask

    return CameraPose(
        rotation=R,
        translation=t,
        fundamental_matrix=F,
        essential_matrix=E,
        inlier_mask=combined_mask,
        num_inliers=int(np.sum(combined_mask)),
        pose_valid=True,
    )


def triangulate_points(
    pts1: np.ndarray,
    pts2: np.ndarray,
    P1: np.ndarray,
    P2: np.ndarray,
) -> TriangulationResult:
    """
    Triangulate 3D points from matched 2D points.

    Args:
        pts1: Nx2 points in first image
        pts2: Nx2 points in second image
        P1: 3x4 projection matrix for camera 1
        P2: 3x4 projection matrix for camera 2

    Returns:
        TriangulationResult with 3D points
    """
    if len(pts1) < 5:
        return TriangulationResult(
            points_3d=np.array([]),
            inlier_mask=np.array([], dtype=bool),
            num_points=0,
            num_valid=0,
            mean_depth=0.0,
        )

    pts1_h = pts1.T.astype(np.float64)  # 2xN
    pts2_h = pts2.T.astype(np.float64)  # 2xN

    points_4d = cv2.triangulatePoints(P1, P2, pts1_h, pts2_h)

    # Convert from homogeneous to Cartesian
    points_3d = points_4d[:3] / points_4d[3]  # 3xN

    # Filter points behind cameras
    depths = points_3d[2]
    valid = (depths > 0.1) & (depths < 1000.0)  # reasonable depth range

    mean_depth = float(np.mean(depths[valid])) if np.any(valid) else 0.0

    return TriangulationResult(
        points_3d=points_3d.T,  # Nx3
        inlier_mask=valid,
        num_points=len(pts1),
        num_valid=int(np.sum(valid)),
        mean_depth=round(mean_depth, 3),
    )


def build_projection_matrix(
    R: np.ndarray,
    t: np.ndarray,
    K: np.ndarray,
) -> np.ndarray:
    """
    Build 3x4 projection matrix from R, t, K.
    P = K @ [R | t]
    """
    Rt = np.hstack([R, t.reshape(3, 1)])
    return K @ Rt


def compute_reprojection_error(
    points_3d: np.ndarray,
    points_2d: np.ndarray,
    R: np.ndarray,
    t: np.ndarray,
    K: np.ndarray,
) -> float:
    """
    Compute mean reprojection error.

    Args:
        points_3d: Nx3 3D points
        points_2d: Nx2 observed 2D points
        R: 3x3 rotation
        t: 3x1 translation
        K: 3x3 intrinsic matrix

    Returns:
        Mean reprojection error in pixels
    """
    if len(points_3d) == 0:
        return float("inf")

    P = build_projection_matrix(R, t, K)

    # Project 3D points to 2D
    pts_h = np.hstack([points_3d, np.ones((len(points_3d), 1))]).T  # 4xN
    projected = P @ pts_h  # 3xN
    projected_2d = projected[:2] / projected[2]  # 2xN

    # Compute error
    error = np.sqrt(np.sum((projected_2d.T - points_2d) ** 2, axis=1))
    return float(np.mean(error))
