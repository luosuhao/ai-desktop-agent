@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0desktop\dist\win-unpacked\resources\backend"

echo ============================================================
echo    启动第二个隔离实例（同机多用户演示）
echo    端口 18329 | 数据目录 %~dp0data2\ | 表格识别共享 18000
echo ============================================================
echo.

set "API_PORT=18329"
set "DATA_DIR=%~dp0data2"
set "TABLENET_PORT=18000"

start "" /b dist\backend.exe
echo 第二个实例已在后台启动。
echo 浏览器打开: http://127.0.0.1:18329/
echo.
echo 说明：第一个实例用 AI桌面端系统.exe（18327），本实例用 18329，
echo       两者数据完全隔离（本实例数据在 data2\ 下），可同时使用。
echo       如需更多实例，复制本脚本并修改端口与 DATA_DIR 后运行。
echo.
pause
