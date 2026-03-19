"""C table → A table sync service (skeleton / placeholder).

This service will sync raw data from Feishu C table into Tencent Docs A table.
Currently a structural placeholder — implementation pending Feishu connector completion.
"""

from __future__ import annotations

from typing import Optional

from config.settings import Settings, SyncMode, get_settings
from connectors.base import BaseSheetConnector
from models.task_models import TaskName, TaskResult
from services.state_service import StateService
from utils.logger import get_logger

logger = get_logger(__name__)


class CToASyncService:
    """Sync records from C table (Feishu) to A table (Tencent Docs).

    TODO: Implement when Feishu connector is ready.
    """

    def __init__(
        self,
        source_connector: BaseSheetConnector,
        target_connector: BaseSheetConnector,
        state_service: StateService,
        settings: Optional[Settings] = None,
    ) -> None:
        self._source = source_connector
        self._target = target_connector
        self._state_svc = state_service
        self._settings = settings or get_settings()

    def run(
        self,
        mode: Optional[SyncMode] = None,
        dry_run: Optional[bool] = None,
    ) -> TaskResult:
        mode = mode or self._settings.c_sync_mode
        dry_run = dry_run if dry_run is not None else self._settings.dry_run
        result = TaskResult(task_name=TaskName.C_TO_A_SYNC, mode=mode, dry_run=dry_run)

        logger.warning("C → A sync service is not yet implemented (Feishu connector pending)")
        result.finish(success=False, error_message="Not implemented")
        return result
