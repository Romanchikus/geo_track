import logging
import math
import pickle
import random
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

LATITUDE_LIMIT = 90.0
LONGITUDE_LIMIT = 180.0
_EARTH_RADIUS_KM = 6371.0
DEFAULT_SPEED_KMH = 50000.0
_STEP_SECONDS = 1.0


@dataclass(slots=True)
class Track:
    latitude: float
    longitude: float
    direction: float


def load_positions(path: Path) -> dict[int, Track]:
    """Load device tracks from a pickle file. Only pass a file you trust."""
    logger.warning("loading %s; only load pickle files you trust", path)
    positions: dict[int, Track] = {}
    for device_id, value in _unpickle(path).items():
        track = _track(value)
        if track is None:
            raise ValueError(f"{path} must store latitude, longitude, and direction for device {device_id}")
        positions[device_id] = track
    return positions


def save_positions(path: Path, positions: dict[int, Track]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    payload = {device_id: (track.latitude, track.longitude, track.direction) for device_id, track in positions.items()}
    with temporary.open("wb") as handle:
        pickle.dump(payload, handle, protocol=pickle.HIGHEST_PROTOCOL)
    temporary.replace(path)
    logger.info("saved %s device positions to %s", len(positions), path)


def positions_for(device_ids: list[int], path: Path, rng: random.Random) -> dict[int, Track]:
    """Reuse stored tracks and place any new device at random on the planet."""
    stored = _stored_tracks(path, rng) if path.is_file() else {}
    positions: dict[int, Track] = {}
    seeded = 0
    for device_id in device_ids:
        found = stored.get(device_id)
        if found is None:
            positions[device_id] = random_track(rng)
            seeded += 1
        else:
            positions[device_id] = found
    save_positions(path, positions)
    logger.info("device positions ready: %s stored, %s placed at random", len(positions) - seeded, seeded)
    return positions


def random_track(rng: random.Random) -> Track:
    """Pick a point spread by area across the whole planet and a fixed direction."""
    latitude = math.degrees(math.asin(rng.uniform(-1.0, 1.0)))
    longitude = rng.uniform(-LONGITUDE_LIMIT, LONGITUDE_LIMIT)
    return Track(latitude, longitude, _heading(rng))


def step_fix(track: Track, speed_kmh: float = DEFAULT_SPEED_KMH) -> Track:
    """Move one step. Past a pole, reverse course so latitude keeps changing."""
    distance_km = speed_kmh * _STEP_SECONDS / 3600.0
    angular_distance = distance_km / _EARTH_RADIUS_KM
    heading_rad = math.radians(track.direction)
    lat_rad = math.radians(track.latitude)
    lon_rad = math.radians(track.longitude)

    new_lat = math.asin(
        _unit(
            math.sin(lat_rad) * math.cos(angular_distance)
            + math.cos(lat_rad) * math.sin(angular_distance) * math.cos(heading_rad)
        )
    )
    new_lon = lon_rad + math.atan2(
        math.sin(heading_rad) * math.sin(angular_distance) * math.cos(lat_rad),
        math.cos(angular_distance) - math.sin(lat_rad) * math.sin(new_lat),
    )
    latitude = _clamp(math.degrees(new_lat), -LATITUDE_LIMIT, LATITUDE_LIMIT)
    longitude = _wrap(math.degrees(new_lon))
    direction = track.direction
    if _passed_pole(track.latitude, angular_distance, direction):
        direction = (direction + 180.0) % 360.0
        if abs(track.latitude) >= LATITUDE_LIMIT:
            longitude = _wrap(longitude + LONGITUDE_LIMIT)
    return Track(latitude, longitude, direction)


def _stored_tracks(path: Path, rng: random.Random) -> dict[int, Track]:
    positions: dict[int, Track] = {}
    migrated = 0
    for device_id, value in _unpickle(path).items():
        track = _track(value)
        if track is None:
            point = _point(value)
            if point is None:
                raise ValueError(f"{path} has coordinates outside the planet for device {device_id}")
            track = Track(point[0], point[1], _heading(rng))
            migrated += 1
        positions[device_id] = track
    if migrated:
        logger.info("assigned a direction to %s stored devices", migrated)
    return positions


def _unpickle(path: Path) -> dict[int, object]:
    with path.open("rb") as handle:
        loaded = pickle.load(handle)
    if not isinstance(loaded, dict):
        raise ValueError(f"{path} must contain a dict of device tracks")
    positions: dict[int, object] = {}
    for device_id, value in loaded.items():
        if isinstance(device_id, bool) or not isinstance(device_id, int):
            raise ValueError(f"{path} has a key that is not a device id")
        positions[device_id] = value
    return positions


def _passed_pole(latitude: float, angular_distance: float, direction: float) -> bool:
    toward_north = angular_distance * math.cos(math.radians(direction))
    if toward_north > 0:
        return toward_north >= math.radians(LATITUDE_LIMIT - latitude)
    return -toward_north >= math.radians(latitude + LATITUDE_LIMIT)


def _unit(value: float) -> float:
    return min(1.0, max(-1.0, value))


def _heading(rng: random.Random) -> float:
    return rng.uniform(0.0, 360.0)


def _clamp(value: float, low: float, high: float) -> float:
    return min(max(value, low), high)


def _wrap(longitude: float) -> float:
    wrapped = (longitude + LONGITUDE_LIMIT) % 360.0 - LONGITUDE_LIMIT
    if wrapped == -LONGITUDE_LIMIT:
        return LONGITUDE_LIMIT
    return wrapped


def _track(value: object) -> Track | None:
    numbers = _numbers(value, 3)
    if numbers is None:
        return None
    latitude, longitude, direction = numbers
    if abs(latitude) > LATITUDE_LIMIT or abs(longitude) > LONGITUDE_LIMIT:
        return None
    return Track(latitude, longitude, direction % 360.0)


def _point(value: object) -> tuple[float, float] | None:
    numbers = _numbers(value, 2)
    if numbers is None:
        return None
    latitude, longitude = numbers
    if abs(latitude) > LATITUDE_LIMIT or abs(longitude) > LONGITUDE_LIMIT:
        return None
    return latitude, longitude


def _numbers(value: object, count: int) -> tuple[float, ...] | None:
    if not isinstance(value, (tuple, list)) or len(value) != count:
        return None
    numbers: list[float] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            return None
        number = float(item)
        if not math.isfinite(number):
            return None
        numbers.append(number)
    return tuple(numbers)
