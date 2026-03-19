"""Interactive setup wizard for one-stop configuration.

Usage:
    tb setup          # Full guided setup
    tb setup --check  # Validate current config
"""

from __future__ import annotations

import getpass
import re
import shutil
import sys
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional, Sequence
from urllib.parse import parse_qs, urlparse

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich import box
except ImportError:
    sys.exit("缺少 rich 库，请先安装: pip install rich")

from dotenv import dotenv_values

from config.settings import APP_HOME, PACKAGE_ROOT
from utils.sheet_selector import resolve_latest_month_sheet

# ── UI 文案 ────────────────────────────────────────────────────────────────
BANNER_TITLE = "多表格同步服务 — 配置向导"
BANNER_SUBTITLE = "按照提示逐步完成配置，按 Ctrl+C 随时退出"

STEP_TENCENT = "第 1 步：腾讯文档凭证"
STEP_SHEETS = "第 2 步：表格 ID 配置"
STEP_FEISHU = "第 3 步：飞书配置（可选）"
STEP_RUNTIME = "第 4 步：运行参数"
STEP_COLUMNS = "第 5 步：列映射"
STEP_SUMMARY = "配置总览"
STEP_WRITE = "写入配置"
STEP_TEST = "连接测试"

ENV_PATH = APP_HOME / ".env"
ENV_EXAMPLE_PATH = PACKAGE_ROOT / ".env.example"

# Column letter validator
_COL_RE = re.compile(r"^[A-Z]{1,3}$")
_TENCENT_FILE_RE = re.compile(r"/(?:sheet|doc|slide|mind|form|pdf)/([^/?#]+)")

TENCENT_DOCS_GUIDE_URL = "https://docs.qq.com/open/document/app/"
TENCENT_DEVELOPER_CONSOLE_URL = "https://docs.qq.com/open/developers/"
FEISHU_DEVELOPER_CONSOLE_URL = "https://open.feishu.cn/app"
FEISHU_TOKEN_DOC_URL = (
    "https://open.feishu.cn/document/server-docs/"
    "authentication-management/access-token/tenant_access_token_internal"
)
FEISHU_TOKEN_TUTORIAL_URL = "https://www.feishu.cn/content/000214591773"
_SETUP_LOGO = (
    "[bold #8ecae6]████████╗██████╗     ██████╗ ██████╗ ██████╗ ███████╗██████╗[/bold #8ecae6]\n"
    "[bold #38bdf8]╚══██╔══╝██╔══██╗   ██╔═══██╗██╔══██╗██╔══██╗██╔════╝██╔══██╗[/bold #38bdf8]\n"
    "[bold #22d3ee]   ██║   ██████╔╝   ██║   ██║██████╔╝██║  ██║█████╗  ██████╔╝[/bold #22d3ee]\n"
    "[bold #2dd4bf]   ██║   ██╔══██╗   ██║   ██║██╔══██╗██║  ██║██╔══╝  ██╔══██╗[/bold #2dd4bf]\n"
    "[bold #86efac]   ██║   ██████╔╝   ╚██████╔╝██║  ██║██████╔╝███████╗██║  ██║[/bold #86efac]\n"
    "[bold #bbf7d0]   ╚═╝   ╚═════╝     ╚═════╝ ╚═╝  ╚═╝╚═════╝ ╚══════╝╚═╝  ╚═╝[/bold #bbf7d0]"
)


# ── Validators ─────────────────────────────────────────────────────────────
def _not_empty(value: str) -> bool:
    return len(value.strip()) > 0


def _is_positive_int(value: str) -> bool:
    try:
        return int(value) > 0
    except ValueError:
        return False


def _is_non_negative_int(value: str) -> bool:
    try:
        return int(value) >= 0
    except ValueError:
        return False


def _is_col_letter(value: str) -> bool:
    return bool(_COL_RE.match(value.upper().strip()))


def _is_bool_str(value: str) -> bool:
    return value.strip().lower() in ("true", "false")


def _is_sync_mode(value: str) -> bool:
    return value.strip().lower() in ("incremental", "full")


def _mask_secret(value: str) -> str:
    """Mask a secret for display: show first 4 chars + ****."""
    if not value:
        return "(未设置)"
    if len(value) <= 6:
        return "****"
    return value[:4] + "****"


