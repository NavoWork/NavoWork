@echo off
rem NavoWork launcher for Windows CMD / double-click.
rem Delegates to start.ps1, which locates Python 3.12+ and runs dev.py.
setlocal EnableExtensions
chcp 65001 >nul 2>&1
cd /d "%~dp0"

where powershell.exe >nul 2>nul
if errorlevel 1 (
    echo [NavoWork] 未找到 Windows PowerShell，无法启动。
    echo            请改用：python dev.py
    if not defined NAVOWORK_NO_PAUSE pause
    exit /b 1
)

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" %*
set "NAVOWORK_EXIT=%ERRORLEVEL%"

if not "%NAVOWORK_EXIT%"=="0" (
    echo.
    echo [NavoWork] 启动失败（退出码 %NAVOWORK_EXIT%）。
    if not defined NAVOWORK_NO_PAUSE pause
)

exit /b %NAVOWORK_EXIT%
