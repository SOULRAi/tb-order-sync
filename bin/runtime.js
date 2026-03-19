const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawnSync } = require("child_process");

const PACKAGE_ROOT = path.resolve(__dirname, "..");
const MIN_PYTHON = { major: 3, minor: 10 };

function exists(target) {
  try {
    return fs.existsSync(target);
  } catch {
    return false;
  }
}

function ensureDir(target) {
  fs.mkdirSync(target, { recursive: true });
}

function getDefaultAppHome() {
  const explicit = (process.env.TB_HOME || "").trim();
  if (explicit) {
    return path.resolve(explicit);
  }

  if (process.platform === "darwin") {
    return path.join(os.homedir(), "Library", "Application Support", "tb-order-sync");
  }
  if (process.platform === "win32") {
    return path.join(
      process.env.APPDATA || path.join(os.homedir(), "AppData", "Roaming"),
      "tb-order-sync",
    );
  }
  return path.join(os.homedir(), ".tb-order-sync");
}

function getAppHome() {
  return getDefaultAppHome();
}

function runtimeEnv(extra = {}) {
  return {
    ...process.env,
    TB_HOME: getAppHome(),
    ...extra,
  };
}

function runChecked(command, commandArgs, options = {}) {
  const result = spawnSync(command, commandArgs, {
    cwd: PACKAGE_ROOT,
    stdio: "inherit",
    env: runtimeEnv(),
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

function probePythonVersion(command, prefixArgs) {
  const probe = spawnSync(
    command,
    [
      ...prefixArgs,
      "-c",
      "import sys; print('.'.join(map(str, sys.version_info[:3])))",
    ],
    {
      cwd: PACKAGE_ROOT,
      stdio: ["ignore", "pipe", "ignore"],
      encoding: "utf-8",
      env: runtimeEnv(),
    },
  );

  if (probe.error || probe.status !== 0) {
    return null;
  }

  const raw = (probe.stdout || "").trim();
  const match = raw.match(/^(\d+)\.(\d+)\.(\d+)$/);
  if (!match) {
    return null;
  }

  const version = {
    major: Number(match[1]),
    minor: Number(match[2]),
    patch: Number(match[3]),
    raw,
  };

  const isSupported = (
    version.major > MIN_PYTHON.major ||
    (version.major === MIN_PYTHON.major && version.minor >= MIN_PYTHON.minor)
  );

  return {
    ...version,
    isSupported,
  };
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
        { command: "python3.10", prefixArgs: [] },
        { command: "python3", prefixArgs: [] },
        { command: "python", prefixArgs: [] },
      ];

  for (const candidate of candidates) {
    const version = probePythonVersion(candidate.command, candidate.prefixArgs);
    if (version && version.isSupported) {
      return { ...candidate, version: version.raw };
    }
  }
  return null;
}

function getVenvDir() {
  return path.join(getAppHome(), ".venv");
}

function getVenvPython() {
  if (process.platform === "win32") {
    return path.join(getVenvDir(), "Scripts", "python.exe");
  }
  return path.join(getVenvDir(), "bin", "python");
}

function getBundledExecutable() {
  const candidates = process.platform === "win32"
    ? [
        path.join(PACKAGE_ROOT, "sync_service.exe"),
        path.join(PACKAGE_ROOT, "dist", "sync_service", "sync_service.exe"),
      ]
    : [
        path.join(PACKAGE_ROOT, "sync_service"),
        path.join(PACKAGE_ROOT, "dist", "sync_service", "sync_service"),
      ];

  return candidates.find(exists) || null;
}

function ensurePythonRuntime(options = {}) {
  const { quiet = false, exitOnError = true } = options;
  const appHome = getAppHome();
  const venvPython = getVenvPython();
  ensureDir(appHome);

  const fail = (lines) => {
    const messages = Array.isArray(lines) ? lines : [lines];
    if (!quiet) {
      for (const line of messages) {
        console.error(line);
      }
    }
    if (exitOnError) {
      process.exit(1);
    }
    return { ok: false, messages };
  };

  if (exists(venvPython)) {
    return { ok: true, command: venvPython, prefixArgs: [] };
  }

  const systemPython = findSystemPython();
  if (!systemPython) {
    return fail([
      "tb: 未找到可用的 Python 3.10+，无法自动部署 CLI 运行环境。",
      "tb: 请先安装 Python 3.10+，然后重新执行 npm install -g tb-order-sync。",
    ]);
  }

  if (!quiet) {
    console.log(`tb: 使用 Python ${systemPython.version} 初始化运行环境...`);
  }

  let result = runChecked(
    systemPython.command,
    [...systemPython.prefixArgs, "-m", "venv", getVenvDir()],
  );
  if (!result.ok) {
    return fail("tb: 创建虚拟环境失败。");
  }

  const freshVenvPython = getVenvPython();
  if (!quiet) {
    console.log("tb: 正在安装 Python 依赖...");
  }
  result = runChecked(
    freshVenvPython,
    ["-m", "pip", "install", "-q", "-r", path.join(PACKAGE_ROOT, "requirements.txt")],
  );
  if (!result.ok) {
    return fail("tb: 安装依赖失败。");
  }

  return { ok: true, command: freshVenvPython, prefixArgs: [] };
}

module.exports = {
  PACKAGE_ROOT,
  exists,
  getAppHome,
  getBundledExecutable,
  getVenvPython,
  ensurePythonRuntime,
  runtimeEnv,
};
