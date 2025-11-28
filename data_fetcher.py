import akshare as ak
import pandas as pd
import datetime
import re


def sanitize_stock_code(code: str) -> str:
    """
    清洗用户输入的股票代码，确保是 6 位数字字符串。
    例如：输入 'sh600519' -> 输出 '600519'
    """
    # 提取字符串中的所有数字
    digits = re.findall(r'\d+', str(code))
    if digits:
        # 拼接并取后6位（防止有些输入带前缀）
        clean_code = "".join(digits)[-6:]
        return clean_code
    return code


def get_ashare_data(symbol: str, period: str = 'daily', limit_days: int = 365) -> pd.DataFrame:
    """
    获取 A 股历史数据并清洗为标准格式。

    :param symbol: 股票代码 (e.g., '600519')
    :param period: 周期 ('daily', 'weekly', 'monthly')
    :param limit_days: 回溯获取多少天的数据 (计算长周期指标如年线需要较多数据)
    :return: 清洗好的 DataFrame，索引为日期，列为 Open, High, Low, Close, Volume
    """
    clean_symbol = sanitize_stock_code(symbol)
    print(f"🔄 [Data Fetcher] 正在获取 {clean_symbol} 的 {period} 数据 (过去 {limit_days} 天)...")

    # 计算开始时间
    end_date = datetime.datetime.now()
    start_date = end_date - datetime.timedelta(days=limit_days)
    start_date_str = start_date.strftime("%Y%m%d")
    end_date_str = end_date.strftime("%Y%m%d")

    try:
        # 调用 AkShare 接口 (stock_zh_a_hist 是目前最稳定的 A 股历史行情接口)
        # adjust='qfq' : 前复权，技术分析必须项
        df = ak.stock_zh_a_hist(
            symbol=clean_symbol,
            period=period,
            start_date=start_date_str,
            end_date=end_date_str,
            adjust="qfq"
        )

        if df is None or df.empty:
            print(f"❌ [Data Fetcher] 未获取到数据，请检查股票代码 {clean_symbol} 是否正确。")
            return None

        # --- 数据清洗标准流程 ---

        # 1. 重命名列 (适配 pandas_ta 需要的英文列名)
        # AkShare 返回的列名通常是中文：'日期', '开盘', '收盘', '最高', '最低', '成交量', ...
        rename_map = {
            '日期': 'timestamp',
            '开盘': 'Open',
            '最高': 'High',
            '最低': 'Low',
            '收盘': 'Close',
            '成交量': 'Volume'
        }
        df = df.rename(columns=rename_map)

        # 2. 确保只保留核心列 (防止接口变动返回多余列干扰)
        required_cols = ['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']
        df = df[required_cols]

        # 3. 类型转换 (确保全是数值，日期转 datetime)
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        # 将价格列转换为 float
        numeric_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        # 4. 设置索引
        df = df.set_index('timestamp')
        df = df.sort_index()  # 确保按时间正序排列

        print(f"✅ [Data Fetcher] 成功获取 {len(df)} 条 K 线数据。")
        print(f"   最新收盘价: {df.iloc[-1]['Close']} (日期: {df.index[-1].date()})")

        return df

    except Exception as e:
        print(f"❌ [Data Fetcher] 发生异常: {e}")
        return None


# ==========================================
# 简单的测试运行
# ==========================================
if __name__ == "__main__":
    # 测试用例 1: 贵州茅台 (600519)
    print("--- 测试 1: 正常股票 ---")
    df_result = get_ashare_data("600519", period="daily")
    if df_result is not None:
        print(df_result.tail())  # 打印最后 5 行看看格式

    # 测试用例 2: 容错测试 (带前缀的代码)
    print("\n--- 测试 2: 输入带前缀的代码 ---")
    get_ashare_data("sz000001")  # 平安银行