def build_layers_controller(layer_count, thickness, exposure_settings):
    """
    Build a JSON-style layers_controller.conf for Anycubic.
      - layer_count: total number of layers (e.g. 961)
      - thickness: layer thickness in mm (e.g. 0.05)
      - exposure_settings: dict with keys:
            'bottom_exposure_time', 'normal_exposure_time', 'num_bottom_layers',
            'zup_height', 'zup_speed'
    """
    num_bottom = exposure_settings.get("num_bottom_layers", 5)
    zup_height = exposure_settings.get("zup_height", 5.0)
    zup_speed = exposure_settings.get("zup_speed", 15.0)

    paras = []
    for i in range(layer_count):
        if i < num_bottom:
            exp_time = exposure_settings["bottom_exposure_time"]
        else:
            exp_time = exposure_settings["normal_exposure_time"]
        layer_minheight = i * thickness
        paras.append({
            "exposure_time": exp_time,
            "layer_index": i,
            "layer_minheight": layer_minheight,
            "layer_thickness": thickness,
            "zup_height": zup_height,
            "zup_speed": zup_speed
        })

    return json.dumps({"count": layer_count, "paras": paras}, indent=2)
#!/usr/bin/env python3
"""
Anycubic PM7M Exporter

This script takes a directory of monochrome PNG slices and packages them
into an Anycubic-compatible .pm7m archive using UVTools' RLE scheme.

Usage:
    python3 anycubic_exporter.py \
      --png_folder output_slices \
      --output 3dbenchy_exported.pm7m \
      --width 512 \
      --height 512 \
      --thickness 0.05
"""

import os
import io
import json
import struct
import zipfile
import argparse
import shutil
import numpy as np
from PIL import Image

def encode_pw0_image(png_path, width, height, x_offset=0, y_offset=0):
    """
    Given a path to a monochrome PNG (width×height), return bytes in Anycubic’s
    .pw0Img format (header + RLE-encoded payload).
    """
    # 1) Load PNG, convert to pure 0/255 grayscale, verify size
    img = Image.open(png_path).convert("L")
    w, h = img.size
    if (w, h) != (width, height):
        raise ValueError(f'Image {png_path} has size {w}×{h}, expected {width}×{height}.')
    arr = np.array(img)
    # Force strict binary values
    arr = np.where(arr < 128, 0, 255).astype(np.uint8)

    # 2) Flatten in row-major order
    flat = arr.flatten().tolist()

    # 3) Build RLE stream: (count, value) pairs
    rle_bytes = bytearray()
    run_value = flat[0]
    run_length = 1
    for pix in flat[1:]:
        if pix == run_value and run_length < 255:
            run_length += 1
        else:
            rle_bytes.append(run_length & 0xFF)
            rle_bytes.append(run_value)
            run_value = pix
            run_length = 1
    # Final run
    rle_bytes.append(run_length & 0xFF)
    rle_bytes.append(run_value)

    # 4) Construct header: UInt16 width, UInt16 height, UInt16 x_offset, UInt16 y_offset
    header = bytearray()
    header.extend(struct.pack("<H", width))
    header.extend(struct.pack("<H", height))
    header.extend(struct.pack("<H", x_offset))
    header.extend(struct.pack("<H", y_offset))
    # (If your printer expects more header fields, insert them here.)

    return bytes(header) + bytes(rle_bytes)


