import pytest
from fastapi import HTTPException
from shapely.geometry import Polygon as ShapePolygon

from app.services.subscriptions.geometry import normalize_ring, to_wkt
from app.services.subscriptions.selection import select_count

TRIANGLE = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0]]


def test_normalize_ring_drops_closing_point() -> None:
    ring = normalize_ring([*TRIANGLE, [0.0, 0.0]])
    assert ring == TRIANGLE
    assert to_wkt(ring) == "POLYGON((0.0 0.0, 1.0 0.0, 1.0 1.0, 0.0 0.0))"


def test_normalize_ring_rejects_a_line() -> None:
    with pytest.raises(HTTPException) as caught:
        normalize_ring([[0.0, 0.0], [1.0, 0.0]])
    assert caught.value.status_code == 422


def test_normalize_ring_unions_a_stroke_that_crosses_itself() -> None:
    crossing = [[0.0, 0.0], [4.0, 0.0], [4.0, 3.0], [1.0, 3.0], [1.0, 1.0], [3.0, 1.0], [3.0, 2.0], [0.0, 2.0]]
    repaired = normalize_ring(crossing)
    shape = ShapePolygon([*repaired, repaired[0]])
    assert shape.is_valid
    assert shape.area == 11


def test_normalize_ring_rejects_out_of_range() -> None:
    with pytest.raises(HTTPException) as caught:
        normalize_ring([[0.0, 0.0], [1.0, 0.0], [200.0, 1.0]])
    assert caught.value.status_code == 422


def test_select_count_keeps_at_least_one() -> None:
    assert select_count(4, 50) == 2
    assert select_count(10, 1) == 1
    assert select_count(3, 100) == 3
    assert select_count(0, 50) == 0
