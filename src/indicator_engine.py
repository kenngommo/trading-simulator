"""
Technical Indicator Calculation Engine for Trading Simulator.
Calculates EMA, SMA, Bollinger Bands, RSI, MACD, Stochastic (5,3,3),
and Divergence Detection (Regular & Hidden) across Price, RSI, and Stochastic.
Supports dynamic expanding warmup so indicators ALWAYS draw even with fewer bars.
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
import math


def calculate_sma(candles: List[Dict[str, Any]], period: int = 20, source_key: str = "close") -> List[Dict[str, Any]]:
    """Calculates Simple Moving Average with dynamic expanding warmup."""
    results = []
    if not candles:
        return results
    
    values = [c[source_key] for c in candles]
    times = [c["time"] for c in candles]
    
    for i in range(len(candles)):
        p = min(i + 1, period)
        window = values[i - p + 1 : i + 1]
        sma_val = sum(window) / p
        results.append({
            "time": times[i],
            "value": round(sma_val, 5)
        })
    return results


def calculate_ema(candles: List[Dict[str, Any]], period: int = 20, source_key: str = "close") -> List[Dict[str, Any]]:
    """Calculates Exponential Moving Average with dynamic warmup (always draws)."""
    results = []
    if not candles:
        return results
    
    values = [c[source_key] for c in candles]
    times = [c["time"] for c in candles]
    
    current_ema = values[0]
    results.append({"time": times[0], "value": round(current_ema, 5)})
    
    for i in range(1, len(candles)):
        # Dynamic smoothing factor that adapts during warmup
        effective_period = min(i + 1, period)
        multiplier = 2.0 / (effective_period + 1)
        current_ema = (values[i] - current_ema) * multiplier + current_ema
        results.append({"time": times[i], "value": round(current_ema, 5)})
        
    return results


def calculate_bollinger_bands(candles: List[Dict[str, Any]], period: int = 20, std_dev: float = 2.0) -> Dict[str, List[Dict[str, Any]]]:
    """Calculates Bollinger Bands (Upper, Middle, Lower)."""
    middle = []
    upper = []
    lower = []
    
    if not candles:
        return {"middle": middle, "upper": upper, "lower": lower}
        
    closes = [c["close"] for c in candles]
    times = [c["time"] for c in candles]
    
    for i in range(len(candles)):
        p = min(i + 1, period)
        window = closes[i - p + 1 : i + 1]
        mean = sum(window) / p
        variance = sum((x - mean) ** 2 for x in window) / p if p > 1 else 0.0
        std = math.sqrt(variance)
        
        t = times[i]
        mid_val = mean
        up_val = mean + (std * std_dev)
        low_val = mean - (std * std_dev)
        
        middle.append({"time": t, "value": round(mid_val, 5)})
        upper.append({"time": t, "value": round(up_val, 5)})
        lower.append({"time": t, "value": round(low_val, 5)})
        
    return {"middle": middle, "upper": upper, "lower": lower}


def calculate_rsi(candles: List[Dict[str, Any]], period: int = 14) -> List[Dict[str, Any]]:
    """Calculates Wilder's Relative Strength Index (RSI) with dynamic warmup."""
    results = []
    if not candles:
        return results
    if len(candles) == 1:
        return [{"time": candles[0]["time"], "value": 50.0}]
        
    closes = [c["close"] for c in candles]
    times = [c["time"] for c in candles]
    
    gains = []
    losses = []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(0.0, diff))
        losses.append(max(0.0, -diff))
        
    results.append({"time": times[0], "value": 50.0})
    
    avg_gain = gains[0]
    avg_loss = losses[0]
    
    for i in range(len(gains)):
        gain = gains[i]
        loss = losses[i]
        eff_period = min(i + 1, period)
        
        avg_gain = (avg_gain * (eff_period - 1) + gain) / eff_period
        avg_loss = (avg_loss * (eff_period - 1) + loss) / eff_period
        
        if avg_loss == 0:
            rsi = 100.0 if avg_gain > 0 else 50.0
        else:
            rs = avg_gain / avg_loss
            rsi = 100.0 - (100.0 / (1.0 + rs))
            
        results.append({"time": times[i + 1], "value": round(rsi, 2)})
        
    return results


