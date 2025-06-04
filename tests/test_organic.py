

import sys
import os
import numpy as np

# Ensure project root is on sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from implicit_core.lattice.organic import voronoi_foam

def test_voronoi_foam_two_points():
    # Two seed points along x-axis
    pts = np.array([[0.0, 0.0, 0.0], [2.0, 0.0, 0.0]])
    # Zero thickness: wall exactly at x = 1
    sdf = voronoi_foam(points=pts, thickness=0.0)

    # At x=1,y=0,z=0, should be on the wall: sdf ~ 0
    assert abs(sdf(1.0, 0.0, 0.0)) < 1e-6

    # At x=0.5, closer to first seed: d1=0.5, d2=1.5 => (1.5-0.5)/2 = 0.5
    assert abs(sdf(0.5, 0.0, 0.0) - 0.5) < 1e-6

    # At x=1.5, closer to second seed: d1=0.5, d2=1.5 => (1.5-0.5)/2 = 0.5
    assert abs(sdf(1.5, 0.0, 0.0) - 0.5) < 1e-6

    # With thickness=0.2, the wall thickens: sdf at x=1 should be -0.2
    sdf_thick = voronoi_foam(points=pts, thickness=0.2)
    assert abs(sdf_thick(1.0, 0.0, 0.0) + 0.2) < 1e-6

if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__]))