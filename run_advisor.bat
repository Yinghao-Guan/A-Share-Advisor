@echo off
:: 设置编码为 UTF-8
chcp 65001 >nul

:: 进入当前脚本所在目录
cd /d "%~dp0"

echo ========================================================
echo 🚀 正在启动 AI A股 投资顾问 (A-Share Advisor)...
echo ========================================================
echo.

:: --- 关键步骤：检查并激活虚拟环境 ---
:: PyCharm 默认通常是 "venv" 或 ".venv"
if exist "venv\Scripts\activate.bat" (
    echo [环境] 检测到 venv 目录，正在激活...
    call venv\Scripts\activate.bat
) else if exist ".venv\Scripts\activate.bat" (
    echo [环境] 检测到 .venv 目录，正在激活...
    call .venv\Scripts\activate.bat
) else (
    echo [警告] 未找到常见的虚拟环境目录 (venv 或 .venv)。
    echo        尝试使用系统全局 Python 运行...
    echo.
)

:: 再次检查 .env 文件
if not exist .env (
    echo [错误] 找不到 .env 文件！程序可能无法运行。
    echo        请确保 .env 文件在当前目录下。
    pause
    exit
)

:: 启动 Streamlit
echo [启动] 正在唤醒浏览器...
streamlit run app.py

:: 如果 Streamlit 意外退出（通常不会执行到这里，除非出错）
pause