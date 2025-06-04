from typing import List, Callable
import math

SDF = Callable[[float, float, float], float]


def union(*sdfs: SDF) -> SDF:
    """
    Returns an SDF that is the union of all provided SDFs.
    u(x) = min(sdf1(x), sdf2(x), …).
    """
    def _u(x: float, y: float, z: float) -> float:
        return min(sdf(x, y, z) for sdf in sdfs)
    return _u


def intersect(*sdfs: SDF) -> SDF:
    """
    Intersection: i(x) = max(sdf1(x), sdf2(x), …).
    """
    def _i(x: float, y: float, z: float) -> float:
        return max(sdf(x, y, z) for sdf in sdfs)
    return _i


def subtract(a: SDF, b: SDF) -> SDF:
    """
    Difference: subtract b from a = max(a(x), -b(x)).
    """
    def _s(x: float, y: float, z: float) -> float:
        return max(a(x, y, z), -b(x, y, z))
    return _s


def smooth_union(a: SDF, b: SDF, k: float) -> SDF:
    """
    A “smooth” union using the polynomial blend parameter k.
    ref: Inigo Quilez’s smooth min function:
      h = clamp(0.5 + 0.5*(b(x)-a(x))/k, 0, 1)
      return lerp(b(x), a(x), h) - k*h*(1-h)
    """
    def _su(x: float, y: float, z: float) -> float:
        va = a(x, y, z)
        vb = b(x, y, z)
        h = max(0.0, min(1.0, 0.5 + 0.5*(vb - va)/k))
        # linear interpolation + polynomial correction
        return (vb*h + va*(1-h)) - k*h*(1-h)
    return _su


def smooth_subtract(a: SDF, b: SDF, k: float) -> SDF:
    """
    Smooth subtraction: essentially unioning a with inverted b.
    """
    def _ss(x: float, y: float, z: float) -> float:
        va = a(x, y, z)
        vb = -b(x, y, z)
        h = max(0.0, min(1.0, 0.5 + 0.5*(vb - va)/k))
        return (vb*h + va*(1-h)) - k*h*(1-h)
    return _ss


def smooth_intersect(a: SDF, b: SDF, k: float) -> SDF:
    """
    Smooth intersection: use a/b swapped in the formula above.
    """
    def _si(x: float, y: float, z: float) -> float:
        va = a(x, y, z)
        vb = b(x, y, z)
        h = max(0.0, min(1.0, 0.5 + 0.5*(va - vb)/k))
        return (vb*h + va*(1-h)) + k*h*(1-h)
    return _si