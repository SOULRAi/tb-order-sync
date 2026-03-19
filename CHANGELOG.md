# Changelog

All notable changes to this project will be documented in this file.

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
