# TB Order Sync

[![npm version](https://img.shields.io/npm/v/tb-order-sync)](https://www.npmjs.com/package/tb-order-sync)
[![GitHub Repo](https://img.shields.io/badge/GitHub-SOULRAi%2Ftb--order--sync-181717?logo=github)](https://github.com/SOULRAi/tb-order-sync)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/SOULRAi/tb-order-sync/blob/main/LICENSE)

**多表格同步与退款标记服务**  
面向订单运营场景的轻量自动化服务，负责同步云表格、计算毛利、标记退款状态，并支持后台守护运行。

> 支持 `tb` 短命令、Rich 控制台、守护进程、Windows / macOS 一键启动，以及后续接入飞书 C 表的扩展路径。

**快速导航**

- [🚀 快速开始](#quick-start)
- [✨ 核心能力](#capabilities)
- [🔐 API 获取指引](#api-guide)
- [🧠 业务规则](#business-rules)
- [🧩 架构设计](#architecture)
- [🛡️ 守护进程](#daemon)
- [⚙️ 配置说明](#configuration)
- [🧪 测试](#testing)

<a id="capabilities"></a>
## ✨ 核心能力

| 能力 | 说明 | 状态 |
|------|------|------|
| 💰 毛利自动计算 | 读取 A 表字段，按固定业务公式回写毛利列 | ✅ 已实现 |
| 🔁 退款自动匹配 | B 表退款单号匹配 A 表订单，写入退款状态列 | ✅ 已实现 |
| 🧾 数据异常标记 | 非法数字直接写入 `数据异常`，并记录日志 | ✅ 已实现 |
| ⚡ 增量同步 | 基于行指纹和退款集合 hash，仅处理变化数据 | ✅ 已实现 |
| 🧨 全量重建 | 支持忽略缓存，对全表重新扫描和回写 | ✅ 已实现 |
| 🖥️ Rich 控制台 | 无参启动即进入交互式控制台首页 | ✅ 已实现 |
| 🛡️ 守护进程 | 支持后台启动、停止、状态检查、日志查看 | ✅ 已实现 |
| 📦 一键分发 | 支持双击脚本、npm launcher、PyInstaller 打包 | ✅ 已实现 |
| 🐦 飞书预留接口 | C 表同步抽象层和 connector skeleton 已预留 | 🔲 骨架已预留 |

<a id="quick-start"></a>
## 🚀 快速开始

### 推荐命令

```bash
npm install -g tb-order-sync

tb
tb setup
tb all --dry-run
tb all
tb daemon start
tb daemon status
```

### 启动方式

| 方式 | 适用场景 | 入口 |
|------|----------|------|
| `tb` 命令 | 开发、运维、长期使用 | `tb` / `tb setup` / `tb all` |
| 双击启动 | 非技术用户 | `启动.bat` / `启动.command` |
| Python 兼容入口 | 调试或源码环境 | `python main.py` |
| 打包分发 | 免安装交付 | `dist/sync_service/` |

### 常用命令速查

```bash
# 控制台
tb
tb menu

# 配置
tb setup
tb check

# 执行
tb all
tb gp
tb rm
tb all --dry-run
tb all --mode full

# 调度 / 守护
tb start
tb daemon start
tb daemon status
tb daemon logs --lines 80
tb daemon stop
```

### 双击启动

| 平台 | 文件 |
|------|------|
| Windows | `启动.bat` |
| macOS | `启动.command` |

首次运行会自动补齐 Python 运行环境并进入 Rich 控制台。

<a id="api-guide"></a>
## 🔐 API 获取指引

### 腾讯文档 API

- 开发文档入口: [腾讯文档开放平台开发文档](https://docs.qq.com/open/document/app/)
- 开发者平台: [腾讯文档开放生态](https://docs.qq.com/open/developers/)
- 建议流程:
  1. 先进入开发者平台创建应用
  2. 在应用详情页获取 `Client ID` 和 `Client Secret`
  3. 按官方 OAuth2 流程获取 `Access Token`
  4. 再回到本项目执行 `tb setup`
- 当前说明:
  - 本项目 MVP 目前依赖你手工提供有效 `Access Token`
  - `Open ID` 先作为可选项保留
  - 腾讯文档实际 endpoint / request schema 代码里仍有 `TODO / NEED_VERIFY`

### 飞书 API

- 开发者平台: [Feishu Open Platform](https://open.feishu.cn/app)
- Token 官方文档: [获取 tenant_access_token](https://open.feishu.cn/document/server-docs/authentication-management/access-token/tenant_access_token_internal)
- 新手教程: [如何解析和使用动态 Token](https://www.feishu.cn/content/000214591773)
- 建议流程:
  1. 在飞书开放平台创建自建应用
  2. 在应用凭证页获取 `App ID` 和 `App Secret`
  3. 按官方文档获取 `tenant_access_token`
  4. 后续接 C 表时再补齐 `File Token` / `Sheet ID`
- 当前说明:
  - 本项目里的飞书 connector 目前还是 skeleton
  - 现阶段向导里先采集配置，为后续 C 表接入做准备

<a id="business-rules"></a>
## 🧠 业务规则

### A 表结构（订单表）

| 列 | 字段 | 说明 |
|----|------|------|
| A | 产品图 | — |
| B | 订单地址 | — |
| C | 产品价格 | 参与毛利计算 |
| D | 包装价格 | 参与毛利计算 |
| E | 运费 | 参与毛利计算 |
| F | 客户报价 | 参与毛利计算 |
| G | 毛利 | **自动计算写入** |
| H | 单号 | 退款匹配关键字段 |
| I | 退款状态 | **自动标记写入** |

### B 表结构（退款表）

| 列 | 字段 |
|----|------|
| A | 单号（用于匹配 A 表 H 列） |
| B-L | 退货单号、店铺、原因、金额等 |

### 毛利计算

```
毛利 = 客户报价(F) - 运费(E) - 包装价格(D) - 产品价格(C)
```

- 字段为合法数字（int / float / 数字字符串）→ 正常计算
- 任一字段非法（空值、文本、None）→ 写入 `数据异常`，日志记录详情

### 退款匹配

- B 表 A 列单号存在于 A 表 H 列 → I 列写入 `进入退款流程`
- 不存在 → 清空 I 列（同步取消）
- 可选：`ENABLE_STYLE_UPDATE=true` 时额外设置行背景色标红

## 🗂️ 项目结构

```
tb-order-sync/
├── main.py                        # 入口
├── build.py                       # PyInstaller 构建脚本
├── sync_service.spec              # PyInstaller spec 文件
├── package.json                   # npm bin 包定义（tb）
├── CHANGELOG.md                   # 更新日志
├── requirements.txt
├── .env.example                   # 环境变量模板
├── tb                             # 本地 Unix launcher
├── tb.cmd                         # 本地 Windows launcher
├── 启动.bat                       # Windows 一键启动
├── 启动.command                   # macOS 一键启动
├── bin/
│   └── tb.js                      # npm / node 统一入口
│
├── config/
│   ├── settings.py                # Pydantic Settings 全局配置
│   └── mappings.py                # 列字母 ↔ 索引映射
│
├── connectors/
│   ├── base.py                    # BaseSheetConnector 抽象接口
│   ├── tencent_docs.py            # 腾讯文档连接器
│   └── feishu_sheets.py           # 飞书连接器（骨架）
│
├── models/
│   ├── records.py                 # OrderRecord / RefundRecord
│   ├── task_models.py             # SyncTaskConfig / TaskResult
│   └── state_models.py            # SyncState / RowFingerprint
│
├── services/
│   ├── gross_profit_service.py    # 毛利计算服务
│   ├── refund_match_service.py    # 退款匹配服务
│   ├── c_to_a_sync_service.py     # C→A 同步（骨架）
│   ├── scheduler_service.py       # APScheduler 定时调度
│   ├── daemon_service.py          # 跨平台守护进程管理
│   └── state_service.py           # 本地 JSON 状态持久化
│
├── utils/
│   ├── logger.py                  # 日志配置
│   ├── parser.py                  # 数值解析 / 单号标准化
│   ├── diff.py                    # 行指纹 / 集合 hash
│   └── retry.py                   # tenacity 重试装饰器
│
├── cli/
│   ├── commands.py                # CLI 命令路由
│   ├── dashboard.py               # Rich 控制台首页
│   └── setup.py                   # 交互式配置向导
│
├── state/                         # 增量状态文件目录
│   └── sync_state.json            # 自动生成
│
└── tests/
    ├── test_parser.py             # 20 tests
    ├── test_gross_profit_service.py  # 9 tests
    └── test_refund_match_service.py  # 6 tests
```

<a id="architecture"></a>
## 🧩 架构设计

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  CLI / 启动  │────▶│   Services  │────▶│ Connectors  │
│  commands.py │     │ (业务逻辑)   │     │ (平台隔离)   │
└─────────────┘     └──────┬──────┘     └──────┬──────┘
                           │                    │
                    ┌──────▼──────┐     ┌──────▼──────┐
                    │   Models    │     │ Tencent Docs │
                    │ (数据结构)   │     │    Feishu    │
                    └──────┬──────┘     │   (更多...)   │
                           │            └─────────────┘
                    ┌──────▼──────┐
                    │ State / Utils│
                    │ (状态/工具)   │
                    └─────────────┘
```

**核心原则：**
- **Connector 抽象** — 腾讯文档/飞书通过统一接口 `BaseSheetConnector` 隔离，新增平台只需实现接口
- **业务与平台分离** — Services 不依赖任何平台 API 细节
- **配置化** — 列映射、业务文案、运行模式全部可通过 `.env` 配置
- **可扩展** — 新增 D 表、E 表时无需重构主程序

## 🔄 增量策略

| 目标 | 策略 | 存储 |
|------|------|------|
| A 表毛利 | 对每行关键字段 (C/D/E/F/H) 生成 MD5 指纹，仅处理指纹变化行 | `state/sync_state.json` |
| B 表退款 | 对退款单号集合生成整体 hash，集合不变则跳过 | `state/sync_state.json` |

<a id="daemon"></a>
## 🛡️ 守护进程

- `tb daemon start`
  - 在后台启动定时调度进程
  - 自动写入 `state/scheduler.pid` 和 `state/scheduler.meta.json`
- `tb daemon status`
  - 查看是否运行中、PID 和日志文件位置
- `tb daemon logs --lines 40`
  - 查看后台日志尾部
- `tb daemon stop`
  - 停止后台调度
- `tb daemon restart`
  - 重启后台调度

后台控制台输出默认写入：
- `state/scheduler.console.log`

<a id="configuration"></a>
## ⚙️ 配置说明

运行 `tb setup` 可交互式完成所有配置。也可手动编辑 `.env`：

```ini
# 腾讯文档凭证
TENCENT_CLIENT_ID=your_client_id
TENCENT_CLIENT_SECRET=your_client_secret
TENCENT_ACCESS_TOKEN=your_access_token
TENCENT_A_FILE_ID=a_table_file_id
TENCENT_A_SHEET_ID=a_table_sheet_id
TENCENT_B_FILE_ID=b_table_file_id
TENCENT_B_SHEET_ID=b_table_sheet_id

# 运行模式
GROSS_PROFIT_MODE=incremental    # incremental | full
REFUND_MATCH_MODE=incremental    # incremental | full
TASK_INTERVAL_MINUTES=10         # 定时调度间隔
DRY_RUN=false                    # true = 模拟执行不写入
ENABLE_STYLE_UPDATE=false        # true = 退款行标红

# 列映射（可自定义）
A_COL_PRODUCT_PRICE=C
A_COL_PACKAGING_PRICE=D
A_COL_FREIGHT=E
A_COL_CUSTOMER_QUOTE=F
A_COL_GROSS_PROFIT=G
A_COL_ORDER_NO=H
A_COL_REFUND_STATUS=I
B_COL_ORDER_NO=A
```

完整配置项见 [.env.example](.env.example)。

<a id="testing"></a>
## 🧪 测试

```bash
# 运行全部测试（35 tests）
pytest tests/ -v

# 单独运行
pytest tests/test_parser.py -v
pytest tests/test_gross_profit_service.py -v
pytest tests/test_refund_match_service.py -v
```

## 🧱 技术栈

| 组件 | 用途 |
|------|------|
| Python 3.11+ | 运行环境 |
| pydantic / pydantic-settings | 数据模型 / 配置管理 |
| httpx | HTTP 客户端 |
| tenacity | 失败重试 |
| APScheduler | 定时任务调度 |
| rich | CLI 交互界面 |
| python-dotenv | 环境变量加载 |
| PyInstaller | 打包为可执行文件 |
| pytest | 单元测试 |

## 📦 部署方式对比

| 方式 | 需要 Python | 适用场景 |
|------|------------|---------|
| 双击启动脚本（源码） | 自动下载 | 开发/内部使用 |
| 打包 exe 分发 | 不需要 | 给非技术用户 |
| 命令行直接运行 | 需要 | 开发者 |

## 🗺️ Roadmap

- [x] 毛利自动计算
- [x] 退款自动匹配
- [x] 增量 / 全量模式
- [x] 交互式配置向导
- [x] 一键启动脚本（Windows + macOS）
- [x] PyInstaller 打包
- [x] 定时调度 + dry-run
- [ ] 飞书 C 表 → A 表同步
- [ ] 腾讯文档 OAuth2 token 自动刷新
- [ ] 腾讯文档行样式 API 验证

## ⚠️ 已知待确认项

- 腾讯文档 Open API 的实际 endpoint 和 request/response 格式（代码中标注 `TODO / NEED_VERIFY`）
- 腾讯文档是否支持通过 API 设置单元格样式
- OAuth2 token 自动刷新流程

## 📄 License

MIT
