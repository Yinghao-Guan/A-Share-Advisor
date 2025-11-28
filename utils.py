import json
import os

WATCHLIST_FILE = "watchlist.json"


def load_watchlist():
    """读取自选股列表"""
    if not os.path.exists(WATCHLIST_FILE):
        return []
    try:
        with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_watchlist(watchlist):
    """保存自选股列表"""
    try:
        with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
            json.dump(watchlist, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving watchlist: {e}")


def add_to_watchlist(symbol, name):
    """
    添加股票到自选列表 (不包含持仓信息)。
    如果已存在，则更新名称。
    """
    watchlist = load_watchlist()

    # 检查是否已存在，如果存在则更新名称
    for item in watchlist:
        if item['symbol'] == symbol:
            item['name'] = name
            save_watchlist(watchlist)
            return True, f"已更新 {name} 的名称"

    # 不存在则新增
    watchlist.append({
        "symbol": symbol,
        "name": name
    })
    save_watchlist(watchlist)
    return True, f"成功添加 {name}"


def remove_from_watchlist(symbol):
    """移除股票"""
    watchlist = load_watchlist()
    new_list = [item for item in watchlist if item['symbol'] != symbol]
    if len(new_list) == len(watchlist):
        return False, "未找到该股票"
    save_watchlist(new_list)
    return True, f"已移除 {symbol}"