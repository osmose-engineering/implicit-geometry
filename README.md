# implicit-geometry

Implicit Geometry File Format (IFG)

This repository kickstarts an open‐source, JSON‐based format for defining implicit geometry. Our aim is to let designers describe shapes, lattices and Boolean operations in a human‐readable graph, then slice directly—no mesh export needed.

What’s Included

In this repo you’ll find:
	•	A minimal schema under schema/ defining primitives (Cube, Sphere, Cylinder), transforms, booleans and lattices.
	•	Sample .ifg files in examples/, including a basic 10 mm cube and a gyroid lattice demo.
	•	A Python stub (loader.py) that reads an .ifg, reconstructs the node graph and evaluates the implicit field at a point.
	•	A placeholder directory pwsz_converter/ where we’ll build the layer‐sampling to .pwsz utility.

Quick Start

First, clone the repo and jump into the examples:

git clone https://github.com/your‐org/ifg.git
cd ifg/examples

Then run the loader on the cube example:

python3 ../loader.py cube.ifg

You should see a sample evaluation (for the cube, at the origin it should return -5.0, since it lies inside a 5 mm half‐extent cube).

Next Steps

Once you’ve confirmed the loader works, you can:
	1.	Extend loader.py to handle all node types (Sphere, Union, Lattice, etc.).
	2.	Write the sampling loop in pwsz_converter/ to generate bitmaps layer by layer.
	3.	Wrap those bitmaps into a .pwsz file and test on your Photon Mono M7.

Contributing

We welcome collaboration. Whether you want to add new primitives, improve the Python loader, or prototype a CLI tool for .pwsz conversion, feel free to open an issue or send a pull request.

License

This project is released under the Apache 2.0 License—see LICENSE for details.
