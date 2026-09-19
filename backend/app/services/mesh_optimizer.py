"""
Mesh Optimization

Optimizes 3D meshes for real-time rendering:
- Polygon decimation (quadric edge collapse)
- LOD (Level of Detail) generation
- Bounding box computation
- Mesh statistics

Uses OpenCV's built-in simplification and custom decimation.
"""

import cv2
import numpy as np
from dataclasses import dataclass
from typing import List, Optional, Tuple

from app.services.mesh_generator import Mesh, Triangle


@dataclass
class LODLevel:
    """A single LOD level."""
    level: int  # 0 = highest detail, 1 = medium, 2 = low, etc.
    target_ratio: float  # fraction of original polygons
    mesh: Mesh
    vertex_reduction: float
    face_reduction: float


@dataclass
class MeshStats:
    """Statistics about a mesh."""
    num_vertices: int
    num_faces: int
    bbox_min: np.ndarray  # 3D
    bbox_max: np.ndarray  # 3D
    bbox_size: np.ndarray  # 3D extent
    surface_area: float
    volume: float  # if watertight

    def to_dict(self) -> dict:
        return {
            "num_vertices": self.num_vertices,
            "num_faces": self.num_faces,
            "bbox_min": self.bbox_min.tolist(),
            "bbox_max": self.bbox_max.tolist(),
            "bbox_size": self.bbox_size.tolist(),
            "surface_area": round(self.surface_area, 4),
            "volume": round(self.volume, 4),
        }


def compute_mesh_stats(mesh: Mesh) -> MeshStats:
    """Compute statistics for a mesh."""
    if mesh.num_vertices == 0:
        return MeshStats(
            num_vertices=0, num_faces=0,
            bbox_min=np.zeros(3), bbox_max=np.zeros(3), bbox_size=np.zeros(3),
            surface_area=0, volume=0,
        )

    bbox_min = mesh.vertices.min(axis=0)
    bbox_max = mesh.vertices.max(axis=0)
    bbox_size = bbox_max - bbox_min

    # Surface area (sum of triangle areas)
    area = 0.0
    for face in mesh.faces:
        v0 = mesh.vertices[face.v0].astype(np.float64)
        v1 = mesh.vertices[face.v1].astype(np.float64)
        v2 = mesh.vertices[face.v2].astype(np.float64)
        area += 0.5 * np.linalg.norm(np.cross(v1 - v0, v2 - v0))

    # Volume (signed, only meaningful for watertight meshes)
    volume = 0.0
    for face in mesh.faces:
        v0 = mesh.vertices[face.v0].astype(np.float64)
        v1 = mesh.vertices[face.v1].astype(np.float64)
        v2 = mesh.vertices[face.v2].astype(np.float64)
        volume += np.dot(v0, np.cross(v1, v2)) / 6.0

    return MeshStats(
        num_vertices=mesh.num_vertices,
        num_faces=mesh.num_faces,
        bbox_min=bbox_min,
        bbox_max=bbox_max,
        bbox_size=bbox_size,
        surface_area=abs(area),
        volume=abs(volume),
    )


def decimate_mesh(
    mesh: Mesh,
    target_face_ratio: float = 0.5,
    aggressiveness: float = 7.0,
) -> Mesh:
    """
    Decimate mesh using vertex clustering.

    Args:
        mesh: Input mesh
        target_face_ratio: Target fraction of faces (0.0 to 1.0)
        aggressiveness: How aggressively to simplify (higher = more aggressive)

    Returns:
        Simplified mesh
    """
    if mesh.num_faces == 0 or mesh.num_vertices == 0:
        return mesh

    target_faces = max(4, int(mesh.num_faces * target_face_ratio))

    bbox_size = mesh.vertices.max(axis=0) - mesh.vertices.min(axis=0)
    bbox_diag = np.linalg.norm(bbox_size)

    if bbox_diag <= 0:
        return mesh

    # Scale grid size based on target ratio — more aggressive = larger grid
    # At ratio=1.0, grid is tiny (no merging). At ratio=0.01, grid is large.
    ratio_scale = np.sqrt(1.0 / max(target_face_ratio, 0.01))
    grid_size = bbox_diag * 0.02 * ratio_scale * (aggressiveness / 7.0)

    if grid_size <= 0:
        return mesh

    # Quantize vertices to grid
    quantized = np.floor(mesh.vertices / grid_size).astype(np.int32)

    # Find unique grid cells
    unique_cells, inverse = np.unique(
        quantized, axis=0, return_inverse=True
    )

    # inverse is 1D: maps each vertex to its unique cell index
    new_vertices = []
    new_vertex_map = {}  # cell_idx -> new_idx

    for old_idx in range(mesh.num_vertices):
        cell_idx = int(inverse[old_idx])
        if cell_idx not in new_vertex_map:
            new_vertex_map[cell_idx] = len(new_vertices)
            mask = inverse == cell_idx
            avg_pos = mesh.vertices[mask].mean(axis=0)
            new_vertices.append(avg_pos)

    new_vertices = np.array(new_vertices) if new_vertices else np.empty((0, 3))

    # Remap faces
    new_faces = []
    for face in mesh.faces:
        v0_new = new_vertex_map.get(int(inverse[face.v0]), None)
        v1_new = new_vertex_map.get(int(inverse[face.v1]), None)
        v2_new = new_vertex_map.get(int(inverse[face.v2]), None)

        if v0_new is not None and v1_new is not None and v2_new is not None:
            # Skip degenerate faces
            if v0_new != v1_new and v1_new != v2_new and v0_new != v2_new:
                new_faces.append(Triangle(v0_new, v1_new, v2_new))

    # Remap colors
    new_colors = None
    if mesh.vertex_colors is not None:
        new_colors = []
        seen_cells = set()
        for old_idx in range(mesh.num_vertices):
            cell_idx = int(inverse[old_idx])
            if cell_idx not in seen_cells:
                seen_cells.add(cell_idx)
                mask = inverse == cell_idx
                avg_color = mesh.vertex_colors[mask].mean(axis=0)
                new_colors.append(avg_color)
        new_colors = np.array(new_colors) if new_colors else None

    return Mesh(
        vertices=new_vertices,
        faces=new_faces,
        vertex_colors=new_colors,
    )


