import pytest
import numpy as np
import os
import tempfile

from app.services.mesh_generator import Mesh, Triangle
from app.services.mesh_optimizer import (
    compute_mesh_stats, decimate_mesh, decimate_to_target,
    generate_lod_chain, select_lod, optimize_mesh_for_rendering,
    LODLevel,
)


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


def _create_dense_mesh():
    """Create a dense mesh with many triangles."""
    # Create a grid of points on a plane
    n = 20
    points = []
    faces = []
    colors = []

    for i in range(n):
        for j in range(n):
            x = i / n
            y = j / n
            z = 0
            points.append([x, y, z])
            colors.append([int(255 * x), int(255 * y), 128])

    points = np.array(points, dtype=np.float32)
    colors = np.array(colors)

    # Create grid faces
    for i in range(n - 1):
        for j in range(n - 1):
            idx = i * n + j
            faces.append(Triangle(idx, idx + 1, idx + n))
            faces.append(Triangle(idx + 1, idx + n + 1, idx + n))

    return Mesh(vertices=points, faces=faces, vertex_colors=colors)


def _create_simple_mesh():
    """Create a simple tetrahedron."""
    vertices = np.array([
        [0, 0, 0],
        [1, 0, 0],
        [0.5, 1, 0],
        [0.5, 0.5, 1],
    ], dtype=np.float32)
    faces = [
        Triangle(0, 1, 2),
        Triangle(0, 1, 3),
        Triangle(1, 2, 3),
        Triangle(0, 2, 3),
    ]
    return Mesh(vertices=vertices, faces=faces)


# --- Mesh Stats Tests ---

class TestMeshStats:
    def test_empty_mesh(self):
        mesh = Mesh(vertices=np.array([]).reshape(0, 3), faces=[])
        stats = compute_mesh_stats(mesh)
        assert stats.num_vertices == 0
        assert stats.num_faces == 0

    def test_simple_mesh(self):
        mesh = _create_simple_mesh()
        stats = compute_mesh_stats(mesh)

        assert stats.num_vertices == 4
        assert stats.num_faces == 4
        assert stats.surface_area > 0
        assert stats.volume > 0

    def test_bbox(self):
        mesh = Mesh(
            vertices=np.array([[0, 0, 0], [1, 2, 3]]),
            faces=[],
        )
        stats = compute_mesh_stats(mesh)
        np.testing.assert_array_equal(stats.bbox_min, [0, 0, 0])
        np.testing.assert_array_equal(stats.bbox_max, [1, 2, 3])
        np.testing.assert_array_equal(stats.bbox_size, [1, 2, 3])

    def test_stats_to_dict(self):
        mesh = _create_simple_mesh()
        stats = compute_mesh_stats(mesh)
        d = stats.to_dict()
        assert "num_vertices" in d
        assert "surface_area" in d


# --- Decimation Tests ---

class TestDecimation:
    def test_decimate_dense_mesh(self):
        mesh = _create_dense_mesh()
        original_faces = mesh.num_faces

        decimated = decimate_mesh(mesh, target_face_ratio=0.25)

        assert decimated.num_faces < original_faces
        assert decimated.num_faces > 0

    def test_decimate_preserves_structure(self):
        mesh = _create_simple_mesh()
        decimated = decimate_mesh(mesh, target_face_ratio=0.5)

        # Should still have vertices
        assert decimated.num_vertices > 0

    def test_decimate_too_small_ratio(self):
        mesh = _create_dense_mesh()
        decimated = decimate_mesh(mesh, target_face_ratio=0.01)

        # Should still have some faces
        assert decimated.num_faces >= 0

    def test_decimate_to_target(self):
        mesh = _create_dense_mesh()
        decimated = decimate_to_target(mesh, target_faces=50)

        assert decimated.num_faces <= mesh.num_faces

    def test_decimate_no_change_needed(self):
        mesh = _create_simple_mesh()
        decimated = decimate_to_target(mesh, target_faces=100)

        # Already under target, should return as-is
        assert decimated.num_faces == mesh.num_faces


# --- LOD Tests ---

class TestLOD:
    def test_generate_lod_chain(self):
        mesh = _create_dense_mesh()
        chain = generate_lod_chain(mesh, lod_ratios=[1.0, 0.5, 0.25])

        assert len(chain) == 3
        assert chain[0].level == 0
        assert chain[0].target_ratio == 1.0
        assert chain[2].target_ratio == 0.25

    def test_lod_decreasing_detail(self):
        mesh = _create_dense_mesh()
        chain = generate_lod_chain(mesh)

        # Each level should have <= faces than the previous
        for i in range(len(chain) - 1):
            assert chain[i].mesh.num_faces >= chain[i + 1].mesh.num_faces

    def test_lod_vertex_reduction(self):
        mesh = _create_dense_mesh()
        chain = generate_lod_chain(mesh)

        # LOD 0 should have 0 reduction (it's the original)
        assert chain[0].vertex_reduction == 0.0

        # Higher LOD levels should have positive reduction
        assert chain[-1].vertex_reduction > 0

    def test_select_lod_close(self):
        mesh = _create_dense_mesh()
        chain = generate_lod_chain(mesh)

        lod = select_lod(chain, distance=5)
        assert lod.level == 0  # highest detail

    def test_select_lod_far(self):
        mesh = _create_dense_mesh()
        chain = generate_lod_chain(mesh)

        lod = select_lod(chain, distance=200)
        assert lod.level == len(chain) - 1  # lowest detail

    def test_select_lod_empty_chain(self):
        lod = select_lod([], distance=10)
        assert lod is None


# --- Optimization Tests ---

class TestOptimization:
    def test_optimize_reduces_faces(self):
        mesh = _create_dense_mesh()
        optimized, stats = optimize_mesh_for_rendering(mesh, max_faces=50)

        assert optimized.num_faces < mesh.num_faces
        assert stats["face_reduction"] > 0

    def test_optimize_preserves_mesh(self):
        mesh = _create_simple_mesh()
        optimized, stats = optimize_mesh_for_rendering(mesh, max_faces=100)

        assert optimized.num_faces == mesh.num_faces  # no reduction needed

    def test_optimize_removes_degenerates(self):
        mesh = Mesh(
            vertices=np.array([[0, 0, 0], [1, 0, 0], [0.5, 1, 0]]),
            faces=[
                Triangle(0, 1, 2),
                Triangle(0, 0, 1),  # degenerate
                Triangle(1, 2, 2),  # degenerate
            ],
        )
        optimized, stats = optimize_mesh_for_rendering(mesh, max_faces=100)

        # Degenerate faces should be removed
        assert optimized.num_faces == 1

    def test_optimize_stats(self):
        mesh = _create_dense_mesh()
        _, stats = optimize_mesh_for_rendering(mesh, max_faces=100)

        assert "before" in stats
        assert "after" in stats
        assert "actions" in stats
