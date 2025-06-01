# stl_to_ifg.py
import argparse
import json
import trimesh

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

    # 1) Load the mesh and compute its bounds
    mesh = trimesh.load(args.stl_path)
    if not mesh.is_watertight:
        mesh = mesh.copy().fill_holes()

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

    # 2) Build the IFG document
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
                    # Use a relative or absolute path—whatever your loader expects
                    "filename": args.stl_path
                },
                "inputs": []
            }
        ]
    }

    # 3) Serialize to JSON and write to file
    with open(args.ifg_path, "w") as f:
        json.dump(doc, f, indent=2)
    print(f"Written IFG → {args.ifg_path}")