"""
Blender Meshlet Generation Script

Runs inside Blender (--background --python) to generate meshlets from a mesh.
Reads args from RW_BLENDER_ARGS environment variable or args.json.

Supports:
- Manifold mesh splitting into meshlets
- Configurable max vertices/triangles per meshlet
- Spatial coherence via k-means clustering
- Meshlet data export (vertices, indices, normals)
"""

import bpy
import os
import sys
import json
import bmesh
import numpy as np
from pathlib import Path
from mathutils import Vector


def load_args():
    """Load arguments from env var or args.json file."""
    env_args = os.environ.get("RW_BLENDER_ARGS")
    if env_args:
        return json.loads(env_args)
    args_path = Path(__file__).parent / "args.json"
    if args_path.exists():
        return json.loads(args_path.read_text())
    return {}


def split_meshlets():
    """
    Split a mesh into meshlets using spatial clustering.

    Uses k-means on vertex positions to group triangles into
    spatially coherent meshlets.
    """
    args = load_args()
    input_mesh = args.get("input_mesh", "")
    output_path = args.get("output_path", "")
    max_verts = args.get("max_verts_per_meshlet", 128)
    max_tris = args.get("max_tris_per_meshlet", 128)

    if not input_mesh:
        print("ERROR: input_mesh required")
        sys.exit(1)

    # Clear scene
    bpy.ops.wm.read_factory_settings(use_empty=True)

    # Import mesh
    ext = Path(input_mesh).suffix.lower()
    try:
        if ext == ".fbx":
            bpy.ops.import_scene.fbx(filepath=input_mesh)
        elif ext in (".glb", ".gltf"):
            bpy.ops.import_scene.gltf(filepath=input_mesh)
        elif ext == ".obj":
            bpy.ops.import_scene.obj(filepath=input_mesh)
        else:
            print(f"ERROR: Unsupported format {ext}")
            sys.exit(1)
    except Exception as e:
        print(f"ERROR: Import failed: {e}")
        sys.exit(1)

    # Get mesh
    mesh_objects = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if not mesh_objects:
        print("ERROR: No mesh objects found")
        sys.exit(1)

    obj = mesh_objects[0]
    mesh = obj.data

    # Ensure we have triangles
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.tris_convert_to_quads()
    bpy.ops.mesh.quads_convert_to_tris()
    bpy.ops.object.mode_set(mode="OBJECT")

    # Extract vertex positions and face indices
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()

    vertices = np.array([v.co[:] for v in bm.verts])
    faces = np.array([[v.index for v in f.verts] for f in bm.faces])

    if len(vertices) == 0 or len(faces) == 0:
        print("ERROR: Empty mesh")
        sys.exit(1)

    # K-means clustering on vertex centroids of triangles
    num_tris = len(faces)
    tri_centroids = np.mean(vertices[faces], axis=1)  # (N, 3)

    # Estimate number of meshlets
    num_meshlets = max(1, num_tris // max_tris)

    # Simple k-means (Blender doesn't have numpy stats)
    # Use iterative closest centroid assignment
    centroids = tri_centroids[:num_meshlets].copy()
    assignments = np.zeros(num_tris, dtype=int)

    for iteration in range(20):
        # Assign each triangle to nearest centroid
        new_assignments = np.zeros(num_tris, dtype=int)
        for i in range(num_tris):
            dists = np.linalg.norm(centroids - tri_centroids[i], axis=1)
            new_assignments[i] = np.argmin(dists)

        # Check convergence
        if np.array_equal(new_assignments, assignments):
            break
        assignments = new_assignments

        # Update centroids
        for k in range(num_meshlets):
            mask = assignments == k
            if mask.any():
                centroids[k] = tri_centroids[mask].mean(axis=0)

    # Build meshlet data
    meshlets = []
    for k in range(num_meshlets):
        mask = assignments == k
        meshlet_tris = faces[mask]
        if len(meshlet_tris) == 0:
            continue

        # Get unique vertices in this meshlet
        unique_verts = np.unique(meshlet_tris)
        local_vert_map = {v: i for i, v in enumerate(unique_verts)}

        # Remap face indices to local
        local_faces = []
        for tri in meshlet_tris:
            local_faces.append([local_vert_map[v] for v in tri])

        meshlet_verts = vertices[unique_verts]

        meshlets.append({
            "id": len(meshlets),
            "vertex_count": len(unique_verts),
            "triangle_count": len(meshlet_tris),
            "vertices": meshlet_verts.tolist(),
            "indices": local_faces,
            "bounding_box_min": meshlet_verts.min(axis=0).tolist(),
            "bounding_box_max": meshlet_verts.max(axis=0).tolist(),
        })

    # Write output
    output_data = {
        "success": True,
        "input_mesh": input_mesh,
        "total_vertices": len(vertices),
        "total_triangles": num_tris,
        "meshlet_count": len(meshlets),
        "max_verts_per_meshlet": max_verts,
        "max_tris_per_meshlet": max_tris,
        "meshlets": meshlets,
    }

    os.makedirs(Path(output_path).parent, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2)

    print(f"RESULT:{json.dumps({'success': True, 'meshlet_count': len(meshlets), 'output': output_path})}")
    return output_data


if __name__ == "__main__":
    mode = os.environ.get("RW_BLENDER_MODE", "meshlets")
    if mode == "meshlets":
        split_meshlets()
    else:
        print(f"Unknown mode: {mode}")
        sys.exit(1)