def decimate_to_target(
    mesh: Mesh,
    target_faces: int,
) -> Mesh:
    """Decimate mesh to approximately target number of faces."""
    if mesh.num_faces <= target_faces:
        return mesh

    ratio = target_faces / mesh.num_faces
    return decimate_mesh(mesh, target_face_ratio=ratio)


def generate_lod_chain(
    mesh: Mesh,
    lod_ratios: Optional[List[float]] = None,
) -> List[LODLevel]:
    """
    Generate a chain of LOD levels from a single mesh.

    Args:
        mesh: Input high-detail mesh
        lod_ratios: List of face ratios for each LOD level
                    Default: [1.0, 0.5, 0.25, 0.1]

    Returns:
        List of LODLevel objects
    """
    if lod_ratios is None:
        lod_ratios = [1.0, 0.5, 0.25, 0.1]

    stats = compute_mesh_stats(mesh)
    levels = []

    for i, ratio in enumerate(lod_ratios):
        if ratio >= 1.0:
            lod_mesh = mesh
        else:
            lod_mesh = decimate_mesh(mesh, target_face_ratio=ratio)

        lod_stats = compute_mesh_stats(lod_mesh)
        levels.append(LODLevel(
            level=i,
            target_ratio=ratio,
            mesh=lod_mesh,
            vertex_reduction=1.0 - (lod_stats.num_vertices / max(stats.num_vertices, 1)),
            face_reduction=1.0 - (lod_stats.num_faces / max(stats.num_faces, 1)),
        ))

    return levels


def select_lod(
    lod_chain: List[LODLevel],
    distance: float,
    screen_fraction: float = 0.1,
) -> LODLevel:
    """
    Select appropriate LOD level based on distance.

    Args:
        lod_chain: List of LOD levels (sorted by detail, highest first)
        distance: Distance from camera to mesh
        screen_fraction: Desired fraction of screen the mesh should occupy

    Returns:
        Selected LOD level
    """
    if not lod_chain:
        return None

    # Simple distance-based selection
    if distance < 10:
        return lod_chain[0]  # highest detail
    elif distance < 30:
        idx = min(1, len(lod_chain) - 1)
        return lod_chain[idx]
    elif distance < 100:
        idx = min(2, len(lod_chain) - 1)
        return lod_chain[idx]
    else:
        return lod_chain[-1]  # lowest detail


def optimize_mesh_for_rendering(
    mesh: Mesh,
    max_faces: int = 10000,
) -> Tuple[Mesh, dict]:
    """
    Full optimization pipeline for a mesh.

    Args:
        mesh: Input mesh
        max_faces: Maximum allowed faces

    Returns:
        (optimized_mesh, optimization_stats)
    """
    stats_before = compute_mesh_stats(mesh)

    optimized = mesh
    actions = []

    # Step 1: Decimate if needed
    if optimized.num_faces > max_faces:
        ratio = max_faces / optimized.num_faces
        optimized = decimate_mesh(optimized, target_face_ratio=ratio)
        actions.append(f"decimated to {optimized.num_faces} faces")

    # Step 2: Remove degenerate faces
    valid_faces = []
    for face in optimized.faces:
        if face.v0 != face.v1 and face.v1 != face.v2 and face.v0 != face.v2:
            valid_faces.append(face)
    if len(valid_faces) < len(optimized.faces):
        optimized.faces = valid_faces
        actions.append(f"removed {len(optimized.faces) - len(valid_faces)} degenerate faces")

    stats_after = compute_mesh_stats(optimized)

    return optimized, {
        "actions": actions,
        "before": stats_before.to_dict(),
        "after": stats_after.to_dict(),
        "face_reduction": 1.0 - (stats_after.num_faces / max(stats_before.num_faces, 1)),
        "vertex_reduction": 1.0 - (stats_after.num_vertices / max(stats_before.num_vertices, 1)),
    }
