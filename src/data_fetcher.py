"""
Data Fetcher and Storage Module for Trading Simulator.
Supports downloading historical data from MetaTrader 5 (MT5), Yahoo Finance, Binance, or loading MT5 CSV exports,
with automated multi-timeframe resampling (M5 -> H1, H4, D1 or M15 -> H1, H4, D1).
"""

import os
import json
import csv
import time
from datetime import datetime, timezone, timedelta
import requests
from typing import List, Dict, Any, Optional

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)

# Standard Timeframe in Seconds
TIMEFRAME_SECONDS = {
    "M1": 60,
    "M5": 300,
    "M15": 900,
    "M30": 1800,
    "H1": 3600,
    "H4": 14400,
    "D1": 86400,
    "W1": 604800,
}

# Common symbol mappings
SYMBOL_MAPPINGS = {
    "XAUUSD": {"yahoo": "GC=F", "binance": "PAXGUSDT", "name": "Gold / US Dollar", "digits": 2, "pip_size": 0.1},
    "JPN225": {"yahoo": "^N225", "binance": None, "name": "Nikkei 225 Index", "digits": 1, "pip_size": 1.0},
    "UK100": {"yahoo": "^FTSE", "binance": None, "name": "FTSE 100 Index", "digits": 1, "pip_size": 0.1},
    "EURUSD": {"yahoo": "EURUSD=X", "binance": "EURUSDT", "name": "Euro / US Dollar", "digits": 5, "pip_size": 0.0001},
    "GBPUSD": {"yahoo": "GBPUSD=X", "binance": "GBPUSDT", "name": "British Pound / US Dollar", "digits": 5, "pip_size": 0.0001},
    "USDJPY": {"yahoo": "JPY=X", "binance": None, "name": "US Dollar / Japanese Yen", "digits": 3, "pip_size": 0.01},
    "GBPJPY": {"yahoo": "GBPJPY=X", "binance": None, "name": "British Pound / Japanese Yen", "digits": 3, "pip_size": 0.01},
    "EURJPY": {"yahoo": "EURJPY=X", "binance": None, "name": "Euro / Japanese Yen", "digits": 3, "pip_size": 0.01},
    "USDCAD": {"yahoo": "CAD=X", "binance": None, "name": "US Dollar / Canadian Dollar", "digits": 5, "pip_size": 0.0001},
    "USDCHF": {"yahoo": "CHF=X", "binance": None, "name": "US Dollar / Swiss Franc", "digits": 5, "pip_size": 0.0001},
    "AUDUSD": {"yahoo": "AUDUSD=X", "binance": None, "name": "Australian Dollar / US Dollar", "digits": 5, "pip_size": 0.0001},
    "NZDUSD": {"yahoo": "NZDUSD=X", "binance": None, "name": "New Zealand Dollar / US Dollar", "digits": 5, "pip_size": 0.0001},
    "BTCUSD": {"yahoo": "BTC-USD", "binance": "BTCUSDT", "name": "Bitcoin / US Dollar", "digits": 2, "pip_size": 1.0},
    "ETHUSD": {"yahoo": "ETH-USD", "binance": "ETHUSDT", "name": "Ethereum / US Dollar", "digits": 2, "pip_size": 0.1},
}


def _init_mt5_terminal() -> bool:
    """Attempts to connect to open MT5 terminal or common installation paths."""
    try:
        import MetaTrader5 as mt5
        # 1. Try default connection to already running MT5
        if mt5.initialize():
            return True

        # 2. Try common broker default paths
        common_paths = [
            r"C:\Program Files\MetaTrader 5\terminal64.exe",
            r"C:\Program Files\MetaTrader 5 IC Markets (SC)\terminal64.exe",
            r"C:\Program Files\Exness MetaTrader 5\terminal64.exe",
            r"C:\Program Files\Five Percent Online MetaTrader 5\terminal64.exe",
            r"C:\Program Files\The5ers MT5\terminal64.exe",
            r"C:\Program Files\FTMO MetaTrader 5\terminal64.exe",
            r"C:\Program Files\XM Global MT5\terminal64.exe",
            r"C:\Program Files (x86)\MetaTrader 5\terminal64.exe"
        ]
        custom_path = os.environ.get("MT5_PATH")
        if custom_path and os.path.exists(custom_path):
            common_paths.insert(0, custom_path)

        for path in common_paths:
            if os.path.exists(path):
                if mt5.initialize(path=path):
                    return True
    except Exception as e:
        print(f"[MT5 Connector] Warning: {e}")
    return False


