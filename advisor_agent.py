import google.generativeai as genai
import os
import json

from dotenv import load_dotenv

load_dotenv()  # 加载 .env 文件

# ==========================================
# 配置：LLM 设置
# ==========================================
# ⚠️ 请将此处替换为你的真实 API Key，或者设置环境变量 GEMINI_API_KEY
API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    # 为了演示，如果你不想设环境变量，可以直接在这里填字符串，但不要分享给别人
    API_KEY = "YOUR_GEMINI_API_KEY_HERE"

genai.configure(api_key=API_KEY)


# ==========================================
# 核心 Prompt 构建器
# ==========================================
def build_prompt(symbol: str, price: float, tech_summary: str, user_style: str, user_holdings: str = "None"):
    """
    构建包含 A 股市场规则、技术指标和用户仓位的完整 Prompt。
    """

    # 1. 市场背景注入 (Context Injection)
    market_rules = (
        "### MARKET CONTEXT: China A-Shares (Shanghai/Shenzhen) ###\n"
        "1. **T+1 Rule**: Shares bought today CANNOT be sold until tomorrow.\n"
        "2. **Price Limits**: Max daily movement is usually ±10% (±20% for STAR/ChiNext boards).\n"
        "3. **Long Only**: Retail traders usually cannot short sell. Profit only comes from price rising.\n"
        "4. **Formatting**: Use bolding for key numbers."
    )

    # 2. 用户画像定义 (Persona)
    persona = (
        "You are a seasoned A-Share Stock Analyst. Your goal is to protect the user's capital first, "
        "and then seek profit. You communicate clearly, concisely, and objectively."
    )

    # 3. 任务描述
    task = (
        "Analyze the provided technical indicators and user situation. "
        "Provide a structured trading plan."
    )

    # 4. 组合最终 Prompt
    full_prompt = f"""
{persona}

{market_rules}

--- USER INFO ---
* **Stock**: {symbol}
* **Strategy Style**: {user_style.upper()} (This determines how you interpret indicators)
* **Current Position**: {user_holdings}

--- MARKET DATA (Real-time) ---
{tech_summary}

--- YOUR TASK ---
Based on the data above, output a response in the following format:

## 1. Market Analysis
(Briefly interpret the Trend and Momentum. Is it bullish or bearish for the user's timeframe?)

## 2. Decision
(One word: **BUY**, **SELL**, **HOLD**, **ADD**, or **REDUCE**)

## 3. Rationale
* **For Logic**: Why this decision? Quote specific indicators (e.g., "RSI is 37, not oversold enough yet" or "MACD just crossed dead").
* **For Position**: If user holds stock, advise on cost management. If empty, advise on entry price.

## 4. Risk Control
* **Stop Loss**: Suggest a price level to exit if wrong.
* **Warning**: Mention any specific risks (e.g., "Downtrend is strong, catching a falling knife").
"""
    return full_prompt


# ==========================================
# LLM 调用函数
# ==========================================
def get_llm_advice(symbol, price, tech_summary, user_style, user_holdings):
    print(f"\n🤖 [Agent] 正在思考 {symbol} ({user_style}) 的策略...")

    try:
        # --- 修改处开始 ---
        # 你的列表中显示支持 'models/gemini-2.5-flash'
        # 在 SDK 中通常只需要传后面这部分名字
        model = genai.GenerativeModel('gemini-2.5-flash')
        # --- 修改处结束 ---

        prompt = build_prompt(symbol, price, tech_summary, user_style, user_holdings)

        # 生成回答
        response = model.generate_content(prompt)

        return response.text

    except Exception as e:
        return f"❌ LLM 调用失败: {e}\n(请检查 API KEY 是否正确或网络是否通畅)"

# ==========================================
# 整合测试 (Integration Test)
# ==========================================
if __name__ == "__main__":
    # 假设你已经有了 data_fetcher 和 tech_analysis
    try:
        from data_fetcher import get_ashare_data
        from tech_analysis import analyze_stock_data
    except ImportError:
        print("⚠️ 请确保 data_fetcher.py 和 tech_analysis.py 在同一目录")
        exit()

    # --- 模拟用户输入 ---
    stock_code = "600519"  # 茅台
    style = "short"  # 用户想做短线
    holdings = "Held 100 shares, Cost 1480.00"  # 用户被套了一点 (现价约 1447)

    # 1. 获取数据
    # 记得去 data_fetcher.py 把 limit_days 改大一点，比如 800
    df = get_ashare_data(stock_code, limit_days=800)

    if df is not None:
        # 2. 分析指标
        analysis_result = analyze_stock_data(df, period_type=style)
        tech_summary = analysis_result['summary_text']
        current_price = analysis_result['raw_data']['price']

        # 3. 询问 LLM
        advice = get_llm_advice(stock_code, current_price, tech_summary, style, holdings)

        print("\n" + "=" * 60)
        print("🌟 AI 投资顾问建议 🌟")
        print("=" * 60)
        print(advice)