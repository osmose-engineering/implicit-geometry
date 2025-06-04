import sys
import os
import json
import tempfile
import subprocess

# Ensure project root is on sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import numpy as np
from sampler import generate_png_slices

def test_generate_png_slices_basic(tmp_path):
    """
    Use the CLI to create a sphere IFG and ensure generate_png_slices produces PNG files.
    """
    # Paths
    sphere_ifg = tmp_path / "sphere.ifg"
    slice_dir = tmp_path / "slices"
    slice_dir.mkdir()

    # Use CLI to create a sphere IFG via implicit.py
    cli_script = os.path.abspath(os.path.join(project_root, "implicit.py"))
    cmd = [
        sys.executable, cli_script,
        "primitive", "sphere",
        "--center", "0", "0", "0",
        "--radius", "0.5",
        "--bounds", "-1", "1", "-1", "1", "-1", "1",
        "--output", str(sphere_ifg)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, f"Failed to create sphere IFG: {result.stderr}"
    assert sphere_ifg.exists(), "Sphere IFG file was not created."

    # Now slice the generated IFG
    layer_thickness = 1.0
    resx, resy = 32, 32

    bounds, num_layers = generate_png_slices(
        str(sphere_ifg),
        str(slice_dir),
        layer_thickness,
        resx,
        resy
    )

    # Expect at least one layer
    assert isinstance(num_layers, int) and num_layers >= 1

    # Check that PNG files were created
    files = os.listdir(slice_dir)
    png_files = [f for f in files if f.endswith(".png")]
    assert len(png_files) == num_layers, f"Expected {num_layers} PNGs, found {len(png_files)}"

    # Ensure generated PNGs have non-zero size
    for fname in png_files:
        path = slice_dir / fname
        assert path.stat().st_size > 0

if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__]))
