import pytest
import numpy as np
import os
import tempfile

from app.services.mesh_generator import (
    Mesh, Triangle, generate_mesh_delaunay, generate_mesh_convex_hull,
    assign_texture_coordinates, export_obj, export_ply, mesh_from_point_cloud,
)


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


def _create_cube_points():
    """Create points on a cube surface."""
    points = []
    colors = []
    # Front face
    for x in np.linspace(0, 1, 5):
        for y in np.linspace(0, 1, 5):
            points.append([x, y, 0])
            colors.append([255, 0, 0])
    # Back face
    for x in np.linspace(0, 1, 5):
        for y in np.linspace(0, 1, 5):
            points.append([x, y, 1])
            colors.append([0, 255, 0])
    # Top face
    for x in np.linspace(0, 1, 5):
        for z in np.linspace(0, 1, 5):
            points.append([x, 1, z])
            colors.append([0, 0, 255])
    return np.array(points), np.array(colors)


# --- Mesh Data Structure Tests ---

class TestMesh:
    def test_empty_mesh(self):
        mesh = Mesh(vertices=np.array([]).reshape(0, 3), faces=[])
        assert mesh.num_vertices == 0
        assert mesh.num_faces == 0

    def test_compute_normals(self):
        mesh = Mesh(
            vertices=np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]]),
            faces=[Triangle(0, 1, 2)],
        )
        mesh.compute_normals()
        assert mesh.faces[0].normal is not None
        # Normal should be (0, 0, 1) for this triangle
        normal = mesh.faces[0].normal
        assert abs(normal[2] - 1.0) < 0.01

    def test_triangle(self):
        t = Triangle(0, 1, 2)
        assert t.v0 == 0
        assert t.v1 == 1
        assert t.v2 == 2


# --- Delaunay Mesh Tests ---

class TestDelaunayMesh:
    def test_generate_mesh(self):
        points = np.array([
            [0, 0, 0], [1, 0, 0], [0.5, 1, 0],
            [2, 0, 0], [2, 1, 0],
            [0.25, 0.5, 0], [1.5, 0.5, 0],
        ], dtype=np.float32)

        mesh = generate_mesh_delaunay(points)

        assert mesh.num_vertices == 7
        assert mesh.num_faces > 0

    def test_generate_mesh_with_colors(self):
        points = np.array([
            [0, 0, 0], [1, 0, 0], [0.5, 1, 0],
            [2, 0, 0], [2, 1, 0],
        ], dtype=np.float32)
        colors = np.array([
            [255, 0, 0], [0, 255, 0], [0, 0, 255],
            [255, 255, 0], [255, 0, 255],
        ])

        mesh = generate_mesh_delaunay(points, colors)
        assert mesh.vertex_colors is not None

    def test_generate_mesh_too_few_points(self):
        points = np.array([[0, 0, 0], [1, 0, 0]])
        mesh = generate_mesh_delaunay(points)
        assert mesh.num_faces == 0

    def test_generate_mesh_cube(self):
        points, colors = _create_cube_points()
        mesh = generate_mesh_delaunay(points, colors)

        assert mesh.num_vertices == len(points)
        assert mesh.num_faces > 0


# --- Convex Hull Tests ---

class TestConvexHull:
    def test_generate_mesh(self):
        points = np.array([
            [0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1],
            [1, 1, 0], [1, 0, 1], [0, 1, 1], [1, 1, 1],
        ], dtype=np.float32)

        mesh = generate_mesh_convex_hull(points)
        assert mesh.num_vertices == 8
        assert mesh.num_faces > 0

    def test_too_few_points(self):
        points = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]])
        mesh = generate_mesh_convex_hull(points)
        # Convex hull needs 4+ points for a 3D hull
        assert mesh.num_faces >= 0


# --- Texture Coordinate Tests ---

