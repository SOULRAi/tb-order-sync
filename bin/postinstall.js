#!/usr/bin/env node

const { ensurePythonRuntime, getAppHome } = require("./runtime");

const isGlobalInstall = process.env.npm_config_global === "true";
const shouldSkip = process.env.TB_SKIP_POSTINSTALL_BOOTSTRAP === "1";

if (!isGlobalInstall || shouldSkip) {
  process.exit(0);
}

console.log("tb-order-sync: 正在准备 CLI 运行环境...");
const result = ensurePythonRuntime({ quiet: false, exitOnError: false });

if (!result.ok) {
  console.warn("tb-order-sync: Python 运行环境未自动安装完成。");
  console.warn("tb-order-sync: 安装仍已完成，后续执行 tb 时会再次尝试初始化。");
  process.exit(0);
}

console.log(`tb-order-sync: CLI 已部署到 ${getAppHome()}`);
