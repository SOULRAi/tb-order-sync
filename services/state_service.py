"""Local JSON-based state persistence for incremental sync."""

from __future__ import annotations

import json
from pathlib import Path

from models.state_models import SyncState
from utils.logger import get_logger

logger = get_logger(__name__)

STATE_FILENAME = "sync_state.json"


class StateService:
    """Read / write incremental sync state from a local JSON file."""

    def __init__(self, state_dir: str) -> None:
        self._dir = Path(state_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / STATE_FILENAME

    def load(self, *, quiet: bool = False) -> SyncState:
        """Load state from disk. Returns fresh state if file missing / corrupt."""
        if not self._path.exists():
            if not quiet:
                logger.info("No existing state file, starting fresh: %s", self._path)
            return SyncState()
        try:
            raw = self._path.read_text(encoding="utf-8")
            data = json.loads(raw)
            state = SyncState.model_validate(data)
            if not quiet:
                logger.info("Loaded sync state from %s", self._path)
            return state
        except Exception as exc:
            if not quiet:
                logger.warning("Failed to load state (%s), starting fresh: %s", exc, self._path)
            return SyncState()

    def save(self, state: SyncState) -> None:
        """Persist state to disk."""
        try:
            raw = state.model_dump_json(indent=2)
            self._path.write_text(raw, encoding="utf-8")
            logger.info("Saved sync state to %s", self._path)
        except Exception as exc:
            logger.error("Failed to save state: %s", exc)
            raise
