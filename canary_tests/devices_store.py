import logging
import pickle
from pathlib import Path

logger = logging.getLogger(__name__)


def load_device_ids(path: Path) -> list[int]:
    """Load device ids from a pickle file. Only pass a file you trust."""
    logger.warning("loading %s; only load pickle files you trust", path)
    with path.open("rb") as handle:
        loaded = pickle.load(handle)
    if not isinstance(loaded, list) or any(not _is_device_id(item) for item in loaded):
        raise ValueError(f"{path} must contain a list of device ids")
    return loaded


def save_device_ids(path: Path, device_ids: list[int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        pickle.dump(device_ids, handle, protocol=pickle.HIGHEST_PROTOCOL)
    logger.info("saved %s device ids to %s", len(device_ids), path)


def _is_device_id(item: object) -> bool:
    return isinstance(item, int) and not isinstance(item, bool)
