import math
from typing import Callable, Tuple

# Type alias: an SDF is any function that takes (x, y, z) and returns a float
SDF = Callable[[float, float, float], float]


def sphere(center: Tuple[float, float, float], radius: float) -> SDF:
    """
    Signed distance for a sphere of given radius, centered at (cx, cy, cz).
    SDF(x,y,z) < 0 inside, > 0 outside, = 0 on the surface.
    """
    cx, cy, cz = center

    def _sdf(x: float, y: float, z: float) -> float:
        dx = x - cx
        dy = y - cy
        dz = z - cz
        return math.sqrt(dx*dx + dy*dy + dz*dz) - radius

    return _sdf


def box(center: Tuple[float, float, float],
        half_widths: Tuple[float, float, float]) -> SDF:
    """
    Axis‐aligned box centered at (cx, cy, cz) with half‐extents (hx, hy, hz).
    Standard “SDF for AABB”:
      dx = abs(x-cx) - hx, etc.  Outside-of‐box: length(max(dx, 0)) 
      Inside‐box: max(dx, dy, dz)
    """
    cx, cy, cz = center
    hx, hy, hz = half_widths

    def _sdf(x: float, y: float, z: float) -> float:
        dx = abs(x - cx) - hx
        dy = abs(y - cy) - hy
        dz = abs(z - cz) - hz

        # If any component > 0, we’re outside in that direction
        outside_dist = math.sqrt(max(dx, 0)**2 +
                                 max(dy, 0)**2 +
                                 max(dz, 0)**2)
        # If all components ≤ 0, we’re inside; distance = max component
        inside_dist = max(dx, dy, dz)
        return outside_dist if outside_dist > 0 else inside_dist

    return _sdf


def cylinder(axis_point: Tuple[float, float, float],
             axis_dir: Tuple[float, float, float],
             radius: float) -> SDF:
    """
    Infinite cylinder with specified axis (through P0 in direction V) and radius.
    Distance = length( (P-P0) - proj_V(P-P0) ) - radius.
    Note: P0 = axis_point, V = normalized axis_dir.
    """
    px0, py0, pz0 = axis_point
    vx, vy, vz = axis_dir
    # Normalize V
    inv_len = 1.0 / math.sqrt(vx*vx + vy*vy + vz*vz)
    vx *= inv_len; vy *= inv_len; vz *= inv_len

    def _sdf(x: float, y: float, z: float) -> float:
        dx = x - px0
        dy = y - py0
        dz = z - pz0
        # Project (dx,dy,dz) onto V: t = dot(D, V)
        t = dx*vx + dy*vy + dz*vz
        # Closest point on axis = P0 + t*V. So vector to axis = D - t*V.
        ax = dx - t*vx
        ay = dy - t*vy
        az = dz - t*vz
        return math.sqrt(ax*ax + ay*ay + az*az) - radius

    return _sdf


def torus(center: Tuple[float, float, float],
          ring_radius: float, tube_radius: float) -> SDF:
    """
    Torus centered at (cx,cy,cz) lying in the XY plane.
    ring_radius = distance from center to centerline of tube,
    tube_radius = radius of the tube.
    SDF:  let P' = P - C, project onto XY: q = (length(P'_{xy}) - ring_radius, P'_z).
          return length(q) - tube_radius.
    """
    cx, cy, cz = center

    def _sdf(x: float, y: float, z: float) -> float:
        dx = x - cx
        dy = y - cy
        dz = z - cz
        qx = math.sqrt(dx*dx + dy*dy) - ring_radius
        qy = dz
        return math.sqrt(qx*qx + qy*qy) - tube_radius

    return _sdf