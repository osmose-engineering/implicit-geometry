import sys
import os
import subprocess
import json
import tempfile
import shutil
import pytest

# Determine project root and CLI script path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
cli_script = os.path.join(project_root, "implicit.py")

@pytest.mark.skipif(not os.path.exists(cli_script), reason="CLI script not found")
def test_end_to_end_demo(tmp_path):
    """
    End-to-end demo:
    1. Create outer box IFG
    2. Create inner sphere IFG
    3. Subtract sphere from box to get hollow shell IFG
    4. Create gyroid lattice IFG
    5. Intersect hollow shell and gyroid to get filled shell IFG
    6. Slice filled shell IFG to PNGs and package as CTB
    """

    # Use tmp_path as a working directory
    wd = tmp_path
    os.chdir(wd)

    # Paths for IFG files
    outer_box_ifg = wd / "outer_box.ifg"
    inner_sphere_ifg = wd / "inner_sphere.ifg"
    hollow_shell_ifg = wd / "hollow_shell.ifg"
    gyroid_ifg = wd / "gyroid_lattice.ifg"
    filled_shell_ifg = wd / "filled_shell.ifg"
    slice_dir = wd / "slices"
    slice_dir.mkdir()
    ctb_path = wd / "filled_shell.ctb"

    # 1) Create outer box
    cmd1 = [
        sys.executable, cli_script,
        "primitive", "box",
        "--center", "0", "0", "0",
        "--halfwidths", "20", "20", "20",
        "--bounds", "-20", "20", "-20", "20", "-20", "20",
        "--output", str(outer_box_ifg)
    ]
    result = subprocess.run(cmd1, capture_output=True, text=True)
    assert result.returncode == 0, f"Outer box creation failed: {result.stderr}"
    assert outer_box_ifg.exists()

    # 2) Create inner sphere
    cmd2 = [
        sys.executable, cli_script,
        "primitive", "sphere",
        "--center", "0", "0", "0",
        "--radius", "17.5",
        "--bounds", "-20", "20", "-20", "20", "-20", "20",
        "--output", str(inner_sphere_ifg)
    ]
    result = subprocess.run(cmd2, capture_output=True, text=True)
    assert result.returncode == 0, f"Inner sphere creation failed: {result.stderr}"
    assert inner_sphere_ifg.exists()

    # 3) Subtract sphere from box
    cmd3 = [
        sys.executable, cli_script,
        "combine",
        "--mode", "subtract",
        "--inputs", str(outer_box_ifg), str(inner_sphere_ifg),
        "--bounds", "-20", "20", "-20", "20", "-20", "20",
        "--output", str(hollow_shell_ifg)
    ]
    result = subprocess.run(cmd3, capture_output=True, text=True)
    assert result.returncode == 0, f"Hollow shell creation failed: {result.stderr}"
    assert hollow_shell_ifg.exists()

    # 4) Create gyroid lattice
    cmd4 = [
        sys.executable, cli_script,
        "lattice", "periodic",
        "--type", "gyroid",
        "--cell_size", "5.0",
        "--thickness", "0.0",
        "--bounds", "-20", "20", "-20", "20", "-20", "20",
        "--output", str(gyroid_ifg)
    ]
    result = subprocess.run(cmd4, capture_output=True, text=True)
    assert result.returncode == 0, f"Gyroid lattice creation failed: {result.stderr}"
    assert gyroid_ifg.exists()

    # 5) Intersect hollow shell and gyroid
    cmd5 = [
        sys.executable, cli_script,
        "combine",
        "--mode", "intersect",
        "--inputs", str(hollow_shell_ifg), str(gyroid_ifg),
        "--bounds", "-20", "20", "-20", "20", "-20", "20",
        "--output", str(filled_shell_ifg)
    ]
    result = subprocess.run(cmd5, capture_output=True, text=True)
    assert result.returncode == 0, f"Filled shell creation failed: {result.stderr}"
    assert filled_shell_ifg.exists()

    # 6) Slice filled shell to PNGs and CTB
    cmd6 = [
        sys.executable, cli_script,
        "slice",
        "--ifg", str(filled_shell_ifg),
        "--slice_dir", str(slice_dir),
        "--archive", str(ctb_path),
        "--layer_thickness", "1.0",
        "--resx", "32",
        "--resy", "32"
    ]
    result = subprocess.run(cmd6, capture_output=True, text=True)
    assert result.returncode == 0, f"Slicing failed: {result.stderr}"
    # Check that at least one PNG exists and CTB file created
    png_files = [f for f in os.listdir(slice_dir) if f.endswith(".png")]
    assert len(png_files) >= 1, "No PNG slices generated"
    assert ctb_path.exists(), "CTB archive not created"

