import os
import sys

# Insert project root and implicit_core onto sys.path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
implicit_core_path = os.path.join(project_root, "implicit_core")
if implicit_core_path not in sys.path:
    sys.path.insert(0, implicit_core_path)

import json
import math
import zipfile
import argparse
import numpy as np
from PIL import Image
from PIL import ImageDraw
import shapely.geometry as geom
import trimesh
from shapely.geometry import Polygon, Point
from shapely.ops import unary_union


# --- Exporter wrappers ---
from exporters.ctb_exporter import create_ctb_archive as wrap_to_ctb
from exporters.anycubic_exporter import create_anycubic_archive as wrap_to_pwsz

# Allow importing loader.py from parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from loader import load_ifg, build_evaluator

# -----------------------------------------------
# Helper: recursively build SDF evaluator for simple SDF/boolean IFG
# -----------------------------------------------
def _build_sdf_eval(doc):
    """
    Recursively build an SDF evaluator from a loaded IFG document (handling both
    'nodes' and simple 'sdf' boolean or sphere definitions).
    """
    # If node-based IFG, delegate to loader
    if "nodes" in doc:
        return build_evaluator(doc["nodes"])
    # Otherwise, simple SDF-based IFG
    sdf_meta = doc.get("sdf", {})
    kind = sdf_meta.get("kind")
    # Sphere
    if kind == "sphere":
        cx, cy, cz = sdf_meta.get("center", [0.0, 0.0, 0.0])
        radius = sdf_meta.get("radius", 0.0)
        def eval_fn(x, y, z):
            dx = x - cx; dy = y - cy; dz = z - cz
            return (dx*dx + dy*dy + dz*dz)**0.5 - radius
        return eval_fn
    # Box
    if kind == "box":
        cx, cy, cz = sdf_meta.get("center", [0.0, 0.0, 0.0])
        hx, hy, hz = sdf_meta.get("halfwidths", [0.0, 0.0, 0.0])
        def eval_fn(x, y, z):
            dx = abs(x - cx) - hx
            dy = abs(y - cy) - hy
            dz = abs(z - cz) - hz
            # outside distances
            ux = max(dx, 0.0)
            uy = max(dy, 0.0)
            uz = max(dz, 0.0)
            outside_dist = (ux*ux + uy*uy + uz*uz) ** 0.5
            # inside distance (negative)
            inside_dist = min(max(dx, max(dy, dz)), 0.0)
            return outside_dist + inside_dist
        return eval_fn

    # Gyroid lattice
    if kind == "gyroid":
        # Extract parameters
        cell = sdf_meta.get("cell_size")
        thickness = sdf_meta.get("thickness", 0.0)
        # If cell is a single float, use it for all axes
        if isinstance(cell, (int, float)):
            cx = cy = cz = cell
        else:
            cx, cy, cz = cell
        def eval_fn(x, y, z):
            gy = (
                math.sin(2 * math.pi * x / cx) * math.cos(2 * math.pi * y / cy) +
                math.sin(2 * math.pi * y / cy) * math.cos(2 * math.pi * z / cz) +
                math.sin(2 * math.pi * z / cz) * math.cos(2 * math.pi * x / cx)
            )
            return abs(gy) - thickness
        return eval_fn
    # Boolean combine
    if kind in ("union", "intersect", "subtract"):
        inputs = sdf_meta.get("inputs", [])
        child_evals = []
        for inp in inputs:
            child_doc = load_ifg(inp)
            child_evals.append(_build_sdf_eval(child_doc))
        if kind == "union":
            return lambda x, y, z: min(f(x, y, z) for f in child_evals)
        elif kind == "intersect":
            return lambda x, y, z: max(f(x, y, z) for f in child_evals)
        else:  # subtract
            return lambda x, y, z: max(child_evals[0](x, y, z), -child_evals[1](x, y, z))
    raise ValueError(f"Unsupported simple SDF kind: {kind}")

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

    # Handle simple IFG containing only a single-sphere SDF (no "nodes" key)
    if "sdf" in doc and "nodes" not in doc:
        sdf_meta = doc["sdf"]
        kind = sdf_meta.get("kind")
        if kind == "sphere":
            cx, cy, cz = sdf_meta.get("center", [0.0, 0.0, 0.0])
            radius = sdf_meta.get("radius", 0.0)
            def eval_fn(x, y, z):
                dx = x - cx
                dy = y - cy
                dz = z - cz
                dist = (dx*dx + dy*dy + dz*dz) ** 0.5
                return dist - radius
            # Use bounds from IFG document directly
            bounds = doc.get("bounds", {})
            zmin, zmax = bounds["zmin"], bounds["zmax"]
            num_layers = int(math.ceil((zmax - zmin) / layer_thickness)) + 1
            os.makedirs(output_dir, exist_ok=True)
            xs = np.linspace(bounds["xmin"], bounds["xmax"], res_x)
            ys = np.linspace(bounds["ymin"], bounds["ymax"], res_y)
            for i, z in enumerate(np.linspace(zmin, zmax, num_layers)):
                xv, yv = np.meshgrid(xs, ys, indexing="xy")
                points = np.vstack((xv.ravel(), yv.ravel(), np.full_like(xv.ravel(), z))).T
                field_vals = np.array([eval_fn(px, py, pz) for px, py, pz in points])
                img_arr = (255 * (field_vals.reshape((res_y, res_x)) < 0)).astype(np.uint8)
                img = Image.fromarray(img_arr, mode="L")
                slice_path = os.path.join(output_dir, f"slice_{i:04d}.png")
                img.save(slice_path)
            return bounds, num_layers
        # Handle simple IFG containing only a simple boolean combine (no "nodes" key)
        sdf_meta = doc["sdf"]
        kind = sdf_meta.get("kind")
        # Build a single evaluator for this combined IFG
        eval_fn = _build_sdf_eval(doc)
        # Use bounds from IFG metadata
        bounds = doc.get("bounds", {})
        zmin, zmax = bounds["zmin"], bounds["zmax"]
        num_layers = int(math.ceil((zmax - zmin) / layer_thickness)) + 1
        os.makedirs(output_dir, exist_ok=True)
        xs = np.linspace(bounds["xmin"], bounds["xmax"], res_x)
        ys = np.linspace(bounds["ymin"], bounds["ymax"], res_y)
        for i, z in enumerate(np.linspace(zmin, zmax, num_layers)):
            xv, yv = np.meshgrid(xs, ys, indexing="xy")
            points = np.vstack((xv.ravel(), yv.ravel(), np.full_like(xv.ravel(), z))).T
            field_vals = np.array([eval_fn(px, py, pz) for px, py, pz in points])
            img_arr = (255 * (field_vals.reshape((res_y, res_x)) < 0)).astype(np.uint8)
            img = Image.fromarray(img_arr, mode="L")
            slice_path = os.path.join(output_dir, f"slice_{i:04d}.png")
            img.save(slice_path)
        return bounds, num_layers

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
    # Redirect all outputs into a dedicated directory
    # Determine base output path from args.output_base
    output_base = args.output_base
    base_dir = os.path.dirname(output_base)
    if base_dir == "":
        base_dir = "output"
        output_base = os.path.join(base_dir, args.output_base)
    # Create base directory
    os.makedirs(output_base, exist_ok=True)
    # Redirect slice directory to be inside the base directory
    slice_dir_full = os.path.join(output_base, args.slice_dir)
    args.slice_dir = slice_dir_full
    os.makedirs(args.slice_dir, exist_ok=True)
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
        # Find the Mesh node (benchy)
        mesh_node = next((n for n in doc["nodes"] if n["type"] == "Mesh"), None)
        if mesh_node is None:
            raise RuntimeError("Cannot add gyroid infill: no Mesh node found.")
        mesh_id = mesh_node["id"]

        # 1) Create Transform "shrink" to make a slightly smaller copy of the mesh
        shrink_id = "shrink"
        shrink_node = {
            "id": shrink_id,
            "type": "Transform",
            "params": {
                "translate": [0, 0, 0],
                "rotate": [0, 0, 0],
                "scale": [0.98, 0.98, 0.98]
            },
            "inputs": [mesh_id]
        }

        # 2) Create Subtract "shell" = Mesh - shrink
        shell_id = "shell"
        shell_node = {
            "id": shell_id,
            "type": "Subtract",
            "params": {},
            "inputs": [mesh_id, shrink_id]
        }

        # 3) Create Lattice "gyroid"
        lattice_id = "gyroid"
        lattice_node = {
            "id": lattice_id,
            "type": "Lattice",
            "params": {
                "cell_size": cell_size,
                "thickness": thickness
            },
            "inputs": []
        }

        # 4) Create Intersect "interiorGyroid" = shrink ∧ gyroid
        intersect_id = "interiorGyroid"
        intersect_node = {
            "id": intersect_id,
            "type": "Intersect",
            "params": {},
            "inputs": [shrink_id, lattice_id]
        }

        # 5) Create Union "final" = shell ∪ interiorGyroid
        final_id = "final"
        union_node = {
            "id": final_id,
            "type": "Union",
            "params": {},
            "inputs": [shell_id, intersect_id]
        }

        # Append new nodes so that "final" is last
        doc["nodes"].extend([
            shrink_node,
            shell_node,
            lattice_node,
            intersect_node,
            union_node
        ])

        # Write updated IFG to a temporary file
        temp_ifg_path = args.ifg_path.replace(".ifg", "_hollow_infill.ifg")
        with open(temp_ifg_path, "w") as tf:
            json.dump(doc, tf, indent=2)

        # Use the new IFG for slicing
        ifg_to_slice = temp_ifg_path

    # Now generate slices using (possibly) updated bounds
    bounds, num_layers = generate_png_slices(
        ifg_to_slice, args.slice_dir,
        args.layer_thickness, args.res_x, args.res_y
    )


    if args.fmt == "pwsz":
        output_file = f"{output_base}.pwsz"
        wrap_to_pwsz(
            slice_dir=args.slice_dir,
            output_file=output_file,
            bounds=bounds,
            res_x=args.res_x,
            res_y=args.res_y,
            layer_thickness=args.layer_thickness
        )
    else:  # args.fmt == "ctb"
        output_file = f"{output_base}.ctb"
        wrap_to_ctb(
            png_folder=args.slice_dir,
            archive_path=output_file,
            image_prefix="Slice",
            width=args.res_x,
            height=args.res_y,
            num_layers=num_layers,
            # Example exposure settings; adjust as needed
            exposure_settings={
                "exposure_time": 2000,
                "bottom_exposure_time": 5000,
                "bottom_layers": 5,
                "z_lift_distance": 6.0,
                "z_lift_speed": 5.0,
                "z_retract_speed": 2.0
            }
        )

    print("✅ Done.")