"""
Tests for Semantic Segmentation and Object Detection services.
"""
import pytest
import numpy as np
from app.services.semantic_segmentation import SemanticSegmenter, SegmentationResult, semantic_segmenter
from app.services.object_detection import ObjectDetector, DetectedObject, BoundingBox, object_detector


class TestSemanticSegmenter:
    def test_segment_basic(self):
        segmenter = SemanticSegmenter()
        image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        result = segmenter.segment(image)
        assert isinstance(result, SegmentationResult)
        assert result.segmentation_map.shape == (100, 100)
        assert result.confidence_map.shape == (100, 100)

    def test_segment_sky(self):
        segmenter = SemanticSegmenter()
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        # Blue sky-like pixels
        image[:, :] = [120, 100, 200]
        result = segmenter.segment(image)
        assert "sky" in result.class_percentages

    def test_segment_vegetation(self):
        segmenter = SemanticSegmenter()
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        # Green vegetation
        image[:, :] = [50, 180, 50]
        result = segmenter.segment(image)
        assert "vegetation" in result.class_percentages

    def test_segment_invalid_image(self):
        segmenter = SemanticSegmenter()
        result = segmenter.segment(None)
        assert result.segmentation_map.shape == (100, 100)

    def test_class_labels_populated(self):
        segmenter = SemanticSegmenter()
        image = np.random.randint(0, 255, (50, 50, 3), dtype=np.uint8)
        result = segmenter.segment(image)
        assert 0 in result.class_labels
        assert result.class_labels[0] == "unknown"

    def test_percentages_sum_to_one(self):
        segmenter = SemanticSegmenter()
        image = np.random.randint(0, 255, (80, 80, 3), dtype=np.uint8)
        result = segmenter.segment(image)
        total = sum(result.class_percentages.values())
        assert abs(total - 1.0) < 0.01


class TestObjectDetector:
    def test_detect_basic(self):
        detector = ObjectDetector()
        image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        objects = detector.detect(image)
        assert isinstance(objects, list)

    def test_detect_returns_list(self):
        detector = ObjectDetector()
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        # Add some edges
        image[30:70, 30:70, :] = 255
        objects = detector.detect(image, min_area=500)
        assert isinstance(objects, list)

    def test_detect_invalid_image(self):
        detector = ObjectDetector()
        objects = detector.detect(None)
        assert objects == []

    def test_bounding_box_properties(self):
        bbox = BoundingBox(x=10, y=20, width=30, height=40, area=1200)
        assert bbox.x == 10
        assert bbox.area == 1200

    def test_detected_object_properties(self):
        obj = DetectedObject(
            label="vehicle",
            confidence=0.8,
            bbox=BoundingBox(10, 20, 30, 40, 1200),
            center_x=25,
            center_y=40,
        )
        assert obj.label == "vehicle"
        assert obj.confidence == 0.8

    def test_detect_by_color(self):
        detector = ObjectDetector()
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        image[20:40, 20:40, :] = [255, 0, 0]  # Red region
        objects = detector.detect_by_color(
            image,
            {"h_min": 0, "h_max": 10, "s_min": 100, "s_max": 255, "v_min": 100, "v_max": 255},
            min_area=100,
        )
        assert isinstance(objects, list)

    def test_detect_max_objects(self):
        detector = ObjectDetector()
        image = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)
        objects = detector.detect(image, max_objects=5)
        assert len(objects) <= 5
