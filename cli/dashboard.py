"""Rich-powered interactive dashboard for the sync service."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from rich import box
from rich.align import Align
from rich.columns import Columns
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from config.settings import APP_VERSION, Settings, get_settings
from services.daemon_service import DaemonService
from services.state_service import StateService

_LOGO_LINES = [
    ("████████╗██████╗      ██████╗ ██████╗ ██████╗ ███████╗██████╗", "bold #8ecae6"),
    ("╚══██╔══╝██╔══██╗    ██╔═══██╗██╔══██╗██╔══██╗██╔════╝██╔══██╗", "bold #6ccff6"),
    ("   ██║   ██████╔╝    ██║   ██║██████╔╝██║  ██║█████╗  ██████╔╝", "bold #38bdf8"),
    ("   ██║   ██╔══██╗    ██║   ██║██╔══██╗██║  ██║██╔══╝  ██╔══██╗", "bold #22d3ee"),
    ("   ██║   ██████╔╝    ╚██████╔╝██║  ██║██████╔╝███████╗██║  ██║", "bold #2dd4bf"),
    ("   ╚═╝   ╚═════╝      ╚═════╝ ╚═╝  ╚═╝╚═════╝ ╚══════╝╚═╝  ╚═╝", "bold #86efac"),
]
_MODAL_ICONS = {
    "success": ("●", "#10b981"),
    "warning": ("●", "#f59e0b"),
    "error": ("●", "#ef4444"),
    "info": ("●", "#38bdf8"),
}


class DashboardApp:
    """Interactive terminal UI for daily operations."""

    def __init__(self, settings: Settings) -> None:
        self.console = Console()
        self._settings = settings
        self._refresh_services()

    def run(self) -> None:
        """Render dashboard and handle user actions until exit."""
        while True:
            self._refresh_settings()
            self.console.clear()
            self.console.print(self._build_screen())

            choice = self._ask(
                "选择操作",
                default="1",
                choices={"1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "0"},
            )
            if not self._handle_choice(choice):
                break

    def _refresh_settings(self) -> None:
        get_settings.cache_clear()
        self._settings = get_settings()
        self._refresh_services()

    def _refresh_services(self) -> None:
        self._daemon = DaemonService(self._settings)
        self._state_svc = StateService(self._settings.state_dir)

    def _build_screen(self) -> Group:
        daemon_status = self._daemon.status()
        state = self._state_svc.load(quiet=True)
        last_run = self._state_svc.load_last_run(quiet=True)
        autostart_status = self._daemon.autostart_status()

        header = self._build_header(daemon_status, last_run)

        runtime_panel = Panel(
            self._build_runtime_table(),
            title="[bold #023047]运行配置[/bold #023047]",
            border_style="#8ecae6",
            box=box.ROUNDED,
            padding=(1, 2),
        )
        daemon_panel = Panel(
            self._build_daemon_table(daemon_status, autostart_status),
            title="[bold #023047]守护进程[/bold #023047]",
            border_style="#90be6d" if daemon_status.running else "#f4a261",
            box=box.ROUNDED,
            padding=(1, 2),
        )
        state_panel = Panel(
            self._build_state_table(state, last_run),
            title="[bold #023047]同步状态[/bold #023047]",
            border_style="#ffb703",
            box=box.ROUNDED,
            padding=(1, 2),
        )
        config_panel = Panel(
            self._build_config_table(),
            title="[bold #023047]接入状态[/bold #023047]",
            border_style="#fb8500" if self._is_config_ready() else "#d62828",
            box=box.ROUNDED,
            padding=(1, 2),
        )

        actions = Panel(
            self._build_action_table(),
            title="[bold #023047]操作台[/bold #023047]",
            border_style="#219ebc",
            box=box.ROUNDED,
            padding=(1, 2),
        )

        footer = Panel(
            Text(
                f"日志目录: {Path(self._settings.state_dir).resolve()}    "
                f"后台日志: {self._daemon.log_file.name}",
                style="dim",
            ),
            border_style="#577590",
            box=box.SIMPLE,
        )

        return Group(
            header,
            Columns([runtime_panel, daemon_panel], equal=True, expand=True),
            Columns([state_panel, config_panel], equal=True, expand=True),
            actions,
            footer,
        )

    def _build_header(self, daemon_status, last_run) -> Panel:
        logo = Text(justify="center")
        for line, style in _LOGO_LINES:
            logo.append(line, style=style)
            logo.append("\n")
        logo.append("Tencent Docs Order Sync Console", style="bold #e0fbfc")

        hero = Group(
            Align.center(logo),
            Align.right(self._build_version_badge()),
        )

        badges = Table.grid(expand=True)
        badges.add_column(justify="center")
        badges.add_column(justify="center")
        badges.add_column(justify="center")
        badges.add_row(
            self._build_badge("运行模式", f"{self._settings.gross_profit_mode.value} / {self._settings.refund_match_mode.value}", "#0ea5e9"),
            self._build_badge("守护状态", "运行中" if daemon_status.running else "未运行", "#10b981" if daemon_status.running else "#f59e0b"),
            self._build_badge("最近结果", self._last_run_label(last_run), "#22c55e" if last_run and last_run.success else "#ef4444" if last_run else "#64748b"),
        )

        subtitle = Text("多表格同步与退款标记服务", style="bold white", justify="center")
        hint = Text("输入编号执行任务，所有结果与失败原因会在控制台内直接返回", style="dim", justify="center")

        body = Group(
            hero,
            Align.center(subtitle),
            Align.center(hint),
            badges,
        )
        return Panel(
            body,
            border_style="#219ebc",
            box=box.HEAVY,
            padding=(1, 2),
        )

    @staticmethod
    def _build_badge(label: str, value: str, color: str) -> Panel:
        inner = Table.grid(padding=(0, 1))
        inner.add_column(justify="center")
        inner.add_row(Text(label, style="bold white"))
        inner.add_row(Text(value, style="bold white"))
        return Panel(inner, border_style=color, box=box.ROUNDED, padding=(0, 1))

    @staticmethod
    def _build_version_badge() -> Panel:
        text = Text(f"v{APP_VERSION}", style="bold #0f172a", justify="center")
        return Panel(text, border_style="#94d2bd", box=box.ROUNDED, padding=(0, 2), title="版本")

    @staticmethod
    def _last_run_label(last_run) -> str:
        if last_run is None:
            return "暂无记录"
        return "成功" if last_run.success else "失败"

    def _build_runtime_table(self) -> Table:
        table = Table(box=None, show_header=False, pad_edge=False)
        table.add_column(style="bold white")
        table.add_column(style="#023047")
        table.add_row("环境", self._settings.app_env.value)
        table.add_row("间隔", f"{self._settings.task_interval_minutes} 分钟")
        table.add_row("抖动", f"{self._settings.startup_jitter_seconds} 秒")
        table.add_row("毛利模式", self._settings.gross_profit_mode.value)
        table.add_row("退款模式", self._settings.refund_match_mode.value)
        table.add_row("Dry Run", "开启" if self._settings.dry_run else "关闭")
        return table

    def _build_daemon_table(self, status, autostart_status) -> Table:
        table = Table(box=None, show_header=False, pad_edge=False)
        table.add_column(style="bold white")
        table.add_column(style="#023047")
        table.add_row("状态", "[green]运行中[/green]" if status.running else "[yellow]未运行[/yellow]")
        table.add_row("登录自启", "[green]已启用[/green]" if autostart_status.enabled else "[yellow]未启用[/yellow]")
        table.add_row("PID", str(status.pid or "-"))
        table.add_row("启动时间", status.started_at or "-")
        table.add_row("日志文件", status.log_file.name)
        table.add_row("PID 文件", status.pid_file.name)
        return table

    def _build_state_table(self, state, last_run) -> Table:
        table = Table(box=None, show_header=False, pad_edge=False)
        table.add_column(style="bold white")
        table.add_column(style="#023047")
        table.add_row("上次运行", self._fmt_time(state.last_run_at))
        if last_run is not None:
            table.add_row("最近结果", "[green]成功[/green]" if last_run.success else "[red]失败[/red]")
            table.add_row("最近变更", str(last_run.rows_changed))
            table.add_row("最近异常", str(last_run.rows_error))
        table.add_row("A 表指纹", str(len(state.a_table_fingerprints)))
        table.add_row("退款快照", str(len(state.b_table_refund_set)))
        table.add_row("退款哈希", state.b_table_refund_hash[:12] if state.b_table_refund_hash else "-")
        table.add_row("C 表预留", str(len(state.c_table_fingerprints)))
        return table

    def _build_config_table(self) -> Table:
        ready = self._is_config_ready()
        table = Table(box=None, show_header=False, pad_edge=False)
        table.add_column(style="bold white")
        table.add_column(style="#023047")
        table.add_row("腾讯 A/B 表", "[green]已配置[/green]" if ready else "[red]未完成[/red]")
        table.add_row("飞书 C 表", "[green]已录入[/green]" if self._settings.feishu_app_id else "[yellow]待接入[/yellow]")
        table.add_row("样式更新", "开启" if self._settings.enable_style_update else "关闭")
        table.add_row("批量写入", str(self._settings.write_batch_size))
        table.add_row("重试次数", str(self._settings.retry_times))
        return table

    def _build_action_table(self) -> Table:
        table = Table(box=box.SIMPLE_HEAVY, expand=True, row_styles=["none", "dim"])
        table.add_column("编号", justify="center", style="bold #38bdf8", width=6)
        table.add_column("动作", style="bold white", width=18)
        table.add_column("说明", style="#023047")
        table.add_row("1", "执行全部任务", "毛利计算 + 退款匹配")
        table.add_row("2", "模拟执行", "全部任务 dry-run，不写入表格")
        table.add_row("3", "仅毛利计算", "按当前模式处理 A 表")
        table.add_row("4", "仅退款匹配", "刷新退款状态列")
        table.add_row("5", "启动守护", "后台持续运行定时调度")
        table.add_row("6", "停止守护", "停止后台调度进程")
        table.add_row("7", "重启守护", "重启后台调度进程")
        table.add_row("8", "查看后台日志", "显示守护日志末尾 40 行")
        table.add_row("9", "配置向导", "打开交互式 setup")
        table.add_row("10", "配置检查", "检查 .env 完整性")
        table.add_row("11", "前台调度", "当前终端直接运行 scheduler")
        table.add_row("12", "启用登录自启", "登录系统后自动拉起后台调度")
        table.add_row("13", "停用登录自启", "移除当前用户的自启配置")
        table.add_row("14", "查看自启状态", "检查当前用户的登录自启状态")
        table.add_row("0", "退出", "返回系统")
        return table

    def _handle_choice(self, choice: str) -> bool:
        if choice == "0":
            return False
        if choice == "1":
            self._run_task("all")
        elif choice == "2":
            self._run_task("all", dry_run=True)
        elif choice == "3":
            self._run_task("gross-profit")
        elif choice == "4":
            self._run_task("refund-match")
        elif choice == "5":
            self._daemon_action("start")
        elif choice == "6":
            self._daemon_action("stop")
        elif choice == "7":
            self._daemon_action("restart")
        elif choice == "8":
            self._show_log_tail()
        elif choice == "9":
            self._run_setup(check=False)
        elif choice == "10":
            self._run_setup(check=True)
        elif choice == "11":
            self._run_foreground_scheduler()
        elif choice == "12":
            self._daemon_action("autostart-enable")
        elif choice == "13":
            self._daemon_action("autostart-disable")
        elif choice == "14":
            self._daemon_action("autostart-status")
        return True

    def _run_task(self, task: str, *, dry_run: bool = False) -> None:
        if not self._ensure_config():
            return
        from cli.commands import execute_tasks

        results = execute_tasks(self._settings, task, dry_run=dry_run)
        table = Table(box=box.SIMPLE_HEAVY, expand=True, row_styles=["none", "dim"])
        table.add_column("任务", style="bold cyan")
        table.add_column("结果", justify="center")
        table.add_column("读取", justify="right")
        table.add_column("变更", justify="right")
        table.add_column("异常", justify="right")
        for item in results:
            status = "[green]成功[/green]" if item.success else "[red]失败[/red]"
            table.add_row(
                item.task_name.value,
                status,
                str(item.rows_read),
                str(item.rows_changed),
                str(item.rows_error),
            )
        body: Group | Table = table
        failures = [item for item in results if item.error_message]
        if failures:
            failure_table = Table(box=box.SIMPLE_HEAVY, expand=True)
            failure_table.add_column("任务", style="bold red")
            failure_table.add_column("失败原因", style="white")
            for item in failures:
                failure_table.add_row(item.task_name.value, item.error_message or "")
            body = Group(
                self._build_modal_summary("执行完成，但存在失败项", style="error"),
                table,
                Panel(failure_table, title="失败详情", border_style="red", box=box.ROUNDED, padding=(1, 2)),
            )
            self._pause_with_panel(body, title="执行结果", border_style="#ef4444")
            return

        body = Group(
            self._build_modal_summary("执行完成，结果已落地", style="success"),
            table,
        )
        self._pause_with_panel(body, title="执行结果", border_style="#219ebc")

    def _daemon_action(self, action: str) -> None:
        if action in {"start", "autostart-enable"} and not self._ensure_config():
            return

        if action == "start":
            status = self._daemon.start()
        elif action == "stop":
            status = self._daemon.stop(force=True)
        elif action == "restart":
            status = self._daemon.restart()
        elif action == "autostart-enable":
            status = self._daemon.enable_autostart()
        elif action == "autostart-disable":
            status = self._daemon.disable_autostart()
        else:
            status = self._daemon.autostart_status()

        style = "success"
        border = "#90be6d"
        if "失败" in status.message or "未找到" in status.message:
            style = "error"
            border = "#ef4444"
        elif "未启用" in status.message or "未运行" in status.message:
            style = "warning"
            border = "#f59e0b"

        body = Group(
            self._build_modal_summary(status.message, style=style),
            self._build_kv_table({
                "动作": action,
                "目标": getattr(status, "target", "") or "-",
            }),
        )
        self._pause_with_panel(body, title="守护结果", border_style=border)

    def _show_log_tail(self) -> None:
        content = self._daemon.read_log_tail(lines=40)
        if content:
            log_panel = Panel(
                Text(content, style="#e5e7eb"),
                title=f"后台日志 · {self._daemon.log_file.name}",
                border_style="#ffb703",
                box=box.ROUNDED,
                padding=(1, 2),
            )
            body = Group(
                self._build_modal_summary("以下为最近 40 行后台日志", style="info"),
                log_panel,
            )
        else:
            body = Group(
                self._build_modal_summary("后台日志暂时为空", style="warning"),
                self._build_kv_table({
                    "日志文件": self._daemon.log_file.name,
                    "日志目录": str(self._daemon.log_file.parent),
                }),
            )
        self._pause_with_panel(body, title="后台日志", border_style="#ffb703")

    def _run_setup(self, *, check: bool) -> None:
        from cli.setup import cmd_setup

        args = argparse.Namespace(check=check)
        cmd_setup(args)
        self._refresh_settings()
        self._wait()

    def _run_foreground_scheduler(self) -> None:
        if not self._ensure_config():
            return
        if not self._confirm("前台调度会占用当前终端，确认继续？", default=False):
            return
        from cli.commands import start_scheduler

        start_scheduler(self._settings)

    def _ensure_config(self) -> bool:
        if self._is_config_ready():
            return True
        body = Group(
            self._build_modal_summary("腾讯文档必填配置尚未完成", style="error"),
            self._build_kv_table({
                "建议动作": "先运行 tb setup",
                "后续检查": "配置完成后运行 tb check",
            }),
        )
        self._pause_with_panel(body, title="配置未完成", border_style="#ef4444")
        return False

    def _is_config_ready(self) -> bool:
        fields = [
            self._settings.tencent_client_id,
            self._settings.tencent_open_id,
            self._settings.tencent_access_token,
            self._settings.tencent_a_file_id,
            self._settings.tencent_a_sheet_id,
            self._settings.tencent_b_file_id,
            self._settings.tencent_b_sheet_id,
        ]
        return all(bool(value.strip()) for value in fields)

    def _pause_with_panel(self, body, *, title: str, border_style: str) -> None:
        self.console.clear()
        self.console.print(
            Panel(
                body,
                title=title,
                border_style=border_style,
                box=box.ROUNDED,
                padding=(1, 2),
            )
        )
        self._wait()

    def _build_modal_summary(self, message: str, *, style: str) -> Panel:
        icon, color = _MODAL_ICONS[style]
        text = Text(justify="center")
        text.append(f"{icon} ", style=f"bold {color}")
        text.append(message, style="bold white")
        return Panel(text, border_style=color, box=box.ROUNDED, padding=(0, 1))

    @staticmethod
    def _build_kv_table(rows: dict[str, str]) -> Table:
        table = Table(box=box.SIMPLE_HEAVY, expand=True, row_styles=["none", "dim"])
        table.add_column("项目", style="bold cyan", width=18)
        table.add_column("内容", style="white")
        for key, value in rows.items():
            table.add_row(key, value)
        return table

    def _wait(self) -> None:
        self.console.input("[dim]按回车返回控制台[/dim]")

    def _ask(self, label: str, *, default: str, choices: set[str]) -> str:
        prompt = f"[bold cyan]{label}[/bold cyan] [dim](默认 {default})[/dim]: "
        while True:
            raw = self.console.input(prompt).strip()
            value = raw or default
            if value in choices:
                return value
            self.console.print("[red]输入无效，请重新输入。[/red]")

    def _confirm(self, label: str, *, default: bool = False) -> bool:
        hint = "Y/n" if default else "y/N"
        raw = self.console.input(f"[bold cyan]{label}[/bold cyan] [dim]{hint}[/dim]: ").strip().lower()
        if not raw:
            return default
        return raw in {"y", "yes", "是"}

    @staticmethod
    def _fmt_time(value: datetime | None) -> str:
        if value is None:
            return "-"
        return value.strftime("%Y-%m-%d %H:%M:%S")


def cmd_menu(args: argparse.Namespace, settings: Settings) -> None:
    """Entry point for the interactive dashboard."""
    DashboardApp(settings).run()
