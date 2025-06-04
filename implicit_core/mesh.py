import numpy as np
import trimesh
from trimesh.proximity import ProximityQuery
from typing import Callable, Tuple

# Type alias: an SDF is any function that takes (x, y, z) and returns a float
SDF = Callable[[float, float, float], float]

def mesh_to_sdf(stl_path: str) -> SDF:
    """
    Load a mesh from the given STL file and return a signed-distance function (SDF).

    The returned function accepts (x, y, z) coordinates and returns the signed
    distance to the mesh surface: negative inside, positive outside, zero on surface.
    """
    mesh = trimesh.load(stl_path, force='mesh')
    if mesh.is_empty:
        raise ValueError(f"Mesh at '{stl_path}' is empty or could not be loaded.")

    # Ensure mesh is watertight for correct inside/outside classification
    if not mesh.is_watertight:
        mesh = mesh.convex_hull

    # Create a proximity query for unsigned distance
    pq = ProximityQuery(mesh)

    def sdf(x: float, y: float, z: float) -> float:
        # Prepare a single-point query
        point = np.array([[x, y, z]], dtype=np.float64)
        # Compute signed distance (may be positive or negative)
        signed_val = pq.signed_distance(point)[0]
        # Use absolute value for magnitude
        dist = abs(signed_val)
        # Determine if point is inside using ray casting
        inside = mesh.contains(point)[0]
        return -dist if inside else float(dist)

    return sdf

def mesh_bounds(stl_path: str) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
    """
    Return the axis-aligned bounding box of the mesh as (min_corner, max_corner).
    Each corner is a tuple of (x, y, z).
    """
    mesh = trimesh.load(stl_path, force='mesh')
    if mesh.is_empty:
        raise ValueError(f"Mesh at '{stl_path}' is empty or could not be loaded.")
    
    bounds = mesh.bounds  # shape (2, 3): [[minx, miny, minz], [maxx, maxy, maxz]]
    min_corner = tuple(bounds[0].tolist())
    max_corner = tuple(bounds[1].tolist())
    return min_corner, max_corner