import os
import sys
import json
import math
import zipfile
import argparse
from PIL import Image
import trimesh

# Allow importing loader.py from parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from loader import load_ifg, build_evaluator

# -----------------------------------------------
# PARAMETERS (Overrides via CLI flags)
# -----------------------------------------------
DEFAULT_IFG_PATH      = "examples/cube.ifg"
DEFAULT_OUTPUT_DIR    = "output_slices"
DEFAULT_LAYER_THICK   = 0.1    # mm
DEFAULT_RES_X         = 200
DEFAULT_RES_Y         = 200
DEFAULT_FORMAT        = "ctb"  # or "pwsz"

# -----------------------------------------------
# FUNCTION: Generate PNG slices from IFG
# -----------------------------------------------
def generate_png_slices(ifg_path, output_dir, layer_thickness, res_x, res_y):
    """
    1) Load IFG and build evaluator
    2) Sample implicit field for each Z-slice, write PNGs to output_dir
    3) Return bounds and number of layers
    """
    doc     = load_ifg(ifg_path)
    eval_fn = build_evaluator(doc["nodes"])
    meta    = doc.get("metadata", {})
    bounds  = meta.get("bounds", {
        "xmin": -5, "xmax": 5,
        "ymin": -5, "ymax": 5,
        "zmin": -5, "zmax": 5
    })

    zmin, zmax = bounds["zmin"], bounds["zmax"]
    num_layers = int(math.ceil((zmax - zmin) / layer_thickness)) + 1
    os.makedirs(output_dir, exist_ok=True)

    print(f"→ Generating {num_layers} PNG slices from z={zmin} to {zmax}")
    for i in range(num_layers):
        z = zmin + i * layer_thickness
        img = Image.new("L", (res_x, res_y))
        for ix in range(res_x):
            for iy in range(res_y):
                x = bounds["xmin"] + ix * (bounds["xmax"] - bounds["xmin"]) / (res_x - 1)
                y = bounds["ymin"] + iy * (bounds["ymax"] - bounds["ymin"]) / (res_y - 1)
                field_val = eval_fn(x, y, z)
                img.putpixel((ix, res_y - 1 - iy), 255 if field_val <= 0 else 0)

        slice_path = os.path.join(output_dir, f"slice_{i:04d}.png")
        img.save(slice_path)

    return bounds, num_layers

