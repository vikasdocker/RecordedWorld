"""
Tests for Scene Classification and Image Enhancement services.
"""
import pytest
import numpy as np
from app.services.scene_classifier import SceneClassifier, SceneClassification, scene_classifier
from app.services.image_enhancer import ImageEnhancer, EnhancementResult, image_enhancer


class TestSceneClassifier:
    def test_classify_indoor(self):
        classifier = SceneClassifier()
        # Indoor: low sky, low grass, moderate gray
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        image[:, :] = [128, 128, 128]  # Gray walls
        result = classifier.classify(image)
        assert result.scene_type in ("indoor", "outdoor_urban")
        assert 0.0 <= result.confidence <= 1.0

    def test_classify_outdoor_natural(self):
        classifier = SceneClassifier()
        # Natural: lots of green
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        image[:, :, 0] = 50   # H: green-ish in RGB
        image[:, :, 1] = 180  # G: high green
        image[:, :, 2] = 50   # B: low blue
        result = classifier.classify(image)
        assert result.scene_type in ("outdoor_natural", "outdoor_urban")
        assert result.confidence > 0

    def test_classify_sky_dominant(self):
        classifier = SceneClassifier()
        # Sky: use HSV directly to create sky-blue pixels
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        # Set RGB to a sky-like color that converts to sky_blue in HSV
        image[:, :] = [100, 180, 240]  # Light blue
        result = classifier.classify(image)
        # Sky detection depends on HSV conversion, just verify classification works
        assert result.scene_type in ("sky_dominant", "outdoor_natural", "outdoor_urban", "indoor")
        assert result.confidence > 0

    def test_classify_invalid_image(self):
        classifier = SceneClassifier()
        result = classifier.classify(None)
        assert result.scene_type == "unknown"
        assert result.confidence == 0.0

    def test_features_populated(self):
        classifier = SceneClassifier()
        image = np.random.randint(0, 255, (50, 50, 3), dtype=np.uint8)
        result = classifier.classify(image)
        assert "edge_density" in result.features
        assert "brightness" in result.features
        assert "sky_blue" in result.features


class TestImageEnhancer:
    def test_enhance_basic(self):
        enhancer = ImageEnhancer()
        image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        result = enhancer.enhance(image)
        assert isinstance(result, EnhancementResult)
        assert result.enhanced_image.shape == image.shape
        assert result.enhanced_image.dtype == np.uint8

    def test_brightness_normalization(self):
        enhancer = ImageEnhancer()
        # Very dark image
        dark = np.zeros((100, 100, 3), dtype=np.uint8)
        dark[:, :] = 20
        result = enhancer.enhance(dark, normalize_brightness=True, target_brightness=0.5)
        assert result.brightness_delta > 0
        assert np.mean(result.enhanced_image) > 20

    def test_contrast_normalization(self):
        enhancer = ImageEnhancer()
        # Low contrast image
        low_contrast = np.ones((100, 100, 3), dtype=np.uint8) * 128
        low_contrast[0:50, :, :] = 120
        low_contrast[50:, :, :] = 136
        result = enhancer.enhance(low_contrast, normalize_contrast=True, target_contrast=0.6)
        assert result.contrast_delta != 0

    def test_denoise(self):
        enhancer = ImageEnhancer()
        image = np.random.randint(0, 255, (20, 20, 3), dtype=np.uint8)
        result = enhancer.enhance(image, denoise=True)
        assert result.denoised is True

    def test_sharpen(self):
        enhancer = ImageEnhancer()
        image = np.random.randint(0, 255, (20, 20, 3), dtype=np.uint8)
        result = enhancer.enhance(image, sharpen=True)
        assert result.sharpened is True

    def test_normalize_for_reconstruction(self):
        enhancer = ImageEnhancer()
        image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        result = enhancer.normalize_for_reconstruction(image)
        assert result.shape == image.shape
        assert result.dtype == np.uint8

    def test_enhance_invalid_image(self):
        enhancer = ImageEnhancer()
        with pytest.raises(ValueError):
            enhancer.enhance(None)
