@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================================
echo    AI桌面端系统 - 首次配置（每台电脑只跑一次）
echo ============================================================
echo.

set "MODEL_DIR=%~dp0Qwen2-VL-2B-TableNet-PubTabNet-smallx2-v1\Qwen2-VL-2B-TableNet-PubTabNet-smallx2-v1"
set "VENV_DIR=%~dp0tablenet-venv"

echo [1/3] 设置表格识别环境变量（写入当前用户环境，持久生效）...
setx TABLENET_MODEL_DIR "%MODEL_DIR%" >nul 2>&1
setx TABLENET_VENV_DIR "%VENV_DIR%" >nul 2>&1
echo        TABLENET_MODEL_DIR = %MODEL_DIR%
echo        TABLENET_VENV_DIR  = %VENV_DIR%

echo [2/3] 校验 tablenet-venv ...
"%VENV_DIR%\Scripts\python.exe" -c "import sys" >nul 2>&1
if not errorlevel 1 (
    echo        venv 可用
    goto :done
)

echo        venv 不可用，尝试自动修复（探测本机 Python 3.11 并改写 pyvenv.cfg）...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0修复venv.ps1" -VenvDir "%VENV_DIR%"
if errorlevel 1 (
    echo.
    echo    [!] 修复失败：请先安装 Python 3.11.9，然后重新运行本脚本。
    echo        或手动编辑 %VENV_DIR%\pyvenv.cfg 的 home / executable 指向本机 Python 3.11。
    echo        （仅表格识别受影响，文档/问答/Agent 等其他功能可正常使用）
) else (
    "%VENV_DIR%\Scripts\python.exe" -c "import sys" >nul 2>&1
    if not errorlevel 1 ( echo        venv 修复成功 ) else ( echo        venv 仍不可用，请手动检查 )
)

:done
echo.
echo [3/3] 完成。
echo        * 双击 desktop\dist\win-unpacked\AI桌面端系统.exe 启动本机实例。
echo        * 如需在同一台电脑上再开一个隔离实例（演示多人），运行 启动第二实例.bat。
echo.
pause
