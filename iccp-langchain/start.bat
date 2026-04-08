@echo off
echo ========================================
echo 启动 ICCP-LangChain 服务
echo ========================================
echo.

echo 重要提示: 请确保已在当前终端激活 conda 环境!
echo 如果尚未激活，请先运行: conda activate opc
echo.
echo 按任意键继续启动服务...
pause >nul

echo.
echo [1/2] 检查环境配置...
if not exist .env (
    echo 警告: .env 文件不存在
    echo 正在从 .env.example 复制...
    copy .env.example .env
    echo.
    echo 请编辑 .env 文件，填入你的 API Keys
    echo 然后重新运行此脚本
    pause
    exit /b 1
)

echo [2/2] 启动 FastAPI 服务...
echo.
echo 服务将在以下地址运行:
echo   - API 文档: http://localhost:8000/docs
echo   - ReDoc: http://localhost:8000/redoc
echo   - 健康检查: http://localhost:8000/health
echo.
echo 按 Ctrl+C 停止服务
echo.

python -m app.main

pause
