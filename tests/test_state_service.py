from datetime import datetime

from config.settings import SyncMode
from models.task_models import RunSummary, TaskName, TaskResult
from services.state_service import StateService


def test_save_and_load_last_run(tmp_path):
    state = StateService(str(tmp_path))
    summary = RunSummary(
        trigger="manual",
        success=False,
        finished_at=datetime.now(),
        task_count=1,
        rows_read=10,
        rows_changed=3,
        rows_error=1,
        tasks=[
            TaskResult(
                task_name=TaskName.GROSS_PROFIT,
                success=False,
                mode=SyncMode.FULL,
                rows_read=10,
                rows_changed=3,
                rows_error=1,
                error_message="rate limit",
            )
        ],
        message="gross_profit: rate limit",
    )

    state.save_last_run(summary)
    loaded = state.load_last_run()

    assert loaded is not None
    assert loaded.trigger == "manual"
    assert loaded.success is False
    assert loaded.rows_changed == 3
    assert loaded.message == "gross_profit: rate limit"