# -----------------------------------------------
# WRAPPER: pack PNG slices into a .pwsz archive
# -----------------------------------------------
def wrap_to_pwsz(slice_dir, output_file, bounds, res_x, res_y, layer_thickness):
    """
    Write a .pwsz ZIP with:
      - Info.json
      - Body/0000, Body/0001, … (no extension), raw PNG bytes
    """
    info = {
        "ResX": res_x,
        "ResY": res_y,
        "LayerThickness": layer_thickness,
        "FlipX": False,
        "FlipY": False,
        "Invert": False,
        "OriginX": bounds["xmin"],
        "OriginY": bounds["ymin"],
        "PixelSizeX": (bounds["xmax"] - bounds["xmin"]) / (res_x - 1),
        "PixelSizeY": (bounds["ymax"] - bounds["ymin"]) / (res_y - 1)
    }

    with zipfile.ZipFile(output_file, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("Info.json", json.dumps(info))
        png_files = sorted(f for f in os.listdir(slice_dir) if f.endswith(".png"))
        for idx, fname in enumerate(png_files):
            layer_name = f"{idx:04d}"
            arcname = f"Body/{layer_name}"
            zf.write(os.path.join(slice_dir, fname), arcname)

    print(f"✓ Packaged {len(png_files)} slices into {output_file} (PWSZ format)")

# -----------------------------------------------
# WRAPPER: pack PNG slices into a .ctb archive
# -----------------------------------------------
def wrap_to_ctb(slice_dir, output_file, bounds, res_x, res_y, layer_thickness):
    """
    Write a .ctb ZIP with:
      - Info.json (CTB-specific keys)
      - Body/0000.png, Body/0001.png, …
    """
    info = {
        "Version":           1,
        "Width":             res_x,
        "Height":            res_y,
        "LayerHeight":       layer_thickness,
        "ExposureTime":      2.0,
        "BottomLayerCount":  5,
        "BottomExposureTime": 30.0,
        "OffTime":           0.0,
        "TiltCompensation":  0,
        "OriginX":           bounds["xmin"],
        "OriginY":           bounds["ymin"],
        "PixelSizeX":        (bounds["xmax"] - bounds["xmin"]) / (res_x - 1),
        "PixelSizeY":        (bounds["ymax"] - bounds["ymin"]) / (res_y - 1)
    }

    with zipfile.ZipFile(output_file, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("Info.json", json.dumps(info))
        png_files = sorted(f for f in os.listdir(slice_dir) if f.endswith(".png"))
        for idx, fname in enumerate(png_files):
            layer_name = f"{idx:04d}.png"
            arcname = f"Body/{layer_name}"
            zf.write(os.path.join(slice_dir, fname), arcname)

    print(f"✓ Packaged {len(png_files)} slices into {output_file} (CTB format)")

# -----------------------------------------------
# COMMAND-LINE INTERFACE
# -----------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Convert IFG → PNG slices → printer-compatible zip"
    )
    parser.add_argument(
        "--ifg", dest="ifg_path", default=DEFAULT_IFG_PATH,
        help="Path to the .ifg file (implicit geometry)."
    )
    parser.add_argument(
        "--out", dest="output_base", default="output",
        help="Base name for outputs (e.g. 'foo' → foo.ctb or foo.pwsz)."
    )
    parser.add_argument(
        "--dir", dest="slice_dir", default=DEFAULT_OUTPUT_DIR,
        help="Directory for intermediate PNG slices."
    )
    parser.add_argument(
        "--slice_thick", dest="layer_thickness", type=float,
        default=DEFAULT_LAYER_THICK, help="Layer thickness in mm."
    )
    parser.add_argument(
        "--resx", dest="res_x", type=int, default=DEFAULT_RES_X,
        help="Horizontal resolution (pixels per layer)."
    )
    parser.add_argument(
        "--resy", dest="res_y", type=int, default=DEFAULT_RES_Y,
        help="Vertical resolution (pixels per layer)."
    )
    parser.add_argument(
        "--format", dest="fmt", choices=["pwsz", "ctb"],
        default=DEFAULT_FORMAT,
        help="Choose 'pwsz' (Anycubic) or 'ctb' (ChituBox)."
    )

    args = parser.parse_args()

    # Load IFG document to inspect metadata and nodes
    doc = load_ifg(args.ifg_path)
    meta = doc.get("metadata", {})

    # If no bounds are provided, infer from any Mesh node
    if "bounds" not in meta:
        mesh_node = next((n for n in doc["nodes"] if n["type"] == "Mesh"), None)
        if mesh_node is None:
            raise RuntimeError("No bounds in metadata and no Mesh node to infer them from.")
        mesh_path = mesh_node["params"]["filename"]
        mesh = trimesh.load(mesh_path)
        if not mesh.is_watertight:
            mesh = mesh.copy().fill_holes()
        min_corner, max_corner = mesh.bounds
        meta["bounds"] = {
            "xmin": float(min_corner[0]),
            "xmax": float(max_corner[0]),
            "ymin": float(min_corner[1]),
            "ymax": float(max_corner[1]),
            "zmin": float(min_corner[2]),
            "zmax": float(max_corner[2])
        }
        doc["metadata"] = meta

    # Now generate slices using (possibly) updated bounds
    bounds, num_layers = generate_png_slices(
        args.ifg_path, args.slice_dir,
        args.layer_thickness, args.res_x, args.res_y
    )

    if args.fmt == "pwsz":
        output_file = f"{args.output_base}.pwsz"
        wrap_to_pwsz(
            slice_dir=args.slice_dir,
            output_file=output_file,
            bounds=bounds,
            res_x=args.res_x,
            res_y=args.res_y,
            layer_thickness=args.layer_thickness
        )
    else:  # args.fmt == "ctb"
        output_file = f"{args.output_base}.ctb"
        wrap_to_ctb(
            slice_dir=args.slice_dir,
            output_file=output_file,
            bounds=bounds,
            res_x=args.res_x,
            res_y=args.res_y,
            layer_thickness=args.layer_thickness
        )

    print("✅ Done.")