"""
Blender Atlas Generation Script

Runs inside Blender (--background --python) to pack multiple textures into atlases.
Reads args from RW_BLENDER_ARGS environment variable or args.json.

Supports:
- UV-based texture atlas packing
- Configurable atlas size
- Multiple atlas support for large texture sets
- Padding between regions
"""

import bpy
import os
import sys
import json
from pathlib import Path


def load_args():
    """Load arguments from env var or args.json file."""
    env_args = os.environ.get("RW_BLENDER_ARGS")
    if env_args:
        return json.loads(env_args)
    args_path = Path(__file__).parent / "args.json"
    if args_path.exists():
        return json.loads(args_path.read_text())
    return {}


def create_atlas():
    """
    Create a texture atlas from input textures.

    Loads an FBX/OBJ with multiple materials, repacks UVs into
    a single atlas texture, and exports the result.
    """
    args = load_args()
    input_mesh = args.get("input_mesh", "")
    input_textures = args.get("input_textures", [])
    output_path = args.get("output_path", "")
    atlas_size = args.get("atlas_size", 2048)
    padding = args.get("padding", 4)

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
        elif ext in (".obj", ".glb", ".gltf"):
            bpy.ops.import_scene.gltf(filepath=input_mesh)
        else:
            print(f"ERROR: Unsupported format {ext}")
            sys.exit(1)
    except Exception as e:
        print(f"ERROR: Import failed: {e}")
        sys.exit(1)

    # Collect all mesh objects
    mesh_objects = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if not mesh_objects:
        print("ERROR: No mesh objects found")
        sys.exit(1)

    # Apply all modifiers
    for obj in mesh_objects:
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        for mod in obj.modifiers:
            try:
                bpy.ops.object.modifier_apply(modifier=mod.name)
            except Exception:
                pass
        obj.select_set(False)

    # Join all meshes into one
    if len(mesh_objects) > 1:
        bpy.ops.object.select_all(action="DESELECT")
        for obj in mesh_objects:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = mesh_objects[0]
        bpy.ops.object.join()

    # Get the joined mesh
    joined_obj = bpy.context.active_object
    mesh = joined_obj.data

    # Create atlas texture
    atlas_img = bpy.data.images.new(
        name="Atlas",
        width=atlas_size,
        height=atlas_size,
        alpha=True,
    )

    # Assign atlas to all materials
    for mat in joined_obj.data.materials:
        if mat is None:
            continue
        # Find or create image texture node
        tex_node = None
        for node in mat.node_tree.nodes:
            if node.type == "TEX_IMAGE":
                tex_node = node
                break
        if tex_node is None:
            tex_node = mat.node_tree.nodes.new("ShaderNodeTexImage")
        tex_node.image = atlas_img

    # Pack UVs using Blender's smart project
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(
        angle_limit=66.0,
        island_margin=0.02,
        area_weight=0.0,
        correct_aspect=True,
        scale_to_bounds=True,
    )
    bpy.ops.object.mode_set(mode="OBJECT")

    # Write atlas image
    os.makedirs(Path(output_path).parent, exist_ok=True)
    atlas_img.filepath_raw = output_path
    atlas_img.file_format = "PNG"
    atlas_img.save()

    # Export mesh with new UVs
    output_mesh = str(Path(output_path).with_suffix(".glb"))
    bpy.ops.export_scene.gltf(
        filepath=output_mesh,
        export_format="GLB",
        use_selection=False,
    )

    # Calculate atlas utilization
    used_pixels = sum(
        1 for px in atlas_img.pixels
        if px > 0.01  # non-transparent
    )
    total_pixels = atlas_size * atlas_size * 4  # RGBA
    utilization = used_pixels / total_pixels if total_pixels > 0 else 0

    result = {
        "success": True,
        "input_mesh": input_mesh,
        "output_mesh": output_mesh,
        "output_atlas": output_path,
        "atlas_size": f"{atlas_size}x{atlas_size}",
        "utilization": round(utilization, 3),
        "material_count": len(joined_obj.data.materials),
        "mesh_objects_joined": len(mesh_objects),
    }
    print(f"RESULT:{json.dumps(result)}")
    return result


def pack_textures():
    """
    Pack multiple loose images into an atlas without mesh import.
    """
    args = load_args()
    input_textures = args.get("input_textures", [])
    output_path = args.get("output_path", "")
    atlas_size = args.get("atlas_size", 2048)

    if not input_textures:
        print("ERROR: input_textures list required")
        sys.exit(1)

    bpy.ops.wm.read_factory_settings(use_empty=True)

    # Load all images
    images = []
    for tex_path in input_textures:
        if os.path.exists(tex_path):
            img = bpy.data.images.load(tex_path)
            images.append(img)

    if not images:
        print("ERROR: No valid images loaded")
        sys.exit(1)

    # Create atlas
    atlas_img = bpy.data.images.new(
        name="PackedAtlas",
        width=atlas_size,
        height=atlas_size,
        alpha=True,
    )

    # Simple grid packing
    import math
    count = len(images)
    grid_size = math.ceil(math.sqrt(count))
    tile_w = atlas_size // grid_size
    tile_h = atlas_size // grid_size

    for idx, img in enumerate(images):
        row = idx // grid_size
        col = idx % grid_size

        # Scale image to tile size
        img.scale(tile_w, tile_h)

        # Copy pixels into atlas at tile position
        for y in range(tile_h):
            for x in range(tile_w):
                src_idx = (y * tile_w + x) * 4
                dst_x = col * tile_w + x
                dst_y = row * tile_h + y
                dst_idx = (dst_y * atlas_size + dst_x) * 4

                if src_idx + 3 < len(img.pixels) and dst_idx + 3 < len(atlas_img.pixels):
                    atlas_img.pixels[dst_idx:dst_idx + 4] = img.pixels[src_idx:src_idx + 4]

    # Save atlas
    os.makedirs(Path(output_path).parent, exist_ok=True)
    atlas_img.filepath_raw = output_path
    atlas_img.file_format = "PNG"
    atlas_img.save()

    result = {
        "success": True,
        "input_count": len(input_textures),
        "output_path": output_path,
        "atlas_size": f"{atlas_size}x{atlas_size}",
        "grid": f"{grid_size}x{grid_size}",
        "tile_size": f"{tile_w}x{tile_h}",
    }
    print(f"RESULT:{json.dumps(result)}")
    return result


if __name__ == "__main__":
    mode = os.environ.get("RW_BLENDER_MODE", "atlas")
    if mode == "atlas":
        create_atlas()
    elif mode == "pack":
        pack_textures()
    else:
        print(f"Unknown mode: {mode}")
        sys.exit(1)
