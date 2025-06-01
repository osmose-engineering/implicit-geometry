# stl_to_ifg.py
import argparse
import json
import trimesh
import os

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate a .ifg file (implicit‐geometry JSON) from an STL"
    )
    parser.add_argument(
        "--stl", dest="stl_path", required=True,
        help="Path to the input STL file"
    )
    parser.add_argument(
        "--out", dest="ifg_path", required=True,
        help="Path where the generated .ifg should be written"
    )
    parser.add_argument(
        "--units", dest="units", default="mm",
        help="Units string to store in metadata (default: mm)"
    )
    args = parser.parse_args()

    # Resolve the STL path and ensure it exists
    stl_path = os.path.abspath(args.stl_path)
    if not os.path.isfile(stl_path):
        print(f"Error: STL file not found at '{args.stl_path}' (resolved to '{stl_path}')")
        print("Please verify the path and try again.")
        exit(1)

    # 1) Attempt to load the STL (Trimesh or Scene)
    mesh_obj = trimesh.load(stl_path)
    # If load returns False or None, fallback to loading a Scene
    if mesh_obj is False or mesh_obj is None:
        scene = trimesh.load(stl_path)
        if isinstance(scene, trimesh.Scene) and scene.geometry:
            mesh = next(iter(scene.geometry.values()))
        else:
            raise ValueError(f"Failed to load a valid mesh from '{stl_path}'")
    elif isinstance(mesh_obj, trimesh.Trimesh):
        mesh = mesh_obj
    elif isinstance(mesh_obj, trimesh.Scene):
        if mesh_obj.geometry:
            mesh = next(iter(mesh_obj.geometry.values()))
        else:
            raise ValueError(f"Failed to load a valid mesh from '{stl_path}'")
    else:
        raise ValueError(f"Loaded object is not a mesh or scene: {type(mesh_obj)}")
    # Ensure the mesh is watertight; fill holes if not
    if not mesh.is_watertight:
        mesh.fill_holes()

    # 2) Compute the mesh bounds
    # mesh.bounds is a (2×3) array: [ [xmin,ymin,zmin], [xmax,ymax,zmax] ]
    min_corner, max_corner = mesh.bounds
    bounds = {
        "xmin": float(min_corner[0]),
        "xmax": float(max_corner[0]),
        "ymin": float(min_corner[1]),
        "ymax": float(max_corner[1]),
        "zmin": float(min_corner[2]),
        "zmax": float(max_corner[2])
    }

    # 3) Build the IFG document
    doc = {
        "metadata": {
            "format_version": "0.1",
            "units": args.units,
            "bounds": bounds
        },
        "nodes": [
            {
                "id": "mesh1",
                "type": "Mesh",
                "params": {
                    # Use the absolute path so the loader can find it
                    "filename": stl_path
                },
                "inputs": []
            }
        ]
    }

    # 4) Serialize to JSON and write to the output file
    ifg_path = os.path.abspath(args.ifg_path)
    with open(ifg_path, "w") as f:
        json.dump(doc, f, indent=2)

    print(f"Written IFG → {ifg_path}")