"""
glTF/GLB Export Utility

Exports meshes to glTF 2.0 / GLB format for web and PC client delivery.
No external dependencies — uses pure binary packing.

Supports:
- Binary GLB (single file, embedded buffers)
- Vertex positions, normals, colors
- Face indices
- Bounding box metadata
"""

import struct
import json
import numpy as np
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass

from app.services.mesh_generator import Mesh


@dataclass
class AssetMetadata:
    """Metadata for a 3D asset."""
    asset_id: str
    vertex_count: int
    face_count: int
    bbox_min: List[float]
    bbox_max: List[float]
    file_size_bytes: int
    format: str  # "glb"


def mesh_to_glb_bytes(mesh: Mesh, asset_id: str = "unknown") -> bytes:
    """
    Convert a Mesh to GLB (binary glTF) bytes.

    GLB structure:
    - 12-byte header: magic (0x46546C67), version (2), total length
    - JSON chunk: scene graph, accessors, buffer views
    - BIN chunk: vertex/index data
    """
    # Prepare vertex data (float32 x,y,z)
    vertex_data = mesh.vertices.astype(np.float32).tobytes()
    vertex_count = mesh.num_vertices

    # Prepare index data (uint32 per face vertex)
    indices = []
    for face in mesh.faces:
        indices.extend([face.v0, face.v1, face.v2])
    index_data = np.array(indices, dtype=np.uint32).tobytes()
    index_count = len(indices)

    # Prepare color data if available
    color_data = b""
    if mesh.vertex_colors is not None:
        colors = mesh.vertex_colors.astype(np.uint8)
        if colors.max() <= 1.0:
            colors = (colors * 255).astype(np.uint8)
        color_data = colors.tobytes()

    # Pad binary data to 4-byte boundaries
    def pad4(data: bytes) -> bytes:
        remainder = len(data) % 4
        if remainder:
            return data + b"\x00" * (4 - remainder)
        return data

    vertex_data_padded = pad4(vertex_data)
    index_data_padded = pad4(index_data)
    color_data_padded = pad4(color_data) if color_data else b""

    # Calculate buffer sizes
    vertex_offset = 0
    index_offset = len(vertex_data_padded)
    color_offset = index_offset + len(index_data_padded) if color_data else 0
    total_buffer_size = len(vertex_data_padded) + len(index_data_padded) + len(color_data_padded)

    # Compute bounding box
    bbox_min = mesh.vertices.min(axis=0).tolist() if vertex_count > 0 else [0, 0, 0]
    bbox_max = mesh.vertices.max(axis=0).tolist() if vertex_count > 0 else [0, 0, 0]

    # Build buffer views
    buffer_views = [
        {
            "buffer": 0,
            "byteOffset": vertex_offset,
            "byteLength": len(vertex_data),
            "target": 34962,  # ARRAY_BUFFER
        },
        {
            "buffer": 0,
            "byteOffset": index_offset,
            "byteLength": len(index_data),
            "target": 34963,  # ELEMENT_ARRAY_BUFFER
        },
    ]

    # Build accessors
    accessors = [
        {
            "bufferView": 0,
            "componentType": 5126,  # FLOAT
            "count": vertex_count,
            "type": "VEC3",
            "min": bbox_min,
            "max": bbox_max,
        },
        {
            "bufferView": 1,
            "componentType": 5125,  # UNSIGNED_INT
            "count": index_count,
            "type": "SCALAR",
        },
    ]

    # Add color accessor if present
    if color_data:
        buffer_views.append({
            "buffer": 0,
            "byteOffset": color_offset,
            "byteLength": len(color_data),
            "target": 34962,
        })
        accessors.append({
            "bufferView": len(buffer_views) - 1,
            "componentType": 5121,  # UNSIGNED_BYTE
            "count": vertex_count,
            "type": "VEC3",
        })

    # Build glTF JSON
    gltf_json = {
        "asset": {
            "version": "2.0",
            "generator": "RecordedWorld-Optimizer",
        },
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0}],
        "meshes": [
            {
                "primitives": [
                    {
                        "attributes": {"POSITION": 0},
                        "indices": 1,
                        **({"COLOR_0": 2} if color_data else {}),
                    }
                ]
            }
        ],
        "accessors": accessors,
        "bufferViews": buffer_views,
        "buffers": [{"byteLength": total_buffer_size}],
    }

    # Encode JSON to bytes
    json_bytes = json.dumps(gltf_json).encode("utf-8")
    json_padded = pad4(json_bytes)

    # BIN chunk data
    bin_data = vertex_data_padded + index_data_padded + color_data_padded
    bin_padded = pad4(bin_data)

    # GLB header
    total_length = 12 + 8 + len(json_padded) + 8 + len(bin_padded)
    header = struct.pack("<III", 0x46546C67, 2, total_length)

    # JSON chunk
    json_chunk_header = struct.pack("<II", len(json_bytes), 0x4E4F534A)  # JSON magic

    # BIN chunk
    bin_chunk_header = struct.pack("<II", len(bin_data), 0x004E4942)  # BIN magic

    return header + json_chunk_header + json_padded + bin_chunk_header + bin_padded