def parse_tencent_sheet_reference(raw: str) -> tuple[str, str]:
    """Parse a Tencent Docs sheet URL or raw file id.

    Returns `(file_id, sheet_id)` where `sheet_id` may be empty.
    """
    value = raw.strip()
    if not value:
        return "", ""

    if not value.startswith(("http://", "https://")):
        return value, ""

    parsed = urlparse(value)
    match = _TENCENT_FILE_RE.search(parsed.path)
    if not match:
        return "", ""

    file_id = match.group(1).strip()
    sheet_id = parse_qs(parsed.query).get("tab", [""])[0].strip()
    return file_id, sheet_id


# ── Setup Wizard ───────────────────────────────────────────────────────────
class SetupWizard:
    def __init__(self, console: Optional[Console] = None) -> None:
        self.console = console or Console()
        self.values: dict[str, str] = {}
        self._existing = self._load_existing()

    def _load_existing(self) -> dict[str, Optional[str]]:
        """Load existing .env values as defaults."""
        if ENV_PATH.exists():
            return dotenv_values(ENV_PATH)  # type: ignore
        return {}

    # ── Prompt helpers ─────────────────────────────────────────────────────

    def _prompt(
        self,
        label: str,
        key: str,
        default: str = "",
        secret: bool = False,
        validator: Optional[Callable[[str], bool]] = None,
        error_msg: str = "输入无效，请重新输入",
    ) -> str:
        """Prompt user for a value with optional validation and masking."""
        existing = self._existing.get(key, "")
        effective_default = existing or default

        while True:
            if secret:
                hint = f" [当前: {_mask_secret(effective_default)}]" if effective_default else ""
                self.console.print(f"  {label}{hint}")
                raw = getpass.getpass("  > ")
                if not raw and effective_default:
                    raw = effective_default
            else:
                hint = f" [默认: {effective_default}]" if effective_default else ""
                self.console.print(f"  {label}{hint}")
                raw = input("  > ").strip()
                if not raw and effective_default:
                    raw = effective_default

            if validator and not validator(raw):
                self.console.print(f"  [red]{error_msg}[/red]")
                continue

            return raw

    def _prompt_bool(self, label: str, default: bool = False) -> bool:
        hint = "Y/n" if default else "y/N"
        self.console.print(f"  {label} [{hint}]")
        raw = input("  > ").strip().lower()
        if not raw:
            return default
        return raw in ("y", "yes", "是")

    def _offer_open_links(self, title: str, links: Sequence[tuple[str, str]]) -> None:
        """Optionally open one or more documentation links in the default browser."""
        if not links:
            return

        self.console.print(f"  [dim]{title}：[/dim]")
        for idx, (label, url) in enumerate(links, start=1):
            self.console.print(f"    {idx}. {label}: [cyan]{url}[/cyan]")

        if not self._prompt_bool("是否现在用浏览器打开这些链接？", default=False):
            return

        opened = 0
        for _, url in links:
            try:
                if webbrowser.open_new_tab(url):
                    opened += 1
            except webbrowser.Error as exc:
                self.console.print(f"  [yellow]打开失败: {url} ({exc})[/yellow]")
            except Exception as exc:  # pragma: no cover - defensive guard
                self.console.print(f"  [yellow]打开失败: {url} ({exc})[/yellow]")

        if opened:
            self.console.print(f"  [green]已尝试打开 {opened} 个链接[/green]")
        else:
            self.console.print("  [yellow]未能自动打开浏览器，请手动复制上面的链接[/yellow]")

    def _show_tencent_guide(self) -> None:
        """Display beginner guidance for Tencent Docs Open API setup."""
        body = (
            "1. 打开腾讯文档开放平台开发文档，先确认你要接的是 Open API。\n"
            f"   文档入口: {TENCENT_DOCS_GUIDE_URL}\n"
            "2. 打开开发者平台，创建应用并进入应用详情页。\n"
            f"   开发者平台: {TENCENT_DEVELOPER_CONSOLE_URL}\n"
            "3. 在应用详情中获取 Client ID / Client Secret。\n"
            "4. 按官方 OAuth2 授权流程获取 Access Token。\n"
            "5. 本项目当前 MVP 需要你先手工提供有效 Access Token；"
            "自动刷新 token 还没接入。\n"
            "6. Open ID 目前是可选项，部分接口或企业场景可能会用到。"
        )
        self.console.print(Panel(
            body,
            title="[bold]腾讯文档 API 获取指引[/bold]",
            border_style="cyan",
            expand=False,
        ))
        self._offer_open_links("腾讯文档相关链接", [
            ("开发文档", TENCENT_DOCS_GUIDE_URL),
            ("开发者平台", TENCENT_DEVELOPER_CONSOLE_URL),
        ])

    def _show_sheet_id_guide(self) -> None:
        """Display how to locate file id and sheet id."""
        body = (
            "1. 先在浏览器打开目标腾讯文档 A 表 / B 表。\n"
            "2. File ID / Sheet ID 的展示形式可能因腾讯文档产品类型不同而不同。\n"
            "3. 第一版请以你在官方链接、页面参数或开发者文档中实际看到的 ID 为准。\n"
            "4. 如果你不确定，请先在腾讯文档开发文档里核对在线表格 API 的文件和 sheet 标识规则。\n"
            f"   文档入口: {TENCENT_DOCS_GUIDE_URL}\n"
            "5. 本项目代码里已把腾讯文档 endpoint 标为 TODO / NEED_VERIFY，"
            "如果你的表格类型不是标准在线表格，后续可能需要再补对接。"
        )
        self.console.print(Panel(
            body,
            title="[bold]A / B 表 ID 获取说明[/bold]",
            border_style="blue",
            expand=False,
        ))
        self._offer_open_links("表格 ID 参考链接", [
            ("腾讯文档开发文档", TENCENT_DOCS_GUIDE_URL),
        ])

    def _show_feishu_guide(self) -> None:
        """Display beginner guidance for Feishu Open Platform setup."""
        body = (
            "1. 打开飞书开放平台，创建自建应用。\n"
            f"   开发者平台: {FEISHU_DEVELOPER_CONSOLE_URL}\n"
            "2. 在应用凭证页获取 App ID 和 App Secret。\n"
            "3. 按官方服务端认证文档获取 tenant_access_token。\n"
            f"   官方文档: {FEISHU_TOKEN_DOC_URL}\n"
            "4. 如果你是第一次接飞书 API，可以先看一遍官方教程示例，"
            "它演示了 token 的获取和后续 API 调用链路。\n"
            f"   教程文章: {FEISHU_TOKEN_TUTORIAL_URL}\n"
            "5. C 表的 File Token / Sheet ID 请以你实际接入的飞书文档或表格链接规则为准。\n"
            "6. 当前项目里飞书 connector 还是 skeleton，先录入配置，后续第二阶段接通。"
        )
        self.console.print(Panel(
            body,
            title="[bold]飞书 API 获取指引[/bold]",
            border_style="green",
            expand=False,
        ))
        self._offer_open_links("飞书相关链接", [
            ("飞书开发者平台", FEISHU_DEVELOPER_CONSOLE_URL),
            ("tenant_access_token 官方文档", FEISHU_TOKEN_DOC_URL),
            ("动态 Token 教程", FEISHU_TOKEN_TUTORIAL_URL),
        ])

    # ── Steps ──────────────────────────────────────────────────────────────

    def _step_tencent_creds(self) -> None:
        self.console.print(f"\n[bold cyan]📋 {STEP_TENCENT}[/bold cyan]")
        self.console.print("  用于访问腾讯文档 Open API\n")
        self._show_tencent_guide()
        self.console.print("")

        self.values["TENCENT_CLIENT_ID"] = self._prompt(
            "Client ID", "TENCENT_CLIENT_ID", secret=True, validator=_not_empty,
            error_msg="Client ID 不能为空",
        )
        self.values["TENCENT_CLIENT_SECRET"] = self._prompt(
            "Client Secret（当前运行可留空）", "TENCENT_CLIENT_SECRET", secret=True,
        )
        self.values["TENCENT_OPEN_ID"] = self._prompt(
            "Open ID（可选，部分接口需要）", "TENCENT_OPEN_ID", secret=True,
        )
        self.values["TENCENT_ACCESS_TOKEN"] = self._prompt(
            "Access Token", "TENCENT_ACCESS_TOKEN", secret=True, validator=_not_empty,
            error_msg="Access Token 不能为空",
        )

    def _step_sheet_ids(self) -> None:
        self.console.print(f"\n[bold cyan]📊 {STEP_SHEETS}[/bold cyan]")
        self.console.print("  可直接粘贴腾讯文档完整链接，系统会自动拆出 File ID / Sheet ID\n")
        self._show_sheet_id_guide()
        self.console.print("")

        def prompt_sheet_target(name: str, file_key: str, sheet_key: str) -> None:
            while True:
                self.console.print(f"  [bold]{name}[/bold]")
                ref = self._prompt(
                    f"{name}链接或 File ID", file_key, validator=_not_empty,
                    error_msg="请输入腾讯文档链接或 File ID",
                )
                file_id, sheet_id = parse_tencent_sheet_reference(ref)
                if not file_id:
                    self.console.print("  [red]无法从链接中解析 File ID，请重新输入完整链接或直接填 File ID[/red]\n")
                    continue
                self.values[file_key] = file_id
                if sheet_id:
                    self.console.print(f"  [green]已自动解析 {name} Sheet ID: {sheet_id}[/green]")
                self.values[sheet_key] = self._prompt(
                    f"{name} Sheet ID", sheet_key, default=sheet_id, validator=_not_empty,
                    error_msg="Sheet ID 不能为空",
                )
                break

        prompt_sheet_target("A 表（订单表）", "TENCENT_A_FILE_ID", "TENCENT_A_SHEET_ID")
        self.values["TENCENT_A_SHEET_NAME_KEYWORD"] = self._prompt(
            "A 表按名称自动选最新月份（可选关键字，如 毛利率）",
            "TENCENT_A_SHEET_NAME_KEYWORD",
            default="",
        )
        self.console.print("")
        prompt_sheet_target("B 表（退款表）", "TENCENT_B_FILE_ID", "TENCENT_B_SHEET_ID")
        self.values["TENCENT_B_SHEET_NAME_KEYWORD"] = self._prompt(
            "B 表按名称自动选最新月份（可选关键字，如 客户退款）",
            "TENCENT_B_SHEET_NAME_KEYWORD",
            default="",
        )

    def _step_feishu_creds(self) -> None:
        self.console.print(f"\n[bold cyan]🐦 {STEP_FEISHU}[/bold cyan]")
        self._show_feishu_guide()
        self.console.print("")
        if not self._prompt_bool("是否现在配置飞书（C 表）？", default=False):
            self.values.setdefault("FEISHU_APP_ID", "")
            self.values.setdefault("FEISHU_APP_SECRET", "")
            self.values.setdefault("FEISHU_C_FILE_TOKEN", "")
            self.values.setdefault("FEISHU_C_SHEET_ID", "")
            self.console.print("  [dim]已跳过飞书配置，后续可重新运行 setup 补充[/dim]")
            return

        self.values["FEISHU_APP_ID"] = self._prompt(
            "飞书 App ID", "FEISHU_APP_ID", secret=True, validator=_not_empty,
        )
        self.values["FEISHU_APP_SECRET"] = self._prompt(
            "飞书 App Secret", "FEISHU_APP_SECRET", secret=True, validator=_not_empty,
        )
        self.values["FEISHU_C_FILE_TOKEN"] = self._prompt(
            "C 表 File Token", "FEISHU_C_FILE_TOKEN", validator=_not_empty,
        )
        self.values["FEISHU_C_SHEET_ID"] = self._prompt(
            "C 表 Sheet ID", "FEISHU_C_SHEET_ID", validator=_not_empty,
        )

    def _step_runtime(self) -> None:
        self.console.print(f"\n[bold cyan]⚙️  {STEP_RUNTIME}[/bold cyan]\n")

        self.values["APP_ENV"] = self._prompt(
            "运行环境 (dev / staging / prod)", "APP_ENV", default="dev",
        )
        self.values["LOG_LEVEL"] = self._prompt(
            "日志级别 (DEBUG / INFO / WARNING / ERROR)", "LOG_LEVEL", default="INFO",
        )
        self.values["STATE_DIR"] = self._prompt(
            "状态文件目录", "STATE_DIR", default="state",
        )
        self.values["GROSS_PROFIT_MODE"] = self._prompt(
            "毛利计算模式 (incremental / full)", "GROSS_PROFIT_MODE", default="incremental",
            validator=_is_sync_mode, error_msg="请输入 incremental 或 full",
        )
        self.values["REFUND_MATCH_MODE"] = self._prompt(
            "退款匹配模式 (incremental / full)", "REFUND_MATCH_MODE", default="incremental",
            validator=_is_sync_mode, error_msg="请输入 incremental 或 full",
        )
        self.values["C_SYNC_MODE"] = self._prompt(
            "C 表同步模式 (incremental / full)", "C_SYNC_MODE", default="incremental",
            validator=_is_sync_mode, error_msg="请输入 incremental 或 full",
        )
        self.values["TASK_INTERVAL_MINUTES"] = self._prompt(
            "定时任务间隔（分钟）", "TASK_INTERVAL_MINUTES", default="10",
            validator=_is_positive_int, error_msg="请输入正整数",
        )
        self.values["STARTUP_JITTER_SECONDS"] = self._prompt(
            "启动抖动时间（秒，防止并发冲突）", "STARTUP_JITTER_SECONDS", default="15",
            validator=_is_non_negative_int, error_msg="请输入非负整数",
        )
        self.values["WRITE_BATCH_SIZE"] = self._prompt(
            "批量写入大小", "WRITE_BATCH_SIZE", default="100",
            validator=_is_positive_int, error_msg="请输入正整数",
        )
        self.values["RETRY_TIMES"] = self._prompt(
            "失败重试次数", "RETRY_TIMES", default="3",
            validator=_is_positive_int, error_msg="请输入正整数",
        )
        self.values["DRY_RUN"] = self._prompt(
            "是否默认 dry-run 模式 (true / false)", "DRY_RUN", default="false",
            validator=_is_bool_str, error_msg="请输入 true 或 false",
        )
        self.values["ENABLE_STYLE_UPDATE"] = self._prompt(
            "是否启用行样式更新 (true / false)", "ENABLE_STYLE_UPDATE", default="true",
            validator=_is_bool_str, error_msg="请输入 true 或 false",
        )

    def _step_column_mapping(self) -> None:
        self.console.print(f"\n[bold cyan]📐 {STEP_COLUMNS}[/bold cyan]\n")

        defaults = {
            "A_COL_PRODUCT_PRICE": ("A表 - 产品价格", "C"),
            "A_COL_PACKAGING_PRICE": ("A表 - 包装价格", "D"),
            "A_COL_FREIGHT": ("A表 - 运费", "E"),
            "A_COL_CUSTOMER_QUOTE": ("A表 - 客户报价", "F"),
            "A_COL_GROSS_PROFIT": ("A表 - 毛利", "G"),
            "A_COL_ORDER_NO": ("A表 - 单号", "H"),
            "A_COL_REFUND_STATUS": ("A表 - 退款状态", "I"),
            "B_COL_ORDER_NO": ("B表 - 单号", "A"),
        }

        # Show current mapping table
        table = Table(title="当前列映射", box=box.SIMPLE_HEAVY)
        table.add_column("配置项", style="cyan")
        table.add_column("含义", style="white")
        table.add_column("列", style="green", justify="center")
        for key, (desc, default) in defaults.items():
            current = self._existing.get(key, default)
            table.add_row(key, desc, current or default)
        self.console.print(table)

        if not self._prompt_bool("是否需要修改列映射？", default=False):
            for key, (_, default) in defaults.items():
                self.values[key] = self._existing.get(key, default) or default
            self.console.print("  [dim]保持默认列映射[/dim]")
            return

        for key, (desc, default) in defaults.items():
            self.values[key] = self._prompt(
                desc, key, default=default,
                validator=_is_col_letter, error_msg="请输入大写列字母（如 A、B、AA）",
            ).upper()

        # Business text
        self.values["REFUND_STATUS_TEXT"] = self._prompt(
            "退款状态文案", "REFUND_STATUS_TEXT", default="已退款",
        )
        self.values["DATA_ERROR_TEXT"] = self._prompt(
            "数据异常文案", "DATA_ERROR_TEXT", default="数据异常",
        )

    # ── Summary ────────────────────────────────────────────────────────────

    def _show_summary(self) -> None:
        self.console.print(f"\n[bold cyan]📝 {STEP_SUMMARY}[/bold cyan]\n")

        secret_keys = {
            "TENCENT_CLIENT_ID", "TENCENT_CLIENT_SECRET", "TENCENT_OPEN_ID",
            "TENCENT_ACCESS_TOKEN", "FEISHU_APP_ID", "FEISHU_APP_SECRET",
        }

        sections = [
            ("腾讯文档凭证", [
                "TENCENT_CLIENT_ID", "TENCENT_CLIENT_SECRET",
                "TENCENT_OPEN_ID", "TENCENT_ACCESS_TOKEN",
            ]),
            ("表格 ID", [
                "TENCENT_A_FILE_ID", "TENCENT_A_SHEET_ID",
                "TENCENT_A_SHEET_NAME_KEYWORD",
                "TENCENT_B_FILE_ID", "TENCENT_B_SHEET_ID",
                "TENCENT_B_SHEET_NAME_KEYWORD",
            ]),
            ("飞书配置", [
                "FEISHU_APP_ID", "FEISHU_APP_SECRET",
                "FEISHU_C_FILE_TOKEN", "FEISHU_C_SHEET_ID",
            ]),
            ("运行参数", [
                "APP_ENV", "LOG_LEVEL", "STATE_DIR",
                "GROSS_PROFIT_MODE", "REFUND_MATCH_MODE", "C_SYNC_MODE",
                "TASK_INTERVAL_MINUTES", "STARTUP_JITTER_SECONDS",
                "WRITE_BATCH_SIZE", "RETRY_TIMES",
                "DRY_RUN", "ENABLE_STYLE_UPDATE",
            ]),
            ("列映射", [
                "A_COL_PRODUCT_PRICE", "A_COL_PACKAGING_PRICE",
                "A_COL_FREIGHT", "A_COL_CUSTOMER_QUOTE",
                "A_COL_GROSS_PROFIT", "A_COL_ORDER_NO",
                "A_COL_REFUND_STATUS", "B_COL_ORDER_NO",
            ]),
        ]

        for section_name, keys in sections:
            table = Table(title=section_name, box=box.ROUNDED, show_lines=False)
            table.add_column("配置项", style="cyan", min_width=28)
            table.add_column("值", style="white")
            for key in keys:
                val = self.values.get(key, "")
                display = _mask_secret(val) if key in secret_keys else (val or "[dim](空)[/dim]")
                table.add_row(key, display)
            self.console.print(table)

    # ── Write .env ─────────────────────────────────────────────────────────

    def _write_env(self) -> None:
        """Write .env using .env.example as template to preserve comments."""
        # Backup existing .env
        if ENV_PATH.exists():
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup = ENV_PATH.with_suffix(f".backup.{ts}")
            shutil.copy2(ENV_PATH, backup)
            self.console.print(f"  已备份旧配置到 [cyan]{backup.name}[/cyan]")

        # Read template
        if ENV_EXAMPLE_PATH.exists():
            template_lines = ENV_EXAMPLE_PATH.read_text(encoding="utf-8").splitlines()
        else:
            template_lines = []

        # Substitute values
        output_lines: list[str] = []
        used_keys: set[str] = set()

        for line in template_lines:
            stripped = line.strip()
            # Preserve comments and blank lines
            if not stripped or stripped.startswith("#"):
                output_lines.append(line)
                continue

            if "=" in stripped:
                key = stripped.split("=", 1)[0].strip()
                if key in self.values:
                    output_lines.append(f"{key}={self.values[key]}")
                    used_keys.add(key)
                else:
                    output_lines.append(line)
            else:
                output_lines.append(line)

        # Append any extra keys not in template
        extra_keys = set(self.values.keys()) - used_keys
        if extra_keys:
            output_lines.append("")
            output_lines.append("# ── 额外配置 ──")
            for key in sorted(extra_keys):
                output_lines.append(f"{key}={self.values[key]}")

        ENV_PATH.write_text("\n".join(output_lines) + "\n", encoding="utf-8")
        self.console.print(f"\n  [bold green]✅ 配置已写入 {ENV_PATH}[/bold green]")

    # ── Connection test ────────────────────────────────────────────────────

    def _test_connection(self) -> bool:
        """Try reading both A/B sheets to verify credentials and document access."""
        self.console.print(f"\n[bold cyan]🔌 {STEP_TEST}[/bold cyan]")
        self.console.print("  正在执行启动自检：状态目录 + 腾讯文档 A/B 表读取...\n")

        state_dir = Path(self.values.get("STATE_DIR", "state")).expanduser()
        if not state_dir.is_absolute():
            state_dir = APP_HOME / state_dir
        try:
            state_dir.mkdir(parents=True, exist_ok=True)
            probe = state_dir / ".write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            self.console.print(f"  [bold green]✅ 状态目录可写: {state_dir}[/bold green]")
        except Exception as exc:
            self.console.print(f"  [bold red]❌ 状态目录不可写: {state_dir} ({exc})[/bold red]")
            return False

        try:
            from connectors.tencent_docs import TencentDocsConnector

            conn = TencentDocsConnector(
                client_id=self.values.get("TENCENT_CLIENT_ID", ""),
                client_secret=self.values.get("TENCENT_CLIENT_SECRET", ""),
                access_token=self.values.get("TENCENT_ACCESS_TOKEN", ""),
                open_id=self.values.get("TENCENT_OPEN_ID", ""),
            )
            a_target = resolve_latest_month_sheet(
                conn,
                file_id=self.values.get("TENCENT_A_FILE_ID", ""),
                fallback_sheet_id=self.values.get("TENCENT_A_SHEET_ID", ""),
                title_keyword=self.values.get("TENCENT_A_SHEET_NAME_KEYWORD", ""),
            )
            b_target = resolve_latest_month_sheet(
                conn,
                file_id=self.values.get("TENCENT_B_FILE_ID", ""),
                fallback_sheet_id=self.values.get("TENCENT_B_SHEET_ID", ""),
                title_keyword=self.values.get("TENCENT_B_SHEET_NAME_KEYWORD", ""),
            )
            a_rows = conn.read_rows(
                self.values.get("TENCENT_A_FILE_ID", ""),
                a_target.sheet_id,
                start_row=0,
                end_row=2,
            )
            b_rows = conn.read_rows(
                self.values.get("TENCENT_B_FILE_ID", ""),
                b_target.sheet_id,
                start_row=0,
                end_row=2,
            )
            self.console.print(f"  [bold green]✅ A 表可读：{len(a_rows)} 行[/bold green]")
            self.console.print(f"  [bold green]✅ B 表可读：{len(b_rows)} 行[/bold green]")
            if a_target.source != "fixed":
                self.console.print(f"  [bold green]✅ A 表自动选择：{a_target.title} ({a_target.sheet_id})[/bold green]")
            if b_target.source != "fixed":
                self.console.print(f"  [bold green]✅ B 表自动选择：{b_target.title} ({b_target.sheet_id})[/bold green]")
            if a_rows:
                self.console.print(f"  A 表表头: {a_rows[0][:5]}...")
            if b_rows:
                self.console.print(f"  B 表表头: {b_rows[0][:5]}...")
            self.console.print("  [bold green]✅ 启动自检通过，可直接运行任务[/bold green]")
            return True
        except Exception as exc:
            self.console.print(f"  [bold red]❌ 连接失败: {exc}[/bold red]")
            if "400007" in str(exc) or "Requests Over Limit" in str(exc):
                self.console.print("  [dim]当前更像是腾讯文档接口限流，请稍等后重新运行 tb check。[/dim]")
            else:
                self.console.print("  [dim]请检查 Access Token、Open ID、表格 ID、文档权限和网络，稍后可重新运行 setup/check[/dim]")
            return False

    # ── Check mode ─────────────────────────────────────────────────────────

    def run_check(self) -> None:
        """Validate the current .env configuration."""
        self.console.print(Panel(
            "验证当前配置状态",
            title="[bold]配置检查[/bold]",
            border_style="cyan",
        ))

        if not ENV_PATH.exists():
            self.console.print("[bold red]❌ .env 文件不存在[/bold red]")
            self.console.print("请运行 [cyan]tb setup[/cyan] 进行配置")
            return

        values = dotenv_values(ENV_PATH)

        required = {
            "TENCENT_CLIENT_ID": "腾讯文档 Client ID",
            "TENCENT_ACCESS_TOKEN": "腾讯文档 Access Token",
            "TENCENT_OPEN_ID": "腾讯文档 Open ID",
            "TENCENT_A_FILE_ID": "A 表 File ID",
            "TENCENT_A_SHEET_ID": "A 表 Sheet ID",
            "TENCENT_B_FILE_ID": "B 表 File ID",
            "TENCENT_B_SHEET_ID": "B 表 Sheet ID",
        }

        optional = {
            "TENCENT_CLIENT_SECRET": "腾讯文档 Client Secret",
            "FEISHU_APP_ID": "飞书 App ID",
            "FEISHU_APP_SECRET": "飞书 App Secret",
            "FEISHU_C_FILE_TOKEN": "飞书 C 表 Token",
            "FEISHU_C_SHEET_ID": "飞书 C 表 Sheet ID",
        }

        secret_keys = {
            "TENCENT_CLIENT_ID", "TENCENT_CLIENT_SECRET", "TENCENT_OPEN_ID",
            "TENCENT_ACCESS_TOKEN", "FEISHU_APP_ID", "FEISHU_APP_SECRET",
        }

        table = Table(title="配置状态", box=box.ROUNDED)
        table.add_column("配置项", style="cyan", min_width=28)
        table.add_column("说明", style="white")
        table.add_column("状态", justify="center")
        table.add_column("值", style="dim")

        all_ok = True
        for key, desc in required.items():
            val = values.get(key, "")
            if val:
                display = _mask_secret(val) if key in secret_keys else val
                table.add_row(key, desc, "[green]✅[/green]", display)
            else:
                table.add_row(key, desc, "[red]❌ 缺失[/red]", "")
                all_ok = False

        for key, desc in optional.items():
            val = values.get(key, "")
            if val:
                display = _mask_secret(val) if key in secret_keys else val
                table.add_row(key, desc, "[green]✅[/green]", display)
            else:
                table.add_row(key, desc, "[yellow]⚠ 未配置[/yellow]", "[dim]可选[/dim]")

        self.console.print(table)

        # Show runtime config
        runtime_keys = [
            "GROSS_PROFIT_MODE", "REFUND_MATCH_MODE", "TASK_INTERVAL_MINUTES",
            "DRY_RUN", "ENABLE_STYLE_UPDATE", "WRITE_BATCH_SIZE",
        ]
        rt_table = Table(title="运行参数", box=box.ROUNDED)
        rt_table.add_column("配置项", style="cyan")
        rt_table.add_column("当前值", style="green")
        for key in runtime_keys:
            rt_table.add_row(key, values.get(key, "(默认)"))
        self.console.print(rt_table)

        if all_ok:
            self.console.print("\n[bold green]✅ 必填配置项均已设置[/bold green]")
            self.console.print("[dim]接下来会做一次启动自检：状态目录写入 + 腾讯文档 A/B 表读取[/dim]")
            if self._prompt_bool("是否执行启动自检？", default=True):
                self.values = dict(values)  # type: ignore
                self._test_connection()
        else:
            self.console.print("\n[bold red]❌ 有必填配置项缺失，请运行 tb setup 补充[/bold red]")

    # ── Main flow ──────────────────────────────────────────────────────────

    def run_full(self) -> None:
        """Run the complete setup wizard."""
        try:
            self.console.print(Panel(
                f"{_SETUP_LOGO}\n\n[bold]{BANNER_TITLE}[/bold]\n{BANNER_SUBTITLE}",
                border_style="cyan",
                padding=(1, 2),
            ))

            if self._existing:
                self.console.print("[dim]检测到已有 .env 配置，将作为默认值显示[/dim]")

            self._step_tencent_creds()
            self._step_sheet_ids()
            self._step_feishu_creds()
            self._step_runtime()
            self._step_column_mapping()

            # Ensure business text defaults
            self.values.setdefault("REFUND_STATUS_TEXT", "已退款")
            self.values.setdefault("DATA_ERROR_TEXT", "数据异常")

            self._show_summary()

            if not self._prompt_bool("确认写入 .env 文件？", default=True):
                self.console.print("[yellow]已取消写入[/yellow]")
                return

            self._write_env()

            if self._prompt_bool("是否测试腾讯文档连接？", default=True):
                self._test_connection()

            # Final tips
            self.console.print(Panel(
                "[bold green]配置完成！[/bold green]\n\n"
                "接下来你可以：\n"
                "  1. [cyan]tb all --dry-run[/cyan]  — 模拟执行\n"
                "  2. [cyan]tb all[/cyan]            — 正式执行\n"
                "  3. [cyan]tb start[/cyan]          — 启动定时任务\n"
                "  4. [cyan]tb check[/cyan]          — 验证配置",
                title="[bold]下一步[/bold]",
                border_style="green",
                padding=(1, 2),
            ))

        except KeyboardInterrupt:
            self.console.print("\n\n[yellow]已取消配置向导[/yellow]")
            sys.exit(0)


# ── CLI handlers ───────────────────────────────────────────────────────────

def cmd_setup(args) -> None:
    """Handle `tb setup [--check]`."""
    wizard = SetupWizard()
    if getattr(args, "check", False):
        wizard.run_check()
    else:
        wizard.run_full()
