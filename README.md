# Implicit Geometry Toolkit (IGT)

This repository provides a small, open-source toolkit for defining, manipulating, and slicing implicit geometry. Rather than relying on meshes (and converting mesh to mesh), we let you describe shapes, lattices, mesh imports, and Boolean combinations as a simple JSON‐centric graph (IFG). A Python loader builds a signed‐distance function (SDF) from that graph, and a sampler produces 2D PNG slices and can package them into printer‐ready formats.

---

## Key Components

1. **Implicit File Format (IFG)**  
   A human‐readable JSON format that describes an implicit shape as a directed acyclic graph of nodes.  
   - **Primitives**: Sphere, Box, Cylinder, etc.  
   - **Transforms**: Translate, Rotate, Scale.  
   - **Boolean Operations**: Union, Intersect, Subtract.  
   - **Lattices**: Gyroid, Voronoi, and other periodic/organic patterns.  
   - **Mesh Nodes**: Point to an external STL, auto‐inferring bounds from the mesh for slicing.

2. **`implicit_core/loader.py`**  
   Loads an IFG, traverses its nodes (primitive, mesh, Boolean, lattice), and constructs a Python function `eval_fn(x, y, z)` that returns a signed‐distance value.  
   - Negative values indicate "inside" the shape, positive are "outside."  
   - Mesh SDFs use `trimesh` and `rtree` to compute signed distances from vertices/faces.

3. **`sampler.py` (in the repo root)**  
   Samples any IFG over its bounding box, layer by layer.  
   - Produces a folder of PNG slice images (binary masks) at a user‐specified resolution and layer thickness.  
   - Calls into the CTB exporter (`exporters/ctb_exporter.py`) to bundle PNGs into a `.ctb` archive with exposure settings.  
   - Can also call the Anycubic exporter (`exporters/anycubic_exporter.py`) to create a `.pm7m`/`.pwsz` file.  

4. **`implicit.py` (CLI Entry Point)**  
   A single command‐line interface exposing all core functionality:  
   - **`primitive`**: Generate standalone primitives (sphere, box, cylinder, etc.) as IFGs.  
   - **`mesh`**: Convert an STL to a minimal IFG with a Mesh node.  
   - **`combine`**: Apply Boolean operations (union/intersect/subtract) to one or more IFG files.  
   - **`lattice`**: Create a periodic or organic lattice over a bounding box.  
   - **`slice`**: Sample an IFG into PNGs and package as CTB or Anycubic format.

5. **`exporters/ctb_exporter.py`**  
   Takes a folder of PNG slices and metadata (resolution, layer thickness, exposure settings) to produce a `.ctb` file compatible with ChituBox and other CTB‐aware slicers.

6. **`exporters/anycubic_exporter.py`**  
   Similar to the CTB exporter, but targets Anycubic Photon `.pm7m` (PWSZ) format. Wraps slice images and helper config files into a Photon Workshop–ready archive.

7. **Utilities and Examples**  
   - **`stl_to_ifg.py`**: Convert any watertight STL into an IFG with a Mesh node (auto‐fills bounds).  
   - **`tests/`**: Pytest test suite covering primitives, mesh SDF, lattices, CLI commands, slicing, and a full end‐to‐end demo.

---

## Quick Start

1. **Install dependencies**  
   ```bash
   pip3 install numpy pillow trimesh shapely rtree
   ```

2. **Generate a simple primitive**  
   ```bash
   python3 implicit.py primitive sphere \
     --center 0 0 0 \
     --radius 1.0 \
     --bounds -1 1 -1 1 -1 1 \
     --output sphere.ifg
   ```
   This writes `sphere.ifg`:
   ```json
   {
     "format": "implicit",
     "bounds": { "xmin": -1, "xmax": 1, "ymin": -1, "ymax": 1, "zmin": -1, "zmax": 1 },
     "sdf": { "kind": "sphere", "center": [0, 0, 0], "radius": 1.0 }
   }
   ```

