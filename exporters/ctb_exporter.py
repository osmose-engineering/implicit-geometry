#!/usr/bin/env python3
"""
CTB Exporter (Full Integration)

This script packages a directory of monochrome 1-bit PNG slices into a .ctb archive
compatible with ChiTuBox and similar CTB-based resin workflows. It implements the
binary header, layer index table, filename table, and RLE-encoded layer payloads.

Usage:
  python3 ctb_exporter.py \
    --png_folder output/benchy_run1/slices \
    --output benchy.ctb \
    --width 512 \
    --height 512 \
    --thickness 0.05 \
    --exposure_time 2000 \
    --bottom_exposure_time 5000 \
    --num_bottom_layers 5 \
    --z_lift_dist 6.0 \
    --z_lift_speed 5.0 \
    --z_retract_speed 2.0
"""

import os
import sys
import struct
import zipfile
import argparse
from PIL import Image


def collect_slices(png_folder):
    """
    Gather all files named slice_XXXX.png in sorted order.
    Returns a list of filenames (relative to png_folder).
    """
    files = [
        f for f in os.listdir(png_folder)
        if f.lower().endswith('.png') and f.startswith('slice_')
    ]
    if not files:
        raise RuntimeError(f"No slice PNGs found in: {png_folder}")
    files.sort()
    return files


def pack_ctb_header(pixel_x, pixel_y, layer_count, layer_thickness,
                    exposure_time, bottom_exposure_time, num_bottom_layers,
                    z_lift_dist, z_lift_speed, z_retract_speed):
    """
    Build the CTB binary header:
      - 4-byte magic "CTB1"
      - uint16 FileVersion (0x0100), uint16 padding
      - uint32 pixel_x, uint32 pixel_y, uint32 layer_count
      - float32 layer_thickness
      - float32 exposure_time, float32 bottom_exposure_time
      - uint16 num_bottom_layers, uint16 padding
      - float32 z_lift_dist, float32 z_lift_speed, float32 z_retract_speed
      - Pad to 16-byte boundary
    """
    # Magic + version
    buf = b"CTB1"
    buf += struct.pack("<H", 0x0100)  # FileVersion = 0x0100
    buf += b"\x00\x00"  # 2 bytes padding

    # Next fields
    buf += struct.pack("<I", pixel_x)
    buf += struct.pack("<I", pixel_y)
    buf += struct.pack("<I", layer_count)
    buf += struct.pack("<f", layer_thickness)
    buf += struct.pack("<f", exposure_time)
    buf += struct.pack("<f", bottom_exposure_time)
    buf += struct.pack("<H", num_bottom_layers)
    buf += b"\x00\x00"  # pad to 4-byte boundary
    buf += struct.pack("<f", z_lift_dist)
    buf += struct.pack("<f", z_lift_speed)
    buf += struct.pack("<f", z_retract_speed)

    # Pad to 16-byte alignment
    pad_len = (-len(buf)) % 16
    buf += b"\x00" * pad_len
    return buf


def rle_encode_ctb(raw_bits, width, height):
    """
    CTB-style PackBits RLE for 1-bit data:
      raw_bits: bytes of row-major 1-bit data (packed 8 bits per byte)
      width, height: in pixels
    Returns a bytes object containing the RLE payload.
    """
    out = bytearray()
    for y in range(height):
        x = 0
        while x < width:
            # Read the bit at (x, y)
            bit_index = y * width + x
            byte_offset = bit_index >> 3
            bit_in_byte = 7 - (bit_index & 0x7)
            val = (raw_bits[byte_offset] >> bit_in_byte) & 1

            # Count run length
            run = 1
            while (x + run) < width:
                next_index = y * width + x + run
                next_byte_offset = next_index >> 3
                next_bit = 7 - (next_index & 0x7)
                if ((raw_bits[next_byte_offset] >> next_bit) & 1) != val:
                    break
                run += 1

            # Emit run chunks capped at 127
            remaining = run
            while remaining > 0:
                this_run = min(remaining, 127)
                out.append(0x80 | this_run)
                out.append(0xFF if val else 0x00)
                remaining -= this_run

            x += run
        # (No explicit end-of-line marker required for CTB RLE)
    return bytes(out)


