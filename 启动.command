#!/bin/bash
# macOS 一键启动脚本 — 双击即可运行
# .command 文件在 macOS 上双击会自动在 Terminal 中打开

cd "$(dirname "$0")"

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║     多表格同步与退款标记服务         ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

# ── 优先级1：已有打包好的可执行文件 ──────────────────
if [ -x "./sync_service" ]; then
    CMD="./sync_service"
elif [ -x "./dist/sync_service/sync_service" ]; then
    CMD="./dist/sync_service/sync_service"

# ── 优先级2：已有虚拟环境 ────────────────────────────
elif [ -f ".venv/bin/python" ]; then
    CMD=".venv/bin/python main.py"

# ── 优先级3：需要初始化 ─────────────────────────────
else
    echo "  [*] 首次运行，正在初始化环境..."
    echo ""

    # 查找可用的 Python 3.11+
    PYTHON=""
    for p in python3.14 python3.13 python3.12 python3.11 python3 python; do
        if command -v "$p" &>/dev/null; then
            ver=$("$p" -c "import sys; print(sys.version_info[:2] >= (3,11))" 2>/dev/null)
            if [ "$ver" = "True" ]; then
                PYTHON="$p"
                break
            fi
        fi
    done

    # 没有 Python：尝试自动安装
    if [ -z "$PYTHON" ]; then
        echo "  [!] 未检测到 Python 3.11+"
        echo ""

        # macOS: 尝试用 Homebrew 安装
        if [ "$(uname)" = "Darwin" ]; then
            if command -v brew &>/dev/null; then
                echo "  [*] 检测到 Homebrew，正在自动安装 Python 3.12..."
                echo ""
                brew install python@3.12
                PYTHON="$(brew --prefix python@3.12)/bin/python3.12"
            else
                echo "  [*] 正在安装 Homebrew（macOS 包管理器）..."
                echo ""
                /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

                # Apple Silicon vs Intel
                if [ -f "/opt/homebrew/bin/brew" ]; then
                    eval "$(/opt/homebrew/bin/brew shellenv)"
                elif [ -f "/usr/local/bin/brew" ]; then
                    eval "$(/usr/local/bin/brew shellenv)"
                fi

                if command -v brew &>/dev/null; then
                    echo ""
                    echo "  [*] Homebrew 安装完成，正在安装 Python..."
                    brew install python@3.12
                    PYTHON="$(brew --prefix python@3.12)/bin/python3.12"
                fi
            fi

        # Linux: 尝试用系统包管理器
        elif [ -f /etc/os-release ]; then
            if command -v apt-get &>/dev/null; then
                echo "  [*] 正在通过 apt 安装 Python 3.12..."
                sudo apt-get update -qq && sudo apt-get install -y -qq python3.12 python3.12-venv python3-pip
                PYTHON="python3.12"
            elif command -v dnf &>/dev/null; then
                echo "  [*] 正在通过 dnf 安装 Python 3.12..."
                sudo dnf install -y python3.12
                PYTHON="python3.12"
            fi
        fi

        # 最终检查
        if [ -z "$PYTHON" ] || ! command -v "$PYTHON" &>/dev/null; then
            echo ""
            echo "  [!] Python 自动安装失败，请手动安装:"
            echo "      macOS:  brew install python@3.12"
            echo "      Ubuntu: sudo apt install python3.12 python3.12-venv"
            echo "      或访问: https://www.python.org/downloads/"
            echo ""
            read -p "  按回车退出..." _
            exit 1
        fi
    fi

    echo "  [1/3] 创建虚拟环境 (使用 $PYTHON)..."
    "$PYTHON" -m venv .venv || {
        echo "  [!] 创建失败"
        read -p "  按回车退出..." _
        exit 1
    }

    echo "  [2/3] 安装依赖..."
    .venv/bin/pip install -q -r requirements.txt || {
        echo "  [!] 安装失败"
        read -p "  按回车退出..." _
        exit 1
    }

    echo "  [3/3] 环境初始化完成!"
    echo ""

    CMD=".venv/bin/python main.py"
fi

# ── 启动 Rich 控制台 / 执行指定命令 ──────────────────
if [ "$#" -gt 0 ]; then
    $CMD "$@"
else
    $CMD
    echo ""
    read -p "  按回车关闭窗口..." _
fi
