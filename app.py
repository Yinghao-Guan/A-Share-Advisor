import streamlit as st
import pandas as pd
import os
from dotenv import load_dotenv

# 引入我们的模块
from data_fetcher import get_ashare_data
from tech_analysis import analyze_stock_data
from advisor_agent import get_llm_advice, build_prompt
from visualizer import plot_stock_analysis
import advisor_agent  # 用于 Monkey Patch

# 加载环境变量
load_dotenv()

# ==========================================
# 页面配置
# ==========================================
st.set_page_config(
    page_title="AI A-Share Advisor",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)


# --- 注入中文 Prompt (与 main.py 逻辑一致) ---
def build_chinese_prompt(symbol, price, tech_summary, user_style, user_holdings):
    market_rules = (
        "### 市场背景：中国 A 股 (上海/深圳) ###\n"
        "1. **T+1 规则**: 今天买入的股票明天才能卖出。\n"
        "2. **涨跌幅限制**: 通常为 ±10% (科创板/创业板为 ±20%)。\n"
        "3. **只能做多**: 散户通常只能靠股价上涨获利。\n"
    )
    full_prompt = f"""
你是一位经验丰富的 A 股投资分析师。你的目标是首先保护用户的本金，其次才是追求利润。
你的回答必须使用**中文 (Simplified Chinese)**。请使用 Markdown 格式优化排版。

{market_rules}

--- 用户信息 ---
* **股票代码**: {symbol}
* **交易风格**: {user_style.upper()}
* **当前持仓**: {user_holdings}

--- 实时市场数据 ---
{tech_summary}

--- 你的任务 ---
基于以上数据，请输出以下格式的建议：

## 1. 市场分析 🧐
(简要解读趋势和动能。)

## 2. 交易决策 ⚖️
(仅限一个词：**买入 (BUY)**、**卖出 (SELL)**、**持有 (HOLD)**、**加仓 (ADD)** 或 **减仓 (REDUCE)**，并加粗)

## 3. 决策逻辑 🧠
* **技术面**: 引用具体指标数值。
* **持仓建议**: 针对用户持仓给出建议。

## 4. 风险控制 🛡️
* **止损位**: 具体价格。
* **风险预警**: 具体的下行风险。
"""
    return full_prompt


# 覆盖 advisor_agent 的 prompt 构建函数
advisor_agent.build_prompt = build_chinese_prompt


# ==========================================
# Streamlit 界面逻辑
# ==========================================

def main():
    # --- 侧边栏：设置区 ---
    with st.sidebar:
        st.header("⚙️ 投资配置")

        # 1. 股票代码
        symbol_input = st.text_input("股票代码 (Stock Code)", value="600519", help="例如 600519 或 000001")

        # 2. 交易风格
        style_options = {'短线/激进 (Short)': 'short', '中线/波段 (Mid)': 'mid', '长线/稳健 (Long)': 'long'}
        selected_style_label = st.selectbox("交易风格 (Strategy)", list(style_options.keys()), index=1)
        period_type = style_options[selected_style_label]

        # 3. 持仓信息
        holdings = st.text_area("当前持仓 (Holdings)", value="", placeholder="例如：持有100股，成本1500元。若空仓请留空。")
        if not holdings.strip():
            holdings = "空仓 (Empty Position)"

        st.markdown("---")
        analyze_btn = st.button("🚀 开始分析", type="primary", use_container_width=True)

        st.caption("Powered by AkShare & Gemini 2.5")

    # --- 主界面 ---
    st.title("📈 AI A-Share Advisor (Pro)")
    st.markdown(f"**当前分析目标**: `{symbol_input}` | **策略**: `{period_type.upper()}`")

    if analyze_btn:
        if not os.getenv("GEMINI_API_KEY"):
            st.error("❌ 未检测到 API Key。请在 .env 文件中配置 GEMINI_API_KEY。")
            return

        try:
            # 1. 获取数据 (使用 st.spinner 显示加载动画)
            with st.spinner('正在从交易所获取实时数据...'):
                # 缓存数据获取，避免重复请求
                @st.cache_data(ttl=3600)  # 缓存 1 小时
                def get_cached_data(code):
                    return get_ashare_data(code, limit_days=800)

                df = get_cached_data(symbol_input)

            if df is None or df.empty:
                st.error(f"❌ 无法获取代码为 {symbol_input} 的数据，请检查代码是否正确。")
                return

            # 2. 显示基础行情指标 (Metrics)
            last_row = df.iloc[-1]
            prev_row = df.iloc[-2]
            change = last_row['Close'] - prev_row['Close']
            pct_change = (change / prev_row['Close']) * 100

            # 使用列布局显示指标
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("最新收盘价", f"{last_row['Close']:.2f}", f"{change:.2f} ({pct_change:.2f}%)")
            col2.metric("成交量", f"{last_row['Volume'] / 10000:.1f} 万手")
            col3.metric("日期", str(last_row.name.date()))
            col4.metric("策略周期", period_type.upper())

            # 3. 技术分析 & AI 思考
            with st.spinner('AI 正在通过 10+ 种技术指标进行计算与推理...'):
                analysis_res = analyze_stock_data(df, period_type=period_type)

                ai_response = get_llm_advice(
                    symbol_input,
                    analysis_res['raw_data']['price'],
                    analysis_res['summary_text'],
                    period_type,
                    holdings
                )

            # 4. 界面布局：左侧图表，右侧建议 (或者上下布局)
            # 这里我们采用上下布局，手机端体验更好

            st.markdown("### 🤖 AI 投资决策报告")
            st.markdown("---")

            # 使用 container 包装 AI 回复
            with st.container(border=True):
                st.markdown(ai_response)

            st.markdown("### 📊 技术分析图表")

            # 5. 绘制图表
            fig = plot_stock_analysis(analysis_res['df'], symbol_input, period_type, return_fig=True)
            st.pyplot(fig)  # 将 Matplotlib 图表渲染到 Streamlit

            # 6. (可选) 展开查看原始数据
            with st.expander("查看原始技术指标数据"):
                st.dataframe(analysis_res['df'].tail(10))

        except Exception as e:
            st.error(f"运行过程中发生错误: {e}")
            # 打印详细堆栈以便调试
            import traceback
            st.code(traceback.format_exc())


if __name__ == "__main__":
    main()