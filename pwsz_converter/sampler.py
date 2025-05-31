import os
import sys
import json
import math
import zipfile
import argparse
from PIL import Image

# Allow importing loader.py from parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from loader import load_ifg, build_evaluator

# -----------------------------------------------
# PARAMETERS (we’ll override these via CLI flags)
# -----------------------------------------------
DEFAULT_IFG_PATH      = "examples/cube.ifg"
DEFAULT_OUTPUT_DIR    = "output_slices"
DEFAULT_LAYER_THICK   = 0.1             # mm
DEFAULT_RES_X         = 200
DEFAULT_RES_Y         = 200
DEFAULT_FORMAT        = "cbddlp"        # or “pwsz”

# -------------------------------------------------
# COMMON FUNCTIONS FOR BOTH FORMATS: generate slices
# -------------------------------------------------
def generate_png_slices(ifg_path, output_dir, layer_thickness, res_x, res_y):
    """
    1) Loads the IFG and builds an evaluator.
    2) Samples the implicit field for each Z‐slice and writes PNGs to output_dir.
    3) Returns (bounds, num_layers) so wrappers know what they’re packaging.
    """
    doc       = load_ifg(ifg_path)
    eval_fn   = build_evaluator(doc["nodes"])
    meta      = doc.get("metadata", {})
    bounds    = meta.get("bounds", {
        "xmin": -5, "xmax": 5,
        "ymin": -5, "ymax": 5,
        "zmin": -5, "zmax": 5
    })

    zmin, zmax = bounds["zmin"], bounds["zmax"]
    num_layers = int(math.ceil((zmax - zmin) / layer_thickness)) + 1
    os.makedirs(output_dir, exist_ok=True)

    print(f"→ Generating {num_layers} PNG slices (Z from {zmin} to {zmax})")
    for i in range(num_layers):
        z = zmin + i * layer_thickness
        img = Image.new("L", (res_x, res_y))
        for ix in range(res_x):
            for iy in range(res_y):
                x = bounds["xmin"] + ix * (bounds["xmax"] - bounds["xmin"]) / (res_x - 1)
                y = bounds["ymin"] + iy * (bounds["ymax"] - bounds["ymin"]) / (res_y - 1)
                field_val = eval_fn(x, y, z)
                # inside => white (255), outside => black (0)
                img.putpixel((ix, res_y - 1 - iy), 255 if field_val <= 0 else 0)

        slice_path = os.path.join(output_dir, f"slice_{i:04d}.png")
        img.save(slice_path)

    return bounds, num_layers


# -------------------------------------------------
# WRAPPER #1: pack PNG slices into a .pwsz archive
# -------------------------------------------------
def wrap_to_pwsz(slice_dir, output_file, bounds, res_x, res_y, layer_thickness):
    """
    Strictly mirrors the Anycubic format. ChituBox might be able to read .pwsz too,
    but we found Anycubic’s slicer is very picky. This produces a ZIP containing:
      - Info.json
      - Body/0000, Body/0001, …  (no extension)
    where each “Body/XXXX” entry is actually raw PNG bytes.
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

    print(f"✓ Packaged {len(png_files)} slices into {output_file} (Anycubic .pwsz format)")


# -------------------------------------------------
# WRAPPER #2: pack PNG slices into a .cbddlp archive
# -------------------------------------------------
def wrap_to_cbddlp(slice_dir, output_file, bounds, res_x, res_y, layer_thickness):
    """
    Generates a ChituBox‐compatible .cbddlp file. Internally, it's a ZIP with:
      - Info.json  (with slightly different keys)
      - Body/0000.png, Body/0001.png, … (ChituBox will look for .png in Body/)
    Note how ChituBox expects “Body/<layerindex>.png” (with .png suffix),
    not just a number without extension. We pack exactly that structure.
    """
    # Info.json keys that ChituBox looks for in a CBDDLP archive:
    info = {
        "Version":        1,                # spec version; 1 is typical
        "Width":          res_x,            # pixel width
        "Height":         res_y,            # pixel height
        "LayerHeight":    layer_thickness,  # in mm
        "ExposureTime":   0.0,              # optional—ChituBox may ignore if zero
        "BottomExposure": 0.0,              # optional
        "OffTime":        0.0,              # optional
        "OriginX":        bounds["xmin"],
        "OriginY":        bounds["ymin"],
        "PixelSizeX":     (bounds["xmax"] - bounds["xmin"]) / (res_x - 1),
        "PixelSizeY":     (bounds["ymax"] - bounds["ymin"]) / (res_y - 1)
        # (You can add “TiltCompensation”: true/false if needed, etc.)
    }

    with zipfile.ZipFile(output_file, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("Info.json", json.dumps(info))

        png_files = sorted(f for f in os.listdir(slice_dir) if f.endswith(".png"))
        for idx, fname in enumerate(png_files):
            # For CB DLP, the slicer expects Body/<index>.png (with .png extension)
            layer_name = f"{idx:04d}.png"
            arcname = f"Body/{layer_name}"
            zf.write(os.path.join(slice_dir, fname), arcname)

    print(f"✓ Packaged {len(png_files)} slices into {output_file} (CBDDLP format)")


# -----------------------------------------------
# COMMAND‐LINE INTERFACE
# -----------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Convert an IFG (implicit) → PNG slices → printer‐compatible zip"
    )
    parser.add_argument(
        "--ifg", dest="ifg_path", default=DEFAULT_IFG_PATH,
        help="Path to the .ifg file (implicit‐geometry graph)."
    )
    parser.add_argument(
        "--out", dest="output_base", default="output",
        help="Base name for outputs. E.g. 'foo' → writes 'foo.pwsz' or 'foo.cbddlp'."
    )
    parser.add_argument(
        "--dir", dest="slice_dir", default=DEFAULT_OUTPUT_DIR,
        help="Directory where intermediate PNG slices land."
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
        "--format", dest="fmt", choices=["pwsz", "cbddlp"],
        default=DEFAULT_FORMAT,
        help="Choose 'pwsz' (Anycubic) or 'cbddlp' (ChituBox)."
    )

    args = parser.parse_args()

    # 1) Generate slices into the directory
    bounds, num_layers = generate_png_slices(
        args.ifg_path, args.slice_dir,
        args.layer_thickness, args.res_x, args.res_y
    )

    # 2) Package into the final archive
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
    else:  # args.fmt == "cbddlp"
        output_file = f"{args.output_base}.cbddlp"
        wrap_to_cbddlp(
            slice_dir=args.slice_dir,
            output_file=output_file,
            bounds=bounds,
            res_x=args.res_x,
            res_y=args.res_y,
            layer_thickness=args.layer_thickness
        )

    print("✅ Done.")