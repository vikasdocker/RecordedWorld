"""
Mesh Generation

Generates 3D meshes from point clouds using:
- Delaunay triangulation (2D projection)
- Convex hull
- Poisson surface reconstruction (when scipy available)

And exports to standard formats:
- OBJ (with MTL texture references)
- PLY (with vertex colors)
- glTF/GLB (when trimesh available)
"""

import cv2
import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from pathlib import Path
import struct
import json


@dataclass
class Triangle:
    """A triangle face with 3 vertex indices."""
    v0: int
    v1: int
    v2: int
    normal: Optional[np.ndarray] = None


@dataclass
class Mesh:
    """A 3D mesh with vertices, faces, and optional texture coordinates."""
    vertices: np.ndarray  # Nx3
    faces: List[Triangle]  # triangle list
    vertex_colors: Optional[np.ndarray] = None  # Nx3 RGB (0-255)
    uv_coords: Optional[np.ndarray] = None  # Nx2 texture coordinates
    texture_path: Optional[str] = None

    @property
    def num_vertices(self) -> int:
        return len(self.vertices)

    @property
    def num_faces(self) -> int:
        return len(self.faces)

    def compute_normals(self):
        """Compute face normals."""
        for face in self.faces:
            v0 = self.vertices[face.v0].astype(np.float64)
            v1 = self.vertices[face.v1].astype(np.float64)
            v2 = self.vertices[face.v2].astype(np.float64)
            normal = np.cross(v1 - v0, v2 - v0)
            norm = np.linalg.norm(normal)
            if norm > 0:
                normal = normal / norm
            face.normal = normal


def generate_mesh_delaunay(
    points_3d: np.ndarray,
    colors: Optional[np.ndarray] = None,
) -> Mesh:
    """
    Generate a mesh using 2D Delaunay triangulation projected from 3D.

    Projects points onto their dominant plane, performs Delaunay,
    then maps back to 3D.

    Args:
        points_3d: Nx3 points
        colors: Nx3 RGB colors

    Returns:
        Mesh with vertices and faces
    """
    if len(points_3d) < 3:
        return Mesh(
            vertices=points_3d if len(points_3d) > 0 else np.array([]).reshape(0, 3),
            faces=[],
            vertex_colors=colors,
        )

    # Project to 2D (XY plane for simplicity, or use PCA)
    pts_2d = points_3d[:, :2].astype(np.float32)

    # Delaunay triangulation
    rect = cv2.boundingRect(pts_2d)
    subdiv = cv2.Subdiv2D(rect)

    # Insert points (with small jitter to avoid degeneracies)
    jitter = np.random.randn(len(pts_2d), 2).astype(np.float32) * 0.001
    pts_jittered = pts_2d + jitter

    for pt in pts_jittered:
        try:
            subdiv.insert((float(pt[0]), float(pt[1])))
        except Exception:
            continue

    # Get triangles
    triangle_list = subdiv.getTriangleList()
    triangles = []

    # Create a mapping from 2D coordinates to vertex indices
    pt_to_idx = {}
    for i, pt in enumerate(pts_2d):
        key = (round(float(pt[0]), 4), round(float(pt[1]), 4))
        pt_to_idx[key] = i

    for t in triangle_list:
        pts = [(t[0], t[1]), (t[2], t[3]), (t[4], t[5])]
        indices = []
        valid = True

        for p in pts:
            # Find nearest vertex
            key = (round(p[0], 4), round(p[1], 4))
            if key in pt_to_idx:
                indices.append(pt_to_idx[key])
            else:
                # Find nearest point
                dists = np.sqrt(np.sum((pts_2d - np.array(p)) ** 2, axis=1))
                nearest = np.argmin(dists)
                if dists[nearest] < 1.0:
                    indices.append(int(nearest))
                else:
                    valid = False
                    break

        if valid and len(indices) == 3:
            # Check for degenerate triangles
            v0, v1, v2 = points_3d[indices[0]], points_3d[indices[1]], points_3d[indices[2]]
            area = np.linalg.norm(np.cross(v1 - v0, v2 - v0))
            if area > 1e-6:
                triangles.append(Triangle(indices[0], indices[1], indices[2]))

    return Mesh(
        vertices=points_3d,
        faces=triangles,
        vertex_colors=colors,
    )


def generate_mesh_convex_hull(points_3d: np.ndarray, colors: Optional[np.ndarray] = None) -> Mesh:
    """Generate a convex hull mesh."""
    if len(points_3d) < 4:
        return Mesh(vertices=points_3d, faces=[], vertex_colors=colors)

    try:
        from scipy.spatial import ConvexHull
        hull = ConvexHull(points_3d)
        triangles = [Triangle(int(s[0]), int(s[1]), int(s[2])) for s in hull.simplices]
        return Mesh(vertices=points_3d, faces=triangles, vertex_colors=colors)
    except ImportError:
        # Fallback: just return points without faces
        return Mesh(vertices=points_3d, faces=[], vertex_colors=colors)


def generate_mesh_poisson(points_3d: np.ndarray, colors: Optional[np.ndarray] = None) -> Mesh:
    """
    Generate mesh using Poisson surface reconstruction.
    Falls back to Delaunay if Open3D not available.
    """
    try:
        import open3d as o3d
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(points_3d)
        if colors is not None:
            pcd.colors = o3d.utility.Vector3dVector(colors / 255.0)

        mesh, _ = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(pcd, depth=9)
        vertices = np.asarray(mesh.vertices)
        faces = [Triangle(int(f[0]), int(f[1]), int(f[2])) for f in np.asarray(mesh.triangles)]
        return Mesh(vertices=vertices, faces=faces, vertex_colors=colors)
    except (ImportError, Exception):
        return generate_mesh_delaunay(points_3d, colors)


