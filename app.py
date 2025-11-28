import streamlit as st
import pandas as pd
import os
from dotenv import load_dotenv

# 引入模块
from data_fetcher import get_ashare_data, get_stock_news  # <--- 注意这里导入了新函数
from tech_analysis import analyze_stock_data
from advisor_agent import get_llm_advice
from visualizer import plot_stock_analysis
import advisor_agent

# 加载环境变量
load_dotenv()

# ==========================================
# 页面配置
# ==========================================
st.set_page_config(
    page_title="AI A-Share Advisor (Sentiment Enhanced)",
    page_icon="🗞️",  # 换个图标
    layout="wide",
    initial_sidebar_state="expanded"
)


# ==========================================
# 升级版 Prompt (加入新闻面)
# ==========================================
def build_chinese_prompt(symbol, price, tech_summary, user_style, user_holdings, news_summary):
    market_rules = (
        "### 市场背景：中国 A 股 (上海/深圳) ###\n"
        "1. **T+1 规则**: 今天买入的股票明天才能卖出。\n"
        "2. **涨跌幅限制**: 通常为 ±10%。\n"
        "3. **只能做多**: 散户通常只能靠股价上涨获利。\n"
    )
    full_prompt = f"""
你是一位经验丰富的 A 股投资分析师。你的强项是结合**技术面 (Technical)** 和 **消息面 (Sentiment)** 进行综合研判。
你的目标是首先保护用户的本金，其次才是追求利润。回答必须使用**中文 (Simplified Chinese)**。

{market_rules}

--- 用户信息 ---
* **股票代码**: {symbol}
* **交易风格**: {user_style.upper()}
* **当前持仓**: {user_holdings}

--- 实时技术指标 (Technical Data) ---
{tech_summary}

--- 近期新闻面 (News/Sentiment) ---
{news_summary}
(注意：如果新闻中有重大利空，即使技术面良好也要提示风险；反之亦然。)

--- 你的任务 ---
基于以上数据，请输出以下格式的建议：

## 1. 综合分析 (Sentiment & Technical) 🧐
(结合新闻面和技术面进行解读。例如："虽然技术面死叉，但近期有重大利好支撑..." 或者 "技术面良好，但需警惕xx减持新闻...")

## 2. 交易决策 ⚖️
(仅限一个词：**买入 (BUY)**、**卖出 (SELL)**、**持有 (HOLD)**、**加仓 (ADD)** 或 **减仓 (REDUCE)**，并加粗)

## 3. 决策逻辑 🧠
* **技术逻辑**: 引用 RSI, MACD, 均线等。
* **消息逻辑**: 引用上述新闻中的关键信息对股价的影响。
* **操作建议**: 针对用户持仓的具体行动。

## 4. 风险控制 🛡️
* **止损位**: 具体价格。
* **风险预警**: 结合技术位破位或消息面雷区。
"""
    return full_prompt


# 覆盖 monkey patch (注意这里参数变多了，所以 advisor_agent.py 里的原始调用其实会报错，
# 但我们在下面直接调用 get_llm_advice 时会手动处理，或者我们需要重写 get_llm_advice 的调用逻辑)
# 为了简单起见，我们直接在这里重写一个调用 LLM 的逻辑，不通过 advisor_agent.get_llm_advice 了，
# 这样更灵活，避免修改 advisor_agent.py 导致参数不匹配。

import google.generativeai as genai


