"""
Tests for Phase 18 — Blender Backend, Texture Compression, Atlas, Meshlets

Unit tests mock the Blender subprocess. Integration tests only run when
Blender is actually installed on the system.
"""

import pytest
import os
import json
import subprocess as sp
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock

from app.services.blender_backend import (
    BlenderBackend, BlenderResult, BlenderInfo,
    _WINDOWS_PATHS, _LINUX_PATHS, _MACOS_PATHS,
)
from app.services.blender_operations import (
    BlenderOperations, TextureCompressionResult, AtlasResult, MeshletResult,
)
from app.services.mesh_optimizer import (
    decimate_mesh, generate_lod_chain, compute_mesh_stats,
)
from app.services.glTF_export import mesh_to_glb_bytes, export_glb, get_asset_path
from app.services.mesh_generator import Mesh, Triangle
import numpy as np


# =========================================================================
# Helpers
# =========================================================================

def make_test_mesh(rows=5, cols=5) -> Mesh:
    vertices = []
    for r in range(rows):
        for c in range(cols):
            vertices.append([float(c), 0.0, float(r)])
    vertices = np.array(vertices)
    faces = []
    for r in range(rows - 1):
        for c in range(cols - 1):
            i = r * cols + c
            faces.append(Triangle(i, i + 1, i + cols))
            faces.append(Triangle(i + 1, i + cols + 1, i + cols))
    return Mesh(vertices=vertices, faces=faces)


# =========================================================================
# BlenderBackend Detection Tests
# =========================================================================

