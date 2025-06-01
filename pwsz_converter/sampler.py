import os
import sys
import json
import math
import zipfile
import argparse
from PIL import Image
from PIL import ImageDraw
import shapely.geometry as geom
import trimesh
import numpy as np
from shapely.geometry import Polygon, Point
from shapely.ops import unary_union

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
    import numpy as np

    doc = load_ifg(ifg_path)
    meta = doc.get("metadata", {})

    # Ensure bounds exist and contain all required keys; otherwise infer from Mesh node
    bounds = meta.get("bounds", {})
    required = ["xmin", "xmax", "ymin", "ymax", "zmin", "zmax"]
    if not all(k in bounds for k in required):
        mesh_node = next((n for n in doc["nodes"] if n["type"] == "Mesh"), None)
        if mesh_node is None:
            raise RuntimeError("Cannot infer bounds: no Mesh node found in IFG.")
        mesh_path = mesh_node["params"]["filename"]
        mesh = trimesh.load(mesh_path)
        if not mesh.is_watertight:
            mesh.fill_holes()
        min_corner, max_corner = mesh.bounds
        bounds = {
            "xmin": float(min_corner[0]),
            "xmax": float(max_corner[0]),
            "ymin": float(min_corner[1]),
            "ymax": float(max_corner[1]),
            "zmin": float(min_corner[2]),
            "zmax": float(max_corner[2])
        }
        meta["bounds"] = bounds
        doc["metadata"] = meta

    zmin, zmax = bounds["zmin"], bounds["zmax"]
    num_layers = int(math.ceil((zmax - zmin) / layer_thickness)) + 1
    os.makedirs(output_dir, exist_ok=True)

    print(f"→ Generating {num_layers} PNG slices from z={zmin} to {zmax}")

    # Precompute XY grid for gyroid evaluation if needed
    xs = np.linspace(bounds["xmin"], bounds["xmax"], res_x)
    ys = np.linspace(bounds["ymin"], bounds["ymax"], res_y)
    X, Y = np.meshgrid(xs, ys)  # shape (res_y, res_x)

    # Detect if root node is a single Mesh for fast planar slicing
    root_node = doc["nodes"][-1]
    is_mesh_root = (root_node["type"] == "Mesh")

    if is_mesh_root:
        # Load mesh once
        mesh_path = root_node["params"]["filename"]
        mesh = trimesh.load(mesh_path)
        if not mesh.is_watertight:
            mesh.fill_holes()

    # For CSG cases (e.g., shell + gyroid), prepare evaluator
    eval_fn = None
    if not is_mesh_root:
        eval_fn = build_evaluator(doc["nodes"])
        # Identify gyroid node parameters if present
        gyroid_node = next((n for n in doc["nodes"] if n["type"] == "Lattice"), None)
        if gyroid_node:
            cell = gyroid_node["params"]["cell_size"]
            thickness = gyroid_node["params"]["thickness"]
            if isinstance(cell, (int, float)):
                cx = cy = cz = cell
            else:
                cx, cy, cz = cell
        else:
            cell = None

    # For CSG hybrid: prepare benchy_mesh and shrink_mesh once before the loop
    if not is_mesh_root:
        # Prepare meshes once before the loop
        benchy_node = next((n for n in doc["nodes"] if n["type"] == "Mesh"), None)
        shrink_node = next((n for n in doc["nodes"] if n["type"] == "Transform"), None)
        benchy_mesh = trimesh.load(benchy_node["params"]["filename"])
        if not benchy_mesh.is_watertight:
            benchy_mesh.fill_holes()
        scale_vals = shrink_node["params"]["scale"]
        shrink_mesh = benchy_mesh.copy()
        shrink_mesh.apply_scale(scale_vals)

    for i in range(num_layers):
        print(f"Processing layer {i+1}/{num_layers}", end="\r", flush=True)
        z = zmin + i * layer_thickness

        if is_mesh_root:
            # Perform a planar section at z
            section = mesh.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
            if section is None:
                img = Image.new("L", (res_x, res_y))
            else:
                planar = section.to_2D()[0]
                img = Image.new("L", (res_x, res_y))
                draw = ImageDraw.Draw(img)

                scale_x = (res_x - 1) / (bounds["xmax"] - bounds["xmin"])
                scale_y = (res_y - 1) / (bounds["ymax"] - bounds["ymin"])

                try:
                    polygons = planar.polygons_full
                except ModuleNotFoundError:
                    raise RuntimeError(
                        "networkx is required for filled-polygon slicing. "
                        "Please install it via 'pip install networkx' and retry."
                    )

                for polygon in polygons:
                    exterior = [
                        (
                            int((x - bounds["xmin"]) * scale_x),
                            int((bounds["ymax"] - y) * scale_y)
                        )
                        for x, y in polygon.exterior.coords
                    ]
                    draw.polygon(exterior, fill=255)
                    for interior in polygon.interiors:
                        interior_pts = [
                            (
                                int((x - bounds["xmin"]) * scale_x),
                                int((bounds["ymax"] - y) * scale_y)
                            )
                            for x, y in interior.coords
                        ]
                        draw.polygon(interior_pts, fill=0)

        else:
            # Hybrid CSG slicing: shell (subtract) + gyroid
            # 2) Get planar sections (benchy and shrink) at this z-level
            benchy_section = benchy_mesh.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
            shrink_section = shrink_mesh.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])

            # Convert to planar 2D Path and collect polygons
            benchy_polygons = []
            if benchy_section is not None:
                be_planar = benchy_section.to_2D()[0]
                try:
                    benchy_polygons = [
                        Polygon(p.exterior.coords, [h.coords for h in p.interiors])
                        for p in be_planar.polygons_full
                    ]
                except ModuleNotFoundError:
                    raise RuntimeError(
                        "networkx is required for filled-polygon slicing. "
                        "Please install it via 'pip install networkx' and retry."
                    )

            shrink_polygons = []
            if shrink_section is not None:
                sh_planar = shrink_section.to_2D()[0]
                shrink_polygons = [
                    Polygon(p.exterior.coords, [h.coords for h in p.interiors])
                    for p in sh_planar.polygons_full
                ]

            # 3) Rasterize shrink_polygons to shrink_mask via PIL
            scale_x = (res_x - 1) / (bounds["xmax"] - bounds["xmin"])
            scale_y = (res_y - 1) / (bounds["ymax"] - bounds["ymin"])
            shrink_img = Image.new("L", (res_x, res_y), 0)
            shr_draw  = ImageDraw.Draw(shrink_img)
            for poly in shrink_polygons:
                # Draw exterior
                ext_pts = [
                    (
                        int((px - bounds["xmin"]) * scale_x),
                        int((bounds["ymax"] - py) * scale_y)
                    )
                    for (px, py) in poly.exterior.coords
                ]
                shr_draw.polygon(ext_pts, fill=255)
                # Draw holes
                for interior in poly.interiors:
                    hole_pts = [
                        (
                            int((px - bounds["xmin"]) * scale_x),
                            int((bounds["ymax"] - py) * scale_y)
                        )
                        for (px, py) in interior.coords
                    ]
                    shr_draw.polygon(hole_pts, fill=0)
            shrink_mask = np.array(shrink_img)

            # 4) Rasterize benchy_polygons via PIL, then subtract shrink_mask to get shell_mask
            shell_mask = np.zeros((res_y, res_x), dtype=np.uint8)
            if benchy_polygons:
                benchy_img = Image.new("L", (res_x, res_y), 0)
                bn_draw    = ImageDraw.Draw(benchy_img)
                for poly in benchy_polygons:
                    ext_pts = [
                        (
                            int((px - bounds["xmin"]) * scale_x),
                            int((bounds["ymax"] - py) * scale_y)
                        )
                        for (px, py) in poly.exterior.coords
                    ]
                    bn_draw.polygon(ext_pts, fill=255)
                    for interior in poly.interiors:
                        hole_pts = [
                            (
                                int((px - bounds["xmin"]) * scale_x),
                                int((bounds["ymax"] - py) * scale_y)
                            )
                            for (px, py) in interior.coords
                        ]
                        bn_draw.polygon(hole_pts, fill=0)
                benchy_mask = np.array(benchy_img)
                shell_mask = benchy_mask.copy()
                shell_mask[shrink_mask == 255] = 0

            # 5) Compute gyroid mask if gyroid is present
            if cell is not None:
                Z = np.full_like(X, z)
                gy = (
                    np.sin(2 * np.pi * X / cx) * np.cos(2 * np.pi * Y / cy) +
                    np.sin(2 * np.pi * Y / cy) * np.cos(2 * np.pi * Z / cz) +
                    np.sin(2 * np.pi * Z / cz) * np.cos(2 * np.pi * X / cx)
                )
                gy_mask = (np.abs(gy) <= thickness).astype(np.uint8) * 255
            else:
                gy_mask = np.zeros((res_y, res_x), dtype=np.uint8)

            # 6) Compute interior gyroid: points inside shrink and gyroid
            interior_mask = np.zeros((res_y, res_x), dtype=np.uint8)
            interior_mask[(gy_mask == 255) & (shrink_mask == 255)] = 255
            # 7) Final mask = shell OR interior gyroid
            final_mask = np.zeros((res_y, res_x), dtype=np.uint8)
            final_mask[(shell_mask == 255) | (interior_mask == 255)] = 255

            img = Image.fromarray(final_mask, mode="L")

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
    parser.add_argument(
        "--infill-gyroid",
        metavar=("CELL_SIZE", "THICKNESS"),
        nargs=2,
        type=float,
        help=(
            "If provided, create a gyroid infill inside any Mesh node. "
            "Two floats: <cell_size> <thickness> in model units."
        )
    )

    args = parser.parse_args()
    ifg_to_slice = args.ifg_path

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

    # If the user requested a gyroid infill, inject nodes into the IFG
    if args.infill_gyroid:
        cell_size, thickness = args.infill_gyroid
        # Find the first Mesh node
        mesh_node = next((n for n in doc["nodes"] if n["type"] == "Mesh"), None)
        if mesh_node is None:
            raise RuntimeError("Cannot add gyroid infill: no Mesh node found.")
        # Create a Lattice node for the gyroid
        infill_id = "infill_gyroid"
        lattice_node = {
            "id": infill_id,
            "type": "Lattice",
            "params": {
                "cell_size": cell_size,
                "thickness": thickness
            },
            "inputs": []
        }
        # Create an Intersect node to carve the gyroid inside the mesh
        intersect_id = "gyroid_interior"
        intersect_node = {
            "id": intersect_id,
            "type": "Intersect",
            "params": {},
            "inputs": [mesh_node["id"], infill_id]
        }
        # Create a Union node to combine the mesh shell and the interior gyroid
        final_id = "mesh_with_gyroid"
        union_node = {
            "id": final_id,
            "type": "Union",
            "params": {},
            "inputs": [mesh_node["id"], intersect_id]
        }
        # Append new nodes to the document
        doc["nodes"].append(lattice_node)
        doc["nodes"].append(intersect_node)
        doc["nodes"].append(union_node)
        # The last node is now the root for sampling

        # After injecting nodes, write updated IFG to a temporary file
        temp_ifg_path = args.ifg_path.replace(".ifg", "_infill.ifg")
        with open(temp_ifg_path, "w") as tf:
            json.dump(doc, tf, indent=2)
        # Use this new IFG for slicing
        ifg_to_slice = temp_ifg_path

    # Now generate slices using (possibly) updated bounds
    bounds, num_layers = generate_png_slices(
        ifg_to_slice, args.slice_dir,
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