def create_ctb_archive(png_folder, output_ctb,
                       pixel_x, pixel_y, layer_thickness,
                       exposure_time, bottom_exposure_time, num_bottom_layers,
                       z_lift_dist, z_lift_speed, z_retract_speed):
    """
    Packages PNG slices into a fully-compliant CTB archive.
    """
    # 1) Gather and validate slices
    slice_files = collect_slices(png_folder)
    layer_count = len(slice_files)

    # 2) Precompute RLE buffers and lengths
    rle_buffers = []
    for fname in slice_files:
        img_path = os.path.join(png_folder, fname)
        im = Image.open(img_path).convert("1")
        raw_bits = im.tobytes()  # 1-bit per pixel, packed
        rle_data = rle_encode_ctb(raw_bits, pixel_x, pixel_y)
        rle_buffers.append(rle_data)

    # 3) Build offset table (uint32 array of length layer_count+1)
    offsets = [0] * (layer_count + 1)
    for i in range(layer_count):
        offsets[i + 1] = offsets[i] + len(rle_buffers[i])

    # 4) Pack the CTB header
    header = pack_ctb_header(
        pixel_x, pixel_y, layer_count, layer_thickness,
        exposure_time, bottom_exposure_time, num_bottom_layers,
        z_lift_dist, z_lift_speed, z_retract_speed
    )

    # 5) Build zero-terminated filename table
    filename_table = bytearray()
    for i in range(layer_count):
        name = f"layer_images/layer_{i:04d}.pw0Img"
        filename_table.extend(name.encode("ascii") + b"\x00")

    # 6) Optional preview
    preview_data = None
    preview_path = os.path.join(os.path.dirname(png_folder), "preview_images", "preview_0.png")
    if os.path.exists(preview_path):
        with open(preview_path, "rb") as pf:
            preview_data = pf.read()

    # 7) Write CTB (ZIP) in correct order
    with zipfile.ZipFile(output_ctb, "w", compression=zipfile.ZIP_STORED) as zf:
        # 7a) Header section
        zf.writestr("header.bin", header)

        # 7b) Layer index table as little-endian uint32s
        offsets_bytes = b"".join(struct.pack("<I", o) for o in offsets)
        zf.writestr("layer_index_table.bin", offsets_bytes)

        # 7c) Filename table
        zf.writestr("layer_filenames.tbl", filename_table)

        # 7d) Preview image if present
        if preview_data:
            zf.writestr("preview_images/preview_0.png", preview_data)

        # 7e) RLE payloads
        for i, rle_data in enumerate(rle_buffers):
            entry_name = f"layer_images/layer_{i:04d}.pw0Img"
            zf.writestr(entry_name, rle_data)

    print(f"✓ CTB written to {output_ctb}")


def main():
    parser = argparse.ArgumentParser(
        description="Produce a fully-compliant .ctb from 1-bit PNG slices."
    )
    parser.add_argument(
        "--png_folder", required=True,
        help="Directory containing slice_0000.png … slice_XXXX.png"
    )
    parser.add_argument(
        "--output", required=True,
        help="Desired CTB filename (e.g. benchy.ctb)"
    )
    parser.add_argument(
        "--width", type=int, required=True,
        help="X resolution in pixels"
    )
    parser.add_argument(
        "--height", type=int, required=True,
        help="Y resolution in pixels"
    )
    parser.add_argument(
        "--thickness", type=float, required=True,
        help="Layer thickness in mm"
    )
    parser.add_argument(
        "--exposure_time", type=int, default=2000,
        help="Exposure for non-bottom layers (ms)"
    )
    parser.add_argument(
        "--bottom_exposure_time", type=int, default=5000,
        help="Exposure for bottom layers (ms)"
    )
    parser.add_argument(
        "--num_bottom_layers", type=int, default=5,
        help="Number of bottom layers"
    )
    parser.add_argument(
        "--z_lift_dist", type=float, default=6.0,
        help="Z-lift distance (mm)"
    )
    parser.add_argument(
        "--z_lift_speed", type=float, default=5.0,
        help="Z-lift speed (mm/s)"
    )
    parser.add_argument(
        "--z_retract_speed", type=float, default=2.0,
        help="Z-retract speed (mm/s)"
    )

    args = parser.parse_args()

    # Determine CTB output location
    out_path = args.output
    base_dir = os.path.dirname(out_path)
    if base_dir == "":
        parent = os.path.dirname(os.path.abspath(args.png_folder))
        out_path = os.path.join(parent, out_path)
    else:
        os.makedirs(base_dir, exist_ok=True)

    create_ctb_archive(
        png_folder=args.png_folder,
        output_ctb=out_path,
        pixel_x=args.width,
        pixel_y=args.height,
        layer_thickness=args.thickness,
        exposure_time=args.exposure_time,
        bottom_exposure_time=args.bottom_exposure_time,
        num_bottom_layers=args.num_bottom_layers,
        z_lift_dist=args.z_lift_dist,
        z_lift_speed=args.z_lift_speed,
        z_retract_speed=args.z_retract_speed
    )


if __name__ == "__main__":
    main()