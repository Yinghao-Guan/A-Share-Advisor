@echo off
chcp 65001 >nul
echo ==========================================
echo 📦 正在初始化 Python 环境...
echo ==========================================

:: 1. 创建虚拟环境 (如果不存在)
if not exist venv (
    echo [1/3] 创建虚拟环境 (venv)...
    python -m venv venv
) else (
    echo [1/3] 虚拟环境已存在，跳过创建。
)

:: 2. 激活环境并安装依赖
echo [2/3] 正在激活环境并安装依赖 (这可能需要几分钟)...
call venv\Scripts\activate
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

echo.
echo [3/3] ✅ 环境配置完成！
echo.
echo 现在你可以直接双击 "run_advisor.bat" 来启动程序了。
pause