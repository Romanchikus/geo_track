import pickle
import random
from pathlib import Path

import pytest

from canary_tests.positions import Track, load_positions, positions_for, random_track, save_positions, step_fix


def test_new_devices_keep_their_own_direction(tmp_path: Path) -> None:
    path = tmp_path / "positions.pkl"
    positions = positions_for([1, 2, 3, 4], path, random.Random(1))

    assert set(positions) == {1, 2, 3, 4}
    assert load_positions(path) == positions
    directions = [track.direction for track in positions.values()]
    assert len(set(directions)) == 4
    assert all(0 <= direction < 360 for direction in directions)
    longitudes = [track.longitude for track in positions.values()]
    assert max(longitudes) - min(longitudes) > 20


def test_next_run_keeps_the_stored_direction(tmp_path: Path) -> None:
    path = tmp_path / "positions.pkl"
    initial = positions_for([7], path, random.Random(2))
    stepped = step_fix(initial[7])
    save_positions(path, {7: stepped})

    again = positions_for([7], path, random.Random(99))

    assert again[7] == stepped
    assert again[7].direction == initial[7].direction


def test_step_follows_the_same_direction() -> None:
    track = Track(10.0, 20.0, 90.0)

    first = step_fix(track)
    second = step_fix(first)

    assert first.direction == 90.0
    assert second.direction == 90.0
    assert first.longitude > track.longitude
    assert second.longitude > first.longitude
    assert first.latitude == pytest.approx(second.latitude)


def test_step_crosses_a_pole_and_keeps_going() -> None:
    north = Track(89.95, 10.0, 0.0)
    for _ in range(20):
        north = step_fix(north)

    assert north.latitude < 88.0
    assert north.direction == pytest.approx(180.0)
    assert north.longitude == pytest.approx(-170.0, abs=1.0)

    south = Track(-89.95, 10.0, 180.0)
    for _ in range(20):
        south = step_fix(south)

    assert south.latitude > -88.0
    assert south.direction == pytest.approx(0.0)
    assert south.longitude == pytest.approx(-170.0, abs=1.0)


def test_step_leaves_the_pole_on_the_far_side() -> None:
    track = step_fix(Track(90.0, 10.0, 0.0))

    assert track.latitude < 90.0
    assert track.direction == pytest.approx(180.0)
    assert track.longitude == pytest.approx(-170.0, abs=1.0)


def test_step_stays_on_the_planet() -> None:
    track = step_fix(Track(90.0, 180.0, 180.0))

    assert -90 <= track.latitude <= 90
    assert -180 <= track.longitude <= 180
    assert track.direction == 180.0


def test_random_track_covers_the_planet() -> None:
    rng = random.Random(4)
    points = [random_track(rng) for _ in range(40)]

    assert min(track.latitude for track in points) < -20
    assert max(track.latitude for track in points) > 20
    assert min(track.longitude for track in points) < -60
    assert max(track.longitude for track in points) > 60


def test_legacy_pair_gets_one_direction(tmp_path: Path) -> None:
    path = tmp_path / "positions.pkl"
    with path.open("wb") as handle:
        pickle.dump({7: (12.0, 34.0)}, handle)

    positions = positions_for([7], path, random.Random(5))

    assert positions[7].latitude == pytest.approx(12.0)
    assert positions[7].longitude == pytest.approx(34.0)
    assert load_positions(path)[7].direction == positions[7].direction


def test_load_rejects_a_bad_pickle(tmp_path: Path) -> None:
    path = tmp_path / "positions.pkl"
    with path.open("wb") as handle:
        pickle.dump([1, 2], handle)

    with pytest.raises(ValueError):
        load_positions(path)


def test_load_rejects_a_track_without_direction(tmp_path: Path) -> None:
    path = tmp_path / "positions.pkl"
    with path.open("wb") as handle:
        pickle.dump({7: (12.0, 34.0)}, handle)

    with pytest.raises(ValueError):
        load_positions(path)
