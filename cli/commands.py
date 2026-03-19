"""CLI entry points for the sync service."""

from __future__ import annotations

import argparse
import sys
from typing import TYPE_CHECKING, Optional

from config.settings import Settings, SyncMode, get_settings
from models.task_models import TaskResult
from services.daemon_service import DaemonService
from services.state_service import StateService
from utils.logger import get_logger, setup_logging

if TYPE_CHECKING:
    from connectors.tencent_docs import TencentDocsConnector

logger = get_logger(__name__)


def _build_connector(settings: Settings) -> TencentDocsConnector:
    from connectors.tencent_docs import TencentDocsConnector

    return TencentDocsConnector(
        client_id=settings.tencent_client_id,
        client_secret=settings.tencent_client_secret,
        access_token=settings.tencent_access_token,
        open_id=settings.tencent_open_id,
    )


def _build_state_service(settings: Settings) -> StateService:
    return StateService(state_dir=settings.state_dir)


def _add_run_options(parser: argparse.ArgumentParser) -> None:
    """Attach common execution flags to a parser."""
    parser.add_argument("--dry-run", action="store_true", help="Simulate without writing")
    parser.add_argument("--mode", choices=["incremental", "full"], help="Override sync mode")


def _normalize_task_name(command: str) -> str:
    """Map shorthand commands to internal task names."""
    if command in ("gross-profit", "gp"):
        return "gross-profit"
    if command in ("refund-match", "rm"):
        return "refund-match"
    if command == "all":
        return "all"
    return command


def has_required_runtime_config(settings: Settings) -> bool:
    """Return whether Tencent runtime essentials are configured."""
    required = [
        settings.tencent_client_id,
        settings.tencent_client_secret,
        settings.tencent_access_token,
        settings.tencent_a_file_id,
        settings.tencent_a_sheet_id,
        settings.tencent_b_file_id,
        settings.tencent_b_sheet_id,
    ]
    return all(bool(value.strip()) for value in required)


def _ensure_runtime_config(settings: Settings) -> bool:
    if has_required_runtime_config(settings):
        return True
    logger.error("缺少腾讯文档必填配置，请先运行 `setup` 或 `config` 完成配置。")
    return False


def execute_tasks(
    settings: Settings,
    task: str,
    *,
    dry_run: bool = False,
    mode: Optional[SyncMode] = None,
) -> list[TaskResult]:
    """Run one or more tasks and return their results."""
    if not _ensure_runtime_config(settings):
        return []

    from services.gross_profit_service import GrossProfitService
    from services.refund_match_service import RefundMatchService

    connector = _build_connector(settings)
    state_svc = _build_state_service(settings)
    results: list[TaskResult] = []

    if task in ("gross-profit", "all"):
        svc = GrossProfitService(connector, state_svc, settings)
        result = svc.run(mode=mode or settings.gross_profit_mode, dry_run=dry_run)
        _print_result(result)
        results.append(result)

    if task in ("refund-match", "all"):
        svc = RefundMatchService(connector, state_svc, settings)
        result = svc.run(mode=mode or settings.refund_match_mode, dry_run=dry_run)
        _print_result(result)
        results.append(result)

    return results


def cmd_run(args: argparse.Namespace, settings: Settings) -> None:
    """Run one or more tasks."""
    dry_run = args.dry_run or settings.dry_run
    mode: Optional[SyncMode] = None
    if args.mode:
        mode = SyncMode(args.mode)

    execute_tasks(settings, args.task, dry_run=dry_run, mode=mode)


def start_scheduler(settings: Settings) -> None:
    """Start the foreground scheduler."""
    if not _ensure_runtime_config(settings):
        return

    from services.scheduler_service import SchedulerService

    connector = _build_connector(settings)
    state_svc = _build_state_service(settings)
    scheduler = SchedulerService(connector, state_svc, settings)
    scheduler.start()


def cmd_schedule(args: argparse.Namespace, settings: Settings) -> None:
    """Start periodic scheduler."""
    start_scheduler(settings)