def create_anycubic_archive(png_folder, output_pm7m, width, height, layer_thickness, exposure_settings=None, template_path=None):
    """
    Packages PNG slices into an Anycubic-compatible .pm7m ZIP.

    png_folder: directory containing slice_0000.png ... slice_{N-1}.png
    output_pm7m: path to write the .pm7m ZIP
    width, height: slice resolution (e.g. 512, 512)
    layer_thickness: layer thickness in mm (e.g. 0.05)
    exposure_settings: optional dict of exposure parameters
    template_path: optional path to a reference .pm7m file to copy metadata from
    """
    # If a template PM7M is provided, open it and read the metadata files
    template_data = {}
    if template_path is not None:
        if not os.path.isfile(template_path):
            raise FileNotFoundError(f"Template PM7M not found: {template_path}")
        with zipfile.ZipFile(template_path, "r") as tz:
            for name in ["anycubic_photon_resins.pwsp",
                         "layers_controller.conf",
                         "software_info.conf",
                         "lcd_function.json"]:
                if name in tz.namelist():
                    template_data[name] = tz.read(name)
            # Copy first preview image if exists
            for entry in tz.namelist():
                if entry.startswith("preview_images/") and entry.endswith(".png"):
                    template_data[entry] = tz.read(entry)
                    break

    # 1) Ensure png_folder exists and list PNG files
    if not os.path.isdir(png_folder):
        raise FileNotFoundError(f'PNG folder not found: {png_folder}')
    png_files = sorted([
        f for f in os.listdir(png_folder)
        if f.lower().endswith('.png') and f.startswith('slice_')
    ])
    layer_count = len(png_files)
    if layer_count == 0:
        raise RuntimeError(f'No slice PNGs found in: {png_folder}')

    # 2) Build minimal exposure_settings if none provided
    if exposure_settings is None:
        exposure_settings = {
            "exposure_time": 2000,
            "bottom_exposure_time": 5000,
            "light_off_time": 500,
            "lift_distance": 6.0,
            "lift_speed": 5.0,
            "retract_speed": 2.0
        }

    # 3) Create the ZIP archive
    with zipfile.ZipFile(output_pm7m, "w", compression=zipfile.ZIP_STORED) as z:
        # 3a) Copy metadata from template if available
        if "anycubic_photon_resins.pwsp" in template_data:
            z.writestr("anycubic_photon_resins.pwsp", template_data["anycubic_photon_resins.pwsp"])
        else:
            z.writestr("anycubic_photon_resins.pwsp", "{}")
        if "layers_controller.conf" in template_data:
            z.writestr("layers_controller.conf", template_data["layers_controller.conf"])
        else:
            json_text = build_layers_controller(
                layer_count=layer_count,
                thickness=layer_thickness,
                exposure_settings={
                    "bottom_exposure_time": exposure_settings["bottom_exposure_time"],
                    "normal_exposure_time": exposure_settings["exposure_time"],
                    "num_bottom_layers": 5,
                    "zup_height": exposure_settings.get("lift_distance", 5.0),
                    "zup_speed": exposure_settings.get("lift_speed", 5.0),
                }
            )
            z.writestr("layers_controller.conf", json_text)
        if "software_info.conf" in template_data:
            z.writestr("software_info.conf", template_data["software_info.conf"])
        if "lcd_function.json" in template_data:
            z.writestr("lcd_function.json", template_data["lcd_function.json"])
        # Copy preview image from template if available
        for key, val in template_data.items():
            if key.startswith("preview_images/"):
                z.writestr(key, val)
                break

        # 3b) Write print_info.json
        print_info = {
            "name": os.path.basename(output_pm7m).replace(".pm7m", ""),
            "layer_count": layer_count,
            "pixel_width": width,
            "pixel_height": height,
            "layer_height": layer_thickness
        }
        z.writestr("print_info.json", json.dumps(print_info, indent=2))

        # 3c) Generate and write each layer .pw0Img
        for layer_idx in range(layer_count):
            png_name = f"slice_{layer_idx:04d}.png"
            png_path = os.path.join(png_folder, png_name)
            if not os.path.exists(png_path):
                raise FileNotFoundError(f'Missing slice image: {png_path}')

            pw0_bytes = encode_pw0_image(png_path, width, height, x_offset=0, y_offset=0)
            entry_name = f"layer_images/layer_{layer_idx:04d}.pw0Img"
            z.writestr(entry_name, pw0_bytes)

        # 3d) (Optional) Create a small preview (e.g. 128×128) from slice_0000 if no preview from template
        has_preview = any(key.startswith("preview_images/") for key in template_data.keys())
        if not has_preview:
            first_png = os.path.join(png_folder, "slice_0000.png")
            if os.path.exists(first_png):
                preview = Image.open(first_png).convert("L").resize((128, 128))
                buf = io.BytesIO()
                preview.save(buf, format="PNG")
                z.writestr("preview_images/preview_0.png", buf.getvalue())

        # 3e) Create a scene.slice with resolution, count, and layer image list
        scene = {
            "layerCount": layer_count,
            "pixelWidth": width,
            "pixelHeight": height,
            "layers": [f"layer_images/layer_{i:04d}.pw0Img" for i in range(layer_count)]
        }
        z.writestr("scene.slice", json.dumps(scene, indent=2))

    print(f'✓ Wrote Anycubic-compatible archive: {output_pm7m}')


