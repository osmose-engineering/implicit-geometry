import trimesh

# 1. Make a unit‐sphere (radius = 1) centered at the origin
sphere = trimesh.creation.icosphere(subdivisions=2, radius=1.0)

# 2. Export to an STL so loader.py can pick it up
sphere.export('examples/sphere.stl')
print("Wrote examples/sphere.stl")