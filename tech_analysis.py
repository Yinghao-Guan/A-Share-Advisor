import pandas as pd
import pandas_ta as ta

# ==========================================
# 配置：不同周期的参数策略
# ==========================================
STRATEGY_PARAMS = {
    # 短线：激进，反应快，噪音多
    'short': {
        'macd': {'fast': 6, 'slow': 13, 'signal': 4},
        'rsi': {'length': 6},
        'ema_fast': 5,  # 5日线 (攻击线)
        'ema_slow': 10,  # 10日线 (操盘线)
        'desc': 'Aggressive/Short-term'
    },
    # 中线：标准，经典参数
    'mid': {
        'macd': {'fast': 12, 'slow': 26, 'signal': 9},
        'rsi': {'length': 14},
        'ema_fast': 20,  # 20日线 (月线/生命线)
        'ema_slow': 60,  # 60日线 (季线/决策线)
        'desc': 'Standard/Swing-trade'
    },
    # 长线：稳健，过滤短期波动
    'long': {
        'macd': {'fast': 24, 'slow': 52, 'signal': 18},
        'rsi': {'length': 21},
        'ema_fast': 60,  # 季线
        'ema_slow': 250,  # 年线 (牛熊分界)
        'desc': 'Conservative/Long-term'
    }
}


def analyze_stock_data(df: pd.DataFrame, period_type: str = 'mid') -> dict:
    """
    根据用户的时间偏好计算指标，并返回一个供 LLM 阅读的摘要字典。

    :param df: 来自 AkShare 的原始 DataFrame
    :param period_type: 'short', 'mid', 'long'
    """
    # 1. 获取参数配置（如果输入不在范围内，默认用 mid）
    params = STRATEGY_PARAMS.get(period_type, STRATEGY_PARAMS['mid'])

    # 2. 计算指标 (Pandas TA)
    # -------------------------------------------------------
    # A. MACD
    # pandas_ta 会自动生成列名，如 MACD_12_26_9, MACDh_12_26_9 (Hist), MACDs_...
    df.ta.macd(
        fast=params['macd']['fast'],
        slow=params['macd']['slow'],
        signal=params['macd']['signal'],
        append=True
    )

    # B. RSI
    df.ta.rsi(length=params['rsi']['length'], append=True)

    # C. EMA (均线)
    df.ta.ema(length=params['ema_fast'], append=True)
    df.ta.ema(length=params['ema_slow'], append=True)

    # 3. 提取最新一行的指标数值
    # -------------------------------------------------------
    last_row = df.iloc[-1]
    prev_row = df.iloc[-2]  # 用于比较趋势变化

    # 动态构建列名 (因为 pandas_ta 列名包含参数)
    p_macd = params['macd']
    col_macd_hist = f"MACDh_{p_macd['fast']}_{p_macd['slow']}_{p_macd['signal']}"
    col_rsi = f"RSI_{params['rsi']['length']}"
    col_ema_fast = f"EMA_{params['ema_fast']}"
    col_ema_slow = f"EMA_{params['ema_slow']}"

    # 获取数值
    price = last_row['Close']
    macd_hist = last_row.get(col_macd_hist, 0)
    rsi_val = last_row.get(col_rsi, 50)
    ema_fast_val = last_row.get(col_ema_fast, 0)
    ema_slow_val = last_row.get(col_ema_slow, 0)

    # 4. 生成自然语言描述 (辅助 LLM 理解)
    # -------------------------------------------------------

    # RSI 状态
    rsi_status = "NEUTRAL"
    if rsi_val > 70:
        rsi_status = "OVERBOUGHT (High Risk)"
    elif rsi_val < 30:
        rsi_status = "OVERSOLD (Potential Bounce)"

    # 均线趋势
    trend = "SIDEWAYS"
    if price > ema_fast_val > ema_slow_val:
        trend = "STRONG UPTREND (Price > Fast > Slow)"
    elif price < ema_fast_val < ema_slow_val:
        trend = "STRONG DOWNTREND (Price < Fast < Slow)"
    elif price > ema_slow_val:
        trend = "MODERATE UPTREND (Above Slow MA)"

    # MACD 动能
    momentum = "BULLISH" if macd_hist > 0 else "BEARISH"

    # 5. 打包结果
    summary_text = (
        f"--- Technical Analysis ({params['desc']}) ---\n"
        f"Date: {last_row.name.date()}\n"
        f"Close Price: {price:.2f}\n"
        f"Trend (EMA): {trend}\n"
        f"  - EMA({params['ema_fast']}): {ema_fast_val:.2f}\n"
        f"  - EMA({params['ema_slow']}): {ema_slow_val:.2f}\n"
        f"Momentum (MACD): {momentum} (Hist: {macd_hist:.3f})\n"
        f"Oscillator (RSI): {rsi_val:.2f} [{rsi_status}]\n"
        f"Volume: {last_row['Volume']:.0f}"
    )

    print(f"✅ [Tech Analyzer] 指标计算完成。策略: {period_type}")

    return {
        "summary_text": summary_text,
        "raw_data": {
            "price": price,
            "rsi": rsi_val,
            "macd_hist": macd_hist,
            "trend": trend
        },
        "df": df  # 返回包含指标的完整 DataFrame，方便后续画图或查阅
    }


# ==========================================
# 测试运行
# ==========================================
if __name__ == "__main__":
    # 假设我们已经有了 Step 1 的数据 fetcher
    # 这里为了演示独立运行，我们简单 mock 一个数据获取，或者你需要把 step1 的代码 import 进来
    # 为了方便，这里直接再次调用 step 1 的逻辑 (你需要确保同一目录下有 data_fetcher.py 或把 step 1 代码贴在上面)

    try:
        from data_fetcher import get_ashare_data
    except ImportError:
        print("⚠️ 请确保 data_fetcher.py 在同一目录下")
        exit()

    # 1. 获取数据
    symbol = "600519"
    df = get_ashare_data(symbol)

    if df is not None:
        # 2. 测试不同周期的计算
        print("\n" + "=" * 50)
        print("测试场景 1: 短线交易者 (Aggressive)")
        res_short = analyze_stock_data(df.copy(), period_type='short')
        print(res_short['summary_text'])

        print("\n" + "=" * 50)
        print("测试场景 2: 稳健长线 (Long)")
        res_long = analyze_stock_data(df.copy(), period_type='long')
        print(res_long['summary_text'])