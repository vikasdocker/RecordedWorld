"""
Blender Procedural Tree Generator
Generates realistic tree models and exports as glTF.
Run: blender --background --python generate_trees.py
"""
import bpy
import bmesh
import math
import random
import os
import json
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent / "public" / "models"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

random.seed(123)

def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for col in bpy.data.collections:
        bpy.data.collections.remove(col)
    for mat in bpy.data.materials:
        bpy.data.materials.remove(mat)
    for mesh in bpy.data.meshes:
        bpy.data.meshes.remove(mesh)

def make_material(name, color, roughness=0.8, alpha=1.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    if alpha < 1.0:
        mat.blend_method = 'HASHED' if hasattr(mat, 'blend_method') else 'OPAQUE'
    return mat

def create_deciduous_tree(name, trunk_h=2.5, canopy_r=1.5, trunk_r=0.12):
    collection = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(collection)

    bark_mat = make_material(f"{name}_bark", (0.35, 0.22, 0.12), roughness=0.95)
    leaf_mat = make_material(f"{name}_leaf", (0.18 + random.uniform(-0.05, 0.05), 0.45 + random.uniform(-0.1, 0.1), 0.15), roughness=0.75)

    bpy.ops.mesh.primitive_cone_add(radius1=trunk_r * 1.3, radius2=trunk_r * 0.7, depth=trunk_h, vertices=8)
    trunk = bpy.context.active_object
    trunk.name = f"{name}_trunk"
    trunk.location = (0, 0, trunk_h / 2)
    trunk.data.materials.append(bark_mat)
    for c in trunk.users_collection:
        c.objects.unlink(trunk)
    collection.objects.link(trunk)

    for i in range(3):
        layer_r = canopy_r * (1.0 - i * 0.2)
        layer_h = 1.2 - i * 0.2
        layer_y = trunk_h + 0.3 + i * 0.8
        bpy.ops.mesh.primitive_cone_add(radius1=layer_r, radius2=layer_r * 0.15, depth=layer_h, vertices=8)
        foliage = bpy.context.active_object
        foliage.name = f"{name}_foliage_{i}"
        foliage.location = (0, 0, layer_y)
        foliage.data.materials.append(leaf_mat)
        for c in foliage.users_collection:
            c.objects.unlink(foliage)
        collection.objects.link(foliage)

    bpy.ops.mesh.primitive_uv_sphere_add(radius=canopy_r * 0.6, segments=8, ring_count=6)
    top = bpy.context.active_object
    top.name = f"{name}_top"
    top.location = (0, 0, trunk_h + canopy_r * 0.8)
    top.scale = (1, 1, 0.7)
    top.data.materials.append(leaf_mat)
    for c in top.users_collection:
        c.objects.unlink(top)
    collection.objects.link(top)

    return collection

def create_conifer_tree(name, trunk_h=3.0, canopy_r=1.0):
    collection = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(collection)

    bark_mat = make_material(f"{name}_bark", (0.3, 0.2, 0.1), roughness=0.95)
    needle_mat = make_material(f"{name}_needle", (0.1 + random.uniform(-0.03, 0.03), 0.35 + random.uniform(-0.05, 0.05), 0.12), roughness=0.8)

    bpy.ops.mesh.primitive_cone_add(radius1=0.1, radius2=0.06, depth=trunk_h, vertices=6)
    trunk = bpy.context.active_object
    trunk.name = f"{name}_trunk"
    trunk.location = (0, 0, trunk_h / 2)
    trunk.data.materials.append(bark_mat)
    for c in trunk.users_collection:
        c.objects.unlink(trunk)
    collection.objects.link(trunk)

    layers = 5
    for i in range(layers):
        layer_r = canopy_r * (1.0 - i / layers)
        layer_h = 1.0
        layer_z = trunk_h * 0.4 + i * (trunk_h * 0.5 / layers)
        bpy.ops.mesh.primitive_cone_add(radius1=layer_r, radius2=0.05, depth=layer_h, vertices=7)
        foliage = bpy.context.active_object
        foliage.name = f"{name}_needle_{i}"
        foliage.location = (0, 0, layer_z + layer_h / 2)
        foliage.data.materials.append(needle_mat)
        for c in foliage.users_collection:
            c.objects.unlink(foliage)
        collection.objects.link(foliage)

    return collection

def create_palm_tree(name, trunk_h=3.5):
    collection = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(collection)

    bark_mat = make_material(f"{name}_bark", (0.45, 0.3, 0.15), roughness=0.9)
    leaf_mat = make_material(f"{name}_leaf", (0.15, 0.5, 0.12), roughness=0.7)

    bpy.ops.mesh.primitive_cylinder_add(radius=0.12, depth=trunk_h, vertices=8)
    trunk = bpy.context.active_object
    trunk.name = f"{name}_trunk"
    trunk.location = (0, 0, trunk_h / 2)
    trunk.data.materials.append(bark_mat)
    for c in trunk.users_collection:
        c.objects.unlink(trunk)
    collection.objects.link(trunk)

    for i in range(7):
        angle = (i / 7) * math.pi * 2
        bpy.ops.mesh.primitive_plane_add(size=2.0)
        frond = bpy.context.active_object
        frond.name = f"{name}_frond_{i}"
        frond.scale = (0.2, 1.0, 1)
        frond.location = (
            math.cos(angle) * 0.5,
            math.sin(angle) * 0.5,
            trunk_h + 0.2
        )
        frond.rotation_euler = (math.pi / 3, 0, angle)
        frond.data.materials.append(leaf_mat)
        for c in frond.users_collection:
            c.objects.unlink(frond)
        collection.objects.link(frond)

    return collection

def export_collection_gltf(collection, filepath):
    bpy.ops.object.select_all(action='DESELECT')
    for obj in collection.objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = collection.objects[0]
    bpy.ops.export_scene.gltf(
        filepath=str(filepath),
        use_selection=True,
        export_format='GLB',
        export_materials='EXPORT',
        export_apply=True,
    )
    bpy.ops.object.select_all(action='DESELECT')

def generate_all():
    clear_scene()

    trees = []

    for i in range(5):
        h = random.uniform(2.0, 3.5)
        r = random.uniform(1.2, 2.0)
        name = f"deciduous_{i}"
        col = create_deciduous_tree(name, trunk_h=h, canopy_r=r)
        export_collection_gltf(col, OUTPUT_DIR / f"{name}.glb")
        trees.append({"name": name, "type": "deciduous", "height": round(h, 1), "canopy_radius": round(r, 1), "file": f"{name}.glb"})
        print(f"  Generated {name}: h={h:.1f}, r={r:.1f}")

    for i in range(3):
        h = random.uniform(2.5, 4.0)
        r = random.uniform(0.8, 1.3)
        name = f"conifer_{i}"
        col = create_conifer_tree(name, trunk_h=h, canopy_r=r)
        export_collection_gltf(col, OUTPUT_DIR / f"{name}.glb")
        trees.append({"name": name, "type": "conifer", "height": round(h, 1), "canopy_radius": round(r, 1), "file": f"{name}.glb"})
        print(f"  Generated {name}: h={h:.1f}, r={r:.1f}")

    for i in range(2):
        h = random.uniform(3.0, 4.5)
        name = f"palm_{i}"
        col = create_palm_tree(name, trunk_h=h)
        export_collection_gltf(col, OUTPUT_DIR / f"{name}.glb")
        trees.append({"name": name, "type": "palm", "height": round(h, 1), "file": f"{name}.glb"})
        print(f"  Generated {name}: h={h:.1f}")

    manifest = {"version": 1, "trees": trees, "generated_by": "blender_tree_generator"}
    with open(OUTPUT_DIR / "trees.json", "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nGenerated {len(trees)} tree models in {OUTPUT_DIR}")

if __name__ == "__main__":
    generate_all()