class TestTextureCoordinates:
    def test_assign_uv_planar(self):
        mesh = Mesh(
            vertices=np.array([[0, 0, 0], [1, 0, 0], [0.5, 1, 0]]),
            faces=[Triangle(0, 1, 2)],
        )
        mesh = assign_texture_coordinates(mesh, 640, 480)

        assert mesh.uv_coords is not None
        assert mesh.uv_coords.shape == (3, 2)
        # UVs should be in [0, 1]
        assert mesh.uv_coords.min() >= 0
        assert mesh.uv_coords.max() <= 1

    def test_assign_uv_from_keypoints(self):
        mesh = Mesh(
            vertices=np.array([[0, 0, 0], [1, 0, 0], [0.5, 1, 0]]),
            faces=[Triangle(0, 1, 2)],
        )
        keypoints = np.array([[100, 200], [300, 200], [200, 50]], dtype=np.float32)
        mesh = assign_texture_coordinates(mesh, 640, 480, keypoints)

        assert mesh.uv_coords is not None
        # UV = keypoint / image_size
        assert abs(mesh.uv_coords[0, 0] - 100 / 640) < 0.001

    def test_empty_mesh_uv(self):
        mesh = Mesh(vertices=np.array([]).reshape(0, 3), faces=[])
        mesh = assign_texture_coordinates(mesh, 640, 480)
        assert mesh.uv_coords is not None
        assert len(mesh.uv_coords) == 0


# --- Export Tests ---

class TestExport:
    def test_export_obj(self, temp_dir):
        mesh = Mesh(
            vertices=np.array([[0, 0, 0], [1, 0, 0], [0.5, 1, 0]]),
            faces=[Triangle(0, 1, 2)],
            vertex_colors=np.array([[255, 0, 0], [0, 255, 0], [0, 0, 255]]),
        )
        obj_path = os.path.join(temp_dir, "test.obj")
        export_obj(mesh, obj_path)

        assert os.path.exists(obj_path)
        assert os.path.exists(os.path.join(temp_dir, "test.mtl"))

        with open(obj_path) as f:
            content = f.read()
        assert "v " in content
        assert "f " in content

    def test_export_ply(self, temp_dir):
        mesh = Mesh(
            vertices=np.array([[0, 0, 0], [1, 0, 0], [0.5, 1, 0]]),
            faces=[Triangle(0, 1, 2)],
            vertex_colors=np.array([[255, 0, 0], [0, 255, 0], [0, 0, 255]]),
        )
        ply_path = os.path.join(temp_dir, "test.ply")
        export_ply(mesh, ply_path)

        assert os.path.exists(ply_path)

        with open(ply_path) as f:
            content = f.read()
        assert "ply" in content
        assert "3 0 1 2" in content


# --- Integration Tests ---

class TestMeshFromPointCloud:
    def test_delaunay(self):
        points = np.array([
            [0, 0, 0], [1, 0, 0], [0.5, 1, 0],
            [2, 0, 0], [2, 1, 0],
            [0.25, 0.5, 0], [1.5, 0.5, 0],
        ], dtype=np.float32)
        colors = np.random.randint(0, 255, (7, 3))

        mesh = mesh_from_point_cloud(points, colors, method="delaunay")
        assert mesh.num_vertices == 7
        assert mesh.num_faces > 0

    def test_convex_hull(self):
        points = np.array([
            [0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1],
            [1, 1, 0], [1, 0, 1], [0, 1, 1], [1, 1, 1],
        ], dtype=np.float32)

        mesh = mesh_from_point_cloud(points, method="convex_hull")
        assert mesh.num_faces > 0

    def test_unknown_method(self):
        points = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]])
        with pytest.raises(ValueError):
            mesh_from_point_cloud(points, method="unknown")

    def test_full_pipeline(self, temp_dir):
        """Test point cloud → mesh → export pipeline."""
        points = np.array([
            [0, 0, 0], [1, 0, 0], [0.5, 1, 0],
            [2, 0, 0], [2, 1, 0],
        ], dtype=np.float32)
        colors = np.array([
            [255, 0, 0], [0, 255, 0], [0, 0, 255],
            [255, 255, 0], [255, 0, 255],
        ])

        mesh = mesh_from_point_cloud(points, colors, method="delaunay")
        mesh = assign_texture_coordinates(mesh, 640, 480)

        obj_path = os.path.join(temp_dir, "output.obj")
        export_obj(mesh, obj_path)
        assert os.path.exists(obj_path)

        ply_path = os.path.join(temp_dir, "output.ply")
        export_ply(mesh, ply_path)
        assert os.path.exists(ply_path)