def cmd_daemon(args: argparse.Namespace, settings: Settings) -> None:
    """Manage the scheduler daemon process."""
    daemon = DaemonService(settings)
    action = args.daemon_action

    if action == "start":
        if not _ensure_runtime_config(settings):
            return
        status = daemon.start(force=getattr(args, "force", False))
        logger.info(status.message)
    elif action == "stop":
        status = daemon.stop(force=getattr(args, "force", False))
        logger.info(status.message)
    elif action == "restart":
        status = daemon.restart(force=True)
        logger.info(status.message)
    elif action == "status":
        status = daemon.status()
        logger.info(status.message)
        if status.running:
            logger.info("daemon pid=%s log=%s", status.pid, status.log_file)
    elif action == "logs":
        content = daemon.read_log_tail(lines=args.lines)
        if content:
            print(content, end="")
        else:
            logger.info("No daemon log output yet: %s", daemon.log_file)


def _print_result(result: TaskResult) -> None:
    status = "OK" if result.success else "FAILED"
    logger.info(
        "[%s] %s — read=%d changed=%d errors=%d dry_run=%s",
        status, result.task_name.value, result.rows_read,
        result.rows_changed, result.rows_error, result.dry_run,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sync-service",
        description="多表格同步与退款标记服务",
    )
    sub = parser.add_subparsers(dest="command", required=False)

    run_parser = sub.add_parser("run", help="Run task(s)")
    run_parser.add_argument(
        "task",
        choices=["gross-profit", "refund-match", "all"],
        help="Which task to run",
    )
    _add_run_options(run_parser)

    all_parser = sub.add_parser("all", help="直接执行全部任务")
    _add_run_options(all_parser)

    gp_parser = sub.add_parser("gross-profit", aliases=["gp"], help="直接执行毛利计算")
    _add_run_options(gp_parser)

    rm_parser = sub.add_parser("refund-match", aliases=["rm"], help="直接执行退款匹配")
    _add_run_options(rm_parser)

    sub.add_parser("schedule", aliases=["start"], help="前台启动定时调度")

    daemon_parser = sub.add_parser("daemon", help="守护进程管理")
    daemon_sub = daemon_parser.add_subparsers(dest="daemon_action", required=True)
    daemon_start = daemon_sub.add_parser("start", help="启动后台守护进程")
    daemon_start.add_argument("--force", action="store_true", help="已运行时先停止再重启")
    daemon_stop = daemon_sub.add_parser("stop", help="停止后台守护进程")
    daemon_stop.add_argument("--force", action="store_true", help="必要时强制终止")
    daemon_sub.add_parser("restart", help="重启后台守护进程")
    daemon_sub.add_parser("status", help="查看后台守护状态")
    daemon_logs = daemon_sub.add_parser("logs", help="查看后台日志")
    daemon_logs.add_argument("--lines", type=int, default=40, help="显示最后 N 行日志")

    setup_parser = sub.add_parser("setup", aliases=["config"], help="交互式配置向导")
    setup_parser.add_argument("--check", action="store_true", help="验证当前配置状态")

    sub.add_parser("check", help="验证当前配置状态")
    sub.add_parser("menu", aliases=["ui", "dashboard"], help="打开交互式控制台")

    return parser


def main(argv: list[str] | None = None) -> None:
    """CLI main entry point."""
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        argv = ["menu"]

    settings = get_settings()
    setup_logging(level=settings.log_level, log_dir=settings.state_dir)

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command in ("setup", "config"):
        from cli.setup import cmd_setup

        cmd_setup(args)
        return

    if args.command == "check":
        from cli.setup import cmd_setup

        args.check = True
        cmd_setup(args)
        return

    if args.command in ("menu", "ui", "dashboard"):
        from cli.dashboard import cmd_menu

        cmd_menu(args, settings)
        return

    if args.command == "run":
        cmd_run(args, settings)
    elif args.command in ("all", "gross-profit", "gp", "refund-match", "rm"):
        args.task = _normalize_task_name(args.command)
        cmd_run(args, settings)
    elif args.command in ("schedule", "start"):
        cmd_schedule(args, settings)
    elif args.command == "daemon":
        cmd_daemon(args, settings)
