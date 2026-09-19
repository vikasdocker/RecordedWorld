"""
Depth Estimation Service

Provides monocular depth estimation from single images using OpenCV.
"""
import numpy as np
from typing import Optional
from dataclasses import dataclass


@dataclass
class DepthResult:
    """Result of depth estimation."""
    depth_map: np.ndarray  # H x W depth values in meters
    confidence_map: Optional[np.ndarray] = None  # H x W confidence [0,1]
    min_depth: float = 0.0
    max_depth: float = 0.0
    mean_depth: float = 0.0


class DepthEstimator:
    """
    Monocular depth estimation using OpenCV DNN or stereo heuristics.

    For production use, this would use a pre-trained MiDaS or DPT model.
    This implementation provides a fallback using image gradients and
    perspective heuristics.
    """

    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path
        self._net = None

    def estimate_from_image(self, image: np.ndarray) -> DepthResult:
        """
        Estimate depth from a single RGB image.

        Args:
            image: H x W x 3 RGB image (uint8)

        Returns:
            DepthResult with depth map in meters
        """
        if image is None or len(image.shape) != 3:
            raise ValueError("Invalid image: expected H x W x 3 RGB")

        h, w = image.shape[:2]

        # Try DNN-based estimation if model available
        if self._net is not None:
            return self._estimate_dnn(image)

        # Fallback: gradient-based depth heuristic
        return self._estimate_gradient_heuristic(image)

    def estimate_from_frames(
        self, frames: list[np.ndarray], poses: Optional[list] = None
    ) -> DepthResult:
        """
        Estimate depth from multiple frames using stereo geometry.

        Args:
            frames: List of RGB images
            poses: Optional camera poses [R|t] for each frame

        Returns:
            DepthResult with aggregated depth map
        """
        if not frames:
            raise ValueError("No frames provided")

        if len(frames) == 1:
            return self.estimate_from_image(frames[0])

        # Use middle frame as reference
        mid_idx = len(frames) // 2
        ref_frame = frames[mid_idx]

        # Simple multi-view depth via SSD matching
        h, w = ref_frame.shape[:2]
        depth_map = np.zeros((h, w), dtype=np.float32)

        ref_gray = np.mean(ref_frame.astype(np.float32), axis=2)

        for i, frame in enumerate(frames):
            if i == mid_idx:
                continue
            other_gray = np.mean(frame.astype(np.float32), axis=2)

            # Compute SSD for small patches
            for y in range(4, h - 4, 8):
                for x in range(4, w - 4, 8):
                    patch_ref = ref_gray[y-4:y+4, x-4:x+4]
                    best_ssd = float('inf')
                    best_disp = 0

                    for disp in range(-8, 9):
                        x2 = x + disp
                        if x2 - 4 < 0 or x2 + 4 > w:
                            continue
                        patch_other = other_gray[y-4:y+4, x2-4:x2+4]
                        ssd = np.sum((patch_ref - patch_other) ** 2)
                        if ssd < best_ssd:
                            best_ssd = ssd
                            best_disp = disp

                    if best_disp != 0:
                        depth_map[y, x] = abs(1.0 / best_disp) if best_disp != 0 else 10.0

        # Fill zeros with median
        valid = depth_map > 0
        if valid.any():
            median_depth = np.median(depth_map[valid])
            depth_map[~valid] = median_depth
        else:
            depth_map[:] = 5.0  # Default 5 meters

        return DepthResult(
            depth_map=depth_map,
            min_depth=float(depth_map.min()),
            max_depth=float(depth_map.max()),
            mean_depth=float(depth_map.mean()),
        )

    def _estimate_gradient_heuristic(self, image: np.ndarray) -> DepthResult:
        """
        Estimate depth using image gradient heuristics.

        Assumes:
          - Lower regions (ground) are closer
          - Darker regions may be farther (atmospheric perspective)
          - High-texture regions are closer
        """
        h, w = image.shape[:2]
        gray = np.mean(image.astype(np.float32), axis=2)

        # Vertical gradient (lower = closer)
        y_coords = np.arange(h).reshape(-1, 1).astype(np.float32)
        vertical_depth = 1.0 + (y_coords / h) * 10.0  # 1-11 meters

        # Texture gradient (high texture = closer)
        grad_x = np.abs(np.diff(gray, axis=1, prepend=gray[:, :1]))
        grad_y = np.abs(np.diff(gray, axis=0, prepend=gray[:1, :]))
        texture = (grad_x + grad_y) / 2.0
        texture_norm = texture / (texture.max() + 1e-6)
        texture_depth = 2.0 + (1.0 - texture_norm) * 8.0  # 2-10 meters

        # Combine
        depth_map = (vertical_depth * 0.6 + texture_depth * 0.4).astype(np.float32)

        return DepthResult(
            depth_map=depth_map,
            min_depth=float(depth_map.min()),
            max_depth=float(depth_map.max()),
            mean_depth=float(depth_map.mean()),
        )

    def _estimate_dnn(self, image: np.ndarray) -> DepthResult:
        """Estimate depth using pre-trained DNN model."""
        # Placeholder for MiDaS/DPT integration
        h, w = image.shape[:2]
        blob = cv2.dnn.blobFromImage(image, 1.0 / 255.0, (384, 384))
        self._net.setInput(blob)
        output = self._net.forward()
        depth_map = cv2.resize(output[0], (w, h))
        depth_map = depth_map.astype(np.float32)

        return DepthResult(
            depth_map=depth_map,
            min_depth=float(depth_map.min()),
            max_depth=float(depth_map.max()),
            mean_depth=float(depth_map.mean()),
        )

    def load_model(self, model_path: str):
        """Load a pre-trained DNN model for depth estimation."""
        try:
            import cv2
            self._net = cv2.dnn.readNetFromONNX(model_path)
            self.model_path = model_path
        except ImportError:
            raise RuntimeError("OpenCV DNN module not available")
        except Exception as e:
            raise RuntimeError(f"Failed to load model: {e}")


# Module-level singleton
depth_estimator = DepthEstimator()
