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


def get_stock_news(symbol: str, limit: int = 5) -> str:
    """
    获取个股最近的新闻。
    注意：akshare 的新闻接口依赖东方财富网页，极其容易因为源站改版而失效。
    这里增加了强鲁棒性处理。
    """
    clean_symbol = sanitize_stock_code(symbol)
    print(f"📰 [Data Fetcher] 正在获取 {clean_symbol} 的新闻面数据...")

    try:
        # 尝试调用主要接口
        news_df = ak.stock_news_em(symbol=clean_symbol)

        # 检查数据是否为空
        if news_df is None or news_df.empty:
            return "未获取到相关新闻 (Source Empty)。"

        # 尝试标准解析
        recent_news = news_df.head(limit)
        news_summary_list = []
        for _, row in recent_news.iterrows():
            # 增加对列名存在的检查，防止列名变更导致 KeyError
            date = str(row.get('发布时间', '未知日期'))[:10]
            title = row.get('新闻标题', '无标题')
            news_summary_list.append(f"- [{date}] {title}")

        return "\n".join(news_summary_list)

    except KeyError as e:
        # 专门捕获你遇到的 'cmsArticle' 错误
        print(f"⚠️ [Data Fetcher Warning] AkShare 解析失败 ({e})，可能是源站接口变动。")
        return "新闻接口暂时不可用 (Source Structure Changed)。建议更新 akshare 或稍后再试。"
    except Exception as e:
        # 捕获网络或其他未知错误
        print(f"❌ [Data Fetcher Error] {e}")
        return f"新闻获取异常: {str(e)[:50]}..."