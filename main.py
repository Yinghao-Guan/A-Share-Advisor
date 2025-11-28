import sys
from data_fetcher import get_ashare_data
from tech_analysis import analyze_stock_data
from advisor_agent import get_llm_advice, build_prompt
from visualizer import plot_stock_analysis


# --- 汉化 Prompt ---
# 我们可以在这里 Monkey Patch (覆盖) advisor_agent 里的 build_prompt
# 或者你可以直接去 advisor_agent.py 里修改 build_prompt 函数
# 这里为了方便，我们重新定义一个中文版 build_prompt 并注入进去

def build_chinese_prompt(symbol, price, tech_summary, user_style, user_holdings):
    market_rules = (
        "### 市场背景：中国 A 股 (上海/深圳) ###\n"
        "1. **T+1 规则**: 今天买入的股票明天才能卖出。\n"
        "2. **涨跌幅限制**: 通常为 ±10% (科创板/创业板为 ±20%)。\n"
        "3. **只能做多**: 散户通常只能靠股价上涨获利 (无做空机制)。\n"
    )

    full_prompt = f"""
你是一位经验丰富的 A 股投资分析师。你的目标是首先保护用户的本金，其次才是追求利润。
你的回答必须使用**中文 (Simplified Chinese)**。

{market_rules}

--- 用户信息 ---
* **股票代码**: {symbol}
* **交易风格**: {user_style.upper()} (这将决定你如何解读指标权重)
* **当前持仓**: {user_holdings}

--- 实时市场数据 ---
{tech_summary}

--- 你的任务 ---
基于以上数据，请输出以下格式的建议：

## 1. 市场分析
(简要解读趋势和动能。对用户的交易周期来说是多头还是空头？)

## 2. 交易决策
(仅限一个词：**买入 (BUY)**、**卖出 (SELL)**、**持有 (HOLD)**、**加仓 (ADD)** 或 **减仓 (REDUCE)**)

## 3. 决策逻辑
* **技术面**: 引用具体指标数值 (如 "RSI 为 37，尚未超卖" 或 "MACD 死叉")。
* **持仓建议**: 如果用户被套，建议如何管理成本；如果空仓，建议入场位。

## 4. 风险控制
* **止损位**: 给出具体的止损价格。
* **风险预警**: 具体的下行风险是什么。
"""
    return full_prompt


# 覆盖原模块的函数
import advisor_agent

advisor_agent.build_prompt = build_chinese_prompt


def main():
    print("🚀 启动 AI A股 投资顾问系统 (Zero Cost Version)...")

    # 1. 交互式输入
    symbol = input("请输入股票代码 (例如 600519): ").strip()
    if not symbol: symbol = "600519"

    print("\n请选择交易风格:")
    print("1. 短线/激进 (Aggressive)")
    print("2. 中线/波段 (Standard)")
    print("3. 长线/稳健 (Conservative)")
    choice = input("请输入选项 (1/2/3, 默认2): ").strip()

    style_map = {'1': 'short', '2': 'mid', '3': 'long'}
    style = style_map.get(choice, 'mid')

    holdings = input("请输入持仓信息 (例如 '持仓100股 成本1480', 若无直接回车): ").strip()
    if not holdings: holdings = "无持仓 (Empty Position)"

    # 2. 获取数据
    df = get_ashare_data(symbol, limit_days=800)
    if df is None:
        print("程序退出。")
        return

    # 3. 技术分析
    analysis_res = analyze_stock_data(df, period_type=style)

    # 4. 获取 AI 建议
    ai_advice = get_llm_advice(
        symbol,
        analysis_res['raw_data']['price'],
        analysis_res['summary_text'],
        style,
        holdings
    )

    print("\n" + "=" * 60)
    print(ai_advice)
    print("=" * 60)

    # 5. 可视化
    print("\n正在生成图表，请稍候...")
    plot_stock_analysis(analysis_res['df'], symbol, style)


if __name__ == "__main__":
    main()