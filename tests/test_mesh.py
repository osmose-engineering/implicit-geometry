import sys
import os
import tempfile
import numpy as np

# Ensure project root is on sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import trimesh
from implicit_core.mesh import mesh_to_sdf, mesh_bounds

def test_mesh_to_sdf_and_bounds():
    # Create a simple unit sphere mesh centered at origin
    sphere_mesh = trimesh.creation.icosphere(subdivisions=3, radius=1.0)
    
    # Write the sphere mesh to a temporary STL file
    with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as tmp:
        sphere_mesh.export(tmp.name)
        tmp_path = tmp.name

    try:
        # Test mesh_bounds returns approximately (-1,-1,-1) to (1,1,1)
        min_corner, max_corner = mesh_bounds(tmp_path)
        # Allow some tolerance for icosphere approximation
        assert isinstance(min_corner, tuple) and isinstance(max_corner, tuple)
        for mn, mx in zip(min_corner, max_corner):
            assert mn <= -0.9 and mx >= 0.9, f"Bounds are incorrect: {min_corner}, {max_corner}"
        
        # Test mesh_to_sdf: points at known distances
        sdf = mesh_to_sdf(tmp_path)
        # At origin (inside sphere), distance should be roughly -1.0
        d_center = sdf(0.0, 0.0, 0.0)
        assert d_center < 0 and abs(d_center + 1.0) < 0.2, f"Center distance off: {d_center}"
        # At (1, 0, 0) on surface, distance ~0
        d_surface = sdf(1.0, 0.0, 0.0)
        assert abs(d_surface) < 0.1, f"Surface distance off: {d_surface}"
        # At (2, 0, 0) outside, distance ~1.0
        d_outside = sdf(2.0, 0.0, 0.0)
        assert d_outside > 0 and abs(d_outside - 1.0) < 0.2, f"Outside distance off: {d_outside}"
    finally:
        # Clean up temporary file
        os.remove(tmp_path)

if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__]))