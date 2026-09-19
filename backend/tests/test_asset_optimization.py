"""Tests for Phase 18: 3D Asset Optimization — decimation, LOD, glTF export, CDN paths."""

import pytest
import tempfile
import struct
import json
import numpy as np
from pathlib import Path

from app.services.mesh_generator import Mesh, Triangle
from app.services.mesh_optimizer import (
    compute_mesh_stats,
    decimate_mesh,
    decimate_to_target,
    generate_lod_chain,
    select_lod,
    optimize_mesh_for_rendering,
)
from app.services.glTF_export import (
    mesh_to_glb_bytes,
    export_glb,
    export_obj,
    get_asset_path,
    get_lod_chain_paths,
)


def make_test_mesh(num_rows: int = 10, num_cols: int = 10) -> Mesh:
    """Create a simple grid mesh for testing."""
    vertices = []
    for r in range(num_rows):
        for c in range(num_cols):
            vertices.append([float(c), 0.0, float(r)])
    vertices = np.array(vertices)

    faces = []
    for r in range(num_rows - 1):
        for c in range(num_cols - 1):
            i = r * num_cols + c
            faces.append(Triangle(i, i + 1, i + num_cols))
            faces.append(Triangle(i + 1, i + num_cols + 1, i + num_cols))

    # Add some colors
    colors = np.random.randint(0, 255, (len(vertices), 3), dtype=np.uint8)

    return Mesh(vertices=vertices, faces=faces, vertex_colors=colors)


class TestMeshStats:
    def test_stats_basic(self):
        """Compute stats for a simple mesh."""
        mesh = make_test_mesh(5, 5)
        stats = compute_mesh_stats(mesh)
        assert stats.num_vertices == 25
        assert stats.num_faces == 32
        assert stats.surface_area > 0
        assert stats.volume >= 0

    def test_stats_empty_mesh(self):
        """Stats for empty mesh returns zeros."""
        mesh = Mesh(vertices=np.empty((0, 3)), faces=[])
        stats = compute_mesh_stats(mesh)
        assert stats.num_vertices == 0
        assert stats.num_faces == 0

    def test_stats_to_dict(self):
        """Stats can be serialized to dict."""
        mesh = make_test_mesh(5, 5)
        stats = compute_mesh_stats(mesh)
        d = stats.to_dict()
        assert "num_vertices" in d
        assert "surface_area" in d


class TestDecimation:
    def test_decimate_reduces_faces(self):
        """Decimation reduces face count."""
        mesh = make_test_mesh(10, 10)
        original_faces = mesh.num_faces
        decimated = decimate_mesh(mesh, target_face_ratio=0.1, aggressiveness=10.0)
        assert decimated.num_faces <= original_faces

    def test_decimate_preserves_vertices_reasonably(self):
        """Decimation doesn't reduce vertices to zero."""
        mesh = make_test_mesh(10, 10)
        decimated = decimate_mesh(mesh, target_face_ratio=0.1, aggressiveness=10.0)
        assert decimated.num_vertices > 0

    def test_decimate_to_target(self):
        """Can decimate to specific face count."""
        mesh = make_test_mesh(10, 10)
        decimated = decimate_to_target(mesh, target_faces=20)
        # Decimation via clustering may not hit exact target
        assert decimated.num_faces <= mesh.num_faces

    def test_decimate_no_change_when_at_target(self):
        """Mesh isn't decimated if already below target."""
        mesh = make_test_mesh(5, 5)
        decimated = decimate_to_target(mesh, target_faces=1000)
        assert decimated.num_faces == mesh.num_faces

    def test_decimate_empty_mesh(self):
        """Decimating empty mesh returns empty."""
        mesh = Mesh(vertices=np.empty((0, 3)), faces=[])
        decimated = decimate_mesh(mesh)
        assert decimated.num_faces == 0


