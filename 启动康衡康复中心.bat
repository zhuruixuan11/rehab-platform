@echo off
chcp 65001 >nul
title 康衡康复中心 - 全周期康复管理平台
cd /d "%~dp0"

netstat -ano | findstr ":8003 " | findstr "LISTENING" >nul
if %errorlevel%==0 (
    echo [提示] 服务已在运行，直接打开浏览器...
    start http://127.0.0.1:8003
    exit /b 0
)

echo [启动] 正在启动服务，首次加载约需 20 秒...
start /b "" cmd /c "timeout /t 22 >nul & start http://127.0.0.1:8003"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8003
pause
