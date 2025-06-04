import sys
import os
import subprocess
import json
import pytest
import tempfile

# Determine project root and path to the CLI script
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
cli_script = os.path.join(project_root, "implicit.py")

def test_cli_help():
    """Ensure that running with --help returns exit code 0 and shows the main description."""
    result = subprocess.run([sys.executable, cli_script, "--help"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "Implicit modeling CLI" in result.stdout

def test_cli_periodic_generates_ifg(tmp_path):
    """Test that the 'lattice periodic' command produces a valid .ifg file."""
    out_ifg = tmp_path / "test_periodic.ifg"
    args = [
        sys.executable, cli_script,
        "lattice", "periodic",
        "--type", "gyroid",
        "--cell_size", "10.0",
        "--thickness", "0.5",
        "--bounds", "0", "5", "0", "5", "0", "5",
        "--output", str(out_ifg)
    ]
    result = subprocess.run(args, capture_output=True, text=True)
    assert result.returncode == 0, f"CLI failed with stderr:\n{result.stderr}"
    assert out_ifg.exists(), "Expected .ifg file was not created."
    data = json.loads(out_ifg.read_text())
    assert data.get("format") == "implicit"
    assert isinstance(data.get("bounds"), dict)
    assert data["bounds"]["xmin"] == 0.0 or data["bounds"]["xmin"] == 0

def test_cli_invalid_command():
    """Running an unknown command should return a non-zero exit code."""
    result = subprocess.run([sys.executable, cli_script, "unknown"], capture_output=True, text=True)
    assert result.returncode != 0
    assert "usage" in result.stderr.lower() or "usage" in result.stdout.lower()

def test_cli_primitive_sphere(tmp_path):
    """Test that the 'primitive sphere' command produces a valid .ifg file."""
    out_ifg = tmp_path / "sphere.ifg"
    args = [
        sys.executable, cli_script,
        "primitive", "sphere",
        "--center", "0", "0", "0",
        "--radius", "1.0",
        "--bounds", "-1", "1", "-1", "1", "-1", "1",
        "--output", str(out_ifg)
    ]
    result = subprocess.run(args, capture_output=True, text=True)
    assert result.returncode == 0, f"Primitive sphere failed: {result.stderr}"
    assert out_ifg.exists(), "Primitive .ifg file not created."
    data = json.loads(out_ifg.read_text())
    assert data["sdf"]["kind"] == "sphere"
    assert data["sdf"]["radius"] == 1.0

def test_cli_mesh(tmp_path):
    """Test that the 'mesh' command produces a valid .ifg file from a minimal STL."""
    # Create minimal ASCII STL
    stl_content = """solid test
  facet normal 0 0 1
    outer loop
      vertex 0 0 0
      vertex 1 0 0
      vertex 0 1 0
    endloop
  endfacet
endsolid test
"""
    stl_file = tmp_path / "test.stl"
    stl_file.write_text(stl_content)

    out_ifg = tmp_path / "mesh.ifg"
    args = [
        sys.executable, cli_script,
        "mesh",
        "--mesh", str(stl_file),
        "--output", str(out_ifg)
    ]
    result = subprocess.run(args, capture_output=True, text=True)
    assert result.returncode == 0, f"Mesh command failed: {result.stderr}"
    assert out_ifg.exists(), "Mesh .ifg file not created."
    data = json.loads(out_ifg.read_text())
    assert data["sdf"]["kind"] == "mesh"
    assert os.path.abspath(str(stl_file)) == data["sdf"]["path"]

def test_cli_combine(tmp_path):
    """Test that the 'combine' command merges IFG files correctly."""
    # Create two minimal IFG files
    input1 = tmp_path / "a.ifg"
    input2 = tmp_path / "b.ifg"
    minimal = {"format": "implicit", "bounds": {"xmin": 0, "xmax": 1, "ymin": 0, "ymax": 1, "zmin": 0, "zmax": 1}, "sdf": {"kind": "sphere", "radius": 1}}
    input1.write_text(json.dumps(minimal))
    input2.write_text(json.dumps(minimal))

    out_ifg = tmp_path / "combined.ifg"
    args = [
        sys.executable, cli_script,
        "combine",
        "--mode", "union",
        "--inputs", str(input1), str(input2),
        "--bounds", "0", "1", "0", "1", "0", "1",
        "--output", str(out_ifg)
    ]
    result = subprocess.run(args, capture_output=True, text=True)
    assert result.returncode == 0, f"Combine command failed: {result.stderr}"
    assert out_ifg.exists(), "Combined .ifg file not created."
    data = json.loads(out_ifg.read_text())
    assert data["sdf"]["kind"] == "union"
    assert set(data["sdf"]["inputs"]) == {str(input1), str(input2)}

def test_cli_slice_help():
    """Ensure that running 'slice --help' returns exit code 0 and shows slice description."""
    result = subprocess.run([sys.executable, cli_script, "slice", "--help"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "--ifg IFG" in result.stdout

if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__]))