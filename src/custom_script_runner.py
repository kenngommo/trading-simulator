"""
Custom Script Runner for Trading Simulator (Pine-style Python Sandbox).
Allows users to write/paste indicator scripts with `ta.*`, `plot()`, and `marker()`
and render them live on all 3 charts in both LIVE and BACKTEST modes.
"""

import os
import math
import time
import traceback
from typing import Dict, Any, List, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CUSTOM_SCRIPTS_DIR = os.path.join(BASE_DIR, "custom_scripts")
os.makedirs(CUSTOM_SCRIPTS_DIR, exist_ok=True)


class TAHelper:
    """TradingView-like `ta.*` math helpers operating on plain Python lists of floats."""

    @staticmethod
    def sma(src: List[float], length: int) -> List[Optional[float]]:
        n = len(src)
        length = max(1, int(length))
        out: List[Optional[float]] = [None] * n
        s = 0.0
        for i in range(n):
            v = src[i] if src[i] is not None else 0.0
            s += v
            if i >= length:
                prev = src[i - length] if src[i - length] is not None else 0.0
                s -= prev
            if i >= length - 1:
                out[i] = round(s / length, 5)
        return out

    @staticmethod
    def ema(src: List[float], length: int) -> List[Optional[float]]:
        n = len(src)
        if n == 0:
            return []
        length = max(1, int(length))
        out: List[Optional[float]] = [None] * n
        cur = float(src[0] if src[0] is not None else 0.0)
        out[0] = round(cur, 5)
        for i in range(1, n):
            v = float(src[i] if src[i] is not None else cur)
            eff = min(i + 1, length)
            k = 2.0 / (eff + 1.0)
            cur = (v - cur) * k + cur
            out[i] = round(cur, 5)
        return out

    @staticmethod
    def wma(src: List[float], length: int) -> List[Optional[float]]:
        n = len(src)
        length = max(1, int(length))
        out: List[Optional[float]] = [None] * n
        denom = length * (length + 1) / 2.0
        for i in range(length - 1, n):
            num = 0.0
            for j in range(length):
                v = src[i - length + 1 + j]
                num += (float(v) if v is not None else 0.0) * (j + 1)
            out[i] = round(num / denom, 5)
        return out

    @staticmethod
    def rsi(src: List[float], length: int = 14) -> List[Optional[float]]:
        n = len(src)
        if n == 0:
            return []
        length = max(2, int(length))
        out: List[Optional[float]] = [50.0] * n
        if n < 2:
            return out
        gains = [max(0.0, src[i] - src[i - 1]) for i in range(1, n)]
        losses = [max(0.0, src[i - 1] - src[i]) for i in range(1, n)]
        avg_g = gains[0]
        avg_l = losses[0]
        for i in range(1, n):
            g = gains[i - 1]
            l = losses[i - 1]
            if i < length:
                avg_g = (avg_g * (i - 1) + g) / i
                avg_l = (avg_l * (i - 1) + l) / i
            else:
                avg_g = (avg_g * (length - 1) + g) / length
                avg_l = (avg_l * (length - 1) + l) / length
            if avg_l == 0:
                out[i] = 100.0 if avg_g > 0 else 50.0
            else:
                rs = avg_g / avg_l
                out[i] = round(100.0 - (100.0 / (1.0 + rs)), 2)
        return out

    @staticmethod
    def highest(src: List[float], length: int) -> List[Optional[float]]:
        n = len(src)
        length = max(1, int(length))
        out: List[Optional[float]] = [None] * n
        for i in range(n):
            start = max(0, i - length + 1)
            out[i] = max(src[start : i + 1])
        return out

    @staticmethod
    def lowest(src: List[float], length: int) -> List[Optional[float]]:
        n = len(src)
        length = max(1, int(length))
        out: List[Optional[float]] = [None] * n
        for i in range(n):
            start = max(0, i - length + 1)
            out[i] = min(src[start : i + 1])
        return out

    @staticmethod
    def stdev(src: List[float], length: int) -> List[Optional[float]]:
        n = len(src)
        length = max(2, int(length))
        out: List[Optional[float]] = [None] * n
        for i in range(length - 1, n):
            win = [float(x) for x in src[i - length + 1 : i + 1] if x is not None]
            if len(win) < 2:
                continue
            mean = sum(win) / len(win)
            var = sum((x - mean) ** 2 for x in win) / len(win)
            out[i] = round(math.sqrt(var), 5)
        return out

    @staticmethod
    def crossover(a: List[Optional[float]], b: List[Optional[float]]) -> List[bool]:
        n = min(len(a), len(b))
        out = [False] * n
        for i in range(1, n):
            if None not in (a[i], b[i], a[i - 1], b[i - 1]):
                out[i] = (a[i - 1] <= b[i - 1]) and (a[i] > b[i])
        return out

    @staticmethod
    def crossunder(a: List[Optional[float]], b: List[Optional[float]]) -> List[bool]:
        n = min(len(a), len(b))
        out = [False] * n
        for i in range(1, n):
            if None not in (a[i], b[i], a[i - 1], b[i - 1]):
                out[i] = (a[i - 1] >= b[i - 1]) and (a[i] < b[i])
        return out