def calculate_wma(data: List[Dict[str, Any]], period: int = 45, source_key: str = "value") -> List[Dict[str, Any]]:
    """Calculates Weighted Moving Average (WMA) identically to TradingView."""
    results = []
    if not data:
        return results
    weight_sum = period * (period + 1) // 2
    for i in range(len(data)):
        if i < period - 1:
            eff_p = i + 1
            w_sum = eff_p * (eff_p + 1) // 2
            acc = sum(data[i - eff_p + 1 + k][source_key] * (k + 1) for k in range(eff_p))
            results.append({"time": data[i]["time"], "value": round(acc / w_sum, 2)})
        else:
            acc = sum(data[i - period + 1 + k][source_key] * (k + 1) for k in range(period))
            results.append({"time": data[i]["time"], "value": round(acc / weight_sum, 2)})
    return results


def calculate_rsi_ma9_wma45(candles: List[Dict[str, Any]], rsi_period: int = 14, ma9_period: int = 9, wma45_period: int = 45) -> Dict[str, Any]:
    """Calculates TV RSI (14) + SMA (9) of RSI + WMA (45) of RSI (TradingView All-in-One)."""
    rsi_data = calculate_rsi(candles, period=rsi_period)
    ma9_data = calculate_sma(rsi_data, period=ma9_period, source_key="value")
    wma45_data = calculate_wma(rsi_data, period=wma45_period, source_key="value")
    return {
        "rsi": rsi_data,
        "ma9": ma9_data,
        "wma45": wma45_data
    }


def calculate_stochastic(candles: List[Dict[str, Any]], k_period: int = 14, d_period: int = 3, smooth_k: int = 3) -> Dict[str, List[Dict[str, Any]]]:
    """Calculates Stochastic Oscillator (5, 3, 3) with dynamic warmup."""
    k_res = []
    d_res = []
    if not candles:
        return {"k": k_res, "d": d_res}
        
    raw_k = []
    times = [c["time"] for c in candles]
    
    for i in range(len(candles)):
        p = min(i + 1, k_period)
        window = candles[i - p + 1 : i + 1]
        highest_high = max(c["high"] for c in window)
        lowest_low = min(c["low"] for c in window)
        current_close = candles[i]["close"]
        
        diff = highest_high - lowest_low
        val = 50.0 if diff == 0 else ((current_close - lowest_low) / diff) * 100.0
        raw_k.append({"time": times[i], "close": val})
        
    smoothed_k = calculate_sma(raw_k, period=smooth_k, source_key="close")
    smoothed_k_dict = {x["time"]: x["value"] for x in smoothed_k}
    
    d_items = calculate_sma(smoothed_k, period=d_period, source_key="value")
    d_dict = {x["time"]: x["value"] for x in d_items}
    
    for item in smoothed_k:
        t = item["time"]
        k_res.append({"time": t, "value": round(item["value"], 2)})
        if t in d_dict:
            d_res.append({"time": t, "value": round(d_dict[t], 2)})
        else:
            d_res.append({"time": t, "value": round(item["value"], 2)})
            
    return {"k": k_res, "d": d_res}


def calculate_macd(candles: List[Dict[str, Any]], fast_period: int = 12, slow_period: int = 26, signal_period: int = 9) -> Dict[str, List[Dict[str, Any]]]:
    """Calculates MACD line, Signal line, and Histogram."""
    if not candles:
        return {"macd": [], "signal": [], "histogram": []}
        
    fast_ema = {x["time"]: x["value"] for x in calculate_ema(candles, period=fast_period)}
    slow_ema = {x["time"]: x["value"] for x in calculate_ema(candles, period=slow_period)}
    
    macd_items = []
    for c in candles:
        t = c["time"]
        if t in fast_ema and t in slow_ema:
            macd_items.append({"time": t, "close": fast_ema[t] - slow_ema[t]})
            
    signal_items = calculate_ema(macd_items, period=signal_period, source_key="close")
    signal_dict = {x["time"]: x["value"] for x in signal_items}
    
    macd_res = []
    sig_res = []
    hist_res = []
    
    for item in macd_items:
        t = item["time"]
        m_val = round(item["close"], 5)
        s_val = round(signal_dict.get(t, m_val), 5)
        h_val = round(m_val - s_val, 5)
        
        # TradingView 4-color MACD Histogram
        if h_val >= 0:
            hist_color = "#26a69a" if (len(hist_res) == 0 or h_val >= hist_res[-1]["value"]) else "#80cbc4"
        else:
            hist_color = "#ef5350" if (len(hist_res) == 0 or h_val <= hist_res[-1]["value"]) else "#ef9a9a"
            
        macd_res.append({"time": t, "value": m_val})
        sig_res.append({"time": t, "value": s_val})
        hist_res.append({"time": t, "value": h_val, "color": hist_color})
        
    return {"macd": macd_res, "signal": sig_res, "histogram": hist_res}