def _get_mt5_symbol_name(symbol: str) -> Optional[str]:
    """Finds exact or mapped symbol name in MT5 terminal across all brokers and suffixes, and automatically adds to Market Watch."""
    try:
        import MetaTrader5 as mt5
        if not _init_mt5_terminal():
            return None
        
        sym_clean = symbol.upper().strip()
        
        # 1. Exact match
        info = mt5.symbol_info(sym_clean)
        if info:
            if not info.visible:
                mt5.symbol_select(sym_clean, True)
            return sym_clean
            
        # 2. Check all available symbols on the broker server
        all_syms_obj = mt5.symbols_get()
        if not all_syms_obj:
            return None
            
        all_syms = [s.name for s in all_syms_obj]

        # Alias map for Gold, Indices, and Crypto
        alias_map = {
            "XAUUSD": ["GOLD", "XAUUSD", "XAU/USD"],
            "JPN225": ["JP225", "NIKKEI", "JPN225", "N225", "JP225Cash"],
            "UK100": ["FTSE", "UK100", "FTSE100", "UK100Cash"],
            "US30": ["DJ30", "WALLSTREET", "US30", "US30Cash", "WS30"],
            "NAS100": ["USTEC", "NAS100", "NASDAQ", "US100", "NAS100Cash"],
            "BTCUSD": ["BITCOIN", "BTCUSD", "BTCUSDT"]
        }

        check_names = alias_map.get(sym_clean, [sym_clean])
        candidates = []
        for name in check_names:
            candidates.extend([
                name,
                f"{name}m",
                f"{name}.raw",
                f"{name}c",
                f"{name}pro",
                f"{name}_i",
                f"{name}.ecn",
                f"{name}.s",
                f"{name}!"
            ])

        for c in candidates:
            if c in all_syms:
                mt5.symbol_select(c, True)
                return c

        # 3. Case-insensitive contains match
        for s in all_syms:
            s_up = s.upper()
            for name in check_names:
                if name == s_up or name in s_up:
                    mt5.symbol_select(s, True)
                    return s

        # 4. Wildcard match on server
        wildcard_matches = mt5.symbols_get(f"*{sym_clean}*")
        if wildcard_matches and len(wildcard_matches) > 0:
            target_name = wildcard_matches[0].name
            mt5.symbol_select(target_name, True)
            return target_name
    except Exception as e:
        print(f"Error resolving MT5 symbol for {symbol}: {e}")
    return None


def fetch_mt5_history(symbol: str, timeframe_str: str = "M5", count: int = 15000) -> List[Dict[str, Any]]:
    """Fetches high-precision historical bars directly from connected MT5 terminal."""
    try:
        import MetaTrader5 as mt5
        if not _init_mt5_terminal():
            return []
            
        mt5_sym = _get_mt5_symbol_name(symbol)
        if not mt5_sym:
            return []
        mt5.symbol_select(mt5_sym, True)
            
        tf_map = {
            "M1": mt5.TIMEFRAME_M1,
            "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30,
            "H1": mt5.TIMEFRAME_H1,
            "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1,
            "W1": mt5.TIMEFRAME_W1,
        }
        tf = tf_map.get(timeframe_str.upper(), mt5.TIMEFRAME_M5)
        rates = mt5.copy_rates_from_pos(mt5_sym, tf, 0, count)
        if rates is None or len(rates) == 0:
            return []
            
        candles = []
        for r in rates:
            candles.append({
                "time": int(r["time"]),
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"]),
                "volume": float(r["tick_volume"])
            })
        candles.sort(key=lambda x: x["time"])
        return candles
    except Exception as e:
        print(f"Error fetching from MT5 for {symbol} ({timeframe_str}): {e}")
        return []