def execute_custom_script(code: str, candles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Executes a user indicator script against `candles` and returns plots & markers."""
    t0 = time.time()
    if not candles:
        return {"success": True, "plots": [], "markers": [], "logs": [], "elapsed_ms": 0.0}

    times = [int(c["time"]) for c in candles]
    opens = [float(c["open"]) for c in candles]
    highs = [float(c["high"]) for c in candles]
    lows = [float(c["low"]) for c in candles]
    closes = [float(c["close"]) for c in candles]
    volumes = [float(c.get("volume", 0.0)) for c in candles]

    plots: List[Dict[str, Any]] = []
    markers: List[Dict[str, Any]] = []
    logs: List[str] = []

    def plot(title: str, values: List[Optional[float]], color: str = "#38bdf8", width: int = 2, style: str = "solid"):
        data = []
        n = min(len(times), len(values))
        for i in range(n):
            v = values[i]
            if v is not None and not (isinstance(v, float) and math.isnan(v)):
                data.append({"time": times[i], "value": float(v)})
        plots.append({
            "title": str(title),
            "color": str(color),
            "lineWidth": float(width),
            "lineStyle": str(style),
            "data": data
        })

    def marker(index_or_time: int, text: str = "SIG", color: str = "#10b981", position: str = "belowBar", shape: str = "arrowUp"):
        if 0 <= index_or_time < len(times):
            t = times[index_or_time]
        else:
            t = int(index_or_time)
        markers.append({
            "time": t,
            "text": str(text),
            "color": str(color),
            "position": str(position),
            "shape": str(shape)
        })

    def log(*args):
        logs.append(" ".join(str(a) for a in args))

    safe_builtins = {
        "range": range, "len": len, "min": min, "max": max, "abs": abs,
        "round": round, "sum": sum, "float": float, "int": int, "str": str,
        "bool": bool, "list": list, "dict": dict, "zip": zip, "enumerate": enumerate,
        "True": True, "False": False, "None": None, "print": log
    }

    env = {
        "__builtins__": safe_builtins,
        "math": math,
        "ta": TAHelper,
        "candles": candles,
        "times": times,
        "opens": opens,
        "highs": highs,
        "lows": lows,
        "closes": closes,
        "close": closes,
        "open": opens,
        "high": highs,
        "low": lows,
        "volume": volumes,
        "volumes": volumes,
        "plot": plot,
        "marker": marker,
        "log": log,
    }

    try:
        exec(compile(code, "<custom_script>", "exec"), env, env)
        elapsed = round((time.time() - t0) * 1000.0, 2)
        return {
            "success": True,
            "plots": plots,
            "markers": markers,
            "logs": logs[:30],
            "elapsed_ms": elapsed
        }
    except Exception as e:
        tb = traceback.format_exc(limit=3)
        return {
            "success": False,
            "error": f"{type(e).__name__}: {e}\n{tb}",
            "plots": [],
            "markers": [],
            "logs": logs[:30],
            "elapsed_ms": round((time.time() - t0) * 1000.0, 2)
        }


def list_saved_scripts() -> List[str]:
    if not os.path.exists(CUSTOM_SCRIPTS_DIR):
        return []
    return sorted([f[:-3] for f in os.listdir(CUSTOM_SCRIPTS_DIR) if f.endswith(".py")])


def load_saved_script(name: str) -> Optional[str]:
    safe_name = "".join(c for c in name if c.isalnum() or c in ("_", "-")).strip()
    if not safe_name:
        return None
    path = os.path.join(CUSTOM_SCRIPTS_DIR, f"{safe_name}.py")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def save_script_file(name: str, code: str) -> str:
    safe_name = "".join(c for c in name if c.isalnum() or c in ("_", "-")).strip() or "custom_script"
    path = os.path.join(CUSTOM_SCRIPTS_DIR, f"{safe_name}.py")
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    return safe_name


def delete_script_file(name: str) -> bool:
    safe_name = "".join(c for c in name if c.isalnum() or c in ("_", "-")).strip()
    if not safe_name:
        return False
    path = os.path.join(CUSTOM_SCRIPTS_DIR, f"{safe_name}.py")
    if os.path.exists(path):
        os.remove(path)
        return True
    return False