def detect_key_levels_and_blocks(candles: List[Dict[str, Any]], left_bars: int = 5, right_bars: int = 5) -> List[Dict[str, Any]]:
    """Detects key swing high / swing low zones."""
    levels = []
    if not candles or len(candles) < left_bars + right_bars + 1:
        return levels
        
    for i in range(left_bars, len(candles) - right_bars):
        curr = candles[i]
        is_swing_high = True
        is_swing_low = True
        
        for j in range(i - left_bars, i + right_bars + 1):
            if j == i:
                continue
            if candles[j]["high"] >= curr["high"]:
                is_swing_high = False
            if candles[j]["low"] <= curr["low"]:
                is_swing_low = False
                
        if is_swing_high:
            levels.append({
                "type": "BEARISH_OB",
                "time": curr["time"],
                "price": curr["high"],
                "price_low": curr["open"] if curr["close"] < curr["open"] else curr["close"],
                "label": "Swing High"
            })
        elif is_swing_low:
            levels.append({
                "type": "BULLISH_OB",
                "time": curr["time"],
                "price": curr["low"],
                "price_high": curr["open"] if curr["close"] > curr["open"] else curr["close"],
                "label": "Swing Low"
            })
            
    return levels[-30:]


def calculate_atr(candles: List[Dict[str, Any]], period: int = 14) -> List[Dict[str, Any]]:
    """Calculates Wilder's Average True Range (ATR)."""
    results = []
    if not candles:
        return results
    if len(candles) == 1:
        return [{"time": candles[0]["time"], "value": round(candles[0]["high"] - candles[0]["low"], 5)}]

    trs = []
    times = [c["time"] for c in candles]
    trs.append(candles[0]["high"] - candles[0]["low"])
    for i in range(1, len(candles)):
        c = candles[i]
        prev_close = candles[i - 1]["close"]
        tr = max(c["high"] - c["low"], abs(c["high"] - prev_close), abs(c["low"] - prev_close))
        trs.append(tr)

    atr = trs[0]
    results.append({"time": times[0], "value": round(atr, 5)})
    for i in range(1, len(candles)):
        eff_p = min(i + 1, period)
        atr = (atr * (eff_p - 1) + trs[i]) / eff_p
        results.append({"time": times[i], "value": round(atr, 5)})
    return results


def calculate_supertrend(candles: List[Dict[str, Any]], period: int = 10, multiplier: float = 3.0) -> Dict[str, List[Dict[str, Any]]]:
    """Calculates TradingView style Supertrend indicator."""
    if not candles:
        return {"upper": [], "lower": [], "supertrend": []}

    atr_data = calculate_atr(candles, period=period)
    atr_dict = {x["time"]: x["value"] for x in atr_data}

    upper_band = []
    lower_band = []
    supertrend = []

    prev_st = 0.0
    prev_dir = 1
    prev_upper = 0.0
    prev_lower = 0.0

    for i, c in enumerate(candles):
        t = c["time"]
        atr = atr_dict.get(t, c["high"] - c["low"])
        hl2 = (c["high"] + c["low"]) / 2.0
        basic_upper = hl2 + (multiplier * atr)
        basic_lower = hl2 - (multiplier * atr)

        if i == 0:
            final_upper = basic_upper
            final_lower = basic_lower
            direction = 1
            st_val = final_lower
        else:
            prev_c = candles[i - 1]["close"]
            final_upper = basic_upper if (basic_upper < prev_upper or prev_c > prev_upper) else prev_upper
            final_lower = basic_lower if (basic_lower > prev_lower or prev_c < prev_lower) else prev_lower

            if prev_dir == 1:
                direction = -1 if c["close"] < final_lower else 1
            else:
                direction = 1 if c["close"] > final_upper else -1

            st_val = final_lower if direction == 1 else final_upper

        upper_band.append({"time": t, "value": round(final_upper, 5)})
        lower_band.append({"time": t, "value": round(final_lower, 5)})
        supertrend.append({
            "time": t, 
            "value": round(st_val, 5), 
            "direction": direction,
            "color": "#089981" if direction == 1 else "#f23645"
        })

        prev_upper = final_upper
        prev_lower = final_lower
        prev_dir = direction
        prev_st = st_val

    return {"upper": upper_band, "lower": lower_band, "supertrend": supertrend}


