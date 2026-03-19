"""Application settings via pydantic-settings + .env file."""

from __future__ import annotations

import os
import sys
from enum import Enum
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

def _get_project_root() -> Path:
    """Resolve project root, compatible with PyInstaller frozen exe."""
    if getattr(sys, "frozen", False):
        # Running as packaged exe — use exe's directory as root
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


PROJECT_ROOT = _get_project_root()


class AppEnv(str, Enum):
    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"


class SyncMode(str, Enum):
    INCREMENTAL = "incremental"
    FULL = "full"


class Settings(BaseSettings):
    """All configuration knobs, sourced from .env / environment variables."""

    model_config = SettingsConfigDict(
        env_file=os.environ.get("DOTENV_PATH", str(PROJECT_ROOT / ".env")),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── 基础 ──────────────────────────────────────────────
    app_env: AppEnv = AppEnv.DEV
    log_level: str = "INFO"
    state_dir: str = str(PROJECT_ROOT / "state")

    # ── 腾讯文档 ──────────────────────────────────────────
    tencent_client_id: str = ""
    tencent_client_secret: str = ""
    tencent_open_id: str = ""
    tencent_access_token: str = ""
    tencent_a_file_id: str = ""
    tencent_a_sheet_id: str = ""
    tencent_b_file_id: str = ""
    tencent_b_sheet_id: str = ""

    # ── 飞书（预留） ─────────────────────────────────────
    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    feishu_c_file_token: str = ""
    feishu_c_sheet_id: str = ""

    # ── 运行 ──────────────────────────────────────────────
    gross_profit_mode: SyncMode = SyncMode.INCREMENTAL
    refund_match_mode: SyncMode = SyncMode.INCREMENTAL
    c_sync_mode: SyncMode = SyncMode.INCREMENTAL
    task_interval_minutes: int = 10
    startup_jitter_seconds: int = 15
    write_batch_size: int = 100
    retry_times: int = 3
    dry_run: bool = False
    enable_style_update: bool = True

    # ── 列映射（可覆盖） ─────────────────────────────────
    a_col_product_price: str = "C"
    a_col_packaging_price: str = "D"
    a_col_freight: str = "E"
    a_col_customer_quote: str = "F"
    a_col_gross_profit: str = "G"
    a_col_order_no: str = "H"
    a_col_refund_status: str = "I"
    b_col_order_no: str = "A"

    # ── 业务文案 ──────────────────────────────────────────
    refund_status_text: str = "已退款"
    data_error_text: str = "数据异常"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
