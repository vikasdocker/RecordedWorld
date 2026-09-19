"""
Tests for Missing-Area Reconstruction service.
"""
import pytest
import numpy as np
from app.services.missing_area_reconstruction import (
    MissingAreaReconstructor, HoleInfo, ReconstructionResult,
    missing_area_reconstructor
)


class TestMissingAreaReconstructor:
    def test_detect_holes_empty_mesh(self):
        reconstructor = MissingAreaReconstructor()
        holes = reconstructor.detect_holes(np.array([]), np.array([]))
        assert holes == []

    def test_detect_holes_no_holes(self):
        reconstructor = MissingAreaReconstructor()
        # Simple tetrahedron - no holes
        vertices = np.array([
            [0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]
        ])
        faces = np.array([
            [0, 1, 2], [0, 1, 3], [0, 2, 3], [1, 2, 3]
        ])
        holes = reconstructor.detect_holes(vertices, faces)
        assert len(holes) == 0

    def test_detect_holes_with_boundary(self):
        reconstructor = MissingAreaReconstructor()
        # Open mesh (missing one face)
        vertices = np.array([
            [0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]
        ])
        faces = np.array([
            [0, 1, 2],  # Only 3 of 4 faces
        ])
        holes = reconstructor.detect_holes(vertices, faces)
        assert len(holes) >= 1

    def test_fill_holes_boundary(self):
        reconstructor = MissingAreaReconstructor()
        # Open mesh with boundary edges (hole)
        vertices = np.array([
            [0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]
        ])
        faces = np.array([
            [0, 1, 2],  # Only 3 of 4 faces = open boundary
        ])
        result = reconstructor.fill_holes_boundary(vertices, faces, max_hole_area=10.0)
        assert isinstance(result, ReconstructionResult)
        # Should find and fill the hole
        assert result.holes_filled >= 1
        assert result.fill_method == "boundary_interpolation"

    def test_fill_holes_nearest_surface(self):
        reconstructor = MissingAreaReconstructor()
        vertices = np.array([
            [0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]
        ])
        faces = np.array([
            [0, 1, 2],  # Only 3 of 4 faces = open boundary
        ])
        result = reconstructor.fill_holes_nearest_surface(vertices, faces, max_hole_area=10.0)
        assert isinstance(result, ReconstructionResult)
        assert result.holes_filled >= 1
        assert result.fill_method == "nearest_surface"

    def test_fill_holes_none_needed(self):
        reconstructor = MissingAreaReconstructor()
        vertices = np.array([
            [0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]
        ])
        faces = np.array([
            [0, 1, 2], [0, 1, 3], [0, 2, 3], [1, 2, 3]
        ])
        result = reconstructor.fill_holes_boundary(vertices, faces)
        assert result.holes_filled == 0

    def test_invalid_inputs(self):
        reconstructor = MissingAreaReconstructor()
        result = reconstructor.fill_holes_boundary(None, None)
        assert result.holes_filled == 0

    def test_hole_info_properties(self):
        hole = HoleInfo(
            center=np.array([1.0, 2.0, 3.0]),
            radius=0.5,
            area=0.25,
            boundary_points=np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0]]),
        )
        assert hole.radius == 0.5
        assert hole.area == 0.25

    def test_reconstruction_result_properties(self):
        result = ReconstructionResult(
            filled_mesh=np.array([[0, 0, 0]]),
            filled_faces=np.array([[0, 0, 0]]),
            holes_filled=3,
            fill_method="boundary_interpolation",
            confidence=0.8,
        )
        assert result.holes_filled == 3
        assert result.confidence == 0.8
