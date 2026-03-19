#!/usr/bin/env node

const path = require("path");
const { spawn } = require("child_process");
const {
  PACKAGE_ROOT,
  exists,
  getBundledExecutable,
  ensurePythonRuntime,
  runtimeEnv,
} = require("./runtime");

const args = process.argv.slice(2);

function launch(command, commandArgs) {
  const child = spawn(command, commandArgs, {
    cwd: PACKAGE_ROOT,
    stdio: "inherit",
    env: runtimeEnv(),
  });

  child.on("error", (error) => {
    console.error(`tb: 启动失败: ${error.message}`);
    process.exit(1);
  });

  child.on("exit", (code) => {
    process.exit(code ?? 0);
  });
}

const mainEntry = path.join(PACKAGE_ROOT, "main.py");
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
