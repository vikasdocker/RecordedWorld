"""
Blender Asset Pipeline Runner
Runs all asset generation scripts in Blender background mode.
"""
import subprocess
import sys
import os
from pathlib import Path

BLENDER_PATH = r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
SCRIPTS_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPTS_DIR.parent / "public" / "models"

def run_blender_script(script_path):
    print(f"\n{'='*60}")
    print(f"Running: {script_path.name}")
    print(f"{'='*60}")

    cmd = [
        BLENDER_PATH,
        "--background",
        "--python", str(script_path),
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=300,
        cwd=str(SCRIPTS_DIR),
    )

    if result.stdout:
        print(result.stdout)
    if result.stderr:
        for line in result.stderr.splitlines():
            if "Error" in line or "error" in line:
                print(f"  ERROR: {line}")

    if result.returncode != 0:
        print(f"  Script failed with return code {result.returncode}")
        return False

    return True

def main():
    print("Recorded World - Blender Asset Pipeline")
    print(f"Blender: {BLENDER_PATH}")
    print(f"Output: {OUTPUT_DIR}")

    if not os.path.exists(BLENDER_PATH):
        print(f"ERROR: Blender not found at {BLENDER_PATH}")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    scripts = [
        SCRIPTS_DIR / "generate_buildings.py",
        SCRIPTS_DIR / "generate_trees.py",
    ]

    results = {}
    for script in scripts:
        if script.exists():
            results[script.name] = run_blender_script(script)
        else:
            print(f"Script not found: {script}")
            results[script.name] = False

    print(f"\n{'='*60}")
    print("Pipeline Results:")
    for name, success in results.items():
        status = "OK" if success else "FAILED"
        print(f"  {name}: {status}")

    glb_files = list(OUTPUT_DIR.glob("*.glb"))
    json_files = list(OUTPUT_DIR.glob("*.json"))
    print(f"\nGenerated files:")
    print(f"  GLB models: {len(glb_files)}")
    print(f"  JSON manifests: {len(json_files)}")

    if all(results.values()):
        print("\nPipeline completed successfully!")
    else:
        print("\nSome scripts failed. Check output above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
