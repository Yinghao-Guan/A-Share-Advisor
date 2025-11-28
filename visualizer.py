import mplfinance as mpf
import pandas as pd


def plot_stock_analysis(df: pd.DataFrame, symbol: str, period_type: str, return_fig: bool = False):
    """
    绘制 K 线图。
    :param return_fig: 如果为 True，返回 figure 对象用于 Streamlit 展示；否则直接弹窗。
    """
    # 1. 准备数据
    plot_df = df.copy().tail(120)  # 网页上显示最近 120 天比较合适

    # 2. 准备均线
    overlays = []
    ema_cols = [c for c in plot_df.columns if c.startswith('EMA_')]
    for col in ema_cols:
        overlays.append(mpf.make_addplot(plot_df[col], width=1.0))

    # 3. 准备副图 (MACD & RSI)
    # 自动寻找列名
    macd_hist_col = [c for c in plot_df.columns if c.startswith('MACDh_')][0]
    macd_line_col = [c for c in plot_df.columns if c.startswith('MACD_')][0]
    signal_line_col = [c for c in plot_df.columns if c.startswith('MACDs_')][0]
    rsi_col = [c for c in plot_df.columns if c.startswith('RSI_')][0]

    # MACD 颜色设置
    macd_hist_colors = ['r' if v >= 0 else 'g' for v in plot_df[macd_hist_col]]  # A股习惯：红涨绿跌

    macd_plots = [
        mpf.make_addplot(plot_df[macd_line_col], panel=2, color='fuchsia', ylabel='MACD', width=1),
        mpf.make_addplot(plot_df[signal_line_col], panel=2, color='b', width=1),
        mpf.make_addplot(plot_df[macd_hist_col], type='bar', panel=2, color=macd_hist_colors, alpha=0.5),
    ]

    rsi_plot = mpf.make_addplot(plot_df[rsi_col], panel=3, color='purple', ylabel='RSI', width=1)

    # 辅助线
    rsi_lines = [
        mpf.make_addplot([70] * len(plot_df), panel=3, color='r', linestyle='--', width=0.5),
        mpf.make_addplot([30] * len(plot_df), panel=3, color='g', linestyle='--', width=0.5)
    ]

    add_plots = overlays + macd_plots + [rsi_plot] + rsi_lines

    # 4. 样式与绘图
    # A股风格：红涨绿跌 (marketcolors)
    mc = mpf.make_marketcolors(up='r', down='g', edge='i', wick='i', volume='in', inherit=True)
    s = mpf.make_mpf_style(base_mpf_style='yahoo', marketcolors=mc, rc={'font.size': 8})

    fig, axes = mpf.plot(
        plot_df,
        type='candle',
        style=s,
        title=f'{symbol} - {period_type.upper()} Strategy',
        ylabel='Price',
        volume=True,
        addplot=add_plots,
        panel_ratios=(4, 1, 1.2, 1.2),
        figscale=1.2,
        tight_layout=True,
        returnfig=True  # <--- 关键修改：强制返回 figure 对象
    )

    if return_fig:
        return fig
    else:
        mpf.show()