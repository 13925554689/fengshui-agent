@echo off
:: UTF-8 代码页: 本文件含中文路径(D:\命理AI模型), 否则 cmd 按 GBK 解析会乱码导致 if exist 失效
chcp 65001 >nul 2>&1
:: ============================================================
:: 传统风水智能体 — 一键启动 (双引擎)
::   1. 命理AI模型 (ReAct 推理引擎, 端口 8765)
::   2. suangua Web 系统 (后端 8888 + 前端 5173)
:: 双击此文件即可启动系统
:: ============================================================
:: 命理AI模型独立后台启动 — 失败不阻塞主系统
if exist "D:\命理AI模型\.venv\Scripts\python.exe" (
    start "MingLiAI-Engine" /min cmd /c "cd /d D:\命理AI模型 && .venv\Scripts\python.exe app.py --serve"
)
cd /d "%~dp0suangua"
call start.bat
