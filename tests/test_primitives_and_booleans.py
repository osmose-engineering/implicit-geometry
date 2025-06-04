import sys
import os

# Ensure the project root (parent of tests/) is on sys.path so that implicit_core can be imported
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from implicit_core.primitives import sphere, box
from implicit_core.booleans import union, subtract

# 1) Sphere of radius 10 at origin
s1 = sphere((0, 0, 0), 10.0)

# 2) Box of half‐extents (5,5,5) centered at (7,0,0)
b1 = box((7, 0, 0), (5, 5, 5))

# 3) Union and then subtract a smaller sphere
u1 = union(s1, b1)
diff1 = subtract(u1, sphere((0, 0, 0), 3.0))

def test_signed_distances():
    # 4) Sample a few points and verify expected sign/distance behavior
    points = [
        ((0, 0, 0), "inside small sphere"),       # inside the subtracted sphere region
        ((7, 0, 0), "inside box region"),         # inside the box
        ((12, 0, 0), "outside both shapes"),      # outside both sphere and box
        ((0, 10, 0), "on sphere boundary"),       # on the original sphere surface
        ((0, 0, -12), "outside both shapes below")# outside below
    ]

    for (x, y, z), desc in points:
        d = diff1(x, y, z)
        # Check type
        assert isinstance(d, (int, float)), f"Distance not a number at point {(x, y, z)}"
        # Validate sign or approximate zero
        if desc == "inside small sphere":
            assert d > 0, f"Expected positive distance outside final shape but got {d} at {(x, y, z)}"
        elif desc in ("outside both shapes", "outside both shapes below"):
            assert d >= 0, f"Expected non-negative distance (outside or on boundary) but got {d} at {(x, y, z)}"
        elif desc == "inside box region":
            assert d < 0, f"Expected negative (inside final) but got {d} at {(x, y, z)}"
        elif desc == "on sphere boundary":
            assert abs(d) < 1e-6, f"Expected ~0.0 at boundary but got {d} at {(x, y, z)}"

if __name__ == "__main__":
    # When run directly, invoke pytest on this file
    import pytest
    sys.exit(pytest.main([__file__]))