"""
Blender Procedural Building Generator
Generates realistic NYC-style buildings and exports as glTF.
Run: blender --background --python generate_buildings.py
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

random.seed(42)

def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for col in bpy.data.collections:
        bpy.data.collections.remove(col)
    for mat in bpy.data.materials:
        bpy.data.materials.remove(mat)
    for mesh in bpy.data.meshes:
        bpy.data.meshes.remove(mesh)

def make_material(name, color, roughness=0.8, metallic=0.0, emission=None):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    if emission:
        bsdf.inputs["Emission Color"].default_value = (*emission, 1.0)
        bsdf.inputs["Emission Strength"].default_value = 0.3
    return mat

def create_residential_building(name, width, depth, floors, style="brick"):
    """Create a residential building with windows, ledges, and roof details."""
    collection = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(collection)
    total_h = floors * 3.2

    if style == "brick":
        wall_color = (0.65 + random.uniform(-0.05, 0.05), 0.45 + random.uniform(-0.05, 0.05), 0.35)
        wall_mat = make_material(f"{name}_wall", wall_color, roughness=0.9)
    elif style == "stone":
        wall_color = (0.6 + random.uniform(-0.05, 0.05), 0.58 + random.uniform(-0.05, 0.05), 0.55)
        wall_mat = make_material(f"{name}_wall", wall_color, roughness=0.85)
    else:
        wall_color = (0.75 + random.uniform(-0.08, 0.08), 0.72 + random.uniform(-0.08, 0.08), 0.68)
        wall_mat = make_material(f"{name}_wall", wall_color, roughness=0.8)

    bpy.ops.mesh.primitive_cube_add(size=1)
    body = bpy.context.active_object
    body.name = f"{name}_body"
    body.scale = (width, depth, total_h)
    body.location = (0, 0, total_h / 2)
    body.data.materials.append(wall_mat)
    body.display_type = 'TEXTURED'
    for c in body.users_collection:
        c.objects.unlink(body)
    collection.objects.link(body)

    window_mat = make_material(f"{name}_window", (0.4, 0.55, 0.7), roughness=0.15, metallic=0.7, emission=(0.3, 0.4, 0.5))
    trim_mat = make_material(f"{name}_trim", (0.7, 0.65, 0.55), roughness=0.7, metallic=0.05)

    win_w = 0.6
    win_h = 1.0
    spacing = 2.2

    for face_dir, face_axis, face_size in [
        ('+x', 0, width), ('-x', 0, width),
        ('+y', 1, depth), ('-y', 1, depth),
    ]:
        count = max(1, int(face_size / spacing))
        for f in range(floors):
            y_base = f * 3.2 + 0.7
            for wi in range(count):
                offset = -face_size / 2 + spacing / 2 + wi * spacing
                bpy.ops.mesh.primitive_plane_add(size=1)
                win = bpy.context.active_object
                win.name = f"{name}_win"
                win.scale = (win_w / 2, win_h / 2, 1)
                win.data.materials.append(window_mat)

                if face_dir == '+x':
                    win.location = (width / 2 + 0.01, offset, y_base + win_h / 2)
                    win.rotation_euler = (0, math.pi / 2, 0)
                elif face_dir == '-x':
                    win.location = (-width / 2 - 0.01, offset, y_base + win_h / 2)
                    win.rotation_euler = (0, -math.pi / 2, 0)
                elif face_dir == '+y':
                    win.location = (offset, depth / 2 + 0.01, y_base + win_h / 2)
                    win.rotation_euler = (0, 0, 0)
                else:
                    win.location = (offset, -depth / 2 - 0.01, y_base + win_h / 2)
                    win.rotation_euler = (0, 0, math.pi)

                for c in win.users_collection:
                    c.objects.unlink(win)
                collection.objects.link(win)

    for f in range(floors + 1):
        bpy.ops.mesh.primitive_cube_add(size=1)
        ledge = bpy.context.active_object
        ledge.name = f"{name}_ledge"
        ledge.scale = (width / 2 + 0.08, depth / 2 + 0.08, 0.1)
        ledge.location = (0, 0, f * 3.2)
        ledge.data.materials.append(trim_mat)
        for c in ledge.users_collection:
            c.objects.unlink(ledge)
        collection.objects.link(ledge)

    roof_mat = make_material(f"{name}_roof", (0.3, 0.3, 0.3), roughness=0.9)
    bpy.ops.mesh.primitive_cube_add(size=1)
    roof = bpy.context.active_object
    roof.name = f"{name}_roof"
    roof.scale = (width / 2 + 0.15, depth / 2 + 0.15, 0.08)
    roof.location = (0, 0, total_h + 0.04)
    roof.data.materials.append(roof_mat)
    for c in roof.users_collection:
        c.objects.unlink(roof)
    collection.objects.link(roof)

    if random.random() > 0.4:
        ac_mat = make_material(f"{name}_ac", (0.5, 0.5, 0.5), roughness=0.6, metallic=0.4)
        for _ in range(random.randint(1, 4)):
            bpy.ops.mesh.primitive_cube_add(size=0.5)
            ac = bpy.context.active_object
            ac.name = f"{name}_ac"
            ac.scale = (1, 0.8, 0.8)
            ac.location = (
                random.uniform(-width / 3, width / 3),
                random.uniform(-depth / 3, depth / 3),
                total_h + 0.3
            )
            ac.data.materials.append(ac_mat)
            for c in ac.users_collection:
                c.objects.unlink(ac)
            collection.objects.link(ac)

    if random.random() > 0.5:
        bpy.ops.mesh.primitive_cylinder_add(radius=0.25, depth=1.5)
        tower = bpy.context.active_object
        tower.name = f"{name}_tower"
        tower.location = (
            random.uniform(-width / 3, width / 3),
            random.uniform(-depth / 3, depth / 3),
            total_h + 0.75
        )
        tower_mat = make_material(f"{name}_tower_mat", (0.45, 0.32, 0.2), roughness=0.9)
        tower.data.materials.append(tower_mat)
        for c in tower.users_collection:
            c.objects.unlink(tower)
        collection.objects.link(tower)

    return collection

def create_office_building(name, width, depth, floors):
    """Create a glass-and-steel office building."""
    collection = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(collection)
    total_h = floors * 3.5

    glass_mat = make_material(f"{name}_glass", (0.3, 0.4, 0.55), roughness=0.05, metallic=0.8, emission=(0.1, 0.15, 0.2))
    steel_mat = make_material(f"{name}_steel", (0.4, 0.4, 0.42), roughness=0.3, metallic=0.9)

    bpy.ops.mesh.primitive_cube_add(size=1)
    body = bpy.context.active_object
    body.name = f"{name}_body"
    body.scale = (width, depth, total_h)
    body.location = (0, 0, total_h / 2)
    body.data.materials.append(glass_mat)
    for c in body.users_collection:
        c.objects.unlink(body)
    collection.objects.link(body)

    for f in range(floors + 1):
        bpy.ops.mesh.primitive_cube_add(size=1)
        frame = bpy.context.active_object
        frame.name = f"{name}_frame"
        frame.scale = (width / 2 + 0.05, depth / 2 + 0.05, 0.06)
        frame.location = (0, 0, f * 3.5)
        frame.data.materials.append(steel_mat)
        for c in frame.users_collection:
            c.objects.unlink(frame)
        collection.objects.link(frame)

    for axis, size in [('x', width), ('y', depth)]:
        for side in [-1, 1]:
            bpy.ops.mesh.primitive_cube_add(size=1)
            col = bpy.context.active_object
            col.name = f"{name}_col"
            if axis == 'x':
                col.scale = (0.08, depth / 2, total_h / 2)
                col.location = (side * width / 2, 0, total_h / 2)
            else:
                col.scale = (width / 2, 0.08, total_h / 2)
                col.location = (0, side * depth / 2, total_h / 2)
            col.data.materials.append(steel_mat)
            for c in col.users_collection:
                c.objects.unlink(col)
            collection.objects.link(col)

    roof_mat = make_material(f"{name}_roof", (0.25, 0.25, 0.28), roughness=0.8)
    bpy.ops.mesh.primitive_cube_add(size=1)
    roof = bpy.context.active_object
    roof.name = f"{name}_roof"
    roof.scale = (width / 2 + 0.2, depth / 2 + 0.2, 0.1)
    roof.location = (0, 0, total_h + 0.05)
    roof.data.materials.append(roof_mat)
    for c in roof.users_collection:
        c.objects.unlink(roof)
    collection.objects.link(roof)

    if floors >= 5 and random.random() > 0.5:
        bpy.ops.mesh.primitive_cube_add(size=1)
        mech = bpy.context.active_object
        mech.name = f"{name}_mech"
        mw = random.uniform(1.5, 3)
        md = random.uniform(1.5, 3)
        mh = random.uniform(1.5, 3)
        mech.scale = (mw / 2, md / 2, mh / 2)
        mech.location = (random.uniform(-width / 4, width / 4), random.uniform(-depth / 4, depth / 4), total_h + mh / 2 + 0.1)
        mech_mat = make_material(f"{name}_mech_mat", (0.45, 0.45, 0.48), roughness=0.7, metallic=0.3)
        mech.data.materials.append(mech_mat)
        for c in mech.users_collection:
            c.objects.unlink(mech)
        collection.objects.link(mech)

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

    bpy.context.scene.render.engine = 'CYCLES'
    bpy.context.scene.cycles.samples = 1

    buildings = []

    residential_styles = ["brick", "stone", "stucco"]
    for i in range(8):
        w = random.uniform(6, 14)
        d = random.uniform(6, 14)
        floors = random.randint(2, 8)
        style = random.choice(residential_styles)
        name = f"residential_{i}"
        col = create_residential_building(name, w, d, floors, style)
        export_collection_gltf(col, OUTPUT_DIR / f"{name}.glb")
        buildings.append({
            "name": name, "type": "residential",
            "width": round(w, 1), "depth": round(d, 1), "floors": floors,
            "style": style, "file": f"{name}.glb"
        })
        print(f"  Generated {name}: {w:.1f}x{d:.1f}, {floors} floors, {style}")

    for i in range(5):
        w = random.uniform(10, 20)
        d = random.uniform(10, 20)
        floors = random.randint(5, 15)
        name = f"office_{i}"
        col = create_office_building(name, w, d, floors)
        export_collection_gltf(col, OUTPUT_DIR / f"{name}.glb")
        buildings.append({
            "name": name, "type": "office",
            "width": round(w, 1), "depth": round(d, 1), "floors": floors,
            "file": f"{name}.glb"
        })
        print(f"  Generated {name}: {w:.1f}x{d:.1f}, {floors} floors, office")

    manifest = {
        "version": 1,
        "buildings": buildings,
        "generated_by": "blender_procedural_pipeline",
        "output_dir": str(OUTPUT_DIR),
    }
    with open(OUTPUT_DIR / "buildings.json", "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nGenerated {len(buildings)} building models in {OUTPUT_DIR}")
    print(f"Manifest: {OUTPUT_DIR / 'buildings.json'}")

if __name__ == "__main__":
    generate_all()