3. **Slice the IFG to PNGs + CTB**  
   ```bash
   python3 implicit.py slice \
     --ifg sphere.ifg \
     --slice_dir sphere_slices \
     --archive sphere.ctb \
     --layer_thickness 0.5 \
     --resx 64 \
     --resy 64
   ```
   - Produces `sphere_slices/slice_0000.png`, `slice_0001.png`, …  
   - Bundles into `sphere.ctb` ready for ChituBox.

4. **Combine shapes and lattices**  
   - Build a box, subtract a sphere, fill with a gyroid, slice to CTB:
     ```bash
     python3 implicit.py primitive box \
       --center 0 0 0 --halfwidths 20 20 20 \
       --bounds -20 20 -20 20 -20 20 --output box.ifg

     python3 implicit.py primitive sphere \
       --center 0 0 0 --radius 17.5 \
       --bounds -20 20 -20 20 -20 20 --output sphere.ifg

     python3 implicit.py combine \
       --mode subtract --inputs box.ifg sphere.ifg \
       --bounds -20 20 -20 20 -20 20 --output shell.ifg

     python3 implicit.py lattice periodic \
       --type gyroid --cell_size 5.0 --thickness 0.0 \
       --bounds -20 20 -20 20 -20 20 --output gyroid.ifg

     python3 implicit.py combine \
       --mode intersect --inputs shell.ifg gyroid.ifg \
       --bounds -20 20 -20 20 -20 20 --output filled_shell.ifg

     python3 implicit.py slice \
       --ifg filled_shell.ifg \
       --slice_dir demo_slices \
       --archive filled_shell.ctb \
       --layer_thickness 0.05 \
       --resx 512 \
       --resy 512
     ```
   - Final `filled_shell.ctb` contains a hollow box with a gyroid infill.

---

## File Structure Overview

```
├── implicit.py                   # CLI entry point
├── sampler.py                    # Slices any IFG → PNGs + CTB
├── stl_to_ifg.py                 # Convert STL → minimal IFG with Mesh node
├── loader.py                     # Build eval_fn(x,y,z) from node‐based IFG
├── implicit_core/
│   ├── primitives.py             # Sphere, Box, Cylinder SDF definitions
│   ├── mesh.py                   # Mesh → signed‐distance function (Trimesh)
│   ├── lattice/
│   │   ├── periodic.py           # Gyroid, Voronoi lattices
│   │   └── organic.py            # Random/point‐based organic lattices
│   └── loader.py                 # Core graph evaluator for node‐based IFG
├── exporters/
│   ├── ctb_exporter.py           # Bundle PNGs into .ctb archive
│   └── anycubic_exporter.py       # Bundle PNGs into .pm7m/.pwsz archive
└── tests/
    ├── test_primitives_and_booleans.py
    ├── test_mesh.py
    ├── test_lattice.py
    ├── test_organic.py
    ├── test_implicit.py
    ├── test_sampler.py
    └── test_demo.py              # End‐to‐end workflow verification
```

---

## Testing

Run `pytest` at the repo root to validate everything:
- Primitives and Boolean operations return correct signed‐distance values.  
- Mesh‐import SDF and lattice generation work as intended.  
- CLI commands produce valid IFG files.  
- Sampler slices a sphere into PNGs and produces a CTB.  
- The full demo (create shapes, boolean, lattice, slice) completes without error.

---

## Next Steps

- **Expand Primitives**: Add torus, sweep profiles, custom 2D‐to‐3D extrusions.  
- **New Lattices**: Cellular, TPMS families, user‐defined unit cell shapes.  
- **GPU‐Accelerated Slicing**: Swap Python loops for CUDA/OpenCL backends.  
- **Additional Exporters**: Support 3MF, SLC, or other printer formats.  
- **Interactive Viewer**: A minimal GUI (Qt or WebGL) for real‐time slice previews.

For contributions, open issues or PRs. Let’s build a fully open, mesh‐free CAD + slicing workflow together!  