def export_glb(
    mesh: Mesh,
    output_path: Path,
    asset_id: str = "unknown",
) -> AssetMetadata:
    """
    Export a mesh to GLB file.

    Returns:
        AssetMetadata with file info
    """
    glb_bytes = mesh_to_glb_bytes(mesh, asset_id)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(glb_bytes)

    bbox_min = mesh.vertices.min(axis=0).tolist() if mesh.num_vertices > 0 else [0, 0, 0]
    bbox_max = mesh.vertices.max(axis=0).tolist() if mesh.num_vertices > 0 else [0, 0, 0]

    return AssetMetadata(
        asset_id=asset_id,
        vertex_count=mesh.num_vertices,
        face_count=mesh.num_faces,
        bbox_min=bbox_min,
        bbox_max=bbox_max,
        file_size_bytes=len(glb_bytes),
        format="glb",
    )


def export_obj(mesh: Mesh, output_path: Path, asset_id: str = "unknown") -> AssetMetadata:
    """Export a mesh to OBJ format."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# RecordedWorld OBJ export — {asset_id}"]

    for v in mesh.vertices:
        lines.append(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}")

    for face in mesh.faces:
        lines.append(f"f {face.v0 + 1} {face.v1 + 1} {face.v2 + 1}")

    output_path.write_text("\n".join(lines), encoding="utf-8")

    bbox_min = mesh.vertices.min(axis=0).tolist() if mesh.num_vertices > 0 else [0, 0, 0]
    bbox_max = mesh.vertices.max(axis=0).tolist() if mesh.num_vertices > 0 else [0, 0, 0]

    return AssetMetadata(
        asset_id=asset_id,
        vertex_count=mesh.num_vertices,
        face_count=mesh.num_faces,
        bbox_min=bbox_min,
        bbox_max=bbox_max,
        file_size_bytes=output_path.stat().st_size,
        format="obj",
    )


# =============================================================================
# CDN-Ready Asset Path Utilities
# =============================================================================

ASSET_DIR = Path("assets")


def get_asset_path(
    asset_id: str,
    lod_level: int = 0,
    format: str = "glb",
) -> Path:
    """
    Generate a CDN-ready asset path.

    Structure: assets/{hash_prefix}/{asset_id}_lod{level}.{format}
    Hash prefix distributes assets across directories for CDN caching.
    """
    # Use first 2 chars of asset_id as directory prefix
    prefix = asset_id[:2] if len(asset_id) >= 2 else "aa"
    return ASSET_DIR / prefix / f"{asset_id}_lod{lod_level}.{format}"


def get_lod_chain_paths(
    asset_id: str,
    lod_levels: int = 4,
    format: str = "glb",
) -> List[Path]:
    """Generate paths for a full LOD chain."""
    return [get_asset_path(asset_id, level, format) for level in range(lod_levels)]