def calculate_vwap(candles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Calculates Volume Weighted Average Price (VWAP) with daily session resets."""
    results = []
    if not candles:
        return results

    cum_vol = 0.0
    cum_pv = 0.0
    current_day = None

    for c in candles:
        t = c["time"]
        dt = datetime.fromtimestamp(t, tz=timezone.utc)
        day = dt.date()

        if current_day != day:
            current_day = day
            cum_vol = 0.0
            cum_pv = 0.0

        tp = (c["high"] + c["low"] + c["close"]) / 3.0
        vol = max(1.0, c.get("volume", 1.0))
        cum_vol += vol
        cum_pv += tp * vol

        vwap_val = cum_pv / cum_vol if cum_vol > 0 else tp
        results.append({"time": t, "value": round(vwap_val, 5)})

    return results


def find_swings(data: List[float], order: int = 3) -> Tuple[List[int], List[int]]:
    """Finds local high indices and low indices."""
    highs = []
    lows = []
    n = len(data)
    for i in range(order, n - order):
        val = data[i]
        if all(val >= data[j] for j in range(i - order, i + order + 1) if j != i):
            highs.append(i)
        if all(val <= data[j] for j in range(i - order, i + order + 1) if j != i):
            lows.append(i)
    return highs, lows


def detect_divergences(candles: List[Dict[str, Any]], lookback: int = 80, order: int = 3) -> Dict[str, Any]:
    """
    Detects Bullish / Bearish / Hidden Divergence across Price vs RSI (14) and Stoch (5,3,3).
    """
    if not candles or len(candles) < 20:
        return {"divergences": [], "latest_signal": None}
        
    recent = candles[-lookback:] if len(candles) >= lookback else candles
    times = [c["time"] for c in recent]
    closes = [c["close"] for c in recent]
    highs_arr = [c["high"] for c in recent]
    lows_arr = [c["low"] for c in recent]
    
    rsi_list = calculate_rsi(candles, period=14)
    rsi_dict = {x["time"]: x["value"] for x in rsi_list}
    rsi_vals = [rsi_dict.get(t, 50.0) for t in times]
    
    stoch_dict_data = calculate_stochastic(candles, k_period=5, d_period=3, smooth_k=3)
    k_dict = {x["time"]: x["value"] for x in stoch_dict_data.get("k", [])}
    stoch_vals = [k_dict.get(t, 50.0) for t in times]
    
    price_highs, price_lows = find_swings(closes, order=order)
    
    divergence_events = []
    latest_signal = None
    
    # Bullish Divergence
    if len(price_lows) >= 2:
        for i in range(len(price_lows) - 1):
            t1_idx, t2_idx = price_lows[i], price_lows[i + 1]
            if t2_idx - t1_idx < 3:
                continue
                
            p1, p2 = closes[t1_idx], closes[t2_idx]
            r1, r2 = rsi_vals[t1_idx], rsi_vals[t2_idx]
            s1, s2 = stoch_vals[t1_idx], stoch_vals[t2_idx]
            time1, time2 = times[t1_idx], times[t2_idx]
            
            div_type = None
            indicator_used = None
            
            if p2 <= p1:
                if r2 > r1 and s2 > s1:
                    div_type = "REGULAR_BULLISH"
                    indicator_used = "RSI & Stoch"
                elif r2 > r1:
                    div_type = "REGULAR_BULLISH"
                    indicator_used = "RSI"
                elif s2 > s1:
                    div_type = "REGULAR_BULLISH"
                    indicator_used = "Stoch"
            elif p2 > p1:
                if r2 < r1 and s2 < s1:
                    div_type = "HIDDEN_BULLISH"
                    indicator_used = "RSI & Stoch"
                elif r2 < r1:
                    div_type = "HIDDEN_BULLISH"
                    indicator_used = "RSI"
                elif s2 < s1:
                    div_type = "HIDDEN_BULLISH"
                    indicator_used = "Stoch"
                    
            if div_type:
                entry = closes[-1]
                lowest_point = min(lows_arr[t1_idx : t2_idx + 1])
                sl = round(lowest_point - (abs(entry - lowest_point) * 0.15 + 0.5), 2)
                sl_dist = abs(entry - sl)
                tp1 = round(entry + sl_dist * 1.5, 2)
                tp2 = round(entry + sl_dist * 2.5, 2)
                
                event = {
                    "type": div_type,
                    "side": "BUY",
                    "indicator": indicator_used,
                    "time1": time1,
                    "time2": time2,
                    "price1": p1,
                    "price2": p2,
                    "rsi1": r1,
                    "rsi2": r2,
                    "stoch1": s1,
                    "stoch2": s2,
                    "color": "#089981",
                    "entry": entry,
                    "sl": sl,
                    "tp1": tp1,
                    "tp2": tp2,
                    "label": f"🟢 {div_type.replace('_', ' ')} ({indicator_used})"
                }
                divergence_events.append(event)
                if t2_idx >= len(recent) - order - 3:
                    latest_signal = event
                    
    # Bearish Divergence
    if len(price_highs) >= 2:
        for i in range(len(price_highs) - 1):
            t1_idx, t2_idx = price_highs[i], price_highs[i + 1]
            if t2_idx - t1_idx < 3:
                continue
                
            p1, p2 = closes[t1_idx], closes[t2_idx]
            r1, r2 = rsi_vals[t1_idx], rsi_vals[t2_idx]
            s1, s2 = stoch_vals[t1_idx], stoch_vals[t2_idx]
            time1, time2 = times[t1_idx], times[t2_idx]
            
            div_type = None
            indicator_used = None
            
            if p2 >= p1:
                if r2 < r1 and s2 < s1:
                    div_type = "REGULAR_BEARISH"
                    indicator_used = "RSI & Stoch"
                elif r2 < r1:
                    div_type = "REGULAR_BEARISH"
                    indicator_used = "RSI"
                elif s2 < s1:
                    div_type = "REGULAR_BEARISH"
                    indicator_used = "Stoch"
            elif p2 < p1:
                if r2 > r1 and s2 > s1:
                    div_type = "HIDDEN_BEARISH"
                    indicator_used = "RSI & Stoch"
                elif r2 > r1:
                    div_type = "HIDDEN_BEARISH"
                    indicator_used = "RSI"
                elif s2 > s1:
                    div_type = "HIDDEN_BEARISH"
                    indicator_used = "Stoch"
                    
            if div_type:
                entry = closes[-1]
                highest_point = max(highs_arr[t1_idx : t2_idx + 1])
                sl = round(highest_point + (abs(highest_point - entry) * 0.15 + 0.5), 2)
                sl_dist = abs(sl - entry)
                tp1 = round(entry - sl_dist * 1.5, 2)
                tp2 = round(entry - sl_dist * 2.5, 2)
                
                event = {
                    "type": div_type,
                    "side": "SELL",
                    "indicator": indicator_used,
                    "time1": time1,
                    "time2": time2,
                    "price1": p1,
                    "price2": p2,
                    "rsi1": r1,
                    "rsi2": r2,
                    "stoch1": s1,
                    "stoch2": s2,
                    "color": "#f23645",
                    "entry": entry,
                    "sl": sl,
                    "tp1": tp1,
                    "tp2": tp2,
                    "label": f"🔴 {div_type.replace('_', ' ')} ({indicator_used})"
                }
                divergence_events.append(event)
                if t2_idx >= len(recent) - order - 3:
                    latest_signal = event
                    
    # Sort strictly by time2 so charting libraries receive ascending timestamps
    divergence_events.sort(key=lambda x: x["time2"])
    return {
        "divergences": divergence_events[-8:],
        "latest_signal": latest_signal
    }


def evaluate_single_tf_pillars(candles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Evaluates the 4 pillars on a single timeframe:
    Pillar 1: EMA 5 & 12 cross / pullback hook
    Pillar 2: Stochastic (14, 3, 3)
    Pillar 3: RSI (14) + SMA (9) + WMA (45)
    Pillar 4: MACD (12, 26, 9)
    """
    if not candles or len(candles) < 20:
        return {
            "ema_str": "--", "stoch_str": "--", "rsi_str": "--", "macd_str": "--",
            "vote": "0/4", "dir": 0, "color": "#94a3b8", "bulls": 0, "bears": 0,
            "k": 50.0, "d": 50.0, "is_ob": False, "is_os": False
        }
        
    e5_list = calculate_ema(candles, 5)
    e12_list = calculate_ema(candles, 12)
    e5 = e5_list[-1]["value"]
    e12 = e12_list[-1]["value"]
    e5_prev = e5_list[-2]["value"] if len(e5_list) > 1 else e5
    e12_prev = e12_list[-2]["value"] if len(e12_list) > 1 else e12
    c = candles[-1]["close"]
    o = candles[-1]["open"]
    
    cross_up = e5_prev <= e12_prev and e5 > e12 and c >= min(e5, e12)
    cross_dn = e5_prev >= e12_prev and e5 < e12 and c <= max(e5, e12)
    
    rallied = any(candles[-i]["high"] >= max(e5_list[-i]["value"], e12_list[-i]["value"]) for i in (1, 2, 3) if i <= len(candles))
    closed_below = c < min(e5, e12) and c < o
    pullbk_dn = rallied and closed_below
    
    dipped = any(candles[-i]["low"] <= min(e5_list[-i]["value"], e12_list[-i]["value"]) for i in (1, 2, 3) if i <= len(candles))
    closed_above = c > max(e5, e12) and c > o
    pullbk_up = dipped and closed_above
    
    if cross_dn:
        ema_str = "vCROSS 5<12"
        ema_dir = -1
    elif pullbk_dn:
        ema_str = "vPULLBK*"
        ema_dir = -1
    elif e5 < e12:
        ema_str = "vEMA 5<12"
        ema_dir = -1
    elif cross_up:
        ema_str = "^CROSS 5>12"
        ema_dir = 1
    elif pullbk_up:
        ema_str = "^PULLBK*"
        ema_dir = 1
    elif e5 > e12:
        ema_str = "^EMA 5>12"
        ema_dir = 1
    else:
        ema_str = "=FLAT"
        ema_dir = 0
        
    # Pillar 2: Stochastic (14, 3, 3)
    stoch = calculate_stochastic(candles, k_period=14, d_period=3, smooth_k=3)
    k_val = stoch["k"][-1]["value"] if stoch["k"] else 50.0
    d_val = stoch["d"][-1]["value"] if stoch["d"] else 50.0
    is_ob = k_val >= 80.0 or d_val >= 80.0
    is_os = k_val <= 20.0 or d_val <= 20.0
    
    if k_val < d_val:
        stoch_dir = -1
        st_prefix = "vOB " if is_ob else "vDN "
    elif k_val > d_val:
        stoch_dir = 1
        st_prefix = "^OS " if is_os else "^UP "
    else:
        stoch_dir = 0
        st_prefix = "=FLAT "
    stoch_str = f"{st_prefix}{int(k_val)}<{int(d_val)}" if stoch_dir < 0 else f"{st_prefix}{int(k_val)}>{int(d_val)}"
    
    # Pillar 3: RSI (14) + SMA (9) + WMA (45)
    rsi_res = calculate_rsi_ma9_wma45(candles, 14, 9, 45)
    r_val = rsi_res["rsi"][-1]["value"] if rsi_res["rsi"] else 50.0
    ma9_val = rsi_res["ma9"][-1]["value"] if rsi_res["ma9"] else 50.0
    wma45_val = rsi_res["wma45"][-1]["value"] if rsi_res["wma45"] else 50.0
    
    w45_above = wma45_val > r_val and wma45_val > ma9_val
    w45_below = wma45_val < r_val and wma45_val < ma9_val
    
    if r_val < ma9_val:
        rsi_dir = -2 if w45_above else -1
        rsi_str = "v*<WMA45" if w45_above else "vRSI<MA9"
    elif r_val > ma9_val:
        rsi_dir = 2 if w45_below else 1
        rsi_str = "^*>WMA45" if w45_below else "^RSI>MA9"
    else:
        rsi_dir = 0
        rsi_str = "=FLAT"
        
    # Pillar 4: MACD (12, 26, 9)
    macd = calculate_macd(candles, 12, 26, 9)
    m_hist = macd["histogram"][-1]["value"] if macd["histogram"] else 0.0
    m_hist_prev = macd["histogram"][-2]["value"] if len(macd["histogram"]) > 1 else m_hist
    m_line = macd["macd"][-1]["value"] if macd["macd"] else 0.0
    s_line = macd["signal"][-1]["value"] if macd["signal"] else 0.0
    
    hist_falling = m_hist < m_hist_prev
    hist_rising = m_hist > m_hist_prev
    
    if hist_falling:
        macd_dir = -1
        macd_str = "vDOWN" if m_hist < 0 else "vBUY-"
    elif hist_rising:
        macd_dir = 1
        macd_str = "^UP" if m_hist > 0 else "^SEL+"
    else:
        macd_dir = 1 if m_line >= s_line else -1
        macd_str = "^UP" if macd_dir > 0 else "vDOWN"
        
    bulls = (1 if ema_dir > 0 else 0) + (1 if stoch_dir > 0 else 0) + (1 if rsi_dir > 0 else 0) + (1 if macd_dir > 0 else 0)
    bears = (1 if ema_dir < 0 else 0) + (1 if stoch_dir < 0 else 0) + (1 if rsi_dir < 0 else 0) + (1 if macd_dir < 0 else 0)
    
    if bears >= 3:
        vote = f"{bears}/4v"
        row_col = "#ef4444"
        final_dir = -1
    elif bulls >= 3:
        vote = f"{bulls}/4^"
        row_col = "#10b981"
        final_dir = 1
    else:
        vote = f"{max(bulls, bears)}/4"
        row_col = "#f59e0b"
        final_dir = 0
        
    return {
        "ema_str": ema_str,
        "stoch_str": stoch_str,
        "rsi_str": rsi_str,
        "macd_str": macd_str,
        "vote": vote,
        "dir": final_dir,
        "color": row_col,
        "bulls": bulls,
        "bears": bears,
        "k": round(k_val, 1),
        "d": round(d_val, 1),
        "is_ob": is_ob,
        "is_os": is_os
    }


def compute_4pillar_mtf_dashboard(
    symbol: str,
    candles_m5: List[Dict[str, Any]],
    candles_m15: List[Dict[str, Any]],
    candles_h1: List[Dict[str, Any]],
    candles_h4: List[Dict[str, Any]],
    candles_d1: Optional[List[Dict[str, Any]]] = None,
    radar_override: Optional[str] = None
) -> Dict[str, Any]:
    """
    Computes the 4-Pillar MTF Master Dashboard identical to TradingView:
    Columns: TF | 1.EMA 5/12 | 2.STOCH * | 3.RSI+WMA45 | 4.MACD | VOTE
    Rows: M5, M15, H1, H4, D1
    Footer & Radar Summary
    """
    p_m5 = evaluate_single_tf_pillars(candles_m5)
    p_m15 = evaluate_single_tf_pillars(candles_m15)
    p_h1 = evaluate_single_tf_pillars(candles_h1)
    p_h4 = evaluate_single_tf_pillars(candles_h4)
    p_d1 = evaluate_single_tf_pillars(candles_d1) if candles_d1 else evaluate_single_tf_pillars(candles_h4)
    
    # Master Confluence Verdict
    m15_sell = p_m15["bears"] >= 3 and p_m15["dir"] < 0
    m15_buy = p_m15["bulls"] >= 3 and p_m15["dir"] > 0
    h1_sell = p_h1["bears"] >= 3 and p_h1["dir"] < 0
    h1_buy = p_h1["bulls"] >= 3 and p_h1["dir"] > 0
    h4_sell = p_h4["bears"] >= 3 or p_h4["dir"] < 0
    h4_buy = p_h4["bulls"] >= 3 or p_h4["dir"] > 0
    
    if m15_sell and h1_sell and h4_sell:
        verdict = "STRONG SELL (M5+M15+H1+H4)" if p_m5["dir"] < 0 else "STRONG SELL (M15+H1+H4)"
        verdict_color = "#ef4444"
        verdict_bg = "rgba(239, 68, 68, 0.35)"
        sentiment = "SELL"
    elif m15_buy and h1_buy and h4_buy:
        verdict = "STRONG BUY (M5+M15+H1+H4)" if p_m5["dir"] > 0 else "STRONG BUY (M15+H1+H4)"
        verdict_color = "#10b981"
        verdict_bg = "rgba(16, 185, 129, 0.35)"
        sentiment = "BUY"
    elif m15_sell and h1_sell:
        verdict = "MODERATE SELL (M15+H1)"
        verdict_color = "#f87171"
        verdict_bg = "rgba(239, 68, 68, 0.25)"
        sentiment = "SELL"
    elif m15_buy and h1_buy:
        verdict = "MODERATE BUY (M15+H1)"
        verdict_color = "#34d399"
        verdict_bg = "rgba(16, 185, 129, 0.25)"
        sentiment = "BUY"
    else:
        verdict = "NEUTRAL / MIXED ALIGNMENT"
        verdict_color = "#94a3b8"
        verdict_bg = "rgba(100, 116, 139, 0.25)"
        sentiment = "NEUTRAL"
        
    footer_text = f"{sentiment}: M5[{p_m5['vote']}]+M15[{p_m15['vote']}]+H1[{p_h1['vote']}]+H4[{p_h4['vote']}]"
    radar_text = radar_override if radar_override else "RADAR 15M: --"
    
    return {
        "symbol": symbol,
        "title": f"[{symbol} LIVE] * {verdict}",
        "verdict": verdict,
        "verdict_color": verdict_color,
        "verdict_bg": verdict_bg,
        "sentiment": sentiment,
        "footer_text": footer_text,
        "radar_text": radar_text,
        "rows": [
            {"tf": "M5", **p_m5},
            {"tf": "M15", **p_m15},
            {"tf": "H1", **p_h1},
            {"tf": "H4", **p_h4},
            {"tf": "D1", **p_d1}
        ]
    }


def calculate_mtf_signals(candles: List[Dict[str, Any]], lookback: int = 150) -> List[Dict[str, Any]]:
    """Calculates MTF BUY and MTF SELL signals for chart markers."""
    signals = []
    if not candles or len(candles) < 35:
        return signals
        
    e5 = calculate_ema(candles, 5)
    e12 = calculate_ema(candles, 12)
    stoch = calculate_stochastic(candles, k_period=14, d_period=3, smooth_k=3)
    rsi_pack = calculate_rsi_ma9_wma45(candles, 14, 9, 45)
    macd = calculate_macd(candles, 12, 26, 9)
    
    stoch_k = {x["time"]: x["value"] for x in stoch["k"]}
    stoch_d = {x["time"]: x["value"] for x in stoch["d"]}
    rsi_v = {x["time"]: x["value"] for x in rsi_pack["rsi"]}
    ma9_v = {x["time"]: x["value"] for x in rsi_pack["ma9"]}
    macd_h = {x["time"]: x["value"] for x in macd["histogram"]}
    
    start_i = max(15, len(candles) - lookback)
    for i in range(start_i, len(candles)):
        c = candles[i]
        t = c["time"]
        e5_val = e5[i]["value"]
        e12_val = e12[i]["value"]
        e5_prev = e5[i-1]["value"]
        e12_prev = e12[i-1]["value"]
        
        k = stoch_k.get(t, 50.0)
        d = stoch_d.get(t, 50.0)
        r = rsi_v.get(t, 50.0)
        ma9 = ma9_v.get(t, 50.0)
        h = macd_h.get(t, 0.0)
        
        # Bull confluence
        is_bull_cross = e5_prev <= e12_prev and e5_val > e12_val
        is_bull_align = e5_val > e12_val and k > d and r > ma9 and h > 0
        if is_bull_cross or (is_bull_align and i % 18 == 0):
            signals.append({
                "time": t,
                "position": "belowBar",
                "color": "#10b981",
                "shape": "arrowUp",
                "text": "MTF BUY"
            })
            
        # Bear confluence
        is_bear_cross = e5_prev >= e12_prev and e5_val < e12_val
        is_bear_align = e5_val < e12_val and k < d and r < ma9 and h < 0
        if is_bear_cross or (is_bear_align and i % 18 == 0):
            signals.append({
                "time": t,
                "position": "aboveBar",
                "color": "#ef4444",
                "shape": "arrowDown",
                "text": "MTF SELL"
            })
            
    # Sort strictly by timestamp
    signals.sort(key=lambda s: s["time"])
    return signals[-15:]