def main():
    parser = argparse.ArgumentParser(
        description="Package a directory of PNG slices into an Anycubic .pm7m file."
    )
    parser.add_argument(
        "--png_folder", required=True,
        help="Directory containing slice_0000.png ... slice_{N-1}.png"
    )
    parser.add_argument(
        "--output", required=True,
        help="Path for the output .pm7m file (e.g. benchy_exported.pm7m)"
    )
    parser.add_argument(
        "--width", type=int, required=True,
        help="X resolution of each slice (e.g. 512)"
    )
    parser.add_argument(
        "--height", type=int, required=True,
        help="Y resolution of each slice (e.g. 512)"
    )
    parser.add_argument(
        "--thickness", type=float, required=True,
        help="Layer thickness in millimeters (e.g. 0.05)"
    )
    parser.add_argument(
        "--exposure_time", type=int, default=2000,
        help="Normal exposure time (ms)"
    )
    parser.add_argument(
        "--bottom_exposure_time", type=int, default=5000,
        help="Bottom layer exposure time (ms)"
    )
    parser.add_argument(
        "--light_off_time", type=int, default=500,
        help="Light-off delay time between layers (ms)"
    )
    parser.add_argument(
        "--lift_distance", type=float, default=6.0,
        help="Z-lift distance (mm)"
    )
    parser.add_argument(
        "--lift_speed", type=float, default=5.0,
        help="Z-lift speed (mm/s)"
    )
    parser.add_argument(
        "--retract_speed", type=float, default=2.0,
        help="Z-retract speed (mm/s)"
    )
    parser.add_argument(
        "--template", required=False, default=None,
        help="Path to a reference .pm7m file to copy metadata from"
    )

    args = parser.parse_args()

    # Place the output .pm7m in the parent directory of the PNG folder
    png_dir = args.png_folder
    # Ensure the PNG folder exists
    if not os.path.isdir(png_dir):
        raise FileNotFoundError(f'PNG folder not found: {png_dir}')
    # Determine parent directory of png_folder (e.g., output/benchy_run1)
    parent_dir = os.path.dirname(os.path.abspath(png_dir))
    # Use the basename of the provided output as filename, but place it in parent_dir
    pm7m_name = os.path.basename(args.output)
    output_path = os.path.join(parent_dir, pm7m_name)
    # Override args.output with this path
    args.output = output_path

    exposure = {
        "exposure_time": args.exposure_time,
        "bottom_exposure_time": args.bottom_exposure_time,
        "light_off_time": args.light_off_time,
        "lift_distance": args.lift_distance,
        "lift_speed": args.lift_speed,
        "retract_speed": args.retract_speed
    }

    template_path = args.template

    create_anycubic_archive(
        png_folder=args.png_folder,
        output_pm7m=args.output,
        width=args.width,
        height=args.height,
        layer_thickness=args.thickness,
        exposure_settings=exposure,
        template_path=template_path
    )

if __name__ == "__main__":
    main()