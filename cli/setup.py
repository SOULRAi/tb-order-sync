"""Interactive setup wizard for one-stop configuration.

Usage:
    tb setup          # Full guided setup
    tb setup --check  # Validate current config
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional, Sequence
from urllib.parse import parse_qs, urlparse

try:
    from rich.align import Align
    from rich.console import Console, Group
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich import box
except ImportError:
    sys.exit("缺少 rich 库，请先安装: pip install rich")

from dotenv import dotenv_values

from config.settings import APP_HOME, APP_VERSION, PACKAGE_ROOT
from utils.sheet_selector import resolve_latest_month_sheet

# ── UI 文案 ────────────────────────────────────────────────────────────────
BANNER_TITLE = "多表格同步服务 — 配置向导"
BANNER_SUBTITLE = "按照提示逐步完成配置，按 Ctrl+C 随时退出"

STEP_TENCENT = "第 1 步：腾讯文档凭证"
STEP_SHEETS = "第 2 步：表格 ID 配置"
STEP_RUNTIME = "第 3 步：运行参数"
STEP_COLUMNS = "第 4 步：列映射"
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
_SETUP_LOGO = (
    "[bold #8ecae6]████████╗██████╗     ██████╗ ██████╗ ██████╗ ███████╗██████╗[/bold #8ecae6]\n"
    "[bold #38bdf8]╚══██╔══╝██╔══██╗   ██╔═══██╗██╔══██╗██╔══██╗██╔════╝██╔══██╗[/bold #38bdf8]\n"
    "[bold #22d3ee]   ██║   ██████╔╝   ██║   ██║██████╔╝██║  ██║█████╗  ██████╔╝[/bold #22d3ee]\n"
    "[bold #2dd4bf]   ██║   ██╔══██╗   ██║   ██║██╔══██╗██║  ██║██╔══╝  ██╔══██╗[/bold #2dd4bf]\n"
    "[bold #86efac]   ██║   ██████╔╝   ╚██████╔╝██║  ██║██████╔╝███████╗██║  ██║[/bold #86efac]\n"
    "[bold #bbf7d0]   ╚═╝   ╚═════╝     ╚═════╝ ╚═╝  ╚═╝╚═════╝ ╚══════╝╚═╝  ╚═╝[/bold #bbf7d0]"
)


def _build_setup_version_badge() -> Panel:
    text = Text(f"v{APP_VERSION}", style="bold #0f172a", justify="center")
    return Panel(text, border_style="#94d2bd", box=box.ROUNDED, padding=(0, 2), title="版本")


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


def resolve_link_selection(raw: str, link_count: int) -> list[int]:
    """Resolve numeric selection for link-opening prompts.

    Rules:
    - empty => skip
    - 1..N => open one specific link
    """
    value = raw.strip()
    if not value:
        return []
    try:
        choice = int(value)
    except ValueError as exc:
        raise ValueError("请输入数字编号") from exc

    index = choice - 1
    if 0 <= index < link_count:
        return [index]
    raise ValueError("编号超出范围")


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


class SetupInputTerminated(RuntimeError):
    """Raised when the setup input stream is unexpectedly closed."""


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

    @staticmethod
    def _read_line(prompt: str = "  > ") -> str:
        """Read one input line using the plain stdlib input path.

        This is intentionally not using `Console.input`, because the Windows
        packaged runtime is more stable with the built-in `input()` behavior.
        """
        try:
            return input(prompt).strip()
        except EOFError as exc:
            raise SetupInputTerminated("输入流已结束") from exc

    def _prompt(
        self,
        label: str,
        key: str,
        default: str = "",
        secret: bool = False,
        validator: Optional[Callable[[str], bool]] = None,
        error_msg: str = "输入无效，请重新输入",
        allow_skip: bool = False,
    ) -> str:
        """Prompt user for a value with optional validation and masking."""
        existing = self._existing.get(key, "")
        effective_default = existing or default

        while True:
            hint_value = _mask_secret(effective_default) if secret and effective_default else effective_default
            hint_label = "当前" if secret else "默认"
            hint = f" [{hint_label}: {hint_value}]" if hint_value else ""
            note = " [dim]可直接粘贴[/dim]"
            if allow_skip:
                note += " [dim]输入 /skip 暂时跳过[/dim]"

            self.console.print(f"  {label}{hint}{note}")
            try:
                raw = self._read_line()
            except SetupInputTerminated:
                if allow_skip:
                    self.console.print("  [yellow]输入已结束，已暂时跳过当前项[/yellow]")
                    return ""
                raise

            if allow_skip and raw.lower() == "/skip":
                self.console.print("  [yellow]已暂时跳过，可稍后重新运行 setup 补充[/yellow]")
                return ""

            if not raw and effective_default:
                raw = effective_default

            if validator and not validator(raw):
                self.console.print(f"  [red]{error_msg}[/red]")
                continue

            return raw

    def _prompt_bool(self, label: str, default: bool = False) -> bool:
        hint = "Y/n" if default else "y/N"
        self.console.print(f"  {label} [{hint}]")
        try:
            raw = self._read_line().lower()
        except SetupInputTerminated:
            self.console.print("  [yellow]输入已结束，已使用默认选项[/yellow]")
            return default
        if not raw:
            return default
        if raw in {"/skip", "skip"}:
            return default
        return raw in ("y", "yes", "是")

    def _prompt_choice(
        self,
        label: str,
        key: str,
        options: Sequence[tuple[str, str, str]],
        default_value: str,
    ) -> str:
        """Prompt the user to choose one option via a numbered list."""
        existing = (self._existing.get(key, "") or "").strip()
        effective_default = existing or default_value
        option_map = {str(idx): value for idx, (value, _, _) in enumerate(options, start=1)}
        default_choice = next(
            (str(idx) for idx, (value, _, _) in enumerate(options, start=1) if value == effective_default),
            "1",
        )

        self.console.print(f"  {label}")
        for idx, (_, title, desc) in enumerate(options, start=1):
            suffix = " [dim](默认)[/dim]" if str(idx) == default_choice else ""
            self.console.print(f"    {idx}. {title}{suffix}")
            self.console.print(f"       [dim]{desc}[/dim]")

        while True:
            self.console.print(f"  [dim]请输入编号，直接回车使用默认选项（{default_choice}）[/dim]")
            raw = self._read_line()
            if not raw:
                return option_map[default_choice]
            if raw in option_map:
                return option_map[raw]
            self.console.print("  [red]请输入有效编号[/red]")

    def _prompt_sheet_link(self, name: str, file_key: str, sheet_key: str) -> None:
        """Prompt for a full Tencent Docs sheet link and parse both file/sheet ids."""
        existing_file = (self._existing.get(file_key, "") or "").strip()
        existing_sheet = (self._existing.get(sheet_key, "") or "").strip()

        self.console.print(f"  [bold]{name}[/bold]")
        if existing_file and existing_sheet:
            self.console.print("  [dim]直接粘贴完整腾讯文档链接；直接回车则保持当前配置[/dim]")
        else:
            self.console.print("  [dim]请直接粘贴完整腾讯文档在线表格链接[/dim]")

        while True:
            hint = " [dim]（可直接粘贴）[/dim]"
            self.console.print(f"  {name}链接{hint}")
            raw = self._read_line()

            if not raw:
                if existing_file and existing_sheet:
                    self.values[file_key] = existing_file
                    self.values[sheet_key] = existing_sheet
                    self.console.print(f"  [green]已保留当前配置：{existing_sheet}[/green]")
                    return
                self.console.print("  [red]请直接粘贴完整腾讯文档链接[/red]")
                continue

            file_id, sheet_id = parse_tencent_sheet_reference(raw)
            if not file_id or not sheet_id:
                self.console.print("  [red]无法自动解析，请直接粘贴完整腾讯文档在线表格链接[/red]\n")
                continue

            self.values[file_key] = file_id
            self.values[sheet_key] = sheet_id
            self.console.print(f"  [green]已自动解析 Sheet ID: {sheet_id}[/green]")
            return

    def _apply_implicit_defaults(self) -> None:
        """Preserve hidden or omitted config values when setup skips them."""
        implicit_defaults = {
            "TENCENT_CLIENT_SECRET": "",
            "FEISHU_APP_ID": "",
            "FEISHU_APP_SECRET": "",
            "FEISHU_C_FILE_TOKEN": "",
            "FEISHU_C_SHEET_ID": "",
            "APP_ENV": "dev",
            "LOG_LEVEL": "INFO",
            "C_SYNC_MODE": "incremental",
            "REFUND_STATUS_TEXT": "已退款",
            "DATA_ERROR_TEXT": "数据异常",
        }
        for key, default in implicit_defaults.items():
            if key not in self.values:
                self.values[key] = (self._existing.get(key, "") or default).strip() or default

    def _offer_open_links(self, title: str, links: Sequence[tuple[str, str]]) -> None:
        """Optionally open one or more documentation links in the default browser."""
        if not links:
            return

        self.console.print(f"  [dim]{title}：[/dim]")
        for idx, (label, url) in enumerate(links, start=1):
            self.console.print(f"    {idx}. {label}: [cyan]{url}[/cyan]")
        if len(links) == 1:
            choice_help = "输入 1 打开链接，直接回车跳过"
        else:
            choice_help = f"输入 1 到 {len(links)} 打开对应链接，直接回车跳过"
        self.console.print(f"  [dim]{choice_help}[/dim]")

        while True:
            try:
                raw = self._read_line()
            except SetupInputTerminated:
                self.console.print("  [yellow]输入已结束，已跳过打开链接[/yellow]")
                return
            try:
                indexes = resolve_link_selection(raw, len(links))
            except ValueError as exc:
                self.console.print(f"  [red]{exc}[/red]")
                continue
            break

        if not indexes:
            self.console.print("  [dim]已跳过打开链接[/dim]")
            return

        opened = 0
        for index in indexes:
            label, url = links[index]
            try:
                if self._open_url(url):
                    opened += 1
                else:
                    self.console.print(f"  [yellow]未能打开: {label} - {url}[/yellow]")
            except Exception as exc:  # pragma: no cover - defensive guard
                self.console.print(f"  [yellow]打开失败: {label} - {url} ({exc})[/yellow]")

        if opened:
            self.console.print(f"  [green]已尝试打开 {opened} 个链接[/green]")
        else:
            self.console.print("  [yellow]未能自动打开浏览器，请手动复制上面的链接[/yellow]")

    @staticmethod
    def _open_url(url: str) -> bool:
        """Open a URL in the default browser with platform fallbacks."""
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
            if os.name == "nt":
                try:
                    os.startfile(url)  # type: ignore[attr-defined]
                    return True
                except Exception:
                    pass
                subprocess.Popen(
                    ["cmd", "/c", "start", "", url],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return True
            subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            pass

        try:
            return bool(webbrowser.open_new_tab(url))
        except webbrowser.Error:
            return False

    def _show_tencent_guide(self) -> None:
        """Display beginner guidance for Tencent Docs Open API setup."""
        body = (
            "1. 先打开腾讯文档开放平台开发文档，确认你接入的是 Open API。\n"
            f"   文档入口: {TENCENT_DOCS_GUIDE_URL}\n"
            "2. 再打开开发者平台，创建应用并进入应用详情页。\n"
            f"   开发者平台: {TENCENT_DEVELOPER_CONSOLE_URL}\n"
            "3. 在应用详情页里获取 Client ID。\n"
            "4. 完成授权后，拿到 Open ID 和 Access Token。\n"
            "5. 当前向导只需要你填写 Client ID、Open ID、Access Token 这三项即可。"
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
            "2. 复制浏览器地址栏里的完整表格链接。\n"
            "3. 直接把完整链接粘贴到下面，系统会自动解析 File ID 和 Sheet ID。\n"
            "4. 如果没有识别成功，通常是因为链接不完整，或者当前页面不是在线表格页。"
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
        self.values["TENCENT_OPEN_ID"] = self._prompt(
            "Open ID", "TENCENT_OPEN_ID", secret=True, validator=_not_empty,
            error_msg="Open ID 不能为空",
        )
        self.values["TENCENT_ACCESS_TOKEN"] = self._prompt(
            "Access Token", "TENCENT_ACCESS_TOKEN", secret=True, validator=_not_empty,
            error_msg="Access Token 不能为空",
        )

    def _step_sheet_ids(self) -> None:
        self.console.print(f"\n[bold cyan]📊 {STEP_SHEETS}[/bold cyan]")
        self.console.print("  直接粘贴腾讯文档完整链接，系统会自动解析表格信息\n")
        self._show_sheet_id_guide()
        self.console.print("")

        self._prompt_sheet_link("A表（订单表/毛利率表）", "TENCENT_A_FILE_ID", "TENCENT_A_SHEET_ID")
        self.values["TENCENT_A_SHEET_NAME_KEYWORD"] = self._prompt(
            "A表表格关键字匹配（可选，例如 毛利率）",
            "TENCENT_A_SHEET_NAME_KEYWORD",
            default="",
        )
        self.console.print("")
        self._prompt_sheet_link("B表（客户退款表）", "TENCENT_B_FILE_ID", "TENCENT_B_SHEET_ID")
        self.values["TENCENT_B_SHEET_NAME_KEYWORD"] = self._prompt(
            "B表表格关键字匹配（可选，例如 客户退款）",
            "TENCENT_B_SHEET_NAME_KEYWORD",
            default="",
        )

    def _step_runtime(self) -> None:
        self.console.print(f"\n[bold cyan]⚙️  {STEP_RUNTIME}[/bold cyan]\n")

        self.values["STATE_DIR"] = self._prompt(
            "状态文件目录", "STATE_DIR", default="state",
        )
        self.values["GROSS_PROFIT_MODE"] = self._prompt_choice(
            "毛利计算模式",
            "GROSS_PROFIT_MODE",
            [
                ("incremental", "增量模式", "只处理新增行或发生变化的行"),
                ("full", "全量模式", "重新计算整张表的毛利"),
            ],
            default_value="incremental",
        )
        self.values["REFUND_MATCH_MODE"] = self._prompt_choice(
            "退款匹配模式",
            "REFUND_MATCH_MODE",
            [
                ("incremental", "增量模式", "只处理新增退款单和发生变化的订单"),
                ("full", "全量模式", "全表重扫并重建退款状态"),
            ],
            default_value="incremental",
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
                "TENCENT_CLIENT_ID", "TENCENT_OPEN_ID", "TENCENT_ACCESS_TOKEN",
            ]),
            ("表格 ID", [
                "TENCENT_A_FILE_ID", "TENCENT_A_SHEET_ID",
                "TENCENT_A_SHEET_NAME_KEYWORD",
                "TENCENT_B_FILE_ID", "TENCENT_B_SHEET_ID",
                "TENCENT_B_SHEET_NAME_KEYWORD",
            ]),
            ("运行参数", [
                "STATE_DIR", "GROSS_PROFIT_MODE", "REFUND_MATCH_MODE",
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
            hero = Group(
                Align.center(Text.from_markup(_SETUP_LOGO)),
                Align.right(_build_setup_version_badge()),
            )
            self.console.print(Panel(
                Group(
                    hero,
                    Text(""),
                    Text(BANNER_TITLE, style="bold", justify="center"),
                    Text(BANNER_SUBTITLE, style="default", justify="center"),
                ),
                border_style="cyan",
                padding=(1, 2),
            ))

            if self._existing:
                self.console.print("[dim]检测到已有 .env 配置，将作为默认值显示[/dim]")

            self._step_tencent_creds()
            self._step_sheet_ids()
            self._step_runtime()
            self._step_column_mapping()
            self._apply_implicit_defaults()

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
        except SetupInputTerminated:
            self.console.print("\n\n[yellow]输入已结束，配置向导已安全退出[/yellow]")
            sys.exit(1)


# ── CLI handlers ───────────────────────────────────────────────────────────

def cmd_setup(args) -> None:
    """Handle `tb setup [--check]`."""
    wizard = SetupWizard()
    if getattr(args, "check", False):
        wizard.run_check()
    else:
        wizard.run_full()
