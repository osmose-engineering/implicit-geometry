# Implicit Geometry File Format (IFG)

Jumpstart an open-source, JSON-centric format for defining implicit geometry. Our goal is to let designers describe shapes, lattices and Boolean operations in a human-readable graph and slice directly—no mesh export required.

## What’s Included

- **Schema/**: minimal definitions for primitives (Cube, Sphere, Cylinder), transforms, booleans and lattices.
- **Examples/**: `.ifg` files showing a 10 mm cube, a simple lattice-in-shell, etc.
- **loader.py**: Python reference loader that reads an `.ifg`, builds the node graph and evaluates the implicit field at any `(x,y,z)`.
- **pwsz_converter/**: contains `sampler.py` which generates PNG slices layer by layer and wraps them into a `.pm7m` file for Anycubic Photon Mono M7 Max.

## Quick Start

1. Clone the repo:
   ```bash
   git clone https://github.com/your-org/ifg.git
   cd ifg
   ```
2. Verify the loader on the cube example:
   ```bash
   python3 loader.py examples/cube.ifg
   ```
   You should see a field evaluation at the origin (e.g. `Field at (0,0,0): -5.0`).

3. Generate slices and package for your Photon Mono:
   ```bash
   python3 pwsz_converter/sampler.py
   ```
   - This writes PNG slices into `output_slices/` and produces `output.pm7m`.

4. Copy `output.pm7m` to your printer’s SD card and print.

## Next Steps

- Enhance `loader.py` to support any custom node types or numerical tolerances.
- Convert `sampler.py` into a CLI tool with flags for input path, layer thickness, resolution and output file.
- Add bounding-box metadata support in your `.ifg` files to avoid hard-coded defaults.
- Provide more examples (nested booleans, complex lattices) and automated tests.

## Contributing

Contributions are welcome! Fork the repo, open issues for discussion, or submit pull requests to:
- Add new primitives (e.g. torus, sweep profiles)
- Improve performance (GPU acceleration hooks)
- Extend the `.pm7m` metadata schema for printer settings

## License

Distributed under Apache 2.0. See `LICENSE` for details.
