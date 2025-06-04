
import numpy as np
from typing import Callable, Tuple, List
import random

# Type alias: an SDF is any function taking (x, y, z) -> float
SDF = Callable[[float, float, float], float]

def voronoi_foam(points: np.ndarray, thickness: float) -> SDF:
    """
    Approximate Voronoi foam as the region around seed points where walls
    lie along bisectors between nearest seeds. For any location (x, y, z):
      - Compute distances to all seed points: d_i = ||P - points[i]||.
      - Let d1 = smallest distance, d2 = second-smallest distance.
      - The signed-distance to the nearest Voronoi wall is (d2 - d1) / 2.
      - Subtract thickness so that inside film (within thickness/2 on each side)
        is solid (SDF <= 0).
    The result is a level-set of thickness around each planar bisector.
    """
    # Ensure `points` is a (N, 3) array
    pts = np.asarray(points, dtype=np.float64)
    if pts.ndim != 2 or pts.shape[1] != 3:
        raise ValueError("`points` must be an (N, 3) NumPy array")

    def _sdf(x: float, y: float, z: float) -> float:
        # Create a 1x3 array for the query point
        p = np.array([x, y, z], dtype=np.float64)
        # Compute squared distances to all seeds
        diffs = pts - p  # shape (N, 3)
        dists_sq = np.einsum('ij,ij->i', diffs, diffs)
        # Sort to find two smallest distances
        idx = np.argpartition(dists_sq, 1)
        # idx[0] is index of nearest seed, idx[1] second-nearest in squared-dists
        d1 = np.sqrt(dists_sq[idx[0]])
        d2 = np.sqrt(dists_sq[idx[1]])
        # Signed distance to nearest bisector
        sdf_val = (d2 - d1) / 2.0
        # Subtract thickness so that walls of given thickness are negative (solid)
        return sdf_val - thickness

    return _sdf

def sample_points_inside(sdf: SDF, bounds: Tuple[Tuple[float, float], Tuple[float, float], Tuple[float, float]], n_points: int) -> List[Tuple[float, float, float]]:
    """
    Generate random points uniformly inside the implicit body defined by sdf < 0,
    using rejection sampling within the given axis-aligned bounding box.
    bounds: ((xmin, xmax), (ymin, ymax), (zmin, zmax))
    """
    (xmin, xmax), (ymin, ymax), (zmin, zmax) = bounds
    pts: List[Tuple[float, float, float]] = []
    tries = 0
    max_tries = n_points * 50

    while len(pts) < n_points:
        x = random.uniform(xmin, xmax)
        y = random.uniform(ymin, ymax)
        z = random.uniform(zmin, zmax)
        if sdf(x, y, z) < 0.0:
            pts.append((x, y, z))
        tries += 1
        if tries > max_tries:
            raise RuntimeError(f"Too many rejects ({tries})—maybe volume is too small.")

    return pts

def approximate_surface_samples(sdf: SDF, bounds: Tuple[Tuple[float, float], Tuple[float, float], Tuple[float, float]], n_seeds: int, eps: float = 1e-3, max_tries: int = 1000000) -> List[Tuple[float, float, float]]:
    """
    Generate random points near the zero-level set (|sdf| < eps) for the implicit body,
    using rejection sampling within the bounding box. May be refined by project_to_surface.
    """
    (xmin, xmax), (ymin, ymax), (zmin, zmax) = bounds
    seeds: List[Tuple[float, float, float]] = []
    tries = 0

    while len(seeds) < n_seeds and tries < max_tries:
        x = random.uniform(xmin, xmax)
        y = random.uniform(ymin, ymax)
        z = random.uniform(zmin, zmax)
        val = sdf(x, y, z)
        if abs(val) < eps:
            seeds.append((x, y, z))
        tries += 1

    if len(seeds) < n_seeds:
        raise RuntimeError(f"Could only find {len(seeds)} surface candidates in {tries} tries.")

    return seeds

def project_to_surface(sdf: SDF, point: Tuple[float, float, float], delta: float = 1e-4, tol: float = 1e-6) -> Tuple[float, float, float]:
    """
    Perform one Newton-like step to push `point` onto the zero-level set of sdf.
    """
    x, y, z = point
    f0 = sdf(x, y, z)
    if abs(f0) < tol:
        return (x, y, z)

    # Estimate gradient via finite differences
    def dfdx(xx, yy, zz):
        return (sdf(xx + delta, yy, zz) - sdf(xx - delta, yy, zz)) / (2 * delta)
    def dfdy(xx, yy, zz):
        return (sdf(xx, yy + delta, zz) - sdf(xx, yy - delta, zz)) / (2 * delta)
    def dfdz(xx, yy, zz):
        return (sdf(xx, yy, zz + delta) - sdf(xx, yy, zz - delta)) / (2 * delta)

    gx = dfdx(x, y, z)
    gy = dfdy(x, y, z)
    gz = dfdz(x, y, z)
    grad_norm_sq = gx * gx + gy * gy + gz * gz
    if grad_norm_sq < 1e-12:
        return (x, y, z)

    x_new = x - f0 * gx / grad_norm_sq
    y_new = y - f0 * gy / grad_norm_sq
    z_new = z - f0 * gz / grad_norm_sq

    return (x_new, y_new, z_new)