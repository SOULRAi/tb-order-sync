# Changelog

All notable changes to this project will be documented in this file.

## [0.4.5] - 2026-03-20

### 新增

- 在 CLI 首页和配置向导的 LOGO 右下角新增版本号展示，便于直接确认当前运行版本。

### 变更

- 变更发布构建内容：打包产物现在会一并包含 `package.json`，保证 macOS / Windows 分发包中的 CLI 也能正确显示版本号。
- 变更 README 的分发包说明，统一 macOS 资产命名为 `tb-order-sync-macos-x64-<version>.zip`。

### 修复

- 修复 `tb setup` 链接选择菜单的残留交互问题：现在支持 `0`、空回车、`/skip`、`q` 等跳过方式，并在输入流中断时安全退出，不再抛出 `EOFError` 栈追踪。

## [0.4.4] - 2026-03-20

### 修复

- 修复 `tb setup` 在 Windows 环境下输入不稳定的问题：配置向导现统一使用原生 `input()` 读取，避免官网链接打开后无法继续输入、无法输入字母数字、无法粘贴的问题。
- 修复 `tb setup` 的官网链接打开交互体验：保持数字菜单方式，支持跳过、打开全部、打开单个链接，并增强 Windows 下的浏览器启动回退逻辑。
- 修复 Windows 双击 `启动.bat` 可能直接闪退的问题：补上缺失的 `:menu` 标签，并修正 Python / EXE 命令拼接与失败停留逻辑。

## [0.4.3] - 2026-03-20

### 新增

- 新增按工作表标题关键字自动选择“最新月份” sheet 的能力，可分别作用于 A 表和 B 表。
- 新增工作表月份解析工具，支持以下标题格式：
  - `2026年3月毛利率`
  - `2026-03 毛利率`
  - `2026/03 客户退款`
  - `3月毛利率`
- 新增 `TENCENT_A_SHEET_NAME_KEYWORD` / `TENCENT_B_SHEET_NAME_KEYWORD` 两个可选配置项。
- 新增月份选择相关单元测试，覆盖同年和跨年场景。

### 变更

- 变更毛利计算与退款匹配服务：当配置了 sheet 标题关键字后，运行时会优先选择匹配关键字的最新月份工作表，而不是只依赖固定 `sheet_id`。
- 变更 `tb setup` 与 `tb check`：配置向导和启动自检现已支持并展示自动月表选择逻辑。
- 变更 CLI 控制台视觉风格：首页新增 LOGO、状态徽章和更统一的配色。
- 变更 CLI 次级页面视觉风格：执行结果、失败详情、守护结果、后台日志、配置未完成提示，统一为一致的模态面板样式。

### 修复

- 修复跨年月份选择歧义：当标题中包含年份时，优先按“年 + 月”判断最新工作表，而不是只比较月份数字。
- 修复本地 CLI 体验不一致问题，使首页与二级页面在视觉上保持统一。
- 修复 `tb setup` 中官网链接打开交互不明确的问题：现已改为数字菜单，支持打开全部、打开单个链接或暂时跳过。
- 修复配置向导中凭证输入不可直接粘贴的问题：`Client ID` / `Open ID` / `Access Token` 等输入现改为可见输入，支持直接粘贴。
- 修复配置向导中无法暂时跳过某一项的问题：现可输入 `/skip` 暂时跳过，后续再补充配置。
- 修复 Windows 双击 `启动.bat` 可能直接闪退的问题：补上缺失的 `:menu` 标签，并修正 Python / EXE 启动命令拼接方式。
- 修复 Windows 打包环境下 setup 输入不稳定的问题：现将配置向导输入统一切回原生 `input()`，避免链接打开后无法继续输入或无法粘贴。

## [0.4.2] - 2026-03-19

### Added

- Added npm global-install bootstrap via `postinstall`, so `npm install -g tb-order-sync` can prepare the CLI runtime in one step on macOS.
- Added dedicated runtime path handling for npm installs, using a writable user app-home instead of the npm package directory.
- Added tests for `TB_HOME` path resolution and relative `state_dir` normalization.
- Added `pytest.ini` to keep local release artifacts from polluting test discovery.

### Changed

- Changed the Node launcher to store `.env`, `state`, and `.venv` under the app home during npm-based CLI usage.
- Changed documentation to describe the one-command npm install flow and the macOS runtime directory.

## [0.4.1] - 2026-03-19

### Added

- Added standard GitHub Release packaging workflow for macOS and Windows.
- Added complete distribution package output including startup scripts, `.env.example`, `快速开始.txt`, and `公司同事使用说明.md`.

### Changed

- Changed release packaging to produce platform-specific archives:
  - `tb-order-sync-macos-x64-<version>.zip`
  - `tb-order-sync-windows-x64-<version>.zip`

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
