@echo off
chcp 65001 >nul 2>&1
title 多表格同步服务
cd /d "%~dp0"

echo.
echo  ╔══════════════════════════════════════╗
echo  ║     多表格同步与退款标记服务         ║
echo  ╚══════════════════════════════════════╝
echo.

:: ── 优先级1：已有打包好的 exe ────────────────────────
if exist "sync_service.exe" (
    set "CMD=sync_service.exe"
    goto :menu
)

:: ── 优先级2：已有虚拟环境 ───────────────────────────
if exist ".venv\Scripts\python.exe" (
    set "CMD=.venv\Scripts\python main.py"
    goto :menu
)

:: ── 优先级3：系统有 Python ──────────────────────────
echo  [*] 首次运行，正在初始化环境...
echo.

where python >nul 2>&1
if not errorlevel 1 (
    echo  [*] 检测到系统 Python，创建虚拟环境...
    goto :venv_setup
)

:: ── 优先级4：使用嵌入式 Python（自动下载）───────────
if exist "python_embed\python.exe" (
    echo  [*] 使用本地嵌入式 Python...
    goto :venv_from_embed
)

echo  [*] 未检测到 Python，正在自动下载嵌入式 Python...
echo  （约 15MB，仅需下载一次）
echo.

:: 创建下载目录
if not exist "python_embed" mkdir python_embed

:: 使用 PowerShell 下载 Python 3.12 嵌入式版本
:: Windows 内置 PowerShell，无需额外依赖
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$url = 'https://www.python.org/ftp/python/3.12.8/python-3.12.8-embed-amd64.zip'; " ^
  "$zip = 'python_embed\python_embed.zip'; " ^
  "Write-Host '  下载中...' ; " ^
  "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; " ^
  "Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing; " ^
  "Write-Host '  解压中...' ; " ^
  "Expand-Archive -Path $zip -DestinationPath 'python_embed' -Force; " ^
  "Remove-Item $zip -Force; " ^
  "Write-Host '  完成!' "

if not exist "python_embed\python.exe" (
    echo.
    echo  [!] Python 下载失败，请检查网络连接
    echo      或手动下载 Python 3.12+ 安装: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

:: 启用嵌入式 Python 的 pip 支持
:: 需要修改 python312._pth 文件，取消注释 import site
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$pth = Get-ChildItem 'python_embed\python*._pth' | Select-Object -First 1; " ^
  "if ($pth) { " ^
  "  $content = Get-Content $pth.FullName; " ^
  "  $content = $content -replace '^#import site', 'import site'; " ^
  "  Set-Content $pth.FullName $content; " ^
  "} "

:: 安装 pip
echo.
echo  [*] 安装 pip...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile 'python_embed\get-pip.py' -UseBasicParsing"
python_embed\python.exe python_embed\get-pip.py --no-warn-script-location -q 2>nul
del python_embed\get-pip.py 2>nul

:venv_from_embed
echo  [*] 使用嵌入式 Python 安装依赖...
echo.
python_embed\python.exe -m pip install -q -r requirements.txt --target=".deps" 2>nul
set "PYTHONPATH=%~dp0.deps;%~dp0"
set "CMD=python_embed\python.exe main.py"
goto :menu

:venv_setup
echo  [1/3] 创建虚拟环境...
python -m venv .venv
if errorlevel 1 (
    echo  [!] 虚拟环境创建失败
    pause
    exit /b 1
)

echo  [2/3] 安装依赖...
.venv\Scripts\pip install -q -r requirements.txt
if errorlevel 1 (
    echo  [!] 依赖安装失败
    pause
    exit /b 1
)

echo  [3/3] 环境初始化完成!
echo.
set "CMD=.venv\Scripts\python main.py"

:: ── 启动 Rich 控制台 / 执行指定命令 ────────────────
if "%~1"=="" (
    %CMD%
    echo.
    pause
    exit /b 0
)

%CMD% %*
exit /b %errorlevel%
