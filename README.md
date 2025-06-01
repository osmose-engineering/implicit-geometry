# Implicit Geometry File Format (IFG)

Jumpstart an open‐source, JSON‐centric format for defining implicit geometry. Our goal is to let designers describe shapes, lattices, Boolean operations, or even arbitrary meshes in a human‐readable graph, then slice directly—no mesh export or mesh‐to‐mesh conversion needed.

## What’s Included

- **Schema/**: Minimal definitions for primitives (Cube, Sphere, Cylinder), transforms, booleans, lattices, and mesh nodes.
- **Examples/**: `.ifg` files showing a 10 mm cube, a simple lattice‐in‐shell, or mesh‐based implicit bodies sourced from an STL.
- **loader.py**: Python reference loader that reads an `.ifg`, builds the node graph, and evaluates the implicit field at any `(x,y,z)`, including support for signed‐distance evaluation of meshes (`Mesh` nodes).
- **pwsz_converter/**: Contains `sampler.py`, which:
  1. Automatically infers bounding boxes, if not provided, from any `Mesh` node.
  2. Generates PNG slices layer by layer.
  3. Packages them into either a `.ctb` (ChituBox/modern) or `.pwsz` (Anycubic Photon) file.

## Generating an IFG from an STL

To convert any arbitrary watertight STL into an IFG with mesh support, use the provided helper script:

```bash
python3 stl_to_ifg.py \
  --stl path/to/your_part.stl \
  --out path/to/your_part.ifg
```

This script:
1. Loads the STL via `trimesh`, fills any holes, and computes `mesh.bounds`.
2. Emits a minimal `.ifg` JSON with:
   - `metadata.bounds` set to the mesh’s axis‐aligned bounding box.
   - A single `Mesh` node pointing at the STL file path.

Once generated, `your_part.ifg` can be sliced without further manual edits.

## Quick Start: From IFG to Slices

1. **Clone the repo**  
   ```bash
   git clone https://github.com/your‐org/ifg.git
   cd ifg
   ```

2. **Install dependencies**  
   ```bash
   pip3 install pillow trimesh rtree
   ```

3. **Generate an IFG (optional)**  
   If you already have an STL and want to automate IFG creation:
   ```bash
   python3 stl_to_ifg.py \
     --stl examples/my_part.stl \
     --out examples/my_part.ifg
   ```
   Otherwise, proceed with any existing `.ifg` in `examples/`.

4. **Verify the loader**  
   ```bash
   python3 loader.py examples/cube.ifg
   ```
   You should see:
   ```
   Field at (0,0,0): -5.0
   ```
   For a `Mesh`‐based IFG (e.g., `sphere_mesh.ifg`), you might see:
   ```
   Field at (0,0,0): -1.000000
   ```

5. **Generate slices & package**  
   By default, we target CTB since it’s the more modern, feature‐rich ChituBox format. For example:
   ```bash
   python3 pwsz_converter/sampler.py \
     --ifg examples/cube.ifg \
     --out cube_print \
     --dir output_slices \
     --slice_thick 0.05 \
     --resx 512 \
     --resy 512 \
     --format ctb
   ```
   This writes:
   - `output_slices/slice_0000.png`, `slice_0001.png`, …  
   - `cube_print.ctb` (ChituBox‐ready).

   To target Anycubic’s `.pwsz`, swap `--format pwsz`:
   ```bash
   python3 pwsz_converter/sampler.py \
     --format pwsz \
     --ifg examples/cube.ifg \
     --out cube_print \
     --dir output_slices \
     --slice_thick 0.05 \
     --resx 512 \
     --resy 512
   ```
   You’ll get `cube_print.pwsz`—loadable in Photon Workshop or Anycubic’s software.

6. **Load into your slicer**  
   - Open `cube_print.ctb` in ChituBox. You should see your layer stack with default exposure settings.  
   - If you generated a `.pwsz`, drop it into Anycubic’s slicer. Verify layers appear correctly.

### Gyroid Infill Support

In addition to slicing solid implicit models, the `sampler.py` script can automatically generate gyroid infill within a mesh. You have two options:

1. **On-the-fly infill via CLI**  
   Pass the `--infill-gyroid <cell_size> <thickness>` arguments to `sampler.py` along with your IFG. For example:
   ```bash
   python3 pwsz_converter/sampler.py \
     --ifg examples/benchy.ifg \
     --out benchy_with_gyroid \
     --dir output_slices \
     --slice_thick 0.05 \
     --resx 512 \
     --resy 512 \
     --format ctb \
     --infill-gyroid 5.0 0.5
   ```
   This will:
   - Create an inner (scaled) copy of the mesh to define a hollow shell.  
   - Subtract the inner copy to extract a thin shell.  
   - Generate a gyroid lattice (with `cell_size` and `thickness`) inside that shell.  
   - Combine shell and infill into a single implicit tree.  
   - Slice using a hybrid approach (planar shell + vectorized 2D gyroid) for fast performance.

2. **Prebuilt infill IFG**  
   Alternatively, write an IFG that contains:
   ```json
   {
     "metadata": { "format_version": "0.1", "units": "mm", "bounds": {} },
     "nodes": [
       { "id": "mesh", "type": "Mesh", "params": { "filename": "examples/3dbenchy.stl" }, "inputs": [] },
       { "id": "shrink", "type": "Transform", "params": { "translate":[0,0,0], "rotate":[0,0,0], "scale":[0.98,0.98,0.98] }, "inputs":["mesh"] },
       { "id": "shell", "type": "Subtract", "params": {}, "inputs":["mesh","shrink"] },
       { "id": "gyroid", "type": "Lattice", "params": { "cell_size":5.0, "thickness":0.5 }, "inputs":[] },
       { "id": "interiorGyroid", "type": "Intersect", "params": {}, "inputs":["shrink","gyroid"] },
       { "id": "final", "type": "Union", "params": {}, "inputs":["shell","interiorGyroid"] }
     ]
   }
   ```
   Save it as, for example, `examples/benchy_hollow_gyroid.ifg`, then slice normally:
   ```bash
   python3 pwsz_converter/sampler.py \
     --ifg examples/benchy_hollow_gyroid.ifg \
     --out benchy_filled_hollow \
     --dir output_slices \
     --slice_thick 0.05 \
     --resx 512 \
     --resy 512 \
     --format ctb
   ```
   The sampler will detect the shell + infill tree and use a fast hybrid slicing method that combines planar mesh sections (for the shell) and vectorized 2D gyroid masks for the interior.

Below either approach, the output PNG stack and final `.ctb` or `.pwsz` file will show the Benchy with a gyroid infill inside a thin shell.

## Dynamic Bounds Detection

`pwsz_converter/sampler.py` automatically checks for `metadata.bounds` in the IFG. If missing, it locates the first `Mesh` node, loads the STL, and uses `mesh.bounds` to infer:
- `xmin, xmax, ymin, ymax, zmin, zmax`

This removes the need to hand‐edit bounds for unknown meshes. Simply point at a `Mesh` node and let the code frame the slice region for you.

## Next Steps

- Create and combine primitive shapes (Cube, Sphere, Cylinder, etc.) directly in IFG; no STL needed.
- Extend `loader.py` to add more implicit primitives (Torus, Sweep profiles, etc.).
- Enhance `sampler.py` to allow custom CTB parameters (e.g., exposure times, resin profiles).
- Add more example IFGs under `examples/` (nested Booleans, multi‐material lattices, complex meshes).
- Write automated tests to confirm each IFG node evaluates correctly (primitives, lattices, meshes).

## Contributing

Contributions welcome—fork, open issues, or send pull requests for:
- Expanding the IFG schema (new node types, composite operations).
- GPU‐accelerated sampling (CUDA or OpenCL backends).
- Support for other slice formats (SLC, GF, proprietary formats).

## License

Distributed under Apache 2.0. See `LICENSE` for details.