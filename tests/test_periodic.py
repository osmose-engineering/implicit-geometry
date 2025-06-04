import sys
import os
import math

# Ensure project root is on sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from implicit_core.lattice.periodic import gyroid, schwarz_p, diamond

def test_gyroid_basic():
    # Use cell_size = 10, thickness = 0
    lam = 10.0
    sdf = gyroid(cell_size=lam, thickness=0.0)

    # At (0,0,0): sin(0)*cos(0) + sin(0)*cos(0) + sin(0)*cos(0) = 0
    assert abs(sdf(0.0, 0.0, 0.0)) < 1e-6

    # At (lam/4, lam/4, lam/4): sin(pi/2)*cos(pi/2) * 3 = 0
    p = lam / 4.0
    assert abs(sdf(p, p, p)) < 1e-6

    # At (lam/8, lam/8, lam/8): sin(pi/4)*cos(pi/4) = (sqrt(2)/2)*(sqrt(2)/2) = 0.5
    # Sum = 0.5 * 3 = 1.5
    expected = 1.5
    d = sdf(lam/8.0, lam/8.0, lam/8.0)
    assert abs(d - expected) < 1e-6

def test_schwarz_p_basic():
    lam = 10.0
    sdf = schwarz_p(cell_size=lam, thickness=0.0)

    # At (0,0,0): cos(0)+cos(0)+cos(0) = 3
    assert abs(sdf(0.0, 0.0, 0.0) - 3.0) < 1e-6

    # At (lam/4, lam/4, lam/4): cos(pi/2)*3 = 0
    p = lam / 4.0
    assert abs(sdf(p, p, p)) < 1e-6

    # At (lam/2, 0, 0): cos(pi)*1 + cos(0)*2 = -1 + 2 = 1
    d = sdf(lam/2.0, 0.0, 0.0)
    assert abs(d - 1.0) < 1e-6

def test_diamond_basic():
    lam = 10.0
    sdf = diamond(cell_size=lam, thickness=0.0)

    # At (0,0,0): value = 0 (as computed); so sdf = 0
    assert abs(sdf(0.0, 0.0, 0.0)) < 1e-6

    # At (lam/4, lam/4, lam/4): 
    # sin(pi/2)=1, cos(pi/2)=0
    # value = 1*1*1 + 1*0*0 + 0*1*0 + 0*0*1 = 1
    expected = 1.0
    p = lam / 4.0
    assert abs(sdf(p, p, p) - expected) < 1e-6

    # At (lam/2, lam/2, lam/2):
    # sin(pi)=0, cos(pi)=-1
    # value = 0*0*0 + 0*(-1)*(-1) + (-1)*0*(-1) + (-1)*(-1)*0 = 0
    assert abs(sdf(lam/2.0, lam/2.0, lam/2.0)) < 1e-6

if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__]))