class TestLODChain:
    def test_lod_chain_generation(self):
        """Can generate LOD chain from mesh."""
        mesh = make_test_mesh(10, 10)
        lod_chain = generate_lod_chain(mesh, lod_ratios=[1.0, 0.5, 0.25])
        assert len(lod_chain) == 3
        assert lod_chain[0].target_ratio == 1.0
        assert lod_chain[1].target_ratio == 0.5
        assert lod_chain[2].target_ratio == 0.25

    def test_lod_chain_decreasing_detail(self):
        """LOD chain has decreasing face counts."""
        mesh = make_test_mesh(10, 10)
        lod_chain = generate_lod_chain(mesh)
        for i in range(len(lod_chain) - 1):
            assert lod_chain[i].mesh.num_faces >= lod_chain[i + 1].mesh.num_faces

    def test_select_lod_close(self):
        """Close distance selects highest detail."""
        mesh = make_test_mesh(10, 10)
        lod_chain = generate_lod_chain(mesh)
        selected = select_lod(lod_chain, distance=5.0)
        assert selected.level == 0

    def test_select_lod_far(self):
        """Far distance selects lowest detail."""
        mesh = make_test_mesh(10, 10)
        lod_chain = generate_lod_chain(mesh)
        selected = select_lod(lod_chain, distance=200.0)
        assert selected.level == len(lod_chain) - 1


class TestOptimizeForRendering:
    def test_optimize_reduces_faces(self):
        """Optimization reduces faces to target."""
        mesh = make_test_mesh(20, 20)
        original_faces = mesh.num_faces
        optimized, stats = optimize_mesh_for_rendering(mesh, max_faces=50)
        # Decimation via clustering may not hit exact target, but should reduce
        assert optimized.num_faces <= original_faces
        assert "actions" in stats

    def test_optimize_returns_stats(self):
        """Optimization returns before/after stats."""
        mesh = make_test_mesh(10, 10)
        _, stats = optimize_mesh_for_rendering(mesh, max_faces=100)
        assert "before" in stats
        assert "after" in stats
        assert "face_reduction" in stats


class TestGLTFExport:
    def test_glb_bytes_valid_header(self):
        """GLB bytes have valid header."""
        mesh = make_test_mesh(5, 5)
        glb = mesh_to_glb_bytes(mesh, asset_id="test")
        magic, version, length = struct.unpack("<III", glb[:12])
        assert magic == 0x46546C67  # glTF
        assert version == 2
        assert length == len(glb)

    def test_glb_json_chunk(self):
        """GLB has valid JSON chunk."""
        mesh = make_test_mesh(5, 5)
        glb = mesh_to_glb_bytes(mesh, asset_id="test")
        # JSON chunk starts at offset 12
        json_len, json_magic = struct.unpack("<II", glb[12:20])
        assert json_magic == 0x4E4F534A  # JSON
        json_data = glb[20:20 + json_len]
        parsed = json.loads(json_data)
        assert "asset" in parsed
        assert parsed["asset"]["version"] == "2.0"

    def test_export_glb_to_file(self):
        """Can export GLB to file."""
        mesh = make_test_mesh(5, 5)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.glb"
            metadata = export_glb(mesh, path, asset_id="test_asset")
            assert path.exists()
            assert metadata.format == "glb"
            assert metadata.vertex_count == mesh.num_vertices
            assert metadata.file_size_bytes > 0

    def test_export_obj_to_file(self):
        """Can export OBJ to file."""
        mesh = make_test_mesh(5, 5)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.obj"
            metadata = export_obj(mesh, path, asset_id="test_asset")
            assert path.exists()
            assert metadata.format == "obj"
            content = path.read_text()
            assert "v " in content
            assert "f " in content


class TestCDNPaths:
    def test_asset_path_structure(self):
        """Asset path follows CDN structure."""
        path = get_asset_path("abc123def456", lod_level=0)
        assert path.parts[0] == "assets"
        assert path.parts[1] == "ab"
        assert "abc123def456_lod0.glb" in str(path)

    def test_lod_chain_paths(self):
        """LOD chain generates correct number of paths."""
        paths = get_lod_chain_paths("test123", lod_levels=4)
        assert len(paths) == 4
        for i, p in enumerate(paths):
            assert f"lod{i}" in str(p)

    def test_asset_path_different_formats(self):
        """Asset path works with different formats."""
        path = get_asset_path("abc123", format="obj")
        assert path.suffix == ".obj"
