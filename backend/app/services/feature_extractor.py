"""
Feature Extraction

Extracts visual features from images/video frames using:
- SIFT (Scale-Invariant Feature Transform) — patented, high quality
- ORB (Oriented FAST and Rotated BRIEF) — free, fast
- AKAZE — good balance of speed and quality

Features are the foundation for:
- Frame matching
- Camera pose estimation
- Structure from Motion
- 3D reconstruction
"""

import cv2
import numpy as np
from dataclasses import dataclass
from typing import List, Optional, Tuple
from enum import Enum


class FeatureMethod(Enum):
    SIFT = "sift"
    ORB = "orb"
    AKAZE = "akaze"


@dataclass
class DetectedFeatures:
    """Features detected in a single image."""
    frame_index: int
    keypoints_count: int
    descriptors: Optional[np.ndarray]  # NxD feature descriptor matrix
    keypoints_xy: np.ndarray  # Nx2 keypoint positions (x, y)
    method: str
    image_shape: Tuple[int, int]  # (height, width)


@dataclass
class FeatureMatch:
    """A match between features in two frames."""
    query_idx: int  # index in query frame
    train_idx: int  # index in train frame
    distance: float  # descriptor distance
    frame_query: int
    frame_train: int


@dataclass
class MatchResult:
    """Result of matching two frames."""
    frame_query: int
    frame_train: int
    matches: List[FeatureMatch]
    good_matches: List[FeatureMatch]
    match_ratio: float  # good_matches / total_matches
    avg_distance: float


def create_detector(
    method: FeatureMethod = FeatureMethod.SIFT,
    max_features: int = 5000,
) -> cv2.Feature2D:
    """
    Create a feature detector.

    Args:
        method: Detection method
        max_features: Maximum features to detect

    Returns:
        OpenCV feature detector
    """
    if method == FeatureMethod.SIFT:
        return cv2.SIFT_create(nfeatures=max_features)
    elif method == FeatureMethod.ORB:
        return cv2.ORB_create(nfeatures=max_features)
    elif method == FeatureMethod.AKAZE:
        return cv2.AKAZE_create()
    else:
        raise ValueError(f"Unknown method: {method}")


def extract_features(
    image: np.ndarray,
    detector: cv2.Feature2D,
    frame_index: int = 0,
    method: str = "sift",
) -> DetectedFeatures:
    """
    Extract features from a single image.

    Args:
        image: BGR or grayscale image
        detector: Feature detector
        frame_index: Frame number for tracking
        method: Method name for metadata

    Returns:
        DetectedFeatures with keypoints and descriptors
    """
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    keypoints, descriptors = detector.detectAndCompute(gray, None)

    if keypoints is None or len(keypoints) == 0:
        h, w = gray.shape
        return DetectedFeatures(
            frame_index=frame_index,
            keypoints_count=0,
            descriptors=None,
            keypoints_xy=np.array([]).reshape(0, 2),
            method=method,
            image_shape=(h, w),
        )

    kp_xy = np.array([[kp.pt[0], kp.pt[1]] for kp in keypoints])

    return DetectedFeatures(
        frame_index=frame_index,
        keypoints_count=len(keypoints),
        descriptors=descriptors,
        keypoints_xy=kp_xy,
        method=method,
        image_shape=(gray.shape[0], gray.shape[1]),
    )


