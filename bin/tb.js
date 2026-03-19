#!/usr/bin/env node

const fs = require("fs");
const path = require("path");
const { spawn, spawnSync } = require("child_process");

const root = path.resolve(__dirname, "..");
const args = process.argv.slice(2);

function exists(target) {
  try {
    return fs.existsSync(target);
  } catch {
    return false;
  }
}

function runChecked(command, commandArgs, options = {}) {
  const result = spawnSync(command, commandArgs, {
    cwd: root,
    stdio: "inherit",
    ...options,
  });

  if (result.error) {
    return { ok: false, error: result.error };
  }
  if (typeof result.status === "number" && result.status !== 0) {
    return { ok: false, code: result.status };
  }
  return { ok: true };
}

function findSystemPython() {
  const candidates = process.platform === "win32"
    ? [
        { command: "py", prefixArgs: ["-3"] },
        { command: "python", prefixArgs: [] },
      ]
    : [
        { command: "python3.14", prefixArgs: [] },
        { command: "python3.13", prefixArgs: [] },
        { command: "python3.12", prefixArgs: [] },
        { command: "python3.11", prefixArgs: [] },
        { command: "python3", prefixArgs: [] },
        { command: "python", prefixArgs: [] },
      ];

  for (const candidate of candidates) {
    const probe = runChecked(candidate.command, [...candidate.prefixArgs, "--version"], {
      stdio: "ignore",
    });
    if (probe.ok) {
      return candidate;
    }
  }
  return null;
}

function getVenvPython() {
  if (process.platform === "win32") {
    return path.join(root, ".venv", "Scripts", "python.exe");
  }
  return path.join(root, ".venv", "bin", "python");
}

function getBundledExecutable() {
  const candidates = process.platform === "win32"
    ? [
        path.join(root, "sync_service.exe"),
        path.join(root, "dist", "sync_service", "sync_service.exe"),
      ]
    : [
        path.join(root, "sync_service"),
        path.join(root, "dist", "sync_service", "sync_service"),
      ];

  return candidates.find(exists) || null;
}

function ensurePythonRuntime() {
  const venvPython = getVenvPython();
  if (exists(venvPython)) {
    return { command: venvPython, prefixArgs: [] };
  }

  const systemPython = findSystemPython();
  if (!systemPython) {
    console.error("tb: 未找到可用的 Python 3.11+，也没有现成的打包可执行文件。");
    console.error("tb: 请先安装 Python，或使用 build.py 构建可执行文件。");
    process.exit(1);
  }

  console.log("tb: 正在初始化 Python 虚拟环境...");
  let result = runChecked(systemPython.command, [...systemPython.prefixArgs, "-m", "venv", ".venv"]);
  if (!result.ok) {
    console.error("tb: 创建虚拟环境失败。");
    process.exit(1);
  }

  const freshVenvPython = getVenvPython();
  console.log("tb: 正在安装 Python 依赖...");
  result = runChecked(freshVenvPython, ["-m", "pip", "install", "-q", "-r", "requirements.txt"]);
  if (!result.ok) {
    console.error("tb: 安装依赖失败。");
    process.exit(1);
  }

  return { command: freshVenvPython, prefixArgs: [] };
}

function launch(command, commandArgs) {
  const child = spawn(command, commandArgs, {
    cwd: root,
    stdio: "inherit",
    env: process.env,
  });

  child.on("error", (error) => {
    console.error(`tb: 启动失败: ${error.message}`);
    process.exit(1);
  });

  child.on("exit", (code) => {
    process.exit(code ?? 0);
  });
}

const mainEntry = path.join(root, "main.py");
const preferBundled = process.env.TB_PREFER_BUNDLED === "1" || !exists(mainEntry);
const bundledExecutable = getBundledExecutable();

if (preferBundled && bundledExecutable) {
  launch(bundledExecutable, args);
} else if (exists(mainEntry)) {
  const python = ensurePythonRuntime();
  launch(python.command, [...python.prefixArgs, mainEntry, ...args]);
} else if (bundledExecutable) {
  launch(bundledExecutable, args);
} else {
  console.error("tb: 未找到 main.py，也未找到可执行分发产物。");
  process.exit(1);
}
