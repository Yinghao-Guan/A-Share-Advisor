import akshare as ak
import baostock as bs
import pandas as pd
import datetime
import re
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
import requests


def sanitize_stock_code(code: str) -> str:
    """
    清洗用户输入的股票代码。
    返回由6位数字组成的字符串。
    """
    digits = re.findall(r'\d+', str(code))
    if digits:
        return "".join(digits)[-6:]
    return code


def _get_ashare_data_primary(clean_symbol: str, period: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    【主引擎】使用 AkShare (东方财富源)
    """
    print(f"🔄 [Primary: AkShare] 尝试获取 {clean_symbol}...")

    # AkShare 接口
    df = ak.stock_zh_a_hist(
        symbol=clean_symbol,
        period=period,
        start_date=start_date,
        end_date=end_date,
        adjust="qfq"
    )

    if df is None or df.empty:
        raise ValueError("AkShare returned empty data")

    # 清洗列名
    rename_map = {
        '日期': 'timestamp', '开盘': 'Open', '最高': 'High',
        '最低': 'Low', '收盘': 'Close', '成交量': 'Volume'
    }
    df = df.rename(columns=rename_map)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df


def _get_baostock_data_fallback(clean_symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    【备用引擎】使用 BaoStock
    注意：BaoStock 需要特定的代码格式 (e.g., sh.600519) 且返回全是字符串
    """
    print(f"🛡️ [Fallback: BaoStock] 主源失败，正在切换备用源获取 {clean_symbol}...")

    # 1. 登录系统
    bs.login()

    # 2. 格式化代码：BaoStock 需要 'sh.600519' 或 'sz.000001'
    # 简单判断：6开头是沪市(sh)，0/3开头是深市(sz)，4/8是北交所(bj - baostock暂不支持bj)
    if clean_symbol.startswith('6'):
        bs_symbol = f"sh.{clean_symbol}"
    elif clean_symbol.startswith(('0', '3')):
        bs_symbol = f"sz.{clean_symbol}"
    else:
        bs.logout()
        raise ValueError(f"BaoStock 可能不支持该代码前缀: {clean_symbol}")

    # 3. 格式化日期：YYYYMMDD -> YYYY-MM-DD
    bs_start = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}"
    bs_end = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}"

    # 4. 获取数据 (adjustflag="2" 前复权)
    rs = bs.query_history_k_data_plus(
        bs_symbol,
        "date,open,high,low,close,volume",
        start_date=bs_start, end_date=bs_end,
        frequency="d", adjustflag="2"
    )

    data_list = []
    while (rs.error_code == '0') & rs.next():
        data_list.append(rs.get_row_data())

    bs.logout()

    if not data_list:
        raise ValueError("BaoStock returned empty data")

    # 5. 转 DataFrame
    df = pd.DataFrame(data_list, columns=['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])

    # 6. 类型清洗 (BaoStock 返回的都是字符串，必须转)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    # 注意：BaoStock 有时候 Volume 是空字符串，需要处理
    for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    return df


# --- 对外暴露的主函数 (带重试) ---
@retry(
    stop=stop_after_attempt(3),
    wait=wait_fixed(1),
    retry=retry_if_exception_type((requests.exceptions.RequestException, ConnectionError, Exception))
)
def get_ashare_data(symbol: str, period: str = 'daily', limit_days: int = 365) -> pd.DataFrame:
    """
    双引擎数据获取：优先 AkShare，失败则降级到 BaoStock。
    """
    clean_symbol = sanitize_stock_code(symbol)

    # 计算时间
    end_date = datetime.datetime.now()
    start_date = end_date - datetime.timedelta(days=limit_days)
    start_date_str = start_date.strftime("%Y%m%d")
    end_date_str = end_date.strftime("%Y%m%d")

    try:
        # 1. 尝试主引擎
        df = _get_ashare_data_primary(clean_symbol, period, start_date_str, end_date_str)

    except Exception as e:
        print(f"⚠️ [Data Fetcher] AkShare 异常: {e}")
        try:
            # 2. 尝试备用引擎 (BaoStock 仅支持日线，如果是周线月线可能需要额外处理，这里暂只处理日线)
            if period == 'daily':
                df = _get_baostock_data_fallback(clean_symbol, start_date_str, end_date_str)
            else:
                raise e  # 如果不是日线，BaoStock 处理起来比较麻烦，直接抛出
        except Exception as e_backup:
            print(f"❌ [Data Fetcher] 所有数据源均失败。最后错误: {e_backup}")
            raise e_backup  # 抛出最后一次异常供 tenacity 重试或 app.py 捕获

    # 通用清洗
    df = df.set_index('timestamp').sort_index()
    # 过滤掉成交量为0的停牌数据
    df = df[df['Volume'] > 0]

    print(f"✅ [Data Fetcher] 成功获取 {len(df)} 条数据。")
    return df


# --- 新闻获取保持不变，或者你可以直接保留之前的重试版本 ---
@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def get_stock_news(symbol: str, limit: int = 5) -> str:
    # ... (保持你之前的代码不变) ...
    clean_symbol = sanitize_stock_code(symbol)
    try:
        news_df = ak.stock_news_em(symbol=clean_symbol)
        if news_df is None or news_df.empty:
            return "暂无新闻"

        recent = news_df.head(limit)
        news_list = []
        for _, row in recent.iterrows():
            d = str(row.get('发布时间', ''))[:10]
            t = row.get('新闻标题', '')
            news_list.append(f"- [{d}] {t}")
        return "\n".join(news_list)
    except Exception:
        return "新闻接口暂时不可用"


# get_stock_name 也可以保持不变 ...
def get_stock_name(symbol: str) -> str:
    # ... (保持不变) ...
    clean_symbol = sanitize_stock_code(symbol)
    try:
        info = ak.stock_individual_info_em(symbol=clean_symbol)
        row = info[info['item'] == '股票简称']
        if not row.empty: return row.iloc[0]['value']
    except:
        pass
    return clean_symbol