def extract_features_from_video(
    video_path: str,
    target_fps: float = 1.0,
    max_features: int = 5000,
    method: FeatureMethod = FeatureMethod.SIFT,
) -> List[DetectedFeatures]:
    """
    Extract features from multiple frames of a video.

    Args:
        video_path: Path to video file
        target_fps: Frame sampling rate
        max_features: Max features per frame
        method: Detection method

    Returns:
        List of DetectedFeatures for each sampled frame
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")

    video_fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    if video_fps <= 0:
        video_fps = 30.0

    frame_interval = max(1, int(video_fps / target_fps))
    detector = create_detector(method, max_features)
    method_str = method.value

    results = []
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % frame_interval == 0:
            features = extract_features(frame, detector, frame_idx, method_str)
            results.append(features)

        frame_idx += 1

    cap.release()
    return results


def extract_features_batch(
    images: List[np.ndarray],
    detector: cv2.Feature2D,
    method: str = "sift",
) -> List[DetectedFeatures]:
    """Extract features from a batch of images."""
    return [
        extract_features(img, detector, i, method)
        for i, img in enumerate(images)
    ]


def get_matcher(
    method: FeatureMethod = FeatureMethod.SIFT,
) -> cv2.DescriptorMatcher:
    """
    Get an appropriate matcher for the feature method.

    SIFT/AKAZE: FLANN-based matcher (faster for float descriptors)
    ORB: BFMatcher with Hamming distance (binary descriptors)
    """
    if method == FeatureMethod.ORB:
        return cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
    else:
        # FLANN parameters for SIFT/AKAZE
        FLANN_INDEX_KDTREE = 1
        index_params = dict(algorithm=FLANN_INDEX_KDTREE, trees=5)
        search_params = dict(checks=50)
        return cv2.FlannBasedMatcher(index_params, search_params)


def match_features(
    features1: DetectedFeatures,
    features2: DetectedFeatures,
    method: FeatureMethod = FeatureMethod.SIFT,
    ratio_threshold: float = 0.75,
) -> MatchResult:
    """
    Match features between two frames using ratio test.

    Args:
        features1: Features from frame 1
        features2: Features from frame 2
        method: Feature method
        ratio_threshold: Lowe's ratio test threshold

    Returns:
        MatchResult with all matches and good matches
    """
    if features1.descriptors is None or features2.descriptors is None:
        return MatchResult(
            frame_query=features1.frame_index,
            frame_train=features2.frame_index,
            matches=[],
            good_matches=[],
            match_ratio=0.0,
            avg_distance=0.0,
        )

    matcher = get_matcher(method)

    # KNN match with k=2 for ratio test
    try:
        knn_matches = matcher.knnMatch(
            features1.descriptors.astype(np.float32),
            features2.descriptors.astype(np.float32),
            k=2,
        )
    except cv2.error:
        return MatchResult(
            frame_query=features1.frame_index,
            frame_train=features2.frame_index,
            matches=[],
            good_matches=[],
            match_ratio=0.0,
            avg_distance=0.0,
        )

    all_matches = []
    good_matches = []

    for match_pair in knn_matches:
        if len(match_pair) < 2:
            continue

        m, n = match_pair
        all_matches.append(FeatureMatch(
            query_idx=m.queryIdx,
            train_idx=m.trainIdx,
            distance=m.distance,
            frame_query=features1.frame_index,
            frame_train=features2.frame_index,
        ))

        # Lowe's ratio test
        if m.distance < ratio_threshold * n.distance:
            good_matches.append(FeatureMatch(
                query_idx=m.queryIdx,
                train_idx=m.trainIdx,
                distance=m.distance,
                frame_query=features1.frame_index,
                frame_train=features2.frame_index,
            ))

    total = len(all_matches)
    good_count = len(good_matches)
    ratio = good_count / total if total > 0 else 0.0
    avg_dist = float(np.mean([m.distance for m in good_matches])) if good_matches else 0.0

    return MatchResult(
        frame_query=features1.frame_index,
        frame_train=features2.frame_index,
        matches=all_matches,
        good_matches=good_matches,
        match_ratio=round(ratio, 4),
        avg_distance=round(avg_dist, 2),
    )


def match_features_chain(
    features_list: List[DetectedFeatures],
    method: FeatureMethod = FeatureMethod.SIFT,
    ratio_threshold: float = 0.75,
) -> List[MatchResult]:
    """
    Match consecutive frames in a chain.
    Returns matches between frame i and frame i+1.
    """
    results = []
    for i in range(len(features_list) - 1):
        result = match_features(
            features_list[i],
            features_list[i + 1],
            method,
            ratio_threshold,
        )
        results.append(result)
    return results
