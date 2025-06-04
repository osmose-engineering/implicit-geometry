#!/usr/bin/env python3
"""
Implicit CLI

Usage examples:
  python implicit.py primitive sphere --center 0 0 0 --radius 10 --bounds -10 10 -10 10 -10 10 --output sphere.ifg
  python implicit.py mesh --mesh model.stl --output model.ifg
  python implicit.py combine union --inputs a.ifg b.ifg --bounds -10 10 -10 10 -10 10 --output combined.ifg
  python implicit.py lattice periodic --type gyroid --cell_size 10 --thickness 0.5 \
    --bounds 0 20 0 20 0 20 --output gyroid.ifg
  python implicit.py lattice organic --seeds 1000 --thickness 0.2 \
    --bounds 0 20 0 20 0 20 --output voronoi.ifg
"""


import argparse
import json
import os
import sys

# Ensure project root is on sys.path for module imports
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import numpy as np

from implicit_core.primitives import sphere, box, cylinder, torus
from implicit_core.mesh import mesh_to_sdf, mesh_bounds
from implicit_core.booleans import union, intersect, subtract
from implicit_core.lattice.periodic import gyroid, schwarz_p, diamond
from implicit_core.lattice.organic import voronoi_foam, sample_points_inside, approximate_surface_samples, project_to_surface
from sampler import generate_png_slices, wrap_to_ctb

def write_ifg(output_path: str, bounds: dict, sdf_description: dict):
    """
    Write a simple .ifg file containing JSON with bounding box and SDF description.
    """
    data = {
        "format": "implicit",
        "bounds": bounds,
        "sdf": sdf_description
    }
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Implicit model written to {output_path}")

