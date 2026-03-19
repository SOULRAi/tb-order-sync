# Changelog

All notable changes to this project will be documented in this file.

## [0.4.0] - 2026-03-19

### Added

- Added startup self-check in `tb check`, including state directory write validation and live Tencent Docs A/B sheet read checks.
- Added Tencent Docs URL parsing in setup so users can paste full sheet links and auto-fill `File ID` / `Sheet ID`.
- Added login auto-start support via `tb daemon autostart-enable|status|disable` for Windows Task Scheduler and macOS LaunchAgent.
- Added `state/last_run.json` execution summaries for manual and scheduled runs.
- Added packaged `快速开始.txt` to distribution outputs for non-technical users.

### Changed

- Changed no-argument startup to enter `setup` automatically when required runtime config is missing.
- Changed config validation so `TENCENT_CLIENT_SECRET` is now optional for the current live Tencent Docs runtime path.
- Changed dashboard and daemon status output to surface recent run status and login auto-start state.
- Changed launcher and README onboarding to emphasize `tb check` as the first runtime self-check after setup.

### Fixed

- Fixed Tencent Docs rate-limit handling by retrying `400007 Requests Over Limit` responses with exponential backoff.
- Fixed repeated batch writes being too aggressive by slowing inter-batch pacing.
- Fixed user-facing error reporting so failed tasks now include clearer cause hints in CLI output.

## [0.3.1] - 2026-03-19

### Added

- Added README badges for npm, GitHub, and license visibility.
- Added npm metadata fields for repository, homepage, and issue tracking.

### Changed

- Improved npm package description and keywords to better reflect order sync, refund workflow, and spreadsheet automation.
- Prepared GitHub release metadata for the public `tb-order-sync` repository.

## [0.3.0] - 2026-03-19

### Added

- Added a Rich-based interactive dashboard with status cards, action panels, and log viewing.
- Added cross-platform daemon management with `daemon start|stop|restart|status|logs`.
- Added beginner onboarding links for Tencent Docs API and Feishu API inside the setup wizard.
- Added optional browser-opening support for official documentation links during setup.
- Added simplified CLI aliases such as `all`, `gp`, `rm`, `check`, `config`, and `menu`.
- Added npm launcher packaging with a `tb` binary entry point.
- Added `.gitignore` for Python build artifacts, runtime state, and local secrets.

### Changed

- Renamed the distribution package to `tb-order-sync` to match the order-sync use case and the `tb` launcher.
- Changed no-argument startup to open the Rich dashboard by default.
- Changed macOS and Windows launcher scripts to delegate to the unified in-app dashboard.
- Changed README to document dashboard usage, daemon commands, API onboarding, and npm packaging.
- Changed CLI command structure to keep backward compatibility while exposing shorter commands.

### Fixed

- Fixed heavy eager imports in the CLI so `--help` and setup-related flows return quickly.
- Fixed dashboard rendering noise by adding a quiet state-load mode.
- Fixed direct task/scheduler/daemon startup to block clearly when Tencent credentials are incomplete.
