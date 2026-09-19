"""
Object Detection Service

Provides basic object detection using contour analysis and color heuristics.
"""
import numpy as np
from typing import List, Dict, Tuple
from dataclasses import dataclass


@dataclass
class BoundingBox:
    """Bounding box for a detected object."""
    x: int
    y: int
    width: int
    height: int
    area: int


@dataclass
class DetectedObject:
    """A detected object in an image."""
    label: str
    confidence: float
    bbox: BoundingBox
    center_x: float
    center_y: float


# Object categories
OBJECT_CATEGORIES = {
    "building": {"min_area": 5000, "color_range": None},
    "vehicle": {"min_area": 500, "max_area": 5000, "color_range": None},
    "vegetation": {"min_area": 1000, "color_range": {"h_min": 35, "h_max": 85}},
    "person": {"min_area": 200, "max_area": 2000, "aspect_ratio": (0.2, 0.5)},
}


class ObjectDetector:
    """
    Basic object detection using contour analysis.

    Detects objects based on:
      - Color regions
      - Contour shapes
      - Size constraints

    For production, use YOLO, Faster R-CNN, etc.
    """

    def detect(
        self,
        image: np.ndarray,
        min_area: int = 100,
        max_objects: int = 50,
    ) -> List[DetectedObject]:
        """
        Detect objects in an image.

        Args:
            image: H x W x 3 RGB image (uint8)
            min_area: Minimum contour area to consider
            max_objects: Maximum objects to return

        Returns:
            List of DetectedObject instances
        """
        if image is None or len(image.shape) != 3:
            return []

        import cv2

        # Convert to grayscale for contour detection
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

        # Edge detection
        edges = cv2.Canny(gray, 50, 150)

        # Find contours
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        detected = []
        h, w = image.shape[:2]

        for contour in contours:
            area = cv2.contourArea(contour)
            if area < min_area:
                continue

            x, y, cw, ch = cv2.boundingRect(contour)
            bbox = BoundingBox(x, y, cw, ch, area)
            center_x = x + cw / 2
            center_y = y + ch / 2

            # Classify based on size and position
            label, confidence = self._classify_contour(area, cw, ch, y, h)

            detected.append(DetectedObject(
                label=label,
                confidence=confidence,
                bbox=bbox,
                center_x=center_x,
                center_y=center_y,
            ))

        # Sort by area descending
        detected.sort(key=lambda d: d.bbox.area, reverse=True)
        return detected[:max_objects]

    def _classify_contour(
        self, area: int, width: int, height: int, y_pos: int, img_height: int
    ) -> Tuple[str, float]:
        """Classify a contour based on its properties."""
        aspect_ratio = width / max(height, 1)

        # Large object at bottom = ground/building
        if area > 10000 and y_pos > img_height * 0.5:
            return "ground", 0.5

        # Large object at top = building/sky
        if area > 10000 and y_pos < img_height * 0.3:
            return "building", 0.4

        # Tall narrow object = person/vehicle
        if 0.2 < aspect_ratio < 0.5 and 500 < area < 5000:
            return "vehicle", 0.3

        # Wide flat object = vehicle
        if aspect_ratio > 2.0 and 500 < area < 5000:
            return "vehicle", 0.3

        # Medium object = vegetation
        if 1000 < area < 10000:
            return "vegetation", 0.4

        return "unknown", 0.2

    def detect_by_color(
        self,
        image: np.ndarray,
        target_color_range: Dict[str, int],
        min_area: int = 100,
    ) -> List[DetectedObject]:
        """
        Detect objects by color range.

        Args:
            image: H x W x 3 RGB image
            target_color_range: HSV range {"h_min", "h_max", "s_min", "s_max", "v_min", "v_max"}
            min_area: Minimum contour area

        Returns:
            List of DetectedObject instances
        """
        import cv2

        hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)

        mask = cv2.inRange(
            hsv,
            np.array([target_color_range["h_min"], target_color_range["s_min"], target_color_range["v_min"]]),
            np.array([target_color_range["h_max"], target_color_range["s_max"], target_color_range["v_max"]]),
        )

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        detected = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < min_area:
                continue

            x, y, w, h = cv2.boundingRect(contour)
            detected.append(DetectedObject(
                label="colored_object",
                confidence=0.6,
                bbox=BoundingBox(x, y, w, h, area),
                center_x=x + w / 2,
                center_y=y + h / 2,
            ))

        return detected


# Module-level singleton
object_detector = ObjectDetector()
