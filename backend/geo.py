from typing import List, Tuple


def point_in_polygon(point: Tuple[float, float], polygon: List[Tuple[float, float]]) -> bool:
    """
    Ray casting algorithm.
    point and polygon are in normalized coordinates (0..1).
    """
    x, y = point
    inside = False
    n = len(polygon)
    if n < 3:
        return False

    x0, y0 = polygon[-1]
    for x1, y1 in polygon:
        intersects = ((y1 > y) != (y0 > y)) and (x < (x0 - x1) * (y - y1) / (y0 - y1 + 1e-12) + x1)
        if intersects:
            inside = not inside
        x0, y0 = x1, y1
    return inside


def bbox_center_norm(x: int, y: int, w: int, h: int, frame_w: int, frame_h: int) -> Tuple[float, float]:
    cx = x + w / 2.0
    cy = y + h / 2.0
    return (cx / max(1.0, float(frame_w)), cy / max(1.0, float(frame_h)))