def get_llm_advice_v2(symbol, price, tech_summary, user_style, user_holdings, news_summary):
    """
    App 本地定义的 LLM 调用函数，支持传入 news_summary
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key: return "Error: No API Key"

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')  # 记得用你的 2.5 flash

    prompt = build_chinese_prompt(symbol, price, tech_summary, user_style, user_holdings, news_summary)

    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"LLM Error: {e}"


# ==========================================
# Streamlit 主程序
# ==========================================

def main():
    # --- 侧边栏 ---
    with st.sidebar:
        st.header("⚙️ 投资配置")
        symbol_input = st.text_input("股票代码", value="600519", help="例如 600519")

        style_options = {'短线/激进 (Short)': 'short', '中线/波段 (Mid)': 'mid', '长线/稳健 (Long)': 'long'}
        selected_style_label = st.selectbox("交易风格", list(style_options.keys()), index=1)
        period_type = style_options[selected_style_label]

        holdings = st.text_area("当前持仓", value="", placeholder="例如：持有100股 成本1500。空仓留空。")
        if not holdings.strip(): holdings = "空仓"

        st.markdown("---")
        analyze_btn = st.button("🚀 开始分析", type="primary", use_container_width=True)

    # --- 主界面 ---
    st.title("🗞️ AI A-Share Advisor (Sentiment)")
    st.markdown(f"**目标**: `{symbol_input}` | **策略**: `{period_type.upper()}`")

    if analyze_btn:
        if not os.getenv("GEMINI_API_KEY"):
            st.error("❌ 请配置 GEMINI_API_KEY")
            return

        try:
            # 1. 获取行情数据 (Cache)
            with st.spinner('正在获取行情数据...'):
                @st.cache_data(ttl=3600)
                def get_market_data(code):
                    return get_ashare_data(code, limit_days=800)

                df = get_market_data(symbol_input)

            if df is None or df.empty:
                st.error("❌ 行情数据获取失败")
                return

            # 2. 获取新闻数据 (Cache - 新闻更新频率高，ttl设短点，比如 10分钟)
            with st.spinner('正在检索最近新闻面...'):
                @st.cache_data(ttl=600)
                def get_news_data(code):
                    return get_stock_news(code, limit=5)  # 获取最近 5 条

                news_text = get_news_data(symbol_input)

            # 3. 显示基础 Metrics
            last_row = df.iloc[-1]
            prev_row = df.iloc[-2]
            change = last_row['Close'] - prev_row['Close']
            pct_change = (change / prev_row['Close']) * 100

            col1, col2, col3 = st.columns(3)
            col1.metric("最新价", f"{last_row['Close']:.2f}", f"{pct_change:.2f}%")
            col2.metric("成交量", f"{last_row['Volume']:.0f}")
            col3.metric("策略", period_type.upper())

            # 4. 展示新闻 (Expander)
            with st.expander("📰 查看最近 5 条相关新闻 (LLM 已读取)", expanded=False):
                st.text(news_text)

            # 5. 技术分析 & AI 推理
            with st.spinner('AI 正在结合“技术面 + 消息面”进行推理...'):
                analysis_res = analyze_stock_data(df, period_type=period_type)

                # 调用我们 App 内部定义的 v2 版函数
                ai_response = get_llm_advice_v2(
                    symbol_input,
                    analysis_res['raw_data']['price'],
                    analysis_res['summary_text'],
                    period_type,
                    holdings,
                    news_text  # <--- 传入新闻
                )

                # 6. 显示结果 (改为垂直布局)

                # --- 第一部分：图表 (全宽) ---
                st.markdown("### 📊 技术图表")
                # use_container_width=True 让图表自动撑满宽度
                fig = plot_stock_analysis(analysis_res['df'], symbol_input, period_type, return_fig=True)
                st.pyplot(fig, use_container_width=True)

                # --- 第二部分：AI 报告 (全宽) ---
                st.markdown("### 🤖 综合决策报告")
                with st.container(border=True):
                    st.markdown(ai_response)

                # 7. 原始数据 (保持在最下方)
                st.markdown("---")
                with st.expander("🔍 查看原始技术指标数据 (Raw Data)", expanded=False):
                    display_df = analysis_res['df'].copy()
                    display_df = display_df.tail(20).sort_index(ascending=False)
                    st.dataframe(
                        display_df.style.format("{:.2f}"),
                        use_container_width=True
                    )

        except Exception as e:
            st.error(f"Error: {e}")
            import traceback
            st.code(traceback.format_exc())


if __name__ == "__main__":
    main()