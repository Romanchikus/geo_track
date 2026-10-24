import pickle
from pathlib import Path

import pytest

from canary_tests.devices_store import load_device_ids, save_device_ids


def test_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "devices.pkl"
    save_device_ids(path, [3, 9])
    assert load_device_ids(path) == [3, 9]


def test_rejects_untrusted_shape(tmp_path: Path) -> None:
    path = tmp_path / "devices.pkl"
    with path.open("wb") as handle:
        pickle.dump({"id": 1}, handle)

    with pytest.raises(ValueError):
        load_device_ids(path)


def test_rejects_bool_ids(tmp_path: Path) -> None:
    path = tmp_path / "devices.pkl"
    with path.open("wb") as handle:
        pickle.dump([True], handle)

    with pytest.raises(ValueError):
        load_device_ids(path)