def get_available_symbols() -> List[Dict[str, Any]]:
    """Returns list of all available symbols from connected MT5 terminal, cached files, and mappings."""
    symbols_dict = {}

    # 1. Pull live symbols from MT5 terminal if connected
    try:
        import MetaTrader5 as mt5
        if _init_mt5_terminal():
            mt5_symbols = mt5.symbols_get()
            if mt5_symbols:
                for s in mt5_symbols:
                    raw_name = s.name.strip()
                    desc = s.description or raw_name
                    digits = s.digits
                    pip_size = s.point * 10 if digits in (3, 5) else s.point
                    path = s.path or ""
                    
                    symbols_dict[raw_name] = {
                        "symbol": raw_name,
                        "name": desc,
                        "digits": digits,
                        "pip_size": round(pip_size, 6),
                        "source": "MT5",
                        "path": path,
                        "visible": s.visible,
                        "is_cached": False
                    }
    except Exception as e:
        print(f"Error fetching symbols from MT5: {e}")

    # 2. Check cached files in data/
    cached_files = [f for f in os.listdir(DATA_DIR) if f.endswith(".json")]
    cached_symbols = set()
    for f in cached_files:
        parts = f.replace(".json", "").split("_")
        if len(parts) >= 1:
            cached_symbols.add(parts[0])

    for sym in cached_symbols:
        if sym in symbols_dict:
            symbols_dict[sym]["is_cached"] = True
        else:
            symbols_dict[sym] = {
                "symbol": sym,
                "name": f"{sym} (Cached)",
                "digits": 2,
                "pip_size": 0.01,
                "source": "CACHE",
                "path": "Local Cache",
                "visible": True,
                "is_cached": True
            }

    # 3. Ensure standard majors & mappings are included
    for sym, info in SYMBOL_MAPPINGS.items():
        if sym not in symbols_dict:
            symbols_dict[sym] = {
                "symbol": sym,
                "name": info["name"],
                "digits": info["digits"],
                "pip_size": info["pip_size"],
                "source": "MAPPING",
                "path": "Forex/Metals",
                "visible": False,
                "is_cached": sym in cached_symbols
            }
        else:
            if not symbols_dict[sym]["name"] or symbols_dict[sym]["name"] == sym:
                symbols_dict[sym]["name"] = info["name"]

    res = list(symbols_dict.values())
    
    # Priority Sorting: Gold / Metals first, then Forex Majors, then Indices, Crypto, Exotics
    def sort_key(x):
        sym = x["symbol"].upper()
        if "XAU" in sym or "GOLD" in sym:
            return (0, sym)
        if sym in ("EURUSD", "GBPUSD", "USDJPY", "USDCAD", "AUDUSD", "USDCHF", "NZDUSD", "GBPJPY", "EURJPY"):
            return (1, sym)
        if any(idx in sym for idx in ("US30", "NAS100", "JPN225", "UK100", "GER40", "SPX500", "USTEC")):
            return (2, sym)
        if any(c in sym for c in ("BTC", "ETH", "SOL")):
            return (3, sym)
        return (4, sym)

    res.sort(key=sort_key)
    return res


def fetch_yahoo_history(symbol: str, interval: str = "5m", range_period: str = "60d") -> List[Dict[str, Any]]:
    """
    Fetch OHLCV data from Yahoo Finance API directly using requests.
    Valid intervals: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo
    """
    yahoo_sym = SYMBOL_MAPPINGS.get(symbol, {}).get("yahoo", symbol)
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_sym}"
    params = {
        "range": range_period,
        "interval": interval,
        "includePrePost": "false",
        "events": "div,splits"
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=12)
        if resp.status_code != 200:
            return []
        
        data = resp.json()
        result = data.get("chart", {}).get("result", [])
        if not result:
            return []
        
        res = result[0]
        timestamps = res.get("timestamp", [])
        indicators = res.get("indicators", {}).get("quote", [{}])[0]
        
        opens = indicators.get("open", [])
        highs = indicators.get("high", [])
        lows = indicators.get("low", [])
        closes = indicators.get("close", [])
        volumes = indicators.get("volume", [])
        
        candles = []
        for i in range(len(timestamps)):
            if (
                timestamps[i] is not None
                and opens[i] is not None
                and highs[i] is not None
                and lows[i] is not None
                and closes[i] is not None
            ):
                candles.append({
                    "time": int(timestamps[i]),
                    "open": float(opens[i]),
                    "high": float(highs[i]),
                    "low": float(lows[i]),
                    "close": float(closes[i]),
                    "volume": float(volumes[i]) if volumes and volumes[i] is not None else 0.0
                })
        
        candles.sort(key=lambda x: x["time"])
        return candles
    except Exception as e:
        print(f"Error fetching from Yahoo Finance for {symbol}: {e}")
        return []


