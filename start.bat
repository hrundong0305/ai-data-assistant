@echo off
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
echo ============================================
echo   电商经营 AI 问答助手 - 启动器
echo   启动后会自动打开浏览器
echo   关闭本窗口即停止服务
echo ============================================
echo.
netstat -ano | findstr ":8000 " | findstr "LISTENING" >nul 2>&1
if errorlevel 1 goto notrun
echo 检测到服务已在运行，直接打开浏览器...
start "" http://127.0.0.1:8000
pause
exit /b
:notrun
echo 正在启动服务（约3秒后自动打开浏览器）...
echo 关闭本窗口即停止服务
E:\python\python.exe app.py
pause