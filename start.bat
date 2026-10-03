@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
echo ============================================
echo   电商经营 AI 问答助手 - 启动器
echo   启动后会自动打开浏览器
echo   关闭本窗口即停止服务
echo ============================================
echo.
E:\python\python.exe app.py
pause
