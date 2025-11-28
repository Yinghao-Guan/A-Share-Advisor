import streamlit as st
import pandas as pd
import os
from dotenv import load_dotenv

from data_fetcher import get_ashare_data, get_stock_news, get_stock_name
from tech_analysis import analyze_stock_data
from visualizer import plot_stock_analysis
import utils
import google.generativeai as genai

load_dotenv()

st.set_page_config(page_title="AI A-Share Advisor", page_icon="📈", layout="wide")

# ==========================================
# 1. Session State 管理
# ==========================================
if 'target_symbol' not in st.session_state:
    st.session_state.target_symbol = "600519"

# 核心缓存
if 'stock_cache' not in st.session_state:
    st.session_state.stock_cache = {}

if 'analysis_started' not in st.session_state:
    st.session_state.analysis_started = False


# ==========================================
# 2. 核心逻辑 (LLM)
# ==========================================

def get_llm_advice_v2(symbol, price, tech_summary, user_style, user_holdings, news_summary):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key: return "Error: No API Key"
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')

    market_rules = "### 市场背景：中国 A 股 (上海/深圳) ###\n1. T+1 规则\n2. 涨跌幅限制\n3. 只能做多\n"
    prompt = f"""
    你是一位经验丰富的 A 股投资分析师。目标：保护本金 > 追求利润。请用**中文**回答。
    
    {market_rules}
    
    --- 用户信息 ---
    * **代码**: {symbol}
    * **风格**: {user_style.upper()}
    * **持仓**: {user_holdings}
    
    --- 技术指标 ---
    {tech_summary}
    
    --- 新闻面 ---
    {news_summary}
    
    --- 任务 ---
    1. **综合分析** (结合技术+消息)
    2. **决策** (BUY/SELL/HOLD/ADD/REDUCE)
    3. **逻辑** (技术逻辑 & 消息逻辑 & 操作建议)
    4. **风控** (止损位 & 预警)
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"LLM Error: {e}"


# ==========================================
# 3. 回调函数
# ==========================================

def on_watchlist_change():
    """Sidebar 切换自选股时触发"""
    selected = st.session_state.watchlist_radio

    if selected != "手动输入 (Manual Input)":
        code = selected.split(" - ")[0]
        st.session_state.target_symbol = code

        # 切换股票后，如果缓存不一致，重置分析状态
        if st.session_state.stock_cache.get('symbol') != code:
            st.session_state.analysis_started = False

    else:
        pass


def on_start_analysis():
    """点击开始分析时触发"""
    st.session_state.analysis_started = True
    if st.session_state.stock_cache.get('symbol') != st.session_state.target_symbol:
        st.session_state.stock_cache = {}


def on_add_watchlist_click():
    """加入自选回调"""
    symbol = st.session_state.target_symbol
    name = get_stock_name(symbol)

    # 只存代码和名称
    success, msg = utils.add_to_watchlist(symbol, name)
    if success:
        st.toast(msg, icon="✅")
    else:
        st.toast(msg, icon="⚠️")


# ==========================================
# 4. 主程序
# ==========================================
def main():
    # --- Sidebar ---
    with st.sidebar:
        st.header("🔍 自选股 (Watchlist)")
        watchlist = utils.load_watchlist()
        watchlist_options = [f"{item['symbol']} - {item['name']}" for item in watchlist]
        watchlist_options.insert(0, "手动输入 (Manual Input)")

        st.radio(
            "我的关注列表:",
            watchlist_options,
            key="watchlist_radio",
            on_change=on_watchlist_change
        )

        if st.session_state.watchlist_radio != "手动输入 (Manual Input)":
            code_to_del = st.session_state.watchlist_radio.split(" - ")[0]
            if st.button(f"🗑️ 移除 {code_to_del}", use_container_width=True):
                utils.remove_from_watchlist(code_to_del)
                st.rerun()

        st.markdown("---")
        st.header("⚙️ 参数配置")

        is_manual = (st.session_state.watchlist_radio == "手动输入 (Manual Input)")

        symbol_input = st.text_input(
            "股票代码",
            key="target_symbol",
            disabled=not is_manual,
            help="选择自选股时自动锁定"
        )

        style_map = {'短线 (Short)': 'short', '中线 (Mid)': 'mid', '长线 (Long)': 'long'}
        style_label = st.selectbox("交易风格", list(style_map.keys()), index=1)
        period_type = style_map[style_label]

        # --- [修改处] 持仓信息 UI 升级 ---
        st.markdown("#### 持仓状态")

        # 1. 勾选框
        has_holdings = st.checkbox("已有持仓 (Held Position)")

        holdings_input = "空仓"  # 默认值

        if has_holdings:
            # 2. 如果勾选，展开输入框
            # 使用 container 让排版更紧凑
            with st.container():
                col_h1, col_h2 = st.columns(2)
                with col_h1:
                    share_count = st.text_input("持有股数", placeholder="如 100")
                with col_h2:
                    avg_cost = st.text_input("持仓成本（单股）", placeholder="如 1500.5")

                # 3. 动态拼装字符串供 LLM 使用
                if share_count and avg_cost:
                    holdings_input = f"持有 {share_count} 股，成本 {avg_cost}"
                elif share_count:
                    holdings_input = f"持有 {share_count} 股，成本未知"
                elif avg_cost:
                    holdings_input = f"持有未知数量，成本 {avg_cost}"
                else:
                    holdings_input = "已有持仓 (未填详情)"

        # -------------------------------

        st.markdown("---")

        st.button("🚀 开始分析", type="primary", use_container_width=True, on_click=on_start_analysis)

    # --- Main Area ---
    st.title("📈 AI A-Share Advisor")

    if st.session_state.analysis_started:

        symbol = st.session_state.target_symbol
        cache = st.session_state.stock_cache

        # --- Level 1: 行情 ---
        if cache.get('symbol') != symbol or 'df' not in cache:
            with st.spinner(f"正在获取 {symbol} 行情数据..."):
                df = get_ashare_data(symbol, limit_days=800)
                if df is None or df.empty:
                    st.error("无法获取数据，请检查代码。")
                    st.session_state.analysis_started = False
                    st.stop()

                cache['symbol'] = symbol
                cache['df'] = df
                cache.pop('news', None)
                cache.pop('llm', None)

        df = cache['df']
        tech_res = analyze_stock_data(df, period_type=period_type)

        last_row = df.iloc[-1]
        prev_row = df.iloc[-2]
        change = last_row['Close'] - prev_row['Close']
        pct = (change / prev_row['Close']) * 100

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("最新价", f"{last_row['Close']:.2f}", f"{pct:.2f}%")
        c2.metric("成交量", f"{last_row['Volume']:.0f}")
        c3.metric("策略", period_type.upper())

        with c4:
            # 检查自选状态
            current_watchlist = utils.load_watchlist()
            is_in_watchlist = any(item['symbol'] == symbol for item in current_watchlist)

            if is_in_watchlist:
                st.button("✅ 已在自选", disabled=True)
            else:
                st.button("❤️ 加入自选", on_click=on_add_watchlist_click)

        st.markdown("### 📊 技术图表")
        fig = plot_stock_analysis(df, symbol, period_type, return_fig=True)
        st.pyplot(fig, use_container_width=True)

        # --- Level 2: 新闻 ---
        if 'news' not in cache:
            with st.spinner("正在检索新闻..."):
                news_text = get_stock_news(symbol, limit=5)
                cache['news'] = news_text

        news_text = cache['news']

        with st.expander("📰 查看新闻面", expanded=False):
            st.text(news_text)

        # --- Level 3: LLM ---
        # 如果用户改了持仓，这里会重新计算，因为 holdings_input 变了
        current_context_key = f"{period_type}_{holdings_input}"

        if 'llm' not in cache or cache.get('llm_context') != current_context_key:
            st.info("🤖 AI 分析师正在撰写报告...")

            response = get_llm_advice_v2(
                symbol,
                tech_res['raw_data']['price'],
                tech_res['summary_text'],
                period_type,
                holdings_input,
                news_text
            )

            cache['llm'] = response
            cache['llm_context'] = current_context_key
            st.rerun()

        if 'llm' in cache:
            st.markdown("### 🤖 决策报告")
            with st.container(border=True):
                st.markdown(cache['llm'])

        st.markdown("---")
        with st.expander("查看原始数据"):
            st.dataframe(df.tail(20).sort_index(ascending=False), use_container_width=True)

    else:
        st.info("👈 请在左侧选择股票并点击“开始分析”")


if __name__ == "__main__":
    main()