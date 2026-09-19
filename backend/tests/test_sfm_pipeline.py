"""Tests for wired SfM pipeline — video_processor with real components."""

import pytest
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.services.video_processor import VideoProcessor
from app.services.point_cloud_generator import PointCloud
from app.services.mesh_generator import Mesh, mesh_from_point_cloud
from app.services.mesh_optimizer import optimize_mesh_for_rendering
from app.services.glTF_export import export_glb


class TestPointCloudIntegration:
    def test_point_cloud_empty(self):
        """PointCloud.empty() works."""
        pc = PointCloud.empty()
        assert pc.num_points == 0

    def test_point_cloud_filter(self):
        """PointCloud filtering works."""
        points = np.array([[1, 2, 0.5], [3, 4, 50], [5, 6, 200]])
        colors = np.array([[255, 0, 0], [0, 255, 0], [0, 0, 255]])
        frame_indices = np.array([0, 1, 2])
        pc = PointCloud(points=points, colors=colors, frame_indices=frame_indices, num_points=3)
        filtered = pc.filter_by_depth(0.1, 100)
        assert filtered.num_points == 2


class TestMeshIntegration:
    def test_mesh_from_point_cloud_delaunay(self):
        """Can create mesh from point cloud using Delaunay."""
        points = np.random.rand(100, 3).astype(np.float64)
        points[:, 2] = np.abs(points[:, 2]) * 10 + 1  # Ensure positive z
        colors = np.random.randint(0, 255, (100, 3), dtype=np.uint8)
        mesh = mesh_from_point_cloud(points, colors, method="delaunay")
        assert mesh.num_vertices > 0

    def test_mesh_from_point_cloud_convex_hull(self):
        """Can create mesh from point cloud using convex hull."""
        points = np.random.rand(50, 3).astype(np.float64)
        colors = np.random.randint(0, 255, (50, 3), dtype=np.uint8)
        mesh = mesh_from_point_cloud(points, colors, method="convex_hull")
        assert mesh.num_vertices > 0
        assert mesh.num_faces > 0


class TestMeshOptimization:
    def test_optimize_mesh(self):
        """Can optimize mesh for rendering."""
        vertices = np.random.rand(200, 3).astype(np.float64)
        from app.services.mesh_generator import Triangle
        faces = [Triangle(i, i+1, i+2) for i in range(0, 198, 3)]
        mesh = Mesh(vertices=vertices, faces=faces)
        optimized, stats = optimize_mesh_for_rendering(mesh, max_faces=100)
        assert optimized.num_faces <= mesh.num_faces
        assert "actions" in stats


class TestGLBExport:
    def test_export_glb(self, tmp_path):
        """Can export mesh to GLB."""
        vertices = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=np.float64)
        from app.services.mesh_generator import Triangle
        faces = [Triangle(0, 1, 2)]
        mesh = Mesh(
            vertices=vertices,
            faces=faces,
            vertex_colors=np.array([[255, 0, 0], [0, 255, 0], [0, 0, 255]], dtype=np.uint8),
        )
        output_path = tmp_path / "test.glb"
        metadata = export_glb(mesh, output_path, asset_id="test_asset")
        assert output_path.exists()
        assert metadata.vertex_count == 3
        assert metadata.face_count == 1
        assert metadata.file_size_bytes > 0


class TestVideoProcessorInit:
    def test_init(self, tmp_path):
        """Can initialize video processor."""
        proc = VideoProcessor(tmp_path / "uploads")
        assert proc.upload_dir.exists()

    def test_singleton(self):
        """Singleton processor exists."""
        from app.services.video_processor import get_processor
        proc = get_processor()
        assert proc is not None
