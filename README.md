# Implicit Geometry File Format (IFG)

Jumpstart an open‐source, JSON‐centric format for defining implicit geometry. Our goal is to let designers describe shapes, lattices, and Boolean operations in a human‐readable graph, then slice directly—no mesh export required.

## What’s Included

- **Schema/**: Minimal definitions for primitives (Cube, Sphere, Cylinder), transforms, booleans, and lattices.
- **Examples/**: `.ifg` files showing a 10 mm cube, a simple lattice‐in‐shell, etc.
- **loader.py**: Python reference loader that reads an `.ifg`, builds the node graph, and evaluates the implicit field at any `(x,y,z)`.
- **pwsz_converter/**: Contains `sampler.py`, which:
  1. Generates PNG slices layer by layer, and  
  2. Packages them into either a `.ctb` (ChituBox/modern) or `.pwsz` (Anycubic Photon) file.

## Quick Start

1. **Clone the repo**
   ```bash
   git clone https://github.com/your‐org/ifg.git
   cd ifg
   ```

2. **Install dependencies**
   ```bash
   pip3 install pillow
   ```

3. **Verify the loader**
   ```bash
   python3 loader.py examples/cube.ifg
   ```
   You should see something like:
   ```
   Field at (0,0,0): -5.0
   ```

4. **Generate slices & package**
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

   If you still want to target Anycubic’s `.pwsz`, swap `--format pwsz`:  
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
   You’ll get `cube_print.pwsz`—loadable in the Photon workshop or Anycubic’s software.

5. **Load into your slicer**
   - Open `cube_print.ctb` in ChituBox. You should see your layer stack in the preview, complete with default exposure and bottom‐layer settings.  
   - If you generated a `.pwsz`, drop it into Anycubic’s slicer. You should see your layers—if not, check the JSON keys or naming conventions.

## Next Steps

- Extend `loader.py` for more primitives (torus, sweep profiles).  
- Improve `sampler.py` to customize CTB parameters (e.g., specific exposure times, resin name).  
- Add more examples under `examples/` (nested booleans, multi‐material lattices).  
- Write automated tests to confirm each IFG node type evaluates as expected.

## Contributing

Contributions welcome—fork, open issues, or send pull requests for:

- New implicit primitives (torus, revolved profiles).  
- GPU‐accelerated sampling (CUDA or OpenCL).  
- Support for other slice formats (SLC, GF, proprietary).  

## License

Distributed under Apache 2.0. See `LICENSE` for details.