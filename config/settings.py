"""Application settings via pydantic-settings + .env file."""

from __future__ import annotations

import json
import os
import sys
from enum import Enum
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

def _get_package_root() -> Path:
    """Resolve package root, compatible with PyInstaller frozen exe."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def _read_app_version(package_root: Path) -> str:
    """Read the app version from package.json when available."""
    explicit = os.environ.get("TB_APP_VERSION", "").strip()
    if explicit:
        return explicit

    package_json = package_root / "package.json"
    if package_json.exists():
        try:
            payload = json.loads(package_json.read_text(encoding="utf-8"))
            version = str(payload.get("version", "")).strip()
            if version:
                return version
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass

    return "0.0.0"


def _looks_like_global_node_package(root: Path) -> bool:
    """Best-effort detection for an npm global package install."""
    parts = {part.lower() for part in root.parts}
    return root.name == "tb-order-sync" and "node_modules" in parts


def _default_app_home() -> Path:
    """Resolve the writable runtime home for config/state/venv."""
    package_root = _get_package_root()
    explicit = os.environ.get("TB_HOME", "").strip()
    if explicit:
        return Path(explicit).expanduser().resolve()

    if getattr(sys, "frozen", False):
        return package_root

    if _looks_like_global_node_package(package_root):
        home = Path.home()
        if os.name == "nt":
            appdata = os.environ.get("APPDATA")
            if appdata:
                return Path(appdata).expanduser().resolve() / "tb-order-sync"
            return (home / "AppData" / "Roaming" / "tb-order-sync").resolve()
        if sys.platform == "darwin":
            return (home / "Library" / "Application Support" / "tb-order-sync").resolve()
        return (home / ".tb-order-sync").resolve()

    return package_root


PACKAGE_ROOT = _get_package_root()
APP_HOME = _default_app_home()
PROJECT_ROOT = PACKAGE_ROOT
APP_VERSION = _read_app_version(PACKAGE_ROOT)


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
        env_file=os.environ.get("DOTENV_PATH", str(APP_HOME / ".env")),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── 基础 ──────────────────────────────────────────────
    app_env: AppEnv = AppEnv.DEV
    log_level: str = "INFO"
    state_dir: str = str(APP_HOME / "state")

    # ── 腾讯文档 ──────────────────────────────────────────
    tencent_client_id: str = ""
    tencent_client_secret: str = ""
    tencent_open_id: str = ""
    tencent_access_token: str = ""
    tencent_a_file_id: str = ""
    tencent_a_sheet_id: str = ""
    tencent_a_sheet_name_keyword: str = ""
    tencent_b_file_id: str = ""
    tencent_b_sheet_id: str = ""
    tencent_b_sheet_name_keyword: str = ""

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

    @field_validator("state_dir", mode="before")
    @classmethod
    def _resolve_state_dir(cls, value: object) -> str:
        """Resolve relative state_dir values against APP_HOME."""
        if value in (None, ""):
            return str(APP_HOME / "state")

        path = Path(str(value)).expanduser()
        if not path.is_absolute():
            path = APP_HOME / path
        return str(path.resolve())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
