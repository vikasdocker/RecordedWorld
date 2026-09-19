"""
Semantic Segmentation Service

Provides basic semantic segmentation using color-based region classification.
"""
import numpy as np
from typing import Dict, List, Tuple
from dataclasses import dataclass


@dataclass
class SegmentationResult:
    """Result of semantic segmentation."""
    segmentation_map: np.ndarray  # H x W class labels
    class_labels: Dict[int, str]  # label_id -> class name
    class_percentages: Dict[str, float]  # class_name -> percentage
    confidence_map: np.ndarray  # H x W confidence values


# Semantic classes
SEMANTIC_CLASSES = {
    0: "unknown",
    1: "sky",
    2: "vegetation",
    3: "ground",
    4: "building",
    5: "road",
    6: "water",
    7: "vehicle",
    8: "person",
}


def rgb_to_hsv(image: np.ndarray) -> np.ndarray:
    """Convert RGB image to HSV."""
    import cv2
    return cv2.cvtColor(image, cv2.COLOR_RGB2HSV)


class SemanticSegmenter:
    """
    Basic semantic segmentation using color-based classification.

    Segments images into: sky, vegetation, ground, building, road, water.
    For production, use a trained neural network (DeepLab, SegFormer, etc.).
    """

    def segment(self, image: np.ndarray) -> SegmentationResult:
        """
        Segment an image into semantic classes.

        Args:
            image: H x W x 3 RGB image (uint8)

        Returns:
            SegmentationResult with class map and statistics
        """
        if image is None or len(image.shape) != 3:
            h, w = (100, 100) if image is None else image.shape[:2]
            return SegmentationResult(
                segmentation_map=np.zeros((h, w), dtype=np.int32),
                class_labels={0: "unknown"},
                class_percentages={"unknown": 1.0},
                confidence_map=np.zeros((h, w), dtype=np.float32),
            )

        h, w = image.shape[:2]
        hsv = rgb_to_hsv(image)
        seg_map = np.zeros((h, w), dtype=np.int32)
        conf_map = np.zeros((h, w), dtype=np.float32)

        # Sky detection (high brightness, low saturation, blue-ish)
        sky_mask = (
            (hsv[:, :, 0] >= 95) & (hsv[:, :, 0] <= 130) &
            (hsv[:, :, 1] >= 30) & (hsv[:, :, 2] >= 100)
        )
        seg_map[sky_mask] = 1
        conf_map[sky_mask] = 0.7

        # Vegetation (green hue)
        veg_mask = (
            (hsv[:, :, 0] >= 35) & (hsv[:, :, 0] <= 85) &
            (hsv[:, :, 1] >= 50) & (hsv[:, :, 2] >= 50)
        )
        seg_map[veg_mask] = 2
        conf_map[veg_mask] = 0.7

        # Water (blue, lower saturation)
        water_mask = (
            (hsv[:, :, 0] >= 95) & (hsv[:, :, 0] <= 130) &
            (hsv[:, :, 1] >= 20) & (hsv[:, :, 1] <= 150) &
            (hsv[:, :, 2] >= 50) & (hsv[:, :, 2] <= 200) &
            (~sky_mask)
        )
        seg_map[water_mask] = 6
        conf_map[water_mask] = 0.6

        # Ground (brown/tan)
        ground_mask = (
            (hsv[:, :, 0] >= 10) & (hsv[:, :, 0] <= 30) &
            (hsv[:, :, 1] >= 30) & (hsv[:, :, 2] >= 30) &
            (hsv[:, :, 2] <= 180) &
            (~sky_mask) & (~veg_mask) & (~water_mask)
        )
        seg_map[ground_mask] = 3
        conf_map[ground_mask] = 0.5

        # Road/building (gray, low saturation)
        gray_mask = (
            (hsv[:, :, 1] <= 30) &
            (hsv[:, :, 2] >= 60) & (hsv[:, :, 2] <= 200) &
            (~sky_mask) & (~veg_mask) & (~water_mask) & (~ground_mask)
        )
        seg_map[gray_mask] = 4  # Default to building
        conf_map[gray_mask] = 0.4

        # Compute class percentages
        total = h * w
        class_percentages = {}
        for label_id, class_name in SEMANTIC_CLASSES.items():
            count = np.sum(seg_map == label_id)
            class_percentages[class_name] = float(count / total)

        return SegmentationResult(
            segmentation_map=seg_map,
            class_labels=SEMANTIC_CLASSES,
            class_percentages=class_percentages,
            confidence_map=conf_map,
        )


# Module-level singleton
semantic_segmenter = SemanticSegmenter()
