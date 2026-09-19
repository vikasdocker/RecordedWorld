"""
Missing-Area Reconstruction Service

Fills in missing areas of 3D reconstructions using:
  - Neighboring surface extrapolation
  - Procedural generation
  - Hole filling algorithms
"""
import numpy as np
from typing import List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class HoleInfo:
    """Information about a detected hole in a mesh."""
    center: np.ndarray  # 3D center point
    radius: float  # Approximate radius
    area: float  # Surface area of the hole
    boundary_points: np.ndarray  # Points on the hole boundary


@dataclass
class ReconstructionResult:
    """Result of missing-area reconstruction."""
    filled_mesh: Optional[np.ndarray] = None  # Vertices
    filled_faces: Optional[np.ndarray] = None  # Face indices
    holes_filled: int = 0
    fill_method: str = "none"
    confidence: float = 0.0


class MissingAreaReconstructor:
    """
    Fills missing areas in 3D reconstructions.

    Methods:
      - Boundary interpolation: Fill holes by interpolating boundary edges
      - Nearest surface: Project hole center to nearest existing surface
      - Procedural fill: Generate geometry based on surrounding context
    """

    def detect_holes(
        self,
        vertices: np.ndarray,
        faces: np.ndarray,
        max_hole_area: float = 1.0,
    ) -> List[HoleInfo]:
        """
        Detect holes in a mesh by finding boundary edges.

        Args:
            vertices: N x 3 array of vertex positions
            faces: M x 3 array of face indices
            max_hole_area: Maximum hole area to fill

        Returns:
            List of HoleInfo for detected holes
        """
        if vertices is None or faces is None or len(faces) == 0:
            return []

        # Find boundary edges (edges shared by only one face)
        edge_count = {}
        for face in faces:
            for i in range(3):
                e = tuple(sorted([face[i], face[(i + 1) % 3]]))
                edge_count[e] = edge_count.get(e, 0) + 1

        boundary_edges = [e for e, c in edge_count.items() if c == 1]

        if not boundary_edges:
            return []

        # Group boundary edges into loops
        loops = self._group_edges_into_loops(boundary_edges)

        holes = []
        for loop in loops:
            if len(loop) < 3:
                continue

            loop_points = vertices[loop]
            center = np.mean(loop_points, axis=0)
            radius = np.max(np.linalg.norm(loop_points - center, axis=1))
            area = self._compute_loop_area(loop_points)

            if area <= max_hole_area:
                holes.append(HoleInfo(
                    center=center,
                    radius=radius,
                    area=area,
                    boundary_points=loop_points,
                ))

        return holes

    def fill_holes_boundary(
        self,
        vertices: np.ndarray,
        faces: np.ndarray,
        holes: Optional[List[HoleInfo]] = None,
        max_hole_area: float = 1.0,
    ) -> ReconstructionResult:
        """
        Fill holes using boundary interpolation.

        For each hole, creates a fan of triangles from the boundary to
        the hole center.
        """
        if vertices is None or faces is None:
            return ReconstructionResult()

        if holes is None:
            holes = self.detect_holes(vertices, faces, max_hole_area)

        if not holes:
            return ReconstructionResult(
                filled_mesh=vertices,
                filled_faces=faces,
                holes_filled=0,
                fill_method="none",
                confidence=1.0,
            )

        new_vertices = list(vertices)
        new_faces = list(faces)
        filled = 0

        for hole in holes:
            center_idx = len(new_vertices)
            new_vertices.append(hole.center)

            # Create fan triangles from boundary to center
            boundary_indices = []
            for point in hole.boundary_points:
                # Find closest existing vertex
                dists = np.linalg.norm(vertices - point, axis=1)
                closest_idx = np.argmin(dists)
                boundary_indices.append(closest_idx)

            for i in range(len(boundary_indices)):
                v1 = boundary_indices[i]
                v2 = boundary_indices[(i + 1) % len(boundary_indices)]
                new_faces.append([v1, v2, center_idx])

            filled += 1

        return ReconstructionResult(
            filled_mesh=np.array(new_vertices),
            filled_faces=np.array(new_faces),
            holes_filled=filled,
            fill_method="boundary_interpolation",
            confidence=0.6,
        )

    def fill_holes_nearest_surface(
        self,
        vertices: np.ndarray,
        faces: np.ndarray,
        holes: Optional[List[HoleInfo]] = None,
        max_hole_area: float = 1.0,
    ) -> ReconstructionResult:
        """
        Fill holes by projecting to nearest existing surface.

        For each hole, finds the nearest surface point and fills
        with a flat patch.
        """
        if vertices is None or faces is None:
            return ReconstructionResult()

        if holes is None:
            holes = self.detect_holes(vertices, faces, max_hole_area)

        if not holes:
            return ReconstructionResult(
                filled_mesh=vertices,
                filled_faces=faces,
                holes_filled=0,
                fill_method="none",
                confidence=1.0,
            )

        new_vertices = list(vertices)
        new_faces = list(faces)
        filled = 0

        for hole in holes:
            # Project hole center to nearest surface
            projected = self._project_to_surface(hole.center, vertices, faces)

            center_idx = len(new_vertices)
            new_vertices.append(projected)

            boundary_indices = []
            for point in hole.boundary_points:
                dists = np.linalg.norm(vertices - point, axis=1)
                closest_idx = np.argmin(dists)
                boundary_indices.append(closest_idx)

            for i in range(len(boundary_indices)):
                v1 = boundary_indices[i]
                v2 = boundary_indices[(i + 1) % len(boundary_indices)]
                new_faces.append([v1, v2, center_idx])

            filled += 1

        return ReconstructionResult(
            filled_mesh=np.array(new_vertices),
            filled_faces=np.array(new_faces),
            holes_filled=filled,
            fill_method="nearest_surface",
            confidence=0.7,
        )

    def _group_edges_into_loops(self, edges: List[Tuple[int, int]]) -> List[List[int]]:
        """Group boundary edges into connected loops."""
        if not edges:
            return []

        adjacency = {}
        for e in edges:
            adjacency.setdefault(e[0], []).append(e[1])
            adjacency.setdefault(e[1], []).append(e[0])

        visited = set()
        loops = []

        for start in adjacency:
            if start in visited:
                continue

            loop = [start]
            visited.add(start)
            current = start

            while True:
                neighbors = [n for n in adjacency.get(current, []) if n not in visited]
                if not neighbors:
                    break
                next_v = neighbors[0]
                loop.append(next_v)
                visited.add(next_v)
                current = next_v
                if current == start:
                    break

            if len(loop) >= 3:
                loops.append(loop)

        return loops

    def _compute_loop_area(self, points: np.ndarray) -> float:
        """Compute area of a polygon using shoelace formula."""
        if len(points) < 3:
            return 0.0

        center = np.mean(points, axis=0)
        projected = points - center

        # Use cross product for area (scalar result)
        area = 0.0
        for i in range(len(projected)):
            j = (i + 1) % len(projected)
            cross = np.cross(projected[i], projected[j])
            if isinstance(cross, np.ndarray):
                area += np.sum(cross)
            else:
                area += cross
        return abs(float(area)) / 2.0

    def _project_to_surface(
        self,
        point: np.ndarray,
        vertices: np.ndarray,
        faces: np.ndarray,
    ) -> np.ndarray:
        """Project a point to the nearest surface."""
        # Find nearest vertex
        dists = np.linalg.norm(vertices - point, axis=1)
        nearest_idx = np.argmin(dists)
        nearest = vertices[nearest_idx]

        # Simple projection: move toward nearest surface
        direction = nearest - point
        dist = np.linalg.norm(direction)
        if dist > 0:
            return point + direction * 0.8  # Move 80% toward surface
        return point


# Module-level singleton
missing_area_reconstructor = MissingAreaReconstructor()