def assign_texture_coordinates(
    mesh: Mesh,
    image_width: int,
    image_height: int,
    keypoints_2d: Optional[np.ndarray] = None,
) -> Mesh:
    """
    Assign UV texture coordinates to mesh vertices.

    Uses planar projection if no 2D keypoints provided,
    otherwise uses keypoint correspondence.

    Args:
        mesh: Input mesh
        image_width: Texture image width
        image_height: Texture image height
        keypoints_2d: Optional Nx2 2D positions corresponding to vertices

    Returns:
        Mesh with UV coordinates assigned
    """
    if mesh.num_vertices == 0:
        mesh.uv_coords = np.array([]).reshape(0, 2)
        return mesh

    if keypoints_2d is not None and len(keypoints_2d) == mesh.num_vertices:
        # Direct mapping from 2D keypoints
        uv = keypoints_2d.copy()
        uv[:, 0] /= image_width
        uv[:, 1] /= image_height
        mesh.uv_coords = uv
    else:
        # Planar projection
        verts = mesh.vertices
        # Normalize to [0, 1]
        mins = verts.min(axis=0)
        maxs = verts.max(axis=0)
        ranges = maxs - mins
        ranges[ranges == 0] = 1  # avoid division by zero

        uv = np.zeros((mesh.num_vertices, 2))
        uv[:, 0] = (verts[:, 0] - mins[0]) / ranges[0]
        uv[:, 1] = (verts[:, 1] - mins[1]) / ranges[1]
        mesh.uv_coords = uv

    return mesh


def export_obj(mesh: Mesh, path: str, texture_filename: str = "texture.jpg"):
    """
    Export mesh to OBJ format with MTL texture reference.

    Args:
        mesh: Mesh to export
        path: Output .obj file path
        texture_filename: Texture image filename
    """
    mesh.compute_normals()

    with open(path, "w") as f:
        f.write(f"# Recorded World Mesh\n")
        f.write(f"# Vertices: {mesh.num_vertices}, Faces: {mesh.num_faces}\n")
        f.write(f"mtllib {Path(texture_filename).stem}.mtl\n\n")

        # Vertices
        for i, v in enumerate(mesh.vertices):
            color_str = ""
            if mesh.vertex_colors is not None and i < len(mesh.vertex_colors):
                c = mesh.vertex_colors[i]
                color_str = f" # {int(c[0])} {int(c[1])} {int(c[2])}"
            f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}{color_str}\n")

        # UV coordinates
        if mesh.uv_coords is not None:
            for uv in mesh.uv_coords:
                f.write(f"vt {uv[0]:.6f} {uv[1]:.6f}\n")

        # Normals
        for face in mesh.faces:
            if face.normal is not None:
                f.write(f"vn {face.normal[0]:.6f} {face.normal[1]:.6f} {face.normal[2]:.6f}\n")

        # Faces
        f.write(f"\nusemtl material0\n")
        for i, face in enumerate(mesh.faces):
            v0, v1, v2 = face.v0 + 1, face.v1 + 1, face.v2 + 1
            if mesh.uv_coords is not None:
                f.write(f"f {v0}/{v0}/{v0} {v1}/{v1}/{v1} {v2}/{v2}/{v2}\n")
            else:
                f.write(f"f {v0} {v1} {v2}\n")

    # Write MTL file
    mtl_path = str(Path(path).with_suffix(".mtl"))
    with open(mtl_path, "w") as f:
        f.write(f"# Material file\n")
        f.write(f"newmtl material0\n")
        f.write(f"Ka 0.2 0.2 0.2\n")
        f.write(f"Kd 0.8 0.8 0.8\n")
        f.write(f"Ks 0.0 0.0 0.0\n")
        f.write(f"map_Kd {texture_filename}\n")


def export_ply(mesh: Mesh, path: str):
    """Export mesh to PLY format with vertex colors."""
    with open(path, "w") as f:
        f.write("ply\n")
        f.write("format ascii 1.0\n")
        f.write(f"element vertex {mesh.num_vertices}\n")
        f.write("property float x\n")
        f.write("property float y\n")
        f.write("property float z\n")
        if mesh.vertex_colors is not None:
            f.write("property uchar red\n")
            f.write("property uchar green\n")
            f.write("property uchar blue\n")
        f.write(f"element face {mesh.num_faces}\n")
        f.write("property list uchar int vertex_indices\n")
        f.write("end_header\n")

        # Vertices
        for i, v in enumerate(mesh.vertices):
            line = f"{v[0]:.6f} {v[1]:.6f} {v[2]:.6f}"
            if mesh.vertex_colors is not None and i < len(mesh.vertex_colors):
                c = mesh.vertex_colors[i]
                line += f" {int(c[0])} {int(c[1])} {int(c[2])}"
            f.write(line + "\n")

        # Faces
        for face in mesh.faces:
            f.write(f"3 {face.v0} {face.v1} {face.v2}\n")


def mesh_from_point_cloud(
    points_3d: np.ndarray,
    colors: Optional[np.ndarray] = None,
    method: str = "delaunay",
) -> Mesh:
    """
    Generate mesh from point cloud.

    Args:
        points_3d: Nx3 points
        colors: Nx3 RGB colors
        method: 'delaunay', 'convex_hull', or 'poisson'

    Returns:
        Mesh object
    """
    if method == "delaunay":
        return generate_mesh_delaunay(points_3d, colors)
    elif method == "convex_hull":
        return generate_mesh_convex_hull(points_3d, colors)
    elif method == "poisson":
        return generate_mesh_poisson(points_3d, colors)
    else:
        raise ValueError(f"Unknown method: {method}")