def fetch_binance_history(symbol: str, interval: str = "5m", limit: int = 1000) -> List[Dict[str, Any]]:
    """Fetch OHLCV data from Binance Public API."""
    binance_sym = SYMBOL_MAPPINGS.get(symbol, {}).get("binance")
    if not binance_sym:
        return []
    
    url = "https://api.binance.com/api/v3/klines"
    params = {
        "symbol": binance_sym,
        "interval": interval,
        "limit": limit
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code != 200:
            return []
        data = resp.json()
        candles = []
        for item in data:
            candles.append({
                "time": int(item[0] // 1000),
                "open": float(item[1]),
                "high": float(item[2]),
                "low": float(item[3]),
                "close": float(item[4]),
                "volume": float(item[5])
            })
        candles.sort(key=lambda x: x["time"])
        return candles
    except Exception as e:
        print(f"Error fetching from Binance for {symbol}: {e}")
        return []


def resample_candles(base_candles: List[Dict[str, Any]], target_seconds: int) -> List[Dict[str, Any]]:
    """
    Resamples smaller timeframe candles (e.g. M5: 300s, M15: 900s) into larger timeframe candles (e.g. H1: 3600s, H4: 14400s).
    """
    if not base_candles:
        return []
    
    resampled = []
    current_bucket_time = None
    current_candle = None
    
    for c in base_candles:
        t = c["time"]
        bucket_time = (t // target_seconds) * target_seconds
        
        if current_bucket_time != bucket_time:
            if current_candle is not None:
                resampled.append(current_candle)
            current_bucket_time = bucket_time
            current_candle = {
                "time": bucket_time,
                "open": c["open"],
                "high": c["high"],
                "low": c["low"],
                "close": c["close"],
                "volume": c.get("volume", 0.0)
            }
        else:
            current_candle["high"] = max(current_candle["high"], c["high"])
            current_candle["low"] = min(current_candle["low"], c["low"])
            current_candle["close"] = c["close"]
            current_candle["volume"] += c.get("volume", 0.0)
            
    if current_candle is not None:
        resampled.append(current_candle)
        
    return resampled


def resample_to_timeframe(base_candles: List[Dict[str, Any]], target_tf: str) -> List[Dict[str, Any]]:
    """
    Resamples smaller timeframe candles into any target timeframe:
    M1, M5, M15, M30, H1, H4, D1, W1.
    """
    if not base_candles:
        return []
    target_tf_upper = target_tf.upper().strip()
    target_seconds = TIMEFRAME_SECONDS.get(target_tf_upper, 900)
    
    if target_tf_upper == "W1":
        # Weekly grouping starting Monday 00:00:00 UTC
        resampled = []
        current_monday_ts = None
        current_candle = None
        for c in base_candles:
            t = c["time"]
            dt = datetime.fromtimestamp(t, tz=timezone.utc)
            monday_dt = dt - timedelta(days=dt.weekday(), hours=dt.hour, minutes=dt.minute, seconds=dt.second)
            monday_ts = int(monday_dt.timestamp())
            
            if current_monday_ts != monday_ts:
                if current_candle is not None:
                    resampled.append(current_candle)
                current_monday_ts = monday_ts
                current_candle = {
                    "time": monday_ts,
                    "open": c["open"],
                    "high": c["high"],
                    "low": c["low"],
                    "close": c["close"],
                    "volume": c.get("volume", 0.0)
                }
            else:
                current_candle["high"] = max(current_candle["high"], c["high"])
                current_candle["low"] = min(current_candle["low"], c["low"])
                current_candle["close"] = c["close"]
                current_candle["volume"] += c.get("volume", 0.0)
                
        if current_candle is not None:
            resampled.append(current_candle)
        return resampled
    else:
        return resample_candles(base_candles, target_seconds=target_seconds)


def build_forming_candle(completed_candles: List[Dict[str, Any]], base_candles_slice: List[Dict[str, Any]], target_tf: str) -> List[Dict[str, Any]]:
    """
    Builds the real-time forming candle for target_tf using base_candles_slice.
    Returns completed candles + 1 forming candle if in-progress.
    """
    if not base_candles_slice:
        return completed_candles
        
    curr_t = base_candles_slice[-1]["time"]
    target_tf_upper = target_tf.upper().strip()
    target_seconds = TIMEFRAME_SECONDS.get(target_tf_upper, 3600)
    
    if target_tf_upper == "W1":
        dt = datetime.fromtimestamp(curr_t, tz=timezone.utc)
        monday_dt = dt - timedelta(days=dt.weekday(), hours=dt.hour, minutes=dt.minute, seconds=dt.second)
        bucket_start = int(monday_dt.timestamp())
    else:
        bucket_start = (curr_t // target_seconds) * target_seconds
        
    # All completed candles strictly before current bucket (scan backwards from tail for O(1) speed)
    cutoff = len(completed_candles)
    while cutoff > 0 and completed_candles[cutoff - 1]["time"] >= bucket_start:
        cutoff -= 1
    start_idx = max(0, cutoff - 1500)
    result = list(completed_candles[start_idx:cutoff])
    
    # Slice of base candles in current forming bucket (scan backwards from tail)
    forming_slice = []
    for i in range(len(base_candles_slice) - 1, -1, -1):
        c = base_candles_slice[i]
        t = c["time"]
        if t < bucket_start:
            break
        if t <= curr_t:
            forming_slice.append(c)
    forming_slice.reverse()
    if forming_slice:
        forming_candle = {
            "time": bucket_start,
            "open": forming_slice[0]["open"],
            "high": max(c["high"] for c in forming_slice),
            "low": min(c["low"] for c in forming_slice),
            "close": forming_slice[-1]["close"],
            "volume": sum(c.get("volume", 0.0) for c in forming_slice),
            "is_forming": True
        }
        result.append(forming_candle)
    elif completed_candles and completed_candles[-1]["time"] == bucket_start:
        result.append(completed_candles[-1])
        
    return result


def parse_mt5_csv(file_content: str) -> List[Dict[str, Any]]:
    """
    Parses standard MT5 exported CSV bar data (Tab, comma, or semicolon separated).
    """
    candles = []
    lines = file_content.strip().splitlines()
    if not lines:
        return []
    
    delimiter = '\t' if '\t' in lines[0] else (',' if ',' in lines[0] else ';')
    reader = csv.reader(lines, delimiter=delimiter)
    header = [h.strip().upper().replace('<', '').replace('>', '') for h in next(reader, [])]
    
    date_idx = header.index("DATE") if "DATE" in header else 0
    time_idx = header.index("TIME") if "TIME" in header else (1 if "TIME" in header else None)
    open_idx = header.index("OPEN") if "OPEN" in header else 2
    high_idx = header.index("HIGH") if "HIGH" in header else 3
    low_idx = header.index("LOW") if "LOW" in header else 4
    close_idx = header.index("CLOSE") if "CLOSE" in header else 5
    vol_idx = header.index("TICKVOL") if "TICKVOL" in header else (header.index("VOL") if "VOL" in header else -1)
    
    for row in reader:
        if not row or len(row) < 5:
            continue
        try:
            if time_idx is not None and time_idx != date_idx:
                date_str = f"{row[date_idx].strip()} {row[time_idx].strip()}"
            else:
                date_str = row[date_idx].strip()
            
            dt = None
            for fmt in ("%Y.%m.%d %H:%M:%S", "%Y.%m.%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S"):
                try:
                    dt = datetime.strptime(date_str, fmt)
                    break
                except ValueError:
                    pass
            
            if dt is None:
                continue
                
            ts = int(dt.replace(tzinfo=timezone.utc).timestamp())
            o = float(row[open_idx])
            h = float(row[high_idx])
            l = float(row[low_idx])
            c = float(row[close_idx])
            v = float(row[vol_idx]) if vol_idx != -1 and len(row) > vol_idx else 100.0
            
            candles.append({
                "time": ts,
                "open": o,
                "high": h,
                "low": l,
                "close": c,
                "volume": v
            })
        except Exception:
            continue
            
    candles.sort(key=lambda x: x["time"])
    return candles


def generate_realistic_mock_data(symbol: str, count: int = 10000, interval_seconds: int = 300) -> List[Dict[str, Any]]:
    """Generates high quality, realistic candlestick data with realistic trends and swings."""
    import math
    import random
    
    now = int(time.time())
    start_time = now - (count * interval_seconds)
    
    initial_prices = {
        "XAUUSD": 2850.50,
        "EURUSD": 1.08450,
        "GBPUSD": 1.29320,
        "USDJPY": 152.400,
        "BTCUSD": 96500.0,
        "ETHUSD": 2750.0,
    }
    
    price = initial_prices.get(symbol, 100.0)
    volatility = price * 0.0012
    
    candles = []
    trend = 0.0
    
    for i in range(count):
        t = start_time + (i * interval_seconds)
        
        if i % 30 == 0:
            trend = random.uniform(-0.0006, 0.0006) * price
            
        noise = random.gauss(0, volatility)
        cycle = math.sin(i / 20.0) * volatility * 1.2
        
        delta = trend + noise + (cycle * 0.2)
        c_open = price
        c_close = c_open + delta
        
        c_high = max(c_open, c_close) + abs(random.gauss(0, volatility * 0.5))
        c_low = min(c_open, c_close) - abs(random.gauss(0, volatility * 0.5))
        c_vol = int(random.uniform(500, 3500))
        
        candles.append({
            "time": t,
            "open": round(c_open, 5),
            "high": round(c_high, 5),
            "low": round(c_low, 5),
            "close": round(c_close, 5),
            "volume": c_vol
        })
        price = c_close
        
    return candles


def get_symbol_dataset(symbol: str, timeframe_pair: str = "H1_M5", count: int = 15000) -> Dict[str, Any]:
    """
    Returns synced datasets for given timeframe pair:
    - If 'H1_M5': execution is M5 (300s), macro is H1 (3600s).
    - If 'H4_M15': execution is M15 (900s), macro is H4 (14400s).
    - If 'H4_H1': execution is H1 (3600s), macro is H4 (14400s) [AGENTS.md Forex Majors Standard].
    """
    tf_upper = (timeframe_pair or "H4_M15").upper().strip()
    is_m5_mode = (tf_upper == "H1_M5")
    is_h1_mode = (tf_upper == "H4_H1")
    if is_m5_mode:
        base_tf_str, base_seconds = "M5", 300
        macro_tf_str, macro_seconds = "H1", 3600
        yh_int, bn_int = "5m", "5m"
    elif is_h1_mode:
        base_tf_str, base_seconds = "H1", 3600
        macro_tf_str, macro_seconds = "H4", 14400
        yh_int, bn_int = "1h", "1h"
    else:
        base_tf_str, base_seconds = "M15", 900
        macro_tf_str, macro_seconds = "H4", 14400
        yh_int, bn_int = "15m", "15m"
        tf_upper = "H4_M15"
    
    cache_file = os.path.join(DATA_DIR, f"{symbol}_{base_tf_str}.json")
    base_candles = []
    
    # 1. First priority: Try fetching live high-precision data from MT5 terminal
    base_candles = fetch_mt5_history(symbol, timeframe_str=base_tf_str, count=count)
    
    # 2. If MT5 empty, try Yahoo Finance
    if not base_candles or len(base_candles) < 500:
        base_candles = fetch_yahoo_history(symbol, interval=yh_int, range_period="730d" if is_h1_mode else "60d")
        
    # 3. If still empty, try Binance (Crypto)
    if not base_candles or len(base_candles) < 500:
        base_candles = fetch_binance_history(symbol, interval=bn_int, limit=1000)
        
    # 4. Check local cache file (or resample from M15 cache if H1 cache missing)
    if (not base_candles or len(base_candles) < 500) and os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cached_data = json.load(f)
            if cached_data and len(cached_data) > 0:
                base_candles = cached_data
        except Exception as e:
            print(f"Error loading cache for {symbol} {base_tf_str}: {e}")
    if is_h1_mode and (not base_candles or len(base_candles) < 200):
        m15_cache = os.path.join(DATA_DIR, f"{symbol}_M15.json")
        if os.path.exists(m15_cache):
            try:
                with open(m15_cache, "r", encoding="utf-8") as f:
                    m15_data = json.load(f)
                if m15_data:
                    base_candles = resample_candles(m15_data, target_seconds=3600)
            except Exception:
                pass
            
    # 5. Fallback to realistic synthetic generator
    if not base_candles or len(base_candles) < 200:
        base_candles = generate_realistic_mock_data(symbol, count=count, interval_seconds=base_seconds)
        
    # Save cache file if we got good data
    if base_candles and len(base_candles) >= 200:
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(base_candles, f)
        except Exception:
            pass
            
    # Resample to macro timeframe
    macro_candles = resample_candles(base_candles, target_seconds=macro_seconds)
    
    # Also generate H4 and D1 for convenience
    h4_candles = resample_candles(base_candles, target_seconds=14400)
    d1_candles = resample_candles(base_candles, target_seconds=86400)
    h1_candles = base_candles if is_h1_mode else resample_candles(base_candles, target_seconds=3600)
    
    return {
        "timeframe_pair": tf_upper,
        "exec_timeframe": base_tf_str,
        "macro_timeframe": macro_tf_str,
        "sub_candles": base_candles,
        "macro_candles": macro_candles,
        # Keep backward compatibility keys
        "M5": base_candles if is_m5_mode else [],
        "M15": base_candles,
        "H1": h1_candles,
        "H4": h4_candles,
        "D1": d1_candles
    }


def fetch_realtime_dataset(symbol: str, timeframe_pair: str = "H4_M15", count: int = 3000) -> Dict[str, Any]:
    """
    Fetches live real-time multi-timeframe bars for Real-Time Forecast Mode.
    Priority:
      1. Connected MetaTrader 5 Terminal (Live Broker Server Time & Ticks)
      2. Yahoo Finance Live Intraday Feed (15m / 5m / 1h)
      3. Binance Public Live API (PAXGUSDT / FX / Crypto)
      4. Local Cached Dataset fallback
    """
    sym = symbol.upper().strip()
    tf_upper = (timeframe_pair or "H4_M15").upper().strip()
    is_m5_mode = (tf_upper == "H1_M5")
    is_h1_mode = (tf_upper == "H4_H1")
    if is_m5_mode:
        base_tf_str, base_seconds = "M5", 300
        macro_tf_str, macro_seconds = "H1", 3600
        yh_int, bn_int = "5m", "5m"
    elif is_h1_mode:
        base_tf_str, base_seconds = "H1", 3600
        macro_tf_str, macro_seconds = "H4", 14400
        yh_int, bn_int = "1h", "1h"
    else:
        base_tf_str, base_seconds = "M15", 900
        macro_tf_str, macro_seconds = "H4", 14400
        yh_int, bn_int = "15m", "15m"
        tf_upper = "H4_M15"

    sub_candles: List[Dict[str, Any]] = []
    macro_candles: List[Dict[str, Any]] = []
    source = "LOCAL_CACHE"

    # 1. Try Live MT5 Terminal
    mt5_sub = fetch_mt5_history(sym, timeframe_str=base_tf_str, count=count)
    if mt5_sub and len(mt5_sub) >= 150:
        sub_candles = mt5_sub
        mt5_macro = fetch_mt5_history(sym, timeframe_str=macro_tf_str, count=min(1500, count))
        macro_candles = mt5_macro if (mt5_macro and len(mt5_macro) >= 40) else resample_candles(sub_candles, target_seconds=macro_seconds)
        source = "MT5_LIVE"

    # 2. Try Live Yahoo Finance Intraday Feed
    if not sub_candles:
        yh_sub = fetch_yahoo_history(sym, interval=yh_int, range_period="730d" if is_h1_mode else "60d")
        if yh_sub and len(yh_sub) >= 150:
            sub_candles = yh_sub
            macro_candles = resample_candles(sub_candles, target_seconds=macro_seconds)
            source = "YAHOO_LIVE"

    # 3. Try Live Binance API
    if not sub_candles:
        bn_sub = fetch_binance_history(sym, interval=bn_int, limit=1000)
        if bn_sub and len(bn_sub) >= 150:
            sub_candles = bn_sub
            macro_candles = resample_candles(sub_candles, target_seconds=macro_seconds)
            source = "BINANCE_LIVE"

    # 4. Fallback to get_symbol_dataset (Cache / Synthetic)
    if not sub_candles:
        ds = get_symbol_dataset(sym, timeframe_pair=tf_upper, count=count)
        sub_candles = ds.get("sub_candles", [])
        macro_candles = ds.get("macro_candles", [])
        source = "CACHE_SIM"

    return {
        "symbol": sym,
        "source": source,
        "timeframe_pair": tf_upper,
        "exec_tf": base_tf_str,
        "macro_tf": macro_tf_str,
        "sub_candles": sub_candles,
        "macro_candles": macro_candles,
        "latest_time": sub_candles[-1]["time"] if sub_candles else int(time.time()),
        "latest_price": sub_candles[-1]["close"] if sub_candles else 0.0,
    }


def get_triplet_dataset(
    symbol: str, 
    tf1: str = "H4", 
    tf2: str = "H1", 
    tf3: str = "M15", 
    count: int = 40000
) -> Dict[str, Any]:
    """
    Returns synced datasets for 3 simultaneous timeframes:
      - tf1 (Macro / High, e.g. H4, D1, W1)
      - tf2 (Structure / Medium, e.g. H1, M15)
      - tf3 (Trigger / Micro, e.g. M15, M5, M1)
    All 3 timeframes are synthesized from base atomic timeframe (M1 or M5).
    """
    sym = symbol.upper().strip()
    tf1_u, tf2_u, tf3_u = tf1.upper().strip(), tf2.upper().strip(), tf3.upper().strip()
    
    # Determine base atomic timeframe needed
    tfs = [tf1_u, tf2_u, tf3_u]
    if "M1" in tfs:
        base_tf = "M1"
    elif "M5" in tfs:
        base_tf = "M5"
    else:
        base_tf = "M5"  # M5 provides high resolution for M15, H1, H4, D1
        
    cache_file = os.path.join(DATA_DIR, f"{sym}_{base_tf}.json")
    base_candles: List[Dict[str, Any]] = []
    source = "LOCAL_CACHE"
    
    # 1. First priority: Live connected MT5 Terminal
    mt5_candles = fetch_mt5_history(sym, timeframe_str=base_tf, count=count)
    if mt5_candles and len(mt5_candles) >= 200:
        base_candles = mt5_candles
        source = "MT5_TERMINAL"
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(base_candles, f)
        except Exception:
            pass
            
    # 2. Local cache
    if not base_candles and os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cached_data = json.load(f)
            if cached_data and len(cached_data) >= 100:
                base_candles = cached_data
                source = "LOCAL_CACHE"
        except Exception as e:
            print(f"Error loading cache for {sym}_{base_tf}: {e}")
            
    # 3. Fallback to existing M15/M5 caches if base missing
    if not base_candles:
        for fallback_tf in ("M5", "M15"):
            alt_cache = os.path.join(DATA_DIR, f"{sym}_{fallback_tf}.json")
            if os.path.exists(alt_cache):
                try:
                    with open(alt_cache, "r", encoding="utf-8") as f:
                        alt_data = json.load(f)
                    if alt_data and len(alt_data) >= 100:
                        base_candles = alt_data
                        base_tf = fallback_tf
                        source = f"CACHE_{fallback_tf}"
                        break
                except Exception:
                    pass
                    
    # 4. Yahoo Finance
    if not base_candles:
        interval = "1m" if base_tf == "M1" else ("5m" if base_tf == "M5" else "15m")
        base_candles = fetch_yahoo_history(sym, interval=interval, range_period="60d")
        if base_candles:
            source = "YAHOO"
            
    # 5. Binance (Crypto)
    if not base_candles:
        interval = "1m" if base_tf == "M1" else ("5m" if base_tf == "M5" else "15m")
        base_candles = fetch_binance_history(sym, interval=interval, limit=1000)
        if base_candles:
            source = "BINANCE"
            
    # 6. Fallback to realistic mock generator
    if not base_candles or len(base_candles) < 200:
        base_candles = generate_realistic_mock_data(sym, count=min(count, 10000), interval_seconds=TIMEFRAME_SECONDS.get(base_tf, 300))
        source = "MOCK_GENERATOR"
        
    # Resample to the 3 target timeframes
    candles_tf1 = resample_to_timeframe(base_candles, tf1_u)
    candles_tf2 = resample_to_timeframe(base_candles, tf2_u)
    candles_tf3 = resample_to_timeframe(base_candles, tf3_u)
    
    sym_info = SYMBOL_MAPPINGS.get(sym, {"digits": 2, "pip_size": 0.1, "name": sym})
    
    return {
        "symbol": sym,
        "name": sym_info.get("name", sym),
        "digits": sym_info.get("digits", 2),
        "pip_size": sym_info.get("pip_size", 0.1),
        "source": source,
        "base_tf": base_tf,
        "base_candles": base_candles,
        "tf1": tf1_u,
        "tf2": tf2_u,
        "tf3": tf3_u,
        "candles_tf1": candles_tf1,
        "candles_tf2": candles_tf2,
        "candles_tf3": candles_tf3,
        "total_base_bars": len(base_candles),
    }