class TestBlenderBackendDetection:
    def test_singleton(self):
        b1 = BlenderBackend()
        b2 = BlenderBackend()
        assert b1 is b2

    def test_detect_from_env_var(self):
        with patch.dict(os.environ, {"BLENDER_PATH": "/mock/blender"}):
            with patch("app.services.blender_backend.BlenderBackend._validate_blender_path", return_value=True):
                with patch("app.services.blender_backend.BlenderBackend._probe_blender") as mock_probe:
                    mock_probe.return_value = BlenderInfo(path="/mock/blender", version="4.2.0")
                    backend = BlenderBackend()
                    backend._detection_done = False
                    backend._detect_blender()
                    assert backend.is_available()
                    assert backend.get_path() == "/mock/blender"

    def test_detect_from_env_var_invalid(self):
        with patch.dict(os.environ, {"BLENDER_PATH": "/nonexistent/blender"}):
            with patch("app.services.blender_backend.BlenderBackend._validate_blender_path", return_value=False):
                backend = BlenderBackend()
                backend._detection_done = False
                backend._detect_blender()
                assert not backend.is_available()

    def test_detect_from_system_paths(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("BLENDER_PATH", None)
            with patch("app.services.blender_backend.shutil.which", return_value="/usr/bin/blender"):
                with patch("app.services.blender_backend.BlenderBackend._validate_blender_path", return_value=True):
                    with patch("app.services.blender_backend.BlenderBackend._probe_blender") as mock_probe:
                        mock_probe.return_value = BlenderInfo(path="/usr/bin/blender", version="3.6.0")
                        backend = BlenderBackend()
                        backend._detection_done = False
                        backend._detect_blender()
                        assert backend.is_available()

    def test_not_found(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("BLENDER_PATH", None)
            with patch("app.services.blender_backend.shutil.which", return_value=None):
                with patch("app.services.blender_backend.BlenderBackend._validate_blender_path", return_value=False):
                    backend = BlenderBackend()
                    backend._detection_done = False
                    backend._detect_blender()
                    assert not backend.is_available()

    def test_validate_path_exists(self):
        with tempfile.NamedTemporaryFile(suffix=".exe" if os.name == "nt" else "") as f:
            assert BlenderBackend._validate_blender_path(BlenderBackend, f.name)

    def test_validate_path_not_exists(self):
        assert not BlenderBackend._validate_blender_path(BlenderBackend, "/nonexistent/path")

    def test_get_info_when_not_available(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("BLENDER_PATH", None)
            with patch("app.services.blender_backend.shutil.which", return_value=None):
                with patch("app.services.blender_backend.BlenderBackend._validate_blender_path", return_value=False):
                    backend = BlenderBackend()
                    backend._detection_done = False
                    backend._detect_blender()
                    info = backend.get_info()
                    assert not info.available


# =========================================================================
# BlenderBackend Subprocess Tests
# =========================================================================

class TestBlenderBackendSubprocess:
    @patch("app.services.blender_backend.blender_backend._blender_path", "/mock/blender")
    @patch("app.services.blender_backend.blender_backend._detection_done", True)
    def test_run_script_success(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Blender 4.2.0\nRESULT:{\"success\": true}"
        mock_result.stderr = ""

        with patch("app.services.blender_backend.subprocess.run", return_value=mock_result):
            backend = BlenderBackend()
            backend._blender_path = "/mock/blender"
            result = backend.run_script("print('hello')", timeout=30)
            assert result.success
            assert result.return_code == 0

    @patch("app.services.blender_backend.blender_backend._blender_path", None)
    def test_run_script_not_available(self):
        backend = BlenderBackend()
        backend._blender_path = None
        result = backend.run_script("print('hello')")
        assert not result.success
        assert result.return_code == -1
        assert "not available" in result.stderr

    @patch("app.services.blender_backend.blender_backend._blender_path", "/mock/blender")
    def test_run_script_timeout(self):
        with patch("app.services.blender_backend.subprocess.run", side_effect=sp.TimeoutExpired(cmd="blender", timeout=30)):
            backend = BlenderBackend()
            backend._blender_path = "/mock/blender"
            result = backend.run_script("import time; time.sleep(999)", timeout=30)
            assert not result.success
            assert result.return_code == -2
            assert "Timeout" in result.stderr

    @patch("app.services.blender_backend.blender_backend._blender_path", "/mock/blender")
    def test_run_script_exception(self):
        with patch("app.services.blender_backend.subprocess.run", side_effect=OSError("permission denied")):
            backend = BlenderBackend()
            backend._blender_path = "/mock/blender"
            result = backend.run_script("print('test')")
            assert not result.success
            assert result.return_code == -3

    def test_result_to_dict(self):
        r = BlenderResult(
            success=True, return_code=0, stdout="ok", stderr="",
            execution_time_ms=150, output_files=["/tmp/out.glb"],
        )
        d = r.to_dict()
        assert d["success"] is True
        assert d["execution_time_ms"] == 150


# =========================================================================
# BlenderOperations — Texture Compression Tests
# =========================================================================

class TestTextureCompressionFallback:
    def test_compress_input_not_found(self):
        ops = BlenderOperations()
        result = ops.compress_texture("/nonexistent/img.png", "/tmp/out.png")
        assert not result.success
        assert "not found" in result.error

    def test_compress_fallback_copy(self):
        pytest.importorskip("PIL")
        from PIL import Image

        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "input.png"
            dst = Path(tmpdir) / "output.png"
            # Create a valid PNG that PIL can open
            img = Image.new("RGB", (8, 8), (128, 128, 128))
            img.save(str(src))

            ops = BlenderOperations()
            # Force fallback by making blender unavailable
            with patch.object(ops, "_blender_available", False):
                result = ops.compress_texture(str(src), str(dst))
                assert result.success
                assert result.backend == "fallback_pil"
                assert dst.exists()

    def test_compress_fallback_with_pil(self):
        pytest.importorskip("PIL")
        with tempfile.TemporaryDirectory() as tmpdir:
            from PIL import Image
            src = Path(tmpdir) / "input.png"
            dst = Path(tmpdir) / "output.jpg"
            img = Image.new("RGB", (100, 100), (255, 0, 0))
            img.save(str(src))

            ops = BlenderOperations()
            with patch.object(ops, "_blender_available", False):
                result = ops.compress_texture(str(src), str(dst), quality="high")
                assert result.success
                assert result.backend == "fallback_pil"
                assert dst.exists()
                assert dst.stat().st_size > 0

    def test_compress_blender_calls_subprocess(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "input.png"
            dst = Path(tmpdir) / "output.png"
            src.write_bytes(b"\x89PNG fake")

            mock_blender_result = BlenderResult(
                success=True, return_code=0, stdout="", stderr="",
                execution_time_ms=100, output_files=[str(dst)],
            )
            # Create the output file so the check passes
            dst.write_bytes(b"\x89PNG compressed")

            ops = BlenderOperations()
            with patch.object(ops, "_blender_available", True):
                with patch("app.services.blender_operations.blender_backend.run_script", return_value=mock_blender_result):
                    result = ops.compress_texture(str(src), str(dst))
                    assert result.success
                    assert result.backend == "blender"


# =========================================================================
# BlenderOperations — Atlas Generation Tests
# =========================================================================

class TestAtlasGenerationFallback:
    def test_atlas_input_not_found(self):
        ops = BlenderOperations()
        result = ops.generate_atlas("/nonexistent/mesh.glb", "/tmp/atlas.png")
        assert not result.success

    def test_atlas_fallback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mesh = Path(tmpdir) / "mesh.glb"
            mesh.write_bytes(b"glTF dummy")
            atlas = Path(tmpdir) / "atlas.png"

            ops = BlenderOperations()
            with patch.object(ops, "_blender_available", False):
                result = ops.generate_atlas(str(mesh), str(atlas))
                assert result.success
                assert result.backend == "fallback"
                assert atlas.exists()


# =========================================================================
# BlenderOperations — Meshlet Generation Tests
# =========================================================================

class TestMeshletGenerationFallback:
    def test_meshlet_input_not_found(self):
        ops = BlenderOperations()
        result = ops.generate_meshlets("/nonexistent/mesh.glb", "/tmp/meshlets.json")
        assert not result.success

    def test_meshlet_fallback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mesh = Path(tmpdir) / "mesh.glb"
            mesh.write_bytes(b"glTF dummy")
            output = Path(tmpdir) / "meshlets.json"

            ops = BlenderOperations()
            with patch.object(ops, "_blender_available", False):
                result = ops.generate_meshlets(str(mesh), str(output))
                assert result.success
                assert result.backend == "fallback"
                assert output.exists()
                data = json.loads(output.read_text())
                assert data["meshlet_count"] == 1

    def test_meshlet_fallback_json_valid(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mesh = Path(tmpdir) / "mesh.glb"
            mesh.write_bytes(b"glTF dummy")
            output = Path(tmpdir) / "meshlets.json"

            ops = BlenderOperations()
            with patch.object(ops, "_blender_available", False):
                ops.generate_meshlets(str(mesh), str(output))
                data = json.loads(output.read_text())
                assert "meshlets" in data
                assert len(data["meshlets"]) == 1
                assert "vertices" in data["meshlets"][0]
                assert "indices" in data["meshlets"][0]


# =========================================================================
# BlenderOperations — glTF Export Tests
# =========================================================================

class TestGLTFExport:
    def test_export_glb_fallback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mesh = make_test_mesh(5, 5)
            src = Path(tmpdir) / "input.glb"
            src.write_bytes(b"glTF dummy")
            dst = Path(tmpdir) / "output.glb"

            ops = BlenderOperations()
            with patch.object(ops, "_blender_available", False):
                meta = ops.export_gltf(str(src), str(dst))
                assert dst.exists()

    def test_export_glb_blender(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mesh = make_test_mesh(5, 5)
            src = Path(tmpdir) / "input.glb"
            src.write_bytes(b"glTF dummy")
            dst = Path(tmpdir) / "output.glb"
            dst.write_bytes(b"glTF exported")

            mock_result = BlenderResult(
                success=True, return_code=0, stdout="", stderr="",
                execution_time_ms=100,
            )

            ops = BlenderOperations()
            with patch.object(ops, "_blender_available", True):
                with patch("app.services.blender_operations.blender_backend.run_script", return_value=mock_result):
                    meta = ops.export_gltf(str(src), str(dst))
                    assert meta.format == "glb"


# =========================================================================
# BlenderOperations — Info Tests
# =========================================================================

class TestBlenderInfo:
    def test_get_info(self):
        ops = BlenderOperations()
        info = ops.get_blender_info()
        assert "available" in info
        assert "version" in info

    def test_blender_available_property(self):
        ops = BlenderOperations()
        assert isinstance(ops.blender_available, bool)


# =========================================================================
# Integration Tests (require real Blender)
# =========================================================================

_BLENDER_AVAILABLE = shutil.which("blender") is not None or (
    os.path.exists(r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe")
    if os.name == "nt" else False
)

pytestmark_int = pytest.mark.skipif(
    not _BLENDER_AVAILABLE,
    reason="Blender not installed — skipping integration tests"
)


@pytestmark_int
class TestBlenderIntegrationTexture:
    def test_compress_real_texture(self):
        pytest.importorskip("PIL")
        from PIL import Image

        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "test.png"
            dst = Path(tmpdir) / "compressed.png"
            img = Image.new("RGB", (512, 512), (100, 150, 200))
            img.save(str(src))

            ops = BlenderOperations()
            if ops.blender_available:
                result = ops.compress_texture(str(src), str(dst), quality="high")
                assert result.success
                assert dst.exists()


@pytestmark_int
class TestBlenderIntegrationAtlas:
    def test_atlas_from_mesh(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mesh = Path(tmpdir) / "scene.glb"
            mesh.write_bytes(b"glTF dummy")
            atlas = Path(tmpdir) / "atlas.png"

            ops = BlenderOperations()
            if ops.blender_available:
                result = ops.generate_atlas(str(mesh), str(atlas))
                assert result.success


@pytestmark_int
class TestBlenderIntegrationMeshlets:
    def test_meshlets_from_mesh(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mesh = Path(tmpdir) / "scene.glb"
            mesh.write_bytes(b"glTF dummy")
            output = Path(tmpdir) / "meshlets.json"

            ops = BlenderOperations()
            if ops.blender_available:
                result = ops.generate_meshlets(str(mesh), str(output))
                assert result.success


# =========================================================================
# Existing Phase 18 Tests (regression)
# =========================================================================

class TestExistingDecimation:
    def test_decimate_reduces_faces(self):
        mesh = make_test_mesh(10, 10)
        original = mesh.num_faces
        decimated = decimate_mesh(mesh, target_face_ratio=0.1, aggressiveness=10.0)
        assert decimated.num_faces <= original

    def test_lod_chain(self):
        mesh = make_test_mesh(10, 10)
        chain = generate_lod_chain(mesh, lod_ratios=[1.0, 0.5, 0.25])
        assert len(chain) == 3

    def test_glb_export_roundtrip(self):
        mesh = make_test_mesh(5, 5)
        glb = mesh_to_glb_bytes(mesh, "test")
        assert len(glb) > 0
        import struct
        magic, version, length = struct.unpack("<III", glb[:12])
        assert magic == 0x46546C67
        assert version == 2

    def test_cdn_path(self):
        path = get_asset_path("abc123def", lod_level=0)
        assert path.parts[0] == "assets"
        assert "abc123def_lod0" in str(path)


# =========================================================================
# Edge Cases
# =========================================================================

class TestEdgeCases:
    def test_compress_empty_path(self):
        ops = BlenderOperations()
        result = ops.compress_texture("", "/tmp/out.png")
        assert not result.success

    def test_atlas_empty_path(self):
        ops = BlenderOperations()
        result = ops.generate_atlas("", "/tmp/atlas.png")
        assert not result.success

    def test_meshlet_empty_path(self):
        ops = BlenderOperations()
        result = ops.generate_meshlets("", "/tmp/out.json")
        assert not result.success

    def test_compress_quality_levels(self):
        pytest.importorskip("PIL")
        from PIL import Image

        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "input.png"
            img = Image.new("RGB", (8, 8), (128, 128, 128))
            img.save(str(src))

            for quality in ["low", "medium", "high", "maximum"]:
                dst = Path(tmpdir) / f"out_{quality}.png"
                ops = BlenderOperations()
                with patch.object(ops, "_blender_available", False):
                    result = ops.compress_texture(str(src), str(dst), quality=quality)
                    assert result.success
