"""
Frame Deduplication

Removes near-duplicate frames from extracted frame sets using:
- Structural Similarity Index (SSIM)
- Perceptual hashing (pHash approximation)
- Color histogram comparison

Goal: Keep only frames with sufficient visual diversity for SfM.
"""

import cv2
import numpy as np
from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class DedupResult:
    """Result of frame deduplication."""
    kept_frames: List[str]  # paths of kept frames
    removed_frames: List[str]  # paths of removed frames
    similarity_matrix: List[List[float]]  # pairwise similarities
    kept_count: int
    removed_count: int


def deduplicate_frames(
    frame_paths: List[str],
    ssim_threshold: float = 0.85,
    hist_threshold: float = 0.80,
) -> DedupResult:
    """
    Remove near-duplicate frames.

    Args:
        frame_paths: List of image file paths
        ssim_threshold: SSIM above which frames are considered duplicates
        hist_threshold: Histogram similarity above which frames are duplicates

    Returns:
        DedupResult with kept/removed frame lists
    """
    if len(frame_paths) <= 1:
        return DedupResult(
            kept_frames=list(frame_paths),
            removed_frames=[],
            similarity_matrix=[],
            kept_count=len(frame_paths),
            removed_count=0,
        )

    # Load all frames as grayscale
    images = []
    for path in frame_paths:
        img = cv2.imread(path)
        if img is not None:
            images.append(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
        else:
            images.append(None)

    # Compute pairwise similarity
    n = len(frame_paths)
    ssim_matrix = np.zeros((n, n))
    hist_matrix = np.zeros((n, n))

    for i in range(n):
        for j in range(i + 1, n):
            if images[i] is None or images[j] is None:
                ssim_matrix[i][j] = 0.0
                ssim_matrix[j][i] = 0.0
                hist_matrix[i][j] = 0.0
                hist_matrix[j][i] = 0.0
                continue

            # SSIM
            ssim_val = _compute_ssim(images[i], images[j])
            ssim_matrix[i][j] = ssim_val
            ssim_matrix[j][i] = ssim_val

            # Histogram
            hist_val = _compute_hist_similarity(
                cv2.imread(frame_paths[i]),
                cv2.imread(frame_paths[j]),
            )
            hist_matrix[i][j] = hist_val
            hist_matrix[j][i] = hist_val

    # Greedy selection: keep frame if not too similar to any already-kept frame
    kept_indices = [0]  # always keep first frame
    removed_indices = []

    for i in range(1, n):
        is_duplicate = False
        for kept_idx in kept_indices:
            if ssim_matrix[i][kept_idx] > ssim_threshold:
                is_duplicate = True
                break
            if hist_matrix[i][kept_idx] > hist_threshold:
                is_duplicate = True
                break

        if not is_duplicate:
            kept_indices.append(i)
        else:
            removed_indices.append(i)

    # Build similarity matrix for kept frames only
    kept_ssim = []
    for i in kept_indices:
        row = []
        for j in kept_indices:
            row.append(round(ssim_matrix[i][j], 4))
        kept_ssim.append(row)

    return DedupResult(
        kept_frames=[frame_paths[i] for i in kept_indices],
        removed_frames=[frame_paths[i] for i in removed_indices],
        similarity_matrix=kept_ssim,
        kept_count=len(kept_indices),
        removed_count=len(removed_indices),
    )


def deduplicate_video_frames(
    video_path: str,
    output_dir: str,
    target_fps: float = 1.0,
    ssim_threshold: float = 0.85,
) -> DedupResult:
    """
    Extract frames from video and deduplicate in one pass.

    Args:
        video_path: Path to video file
        output_dir: Directory to save deduplicated frames
        target_fps: Extraction rate
        ssim_threshold: SSIM duplicate threshold

    Returns:
        DedupResult
    """
    from app.services.frame_extractor import extract_frames

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    dedup_dir = output_path / "deduped"
    dedup_dir.mkdir(exist_ok=True)

    # Extract frames
    frames = extract_frames(video_path, str(output_path / "raw"), target_fps=target_fps)
    frame_paths = [f.path for f in frames]

    if not frame_paths:
        return DedupResult(
            kept_frames=[], removed_frames=[],
            similarity_matrix=[], kept_count=0, removed_count=0,
        )

    # Deduplicate
    result = deduplicate_frames(frame_paths, ssim_threshold=ssim_threshold)

    # Copy kept frames to deduped directory
    kept_paths = []
    for i, path in enumerate(result.kept_frames):
        new_path = str(dedup_dir / f"frame_{i:04d}.jpg")
        img = cv2.imread(path)
        if img is not None:
            cv2.imwrite(new_path, img, [cv2.IMWRITE_JPEG_QUALITY, 95])
            kept_paths.append(new_path)

    result.kept_frames = kept_paths
    return result


def _compute_ssim(img1: np.ndarray, img2: np.ndarray) -> float:
    """
    Compute Structural Similarity Index between two grayscale images.
    Returns value between 0 (completely different) and 1 (identical).
    """
    # Ensure same size
    if img1.shape != img2.shape:
        h = min(img1.shape[0], img2.shape[0])
        w = min(img1.shape[1], img2.shape[1])
        img1 = img1[:h, :w]
        img2 = img2[:h, :w]

    C1 = (0.01 * 255) ** 2
    C2 = (0.03 * 255) ** 2

    img1 = img1.astype(np.float64)
    img2 = img2.astype(np.float64)

    mu1 = cv2.GaussianBlur(img1, (11, 11), 1.5)
    mu2 = cv2.GaussianBlur(img2, (11, 11), 1.5)

    mu1_sq = mu1 ** 2
    mu2_sq = mu2 ** 2
    mu1_mu2 = mu1 * mu2

    sigma1_sq = cv2.GaussianBlur(img1 ** 2, (11, 11), 1.5) - mu1_sq
    sigma2_sq = cv2.GaussianBlur(img2 ** 2, (11, 11), 1.5) - mu2_sq
    sigma12 = cv2.GaussianBlur(img1 * img2, (11, 11), 1.5) - mu1_mu2

    ssim_map = ((2 * mu1_mu2 + C1) * (2 * sigma12 + C2)) / \
               ((mu1_sq + mu2_sq + C1) * (sigma1_sq + sigma2_sq + C2))

    return float(np.mean(ssim_map))


def _compute_hist_similarity(img1: np.ndarray, img2: np.ndarray) -> float:
    """
    Compute histogram similarity between two BGR images.
    Returns value between 0 (different) and 1 (identical).
    """
    if img1 is None or img2 is None:
        return 0.0

    hist1 = cv2.calcHist([img1], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
    hist2 = cv2.calcHist([img2], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])

    cv2.normalize(hist1, hist1)
    cv2.normalize(hist2, hist2)

    return float(cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL))


def compute_pairwise_ssim(frame_paths: List[str]) -> List[List[float]]:
    """Compute pairwise SSIM matrix for a list of frame paths."""
    images = []
    for path in frame_paths:
        img = cv2.imread(path)
        if img is not None:
            images.append(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
        else:
            images.append(None)

    n = len(frame_paths)
    matrix = []
    for i in range(n):
        row = []
        for j in range(n):
            if i == j:
                row.append(1.0)
            elif images[i] is None or images[j] is None:
                row.append(0.0)
            else:
                row.append(round(_compute_ssim(images[i], images[j]), 4))
        matrix.append(row)

    return matrix
