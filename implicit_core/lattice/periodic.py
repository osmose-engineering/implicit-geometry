

import math
from typing import Callable

# Type alias: an SDF is any function taking (x, y, z) -> float
SDF = Callable[[float, float, float], float]

def gyroid(cell_size: float, thickness: float) -> SDF:
    """
    Triply periodic minimal surface (gyroid).
    Equation: sin(2πx/λ)cos(2πy/λ) + sin(2πy/λ)cos(2πz/λ) + sin(2πz/λ)cos(2πx/λ) = t
    λ = cell_size, thickness shifts the level-set.
    """
    inv_lambda = 2.0 * math.pi / cell_size

    def _sdf(x: float, y: float, z: float) -> float:
        gx = math.sin(inv_lambda * x) * math.cos(inv_lambda * y)
        gy = math.sin(inv_lambda * y) * math.cos(inv_lambda * z)
        gz = math.sin(inv_lambda * z) * math.cos(inv_lambda * x)
        value = gx + gy + gz
        return value - thickness

    return _sdf

def schwarz_p(cell_size: float, thickness: float) -> SDF:
    """
    Schwarz P (Primitive) triply periodic surface.
    Equation: cos(2πx/λ) + cos(2πy/λ) + cos(2πz/λ) = t
    λ = cell_size, thickness shifts the level-set.
    """
    inv_lambda = 2.0 * math.pi / cell_size

    def _sdf(x: float, y: float, z: float) -> float:
        value = math.cos(inv_lambda * x) + math.cos(inv_lambda * y) + math.cos(inv_lambda * z)
        return value - thickness

    return _sdf

def diamond(cell_size: float, thickness: float) -> SDF:
    """
    Diamond (D) triply periodic minimal surface.
    Equation: sin(2πx/λ)sin(2πy/λ)sin(2πz/λ) + sin(2πx/λ)cos(2πy/λ)cos(2πz/λ)
               + cos(2πx/λ)sin(2πy/λ)cos(2πz/λ) + cos(2πx/λ)cos(2πy/λ)sin(2πz/λ) = t
    λ = cell_size, thickness shifts the level-set.
    """
    inv_lambda = 2.0 * math.pi / cell_size

    def _sdf(x: float, y: float, z: float) -> float:
        sx = math.sin(inv_lambda * x)
        sy = math.sin(inv_lambda * y)
        sz = math.sin(inv_lambda * z)
        cx = math.cos(inv_lambda * x)
        cy = math.cos(inv_lambda * y)
        cz = math.cos(inv_lambda * z)

        value = (
            sx * sy * sz +
            sx * cy * cz +
            cx * sy * cz +
            cx * cy * sz
        )
        return value - thickness

    return _sdf