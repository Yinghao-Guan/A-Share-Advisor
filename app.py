import streamlit as st
import pandas as pd
import os
from dotenv import load_dotenv

# 引入模块
from data_fetcher import get_ashare_data, get_stock_news, get_stock_name
from tech_analysis import analyze_stock_data
from advisor_agent import get_llm_advice
from visualizer import plot_stock_analysis
import utils
import advisor_agent
import google.generativeai as genai

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

# --- Session State 初始化 ---
# 1. target_symbol: 存储当前选中的股票代码
if 'target_symbol' not in st.session_state:
    st.session_state.target_symbol = "600519"

# 2. analysis_triggered: 标记是否点击过“开始分析”，防止刷新后内容消失
if 'analysis_triggered' not in st.session_state:
    st.session_state.analysis_triggered = False


# ==========================================
# 辅助函数 (Callbacks & Logic)
# ==========================================

def trigger_analysis():
    """点击“开始分析”或切换自选股时触发"""
    st.session_state.analysis_triggered = True


def add_to_watchlist_callback(symbol):
    """点击“加入自选”时的回调函数"""
    current_name = get_stock_name(symbol)
    success, msg = utils.add_to_watchlist(symbol, current_name)
    if success:
        st.toast(msg, icon="✅")
    else:
        st.toast(msg, icon="⚠️")


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

--- 你的任务 ---
基于以上数据，请输出以下格式的建议：

## 1. 综合分析 (Sentiment & Technical) 🧐
(结合新闻面和技术面进行解读。)

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


def get_llm_advice_v2(symbol, price, tech_summary, user_style, user_holdings, news_summary):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key: return "Error: No API Key"
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
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
    # --- Sidebar 逻辑 ---
    with st.sidebar:
        st.header("🔍 自选股 (Watchlist)")

        # 1. 读取自选股
        watchlist = utils.load_watchlist()
        watchlist_options = [f"{item['symbol']} - {item['name']}" for item in watchlist]
        watchlist_options.insert(0, "手动输入 (Manual Input)")

        # 2. 自选股选择器
        # index=0 默认选手动，除非 session 里有记录需要恢复状态（这里简化处理）
        selected_option = st.radio("我的关注列表:", watchlist_options)

        # 3. 处理选择逻辑
        if selected_option != "手动输入 (Manual Input)":
            selected_code = selected_option.split(" - ")[0]
            if selected_code != st.session_state.target_symbol:
                st.session_state.target_symbol = selected_code
                st.session_state.analysis_triggered = True  # 切换股票自动触发分析状态
                st.rerun()

        # 4. 删除按钮
        if selected_option != "手动输入 (Manual Input)":
            code_to_del = selected_option.split(" - ")[0]
            if st.button(f"🗑️ 移除 {code_to_del}", use_container_width=True):
                success, msg = utils.remove_from_watchlist(code_to_del)
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

        st.markdown("---")
        st.header("⚙️ 参数配置")

        # 5. 输入框 (key绑定session_state，实现双向同步)
        symbol_input = st.text_input("股票代码", key="target_symbol")

        style_options = {'短线/激进 (Short)': 'short', '中线/波段 (Mid)': 'mid', '长线/稳健 (Long)': 'long'}
        selected_style_label = st.selectbox("交易风格", list(style_options.keys()), index=1)
        period_type = style_options[selected_style_label]

        holdings = st.text_area("当前持仓", value="", placeholder="例如：持有100股 成本1500。空仓留空。")
        if not holdings.strip(): holdings = "空仓"

        st.markdown("---")

        # 6. 开始分析按钮
        # 注意：这里使用 on_click 回调来改变状态，而不是直接 if button
        st.button("🚀 开始分析", type="primary", use_container_width=True, on_click=trigger_analysis)

    # --- 主界面逻辑 ---
    st.title("📈 AI A-Share Advisor (Pro)")
    st.markdown(f"**目标**: `{symbol_input}` | **策略**: `{period_type.upper()}`")

    # 核心判断：只有当 analysis_triggered 为 True 时才运行分析逻辑
    # 这样即使点击其他按钮导致页面刷新，只要状态没变，内容就会保留
    if st.session_state.analysis_triggered:

        if not os.getenv("GEMINI_API_KEY"):
            st.error("❌ 请配置 GEMINI_API_KEY")
            return

        try:
            # 1. 获取行情
            with st.spinner('正在获取行情数据...'):
                @st.cache_data(ttl=3600)
                def get_market_data(code):
                    return get_ashare_data(code, limit_days=800)

                df = get_market_data(symbol_input)

            if df is None or df.empty:
                st.error("❌ 行情数据获取失败")
                st.session_state.analysis_triggered = False  # 重置状态
                return

            # 2. 获取新闻
            with st.spinner('正在检索最近新闻面...'):
                @st.cache_data(ttl=600)
                def get_news_data(code):
                    return get_stock_news(code, limit=5)

                news_text = get_news_data(symbol_input)

            # 3. 显示 Metrics
            last_row = df.iloc[-1]
            prev_row = df.iloc[-2]
            change = last_row['Close'] - prev_row['Close']
            pct_change = (change / prev_row['Close']) * 100

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("最新价", f"{last_row['Close']:.2f}", f"{pct_change:.2f}%")
            col2.metric("成交量", f"{last_row['Volume']:.0f}")
            col3.metric("策略", period_type.upper())

            # --- [按钮] 加入自选股 ---
            # 检查是否已存在
            watchlist_codes = [item['symbol'] for item in utils.load_watchlist()]
            is_in_watchlist = symbol_input in watchlist_codes

            with col4:
                if not is_in_watchlist:
                    # 关键修改：使用 on_click 回调，并传递 args
                    st.button(
                        "❤️ 加入自选",
                        on_click=add_to_watchlist_callback,
                        args=(symbol_input,)  # 传递参数给回调函数
                    )
                else:
                    st.button("✅ 已关注", disabled=True)

            # 4. 新闻折叠
            with st.expander("📰 查看最近 5 条相关新闻", expanded=False):
                st.text(news_text)

            # 5. AI 推理
            with st.spinner('AI 正在结合“技术面 + 消息面”进行推理...'):
                analysis_res = analyze_stock_data(df, period_type=period_type)

                ai_response = get_llm_advice_v2(
                    symbol_input,
                    analysis_res['raw_data']['price'],
                    analysis_res['summary_text'],
                    period_type,
                    holdings,
                    news_text
                )

            # 6. [Vertical Layout] 垂直布局

            # 部分 A: 图表
            st.markdown("### 📊 技术图表")
            # 传递 use_container_width=True 让图表自适应宽度
            fig = plot_stock_analysis(analysis_res['df'], symbol_input, period_type, return_fig=True)
            st.pyplot(fig, use_container_width=True)

            # 部分 B: AI 报告
            st.markdown("### 🤖 综合决策报告")
            with st.container(border=True):
                st.markdown(ai_response)

            # 部分 C: 原始数据
            st.markdown("---")
            with st.expander("🔍 查看原始技术指标数据 (Raw Data)", expanded=False):
                display_df = analysis_res['df'].copy()
                display_df = display_df.tail(20).sort_index(ascending=False)
                st.dataframe(display_df.style.format("{:.2f}"), use_container_width=True)

        except Exception as e:
            st.error(f"Error: {e}")
            import traceback
            st.code(traceback.format_exc())


if __name__ == "__main__":
    main()