def main():
    parser = argparse.ArgumentParser(description="Implicit modeling CLI")
    subparsers = parser.add_subparsers(dest="command")

    # Primitive subparser
    prim_parser = subparsers.add_parser("primitive", help="Generate a primitive SDF")
    prim_sub = prim_parser.add_subparsers(dest="prim_type")

    # Sphere primitive
    sph_parser = prim_sub.add_parser("sphere", help="Create a sphere")
    sph_parser.add_argument("--center", type=float, nargs=3, required=True, metavar=("cx","cy","cz"))
    sph_parser.add_argument("--radius", type=float, required=True)
    sph_parser.add_argument("--bounds", type=float, nargs=6, metavar=("xmin","xmax","ymin","ymax","zmin","zmax"), required=True)
    sph_parser.add_argument("--output", required=True)

    # Box primitive
    box_parser = prim_sub.add_parser("box", help="Create a box")
    box_parser.add_argument("--center", type=float, nargs=3, required=True, metavar=("cx","cy","cz"))
    box_parser.add_argument("--halfwidths", type=float, nargs=3, required=True, metavar=("hx","hy","hz"))
    box_parser.add_argument("--bounds", type=float, nargs=6, metavar=("xmin","xmax","ymin","ymax","zmin","zmax"), required=True)
    box_parser.add_argument("--output", required=True)

    # Cylinder primitive
    cyl_parser = prim_sub.add_parser("cylinder", help="Create a cylinder")
    cyl_parser.add_argument("--axis_point", type=float, nargs=3, required=True, metavar=("px","py","pz"))
    cyl_parser.add_argument("--axis_dir", type=float, nargs=3, required=True, metavar=("vx","vy","vz"))
    cyl_parser.add_argument("--radius", type=float, required=True)
    cyl_parser.add_argument("--bounds", type=float, nargs=6, metavar=("xmin","xmax","ymin","ymax","zmin","zmax"), required=True)
    cyl_parser.add_argument("--output", required=True)

    # Torus primitive
    tor_parser = prim_sub.add_parser("torus", help="Create a torus")
    tor_parser.add_argument("--center", type=float, nargs=3, required=True, metavar=("cx","cy","cz"))
    tor_parser.add_argument("--ring_radius", type=float, required=True)
    tor_parser.add_argument("--tube_radius", type=float, required=True)
    tor_parser.add_argument("--bounds", type=float, nargs=6, metavar=("xmin","xmax","ymin","ymax","zmin","zmax"), required=True)
    tor_parser.add_argument("--output", required=True)

    # Mesh subparser
    mesh_parser = subparsers.add_parser("mesh", help="Convert a mesh STL to implicit")
    mesh_parser.add_argument("--mesh", required=True, help="Path to STL file")
    mesh_parser.add_argument("--output", required=True)

    # Combine subparser
    combine_parser = subparsers.add_parser("combine", help="Combine two or more IFG files")
    combine_parser.add_argument("--mode", required=True, choices=["union","intersect","subtract"], help="Boolean operation")
    combine_parser.add_argument("--inputs", nargs="+", required=True, help="List of IFG files")
    combine_parser.add_argument("--bounds", type=float, nargs=6, metavar=("xmin","xmax","ymin","ymax","zmin","zmax"), required=True)
    combine_parser.add_argument("--output", required=True)

    # Lattice subparser
    lattice_parser = subparsers.add_parser("lattice", help="Generate lattice-based implicit models")
    lattice_subparsers = lattice_parser.add_subparsers(dest="lattice_type")

    # Periodic lattice
    periodic_parser = lattice_subparsers.add_parser("periodic", help="Generate a periodic lattice (gyroid, schwarz_p, diamond)")
    periodic_parser.add_argument("--type", required=True, choices=["gyroid","schwarz_p","diamond"], help="Type of periodic lattice")
    periodic_parser.add_argument("--cell_size", type=float, required=True, help="Cell size for periodic lattice")
    periodic_parser.add_argument("--thickness", type=float, default=0.0, help="Thickness (level-set shift)")
    periodic_parser.add_argument("--bounds", type=float, nargs=6, metavar=("xmin","xmax","ymin","ymax","zmin","zmax"), required=True, help="Axis-aligned bounding box for the lattice region")
    periodic_parser.add_argument("--output", required=True)

    # Organic lattice
    organic_parser = lattice_subparsers.add_parser("organic", help="Generate an organic Voronoi foam")
    organic_parser.add_argument("--seeds", type=int, required=True, help="Number of random seed points")
    organic_parser.add_argument("--thickness", type=float, default=0.0, help="Thickness (level-set shift) of Voronoi walls")
    organic_parser.add_argument("--surface_seeds", type=int, default=0, help="Number of seeds to place on surface")
    organic_parser.add_argument("--bounds", type=float, nargs=6, metavar=("xmin","xmax","ymin","ymax","zmin","zmax"), required=True, help="Axis-aligned bounding box for sampling points")
    organic_parser.add_argument("--output", required=True, help="Output .ifg filename")
    organic_parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")

    # Slice subparser
    slice_parser = subparsers.add_parser("slice", help="Slice an IFG to PNGs and package as CTB")
    slice_parser.add_argument("--ifg", required=True, help="Path to the .ifg input file")
    slice_parser.add_argument("--slice_dir", required=True, help="Directory to write PNG slices")
    slice_parser.add_argument("--archive", required=True, help="Path for output CTB archive")
    slice_parser.add_argument("--layer_thickness", type=float, required=True, help="Layer thickness in mm")
    slice_parser.add_argument("--resx", type=int, required=True, help="Slice image width in pixels")
    slice_parser.add_argument("--resy", type=int, required=True, help="Slice image height in pixels")

    args = parser.parse_args()

    if args.command == "primitive":
        # Sphere
        if args.prim_type == "sphere":
            cx, cy, cz = args.center
            sdf_fn = sphere((cx, cy, cz), args.radius)
            b = args.bounds
            bounds_dict = {"xmin": b[0], "xmax": b[1], "ymin": b[2], "ymax": b[3], "zmin": b[4], "zmax": b[5]}
            sdf_desc = {"kind": "sphere", "center": [cx, cy, cz], "radius": args.radius}
            write_ifg(args.output, bounds_dict, sdf_desc)

        # Box
        elif args.prim_type == "box":
            cx, cy, cz = args.center
            hx, hy, hz = args.halfwidths
            sdf_fn = box((cx, cy, cz), (hx, hy, hz))
            b = args.bounds
            bounds_dict = {"xmin": b[0], "xmax": b[1], "ymin": b[2], "ymax": b[3], "zmin": b[4], "zmax": b[5]}
            sdf_desc = {"kind": "box", "center": [cx, cy, cz], "halfwidths": [hx, hy, hz]}
            write_ifg(args.output, bounds_dict, sdf_desc)

        # Cylinder
        elif args.prim_type == "cylinder":
            px, py, pz = args.axis_point
            vx, vy, vz = args.axis_dir
            sdf_fn = cylinder((px, py, pz), (vx, vy, vz), args.radius)
            b = args.bounds
            bounds_dict = {"xmin": b[0], "xmax": b[1], "ymin": b[2], "ymax": b[3], "zmin": b[4], "zmax": b[5]}
            sdf_desc = {"kind": "cylinder", "axis_point": [px, py, pz], "axis_dir": [vx, vy, vz], "radius": args.radius}
            write_ifg(args.output, bounds_dict, sdf_desc)

        # Torus
        elif args.prim_type == "torus":
            cx, cy, cz = args.center
            ring_r = args.ring_radius
            tube_r = args.tube_radius
            sdf_fn = torus((cx, cy, cz), ring_r, tube_r)
            b = args.bounds
            bounds_dict = {"xmin": b[0], "xmax": b[1], "ymin": b[2], "ymax": b[3], "zmin": b[4], "zmax": b[5]}
            sdf_desc = {"kind": "torus", "center": [cx, cy, cz], "ring_radius": ring_r, "tube_radius": tube_r}
            write_ifg(args.output, bounds_dict, sdf_desc)

        else:
            print("Unknown primitive type.")
            sys.exit(1)

    elif args.command == "mesh":
        # Load mesh, compute bounds, and output IFG
        min_corner, max_corner = mesh_bounds(args.mesh)
        bounds_dict = {"xmin": min_corner[0], "xmax": max_corner[0],
                       "ymin": min_corner[1], "ymax": max_corner[1],
                       "zmin": min_corner[2], "zmax": max_corner[2]}
        sdf_desc = {"kind": "mesh", "path": os.path.abspath(args.mesh)}
        write_ifg(args.output, bounds_dict, sdf_desc)

    elif args.command == "combine":
        # Load all IFG descriptions, combine bounds, and record operation
        inputs = []
        for path in args.inputs:
            with open(path, "r") as f:
                data = json.load(f)
            inputs.append(data)
        # Simplest bounds: take provided CLI bounds
        b = args.bounds
        bounds_dict = {"xmin": b[0], "xmax": b[1],
                       "ymin": b[2], "ymax": b[3],
                       "zmin": b[4], "zmax": b[5]}
        sdf_desc = {"kind": args.mode, "inputs": args.inputs}
        write_ifg(args.output, bounds_dict, sdf_desc)

    elif args.command == "lattice":
        if args.lattice_type == "periodic":
            # Extract periodic parameters
            b = args.bounds
            bounds_dict = {"xmin": b[0], "xmax": b[1],
                           "ymin": b[2], "ymax": b[3],
                           "zmin": b[4], "zmax": b[5]}

            # Choose the correct SDF constructor
            if args.type == "gyroid":
                sdf_fn = gyroid(cell_size=args.cell_size, thickness=args.thickness)
            elif args.type == "schwarz_p":
                sdf_fn = schwarz_p(cell_size=args.cell_size, thickness=args.thickness)
            else:
                sdf_fn = diamond(cell_size=args.cell_size, thickness=args.thickness)

            sdf_desc = {"kind": args.type, "cell_size": args.cell_size, "thickness": args.thickness}
            write_ifg(args.output, bounds_dict, sdf_desc)

        elif args.lattice_type == "organic":
            # Set random seed if provided
            if args.seed is not None:
                np.random.seed(args.seed)
                import random
                random.seed(args.seed)

            b = args.bounds
            bounds = ((b[0], b[1]), (b[2], b[3]), (b[4], b[5]))
            bounds_dict = {"xmin": b[0], "xmax": b[1],
                           "ymin": b[2], "ymax": b[3],
                           "zmin": b[4], "zmax": b[5]}

            # Example: sample interior with bounding sphere SDF or user-supplied; using bounding box edges
            # Here we sample uniformly inside the bounding box rather than an SDF body
            interior_pts = sample_points_inside(
                sdf=lambda x,y,z: -1.0,  # flat negative inside to fill entire box
                bounds=bounds,
                n_points=args.seeds
            )

            surface_pts = []
            if args.surface_seeds > 0:
                surface_pts = approximate_surface_samples(
                    sdf=lambda x,y,z: 0.0,  # flat zero SDF to allow any surface point
                    bounds=bounds,
                    n_seeds=args.surface_seeds
                )
                surface_pts = [project_to_surface(lambda x,y,z: 0.0, pt) for pt in surface_pts]

            pts = np.vstack([interior_pts, surface_pts]) if surface_pts else np.vstack([interior_pts])
            sdf_fn = voronoi_foam(points=pts, thickness=args.thickness)
            sdf_desc = {"kind": "voronoi_foam",
                        "seed_count": args.seeds,
                        "surface_seed_count": args.surface_seeds,
                        "thickness": args.thickness}
            write_ifg(args.output, bounds_dict, sdf_desc)

        else:
            print("Unknown lattice type. Use 'periodic' or 'organic'.")
            sys.exit(1)

    elif args.command == "slice":
        # Generate PNG slices
        bounds, num_layers = generate_png_slices(
            args.ifg,
            args.slice_dir,
            args.layer_thickness,
            args.resx,
            args.resy
        )
        print(f"Generated {num_layers} PNG slices in {args.slice_dir}")

        # Package as CTB
        wrap_to_ctb(
            png_folder=args.slice_dir,
            output_ctb=args.archive,
            pixel_x=args.resx,
            pixel_y=args.resy,
            layer_thickness=args.layer_thickness,
            exposure_time=2000,
            bottom_exposure_time=5000,
            num_bottom_layers=5,
            z_lift_dist=6.0,
            z_lift_speed=5.0,
            z_retract_speed=2.0
        )
        print(f"CTB archive written to {args.archive}")

    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()