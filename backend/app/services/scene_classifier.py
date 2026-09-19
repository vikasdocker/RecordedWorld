"""
Scene Classification Service

Classifies images into scene categories using color/histogram analysis.
"""
import numpy as np
from typing import Dict, List, Tuple
from dataclasses import dataclass


@dataclass
class SceneClassification:
    """Result of scene classification."""
    scene_type: str  # indoor, outdoor_urban, outdoor_natural, sky, water, etc.
    confidence: float  # 0.0-1.0
    features: Dict[str, float]  # Intermediate feature values


# Color ranges for classification (HSV)
COLOR_RANGES = {
    "sky_blue": {"h_min": 100, "h_max": 130, "s_min": 50, "s_max": 255, "v_min": 100, "v_max": 255},
    "grass_green": {"h_min": 35, "h_max": 85, "s_min": 50, "s_max": 255, "v_min": 50, "v_max": 255},
    "water_blue": {"h_min": 95, "h_max": 130, "s_min": 30, "s_max": 255, "v_min": 50, "v_max": 200},
    "earth_brown": {"h_min": 10, "h_max": 30, "s_min": 30, "s_max": 200, "v_min": 30, "v_max": 180},
    "concrete_gray": {"h_min": 0, "h_max": 180, "s_min": 0, "s_max": 30, "v_min": 80, "v_max": 200},
}


def rgb_to_hsv(image: np.ndarray) -> np.ndarray:
    """Convert RGB image to HSV color space."""
    import cv2
    return cv2.cvtColor(image, cv2.COLOR_RGB2HSV)


def compute_color_histogram(image: np.ndarray, bins: int = 16) -> Dict[str, np.ndarray]:
    """Compute color histograms for each channel."""
    histograms = {}
    for i, channel in enumerate(["h", "s", "v"]):
        hist, _ = np.histogram(image[:, :, i], bins=bins, range=(0, 256))
        histograms[channel] = hist.astype(float) / hist.sum()
    return histograms


def compute_texture_features(image: np.ndarray) -> Dict[str, float]:
    """Compute basic texture features."""
    gray = np.mean(image.astype(float), axis=2)

    # Edge density
    edges = np.abs(np.diff(gray, axis=1))
    edge_density = np.mean(edges) / 255.0

    # Color variance (high = textured, low = uniform)
    color_variance = np.std(gray) / 128.0

    # Brightness
    brightness = np.mean(gray) / 255.0

    return {
        "edge_density": float(edge_density),
        "color_variance": float(color_variance),
        "brightness": float(brightness),
    }


class SceneClassifier:
    """
    Classifies images into scene categories using color and texture analysis.

    Categories:
      - indoor: artificial lighting, walls, furniture
      - outdoor_urban: buildings, roads, concrete
      - outdoor_natural: vegetation, sky, water
      - sky_dominant: mostly sky visible
      - water_dominant: mostly water visible
    """

    def classify(self, image: np.ndarray) -> SceneClassification:
        """
        Classify an image into a scene category.

        Args:
            image: H x W x 3 RGB image (uint8)

        Returns:
            SceneClassification with type, confidence, and features
        """
        if image is None or len(image.shape) != 3:
            return SceneClassification("unknown", 0.0, {})

        hsv = rgb_to_hsv(image)
        texture = compute_texture_features(image)

        # Compute color region percentages
        regions = self._compute_color_regions(hsv)

        # Classify based on dominant features
        scene_type, confidence = self._classify_from_features(regions, texture)

        return SceneClassification(
            scene_type=scene_type,
            confidence=confidence,
            features={**regions, **texture},
        )

    def _compute_color_regions(self, hsv: np.ndarray) -> Dict[str, float]:
        """Compute percentage of image in each color region."""
        h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
        total_pixels = h.shape[0] * h.shape[1]

        regions = {}
        for name, ranges in COLOR_RANGES.items():
            mask = (
                (h >= ranges["h_min"]) & (h <= ranges["h_max"]) &
                (s >= ranges["s_min"]) & (s <= ranges["s_max"]) &
                (v >= ranges["v_min"]) & (v <= ranges["v_max"])
            )
            regions[name] = float(mask.sum() / total_pixels)

        return regions

    def _classify_from_features(
        self, regions: Dict[str, float], texture: Dict[str, float]
    ) -> Tuple[str, float]:
        """Classify scene from extracted features."""
        sky_pct = regions.get("sky_blue", 0)
        grass_pct = regions.get("grass_green", 0)
        water_pct = regions.get("water_blue", 0)
        concrete_pct = regions.get("concrete_gray", 0)
        earth_pct = regions.get("earth_brown", 0)
        brightness = texture.get("brightness", 0.5)
        edge_density = texture.get("edge_density", 0)

        # Sky dominant
        if sky_pct > 0.4:
            return "sky_dominant", min(0.9, 0.5 + sky_pct)

        # Water dominant
        if water_pct > 0.3:
            return "water_dominant", min(0.9, 0.5 + water_pct)

        # Outdoor natural
        natural_score = grass_pct + earth_pct
        if natural_score > 0.3 and concrete_pct < 0.2:
            return "outdoor_natural", min(0.85, 0.4 + natural_score)

        # Outdoor urban
        if concrete_pct > 0.2 and edge_density > 0.05:
            return "outdoor_urban", min(0.8, 0.3 + concrete_pct)

        # Indoor (default for low natural, low sky)
        if natural_score < 0.1 and sky_pct < 0.1:
            return "indoor", min(0.7, 0.4 + (1 - natural_score) * 0.3)

        # Default
        return "outdoor_natural", 0.4


# Module-level singleton
scene_classifier = SceneClassifier()
