"""APScheduler-based task scheduler."""

from __future__ import annotations

import random
import time
from typing import Optional

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from config.settings import Settings, SyncMode, get_settings
from connectors.base import BaseSheetConnector
from services.gross_profit_service import GrossProfitService
from services.refund_match_service import RefundMatchService
from services.state_service import StateService
from utils.logger import get_logger

logger = get_logger(__name__)


class SchedulerService:
    """Manages periodic execution of sync tasks."""

    def __init__(
        self,
        connector: BaseSheetConnector,
        state_service: StateService,
        settings: Optional[Settings] = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._connector = connector
        self._state_svc = state_service
        self._scheduler = BlockingScheduler()

        self._gp_svc = GrossProfitService(connector, state_service, self._settings)
        self._rm_svc = RefundMatchService(connector, state_service, self._settings)

    def _run_all(self) -> None:
        """Execute all tasks in sequence."""
        logger.info("--- Scheduled run: all tasks ---")
        self._gp_svc.run()
        self._rm_svc.run()

    def start(self) -> None:
        """Start the blocking scheduler with configured interval and jitter."""
        jitter = self._settings.startup_jitter_seconds
        if jitter > 0:
            delay = random.uniform(0, jitter)
            logger.info("Startup jitter: sleeping %.1f seconds", delay)
            time.sleep(delay)

        interval_minutes = self._settings.task_interval_minutes
        self._scheduler.add_job(
            self._run_all,
            trigger=IntervalTrigger(minutes=interval_minutes),
            id="sync_all",
            name="Sync All Tasks",
            max_instances=1,
            coalesce=True,
        )
        logger.info("Scheduler started: interval=%d minutes", interval_minutes)

        # Run once immediately
        self._run_all()

        try:
            self._scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Scheduler stopped by user")
            self._scheduler.shutdown(wait=False)

    def stop(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("Scheduler stopped")
