"""Reusable interpolation helpers for future calculators.

These helpers are not wired into legacy solver.py interpolation in Phase 11.
"""


def interpolate_1d(points, x, method="linear"):
    """Interpolate y at x from [(x, y), ...]."""
    if not points:
        return None
    clean = sorted((float(px), float(py)) for px, py in points)
    x = float(x)
    if method == "nearest":
        return nearest_neighbor(clean, x)
    if x <= clean[0][0]:
        return clean[0][1]
    if x >= clean[-1][0]:
        return clean[-1][1]
    for (x0, y0), (x1, y1) in zip(clean, clean[1:]):
        if x0 <= x <= x1:
            if x1 == x0:
                return y0
            ratio = (x - x0) / (x1 - x0)
            return y0 + ratio * (y1 - y0)
    return clean[-1][1]


def interpolate_2d(points, x, y, method="nearest"):
    """Return a simple 2D interpolated value from [(x, y, z), ...].

    Phase 11 uses nearest-neighbor behavior as a safe placeholder interface.
    """
    if not points:
        return None
    if method != "nearest":
        method = "nearest"
    x = float(x)
    y = float(y)
    nearest = min(
        ((float(px), float(py), float(pz)) for px, py, pz in points),
        key=lambda item: (item[0] - x) ** 2 + (item[1] - y) ** 2,
    )
    return nearest[2]


def nearest_neighbor(points, x):
    """Return nearest y value from [(x, y), ...]."""
    if not points:
        return None
    x = float(x)
    px, py = min(points, key=lambda item: abs(float(item[0]) - x))
    return float(py)
