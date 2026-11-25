"""
FastAPI Server for Standalone Trading Simulator.
Provides REST APIs for Replay Control, Orders, Indicators, Templates, and Divergence Detection.
"""

import os
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .data_fetcher import (
    get_available_symbols,
    get_symbol_dataset,
    get_triplet_dataset,
    fetch_mt5_history,
    fetch_realtime_dataset,
    parse_mt5_csv,
    resample_candles,
    resample_to_timeframe,
    DATA_DIR
)
from .indicator_engine import (
    calculate_ema,
    calculate_sma,
    calculate_bollinger_bands,
    calculate_rsi,
    calculate_macd,
    calculate_stochastic,
    calculate_atr,
    calculate_supertrend,
    calculate_vwap,
    detect_key_levels_and_blocks,
    detect_divergences,
    calculate_rsi_ma9_wma45,
    compute_4pillar_mtf_dashboard,
    evaluate_single_tf_pillars,
    calculate_mtf_signals
)
from .custom_script_runner import (
    execute_custom_script,
    list_saved_scripts,
    load_saved_script,
    save_script_file,
    delete_script_file
)
from .preset_manager import get_all_presets, BUILTIN_PRESETS
from .ea_engine import SimpleDCAEngine
from .probabilistic_context_engine import (
    ProbabilisticContextForecaster,
    EMA21ProbabilisticSimulatorEngine,
    evaluate_dna_session_and_time,
)
from .forecast_evaluator import forecast_calibrator
from .simulation_engine import TradeSimulator

app = FastAPI(title="Trading Strategy Simulator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
os.makedirs(TEMPLATES_DIR, exist_ok=True)

# Global Simulator Instance (Clean initial state, 0 positions, 0 mockup PnL)
simulator = TradeSimulator(initial_balance=10000.0)

# Default Active Indicators Configuration: TradingView KHƯƠNG Suite (9EMA Ribbon, BB 20-2, RSI 14 + SMA 9 + WMA 45, Stoch 14-3-3, MACD, Div, MTF Signals)
active_indicators = {
    # === TF1 (Khung Lớn / H4) ===
    "ema5_tf1": {"enabled": True, "type": "EMA", "period": 5, "color": "#ffeb3b", "timeframe": "TF1"},
    "ema12_tf1": {"enabled": True, "type": "EMA", "period": 12, "color": "#ff9800", "timeframe": "TF1"},
    "ema21_tf1": {"enabled": True, "type": "EMA", "period": 21, "color": "#4caf50", "timeframe": "TF1"},
    "ema50_tf1": {"enabled": True, "type": "EMA", "period": 50, "color": "#2962ff", "timeframe": "TF1"},
    "ema100_tf1": {"enabled": True, "type": "EMA", "period": 100, "color": "#f23645", "timeframe": "TF1"},
    "ema200_tf1": {"enabled": True, "type": "EMA", "period": 200, "color": "#dbdbdb", "timeframe": "TF1"},
    "bb_tf1": {"enabled": True, "type": "BB", "period": 20, "std_dev": 2.0, "color": "#38bdf8", "timeframe": "TF1"},
    "rsi_tf1": {"enabled": True, "type": "RSI_MA9_WMA45", "period": 14, "ma9_period": 9, "wma45_period": 45, "timeframe": "TF1"},
    "stochastic_tf1": {"enabled": True, "type": "STOCH", "k": 14, "d": 3, "smooth_k": 3, "timeframe": "TF1"},
    "macd_tf1": {"enabled": True, "type": "MACD", "fast": 12, "slow": 26, "signal": 9, "timeframe": "TF1"},
    "divergence_tf1": {"enabled": True, "type": "DIVERGENCE", "timeframe": "TF1"},
    "mtf_signals_tf1": {"enabled": True, "type": "MTF_SIGNALS", "timeframe": "TF1"},

    # === TF2 (Cấu Trúc / H1) ===
    "ema5_tf2": {"enabled": True, "type": "EMA", "period": 5, "color": "#ffeb3b", "timeframe": "TF2"},
    "ema12_tf2": {"enabled": True, "type": "EMA", "period": 12, "color": "#ff9800", "timeframe": "TF2"},
    "ema21_tf2": {"enabled": True, "type": "EMA", "period": 21, "color": "#4caf50", "timeframe": "TF2"},
    "ema50_tf2": {"enabled": True, "type": "EMA", "period": 50, "color": "#2962ff", "timeframe": "TF2"},
    "ema100_tf2": {"enabled": True, "type": "EMA", "period": 100, "color": "#f23645", "timeframe": "TF2"},
    "ema200_tf2": {"enabled": True, "type": "EMA", "period": 200, "color": "#dbdbdb", "timeframe": "TF2"},
    "bb_tf2": {"enabled": True, "type": "BB", "period": 20, "std_dev": 2.0, "color": "#818cf8", "timeframe": "TF2"},
    "rsi_tf2": {"enabled": True, "type": "RSI_MA9_WMA45", "period": 14, "ma9_period": 9, "wma45_period": 45, "timeframe": "TF2"},
    "stochastic_tf2": {"enabled": True, "type": "STOCH", "k": 14, "d": 3, "smooth_k": 3, "timeframe": "TF2"},
    "macd_tf2": {"enabled": True, "type": "MACD", "fast": 12, "slow": 26, "signal": 9, "timeframe": "TF2"},
    "divergence_tf2": {"enabled": True, "type": "DIVERGENCE", "timeframe": "TF2"},
    "mtf_signals_tf2": {"enabled": True, "type": "MTF_SIGNALS", "timeframe": "TF2"},

    # === TF3 (Thực Thi / M15) ===
    "ema5_tf3": {"enabled": True, "type": "EMA", "period": 5, "color": "#ffeb3b", "timeframe": "TF3"},
    "ema12_tf3": {"enabled": True, "type": "EMA", "period": 12, "color": "#ff9800", "timeframe": "TF3"},
    "ema21_tf3": {"enabled": True, "type": "EMA", "period": 21, "color": "#4caf50", "timeframe": "TF3"},
    "ema50_tf3": {"enabled": True, "type": "EMA", "period": 50, "color": "#2962ff", "timeframe": "TF3"},
    "ema100_tf3": {"enabled": True, "type": "EMA", "period": 100, "color": "#f23645", "timeframe": "TF3"},
    "ema200_tf3": {"enabled": True, "type": "EMA", "period": 200, "color": "#dbdbdb", "timeframe": "TF3"},
    "bb_tf3": {"enabled": True, "type": "BB", "period": 20, "std_dev": 2.0, "color": "#a855f7", "timeframe": "TF3"},
    "rsi_tf3": {"enabled": True, "type": "RSI_MA9_WMA45", "period": 14, "ma9_period": 9, "wma45_period": 45, "timeframe": "TF3"},
    "stochastic_tf3": {"enabled": True, "type": "STOCH", "k": 14, "d": 3, "smooth_k": 3, "timeframe": "TF3"},
    "macd_tf3": {"enabled": True, "type": "MACD", "fast": 12, "slow": 26, "signal": 9, "timeframe": "TF3"},
    "divergence_tf3": {"enabled": True, "type": "DIVERGENCE", "timeframe": "TF3"},
    "mtf_signals_tf3": {"enabled": True, "type": "MTF_SIGNALS", "timeframe": "TF3"}
}

# Persistent Indicator Configuration (survives reloads & server restarts!)
ACTIVE_INDICATORS_FILE = os.path.join(DATA_DIR, "active_indicators.json")

def save_active_indicators_to_disk():
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(ACTIVE_INDICATORS_FILE, "w", encoding="utf-8") as f:
            json.dump(active_indicators, f, indent=2)
    except Exception as e:
        print(f"Warning: could not persist active_indicators: {e}")

if os.path.exists(ACTIVE_INDICATORS_FILE):
    try:
        with open(ACTIVE_INDICATORS_FILE, "r", encoding="utf-8") as f:
            loaded_cfg = json.load(f)
            if isinstance(loaded_cfg, dict) and len(loaded_cfg) > 0:
                active_indicators = loaded_cfg
    except Exception as e:
        print(f"Warning: could not load persisted active_indicators: {e}")

# Auto-save Divergence.tpl / Divergence.json template
divergence_tpl_path = os.path.join(TEMPLATES_DIR, "Divergence.json")
try:
    with open(divergence_tpl_path, "w", encoding="utf-8") as f:
        json.dump(active_indicators, f, indent=2)
except Exception:
    pass


# Mount Static Files
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=HTMLResponse)
def index():
    html_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Trading Simulator Frontend is Loading...</h1>"


@app.get("/api/symbols")
def get_symbols():
    return {"symbols": get_available_symbols()}


@app.get("/api/symbols/search")
def search_symbols(query: str = ""):
    """Searches symbols from MT5 broker server and cached symbols in real time."""
    q = query.upper().strip()
    all_syms = get_available_symbols()
    if not q:
        return {"query": "", "symbols": all_syms[:60]}
    
    matches = []
    seen = set()
    for s in all_syms:
        sym = s["symbol"].upper()
        name = (s.get("name") or "").upper()
        if q in sym or q in name:
            matches.append(s)
            seen.add(sym)
            
    # Also if MT5 is connected, do an active search via mt5.symbols_get
    try:
        import MetaTrader5 as mt5
        from .data_fetcher import _init_mt5_terminal
        if _init_mt5_terminal():
            server_matches = mt5.symbols_get(f"*{q}*")
            if server_matches:
                for sm in server_matches:
                    raw = sm.name.strip()
                    if raw.upper() not in seen:
                        seen.add(raw.upper())
                        matches.append({
                            "symbol": raw,
                            "name": sm.description or raw,
                            "digits": sm.digits,
                            "pip_size": round(sm.point * 10 if sm.digits in (3, 5) else sm.point, 6),
                            "source": "MT5",
                            "path": sm.path or "",
                            "visible": sm.visible,
                            "is_cached": False
                        })
    except Exception:
        pass
        
    return {"query": query, "symbols": matches[:60]}


VALID_TIMEFRAMES = {"M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1"}


def _parse_tf_triplet(timeframe_pair: Optional[str], tf1: str = "H4", tf2: str = "H1", tf3: str = "M15"):
    if not timeframe_pair:
        return tf1, tf2, tf3
    tfp = timeframe_pair.upper().strip()
    if tfp in ("H4_H1_M15", "H4_M15"):
        return "H4", "H1", "M15"
    if tfp in ("D1_H4_H1", "H4_H1"):
        return "D1", "H4", "H1"
    if tfp in ("H1_M15_M5", "H1_M5"):
        return "H1", "M15", "M5"
    if tfp in ("M15_M5_M1", "M5_M1"):
        return "M15", "M5", "M1"
    parts = tfp.split("_")
    if len(parts) == 3 and all(p in VALID_TIMEFRAMES for p in parts):
        return parts[0], parts[1], parts[2]
    return tf1, tf2, tf3


@app.get("/api/load_symbol")
def load_symbol(
    symbol: str = "XAUUSD", 
    timeframe_pair: Optional[str] = "H4_H1_M15",
    tf1: str = "H4",
    tf2: str = "H1",
    tf3: str = "M15"
):
    sym = symbol.upper().strip()
    tf1, tf2, tf3 = _parse_tf_triplet(timeframe_pair, tf1, tf2, tf3)
            
    triplet_data = get_triplet_dataset(sym, tf1=tf1, tf2=tf2, tf3=tf3)
    
    simulator.load_triplet_dataset(
        symbol=sym,
        base_candles=triplet_data["base_candles"],
        tf1_candles=triplet_data["candles_tf1"],
        tf2_candles=triplet_data["candles_tf2"],
        tf3_candles=triplet_data["candles_tf3"],
        tf1_name=triplet_data["tf1"],
        tf2_name=triplet_data["tf2"],
        tf3_name=triplet_data["tf3"]
    )
    
    return {
        "success": True,
        "symbol": sym,
        "source": triplet_data.get("source", "LOCAL_CACHE"),
        "base_tf": triplet_data.get("base_tf", "M5"),
        "tf1": triplet_data["tf1"],
        "tf2": triplet_data["tf2"],
        "tf3": triplet_data["tf3"],
        "tf1_count": len(triplet_data["candles_tf1"]),
        "tf2_count": len(triplet_data["candles_tf2"]),
        "tf3_count": len(triplet_data["candles_tf3"]),
        "total_base_bars": triplet_data.get("total_base_bars", 0),
        "current_index": simulator.current_m15_index,
        "start_time": triplet_data["base_candles"][0]["time"] if triplet_data["base_candles"] else 0,
        "end_time": triplet_data["base_candles"][-1]["time"] if triplet_data["base_candles"] else 0
    }


_radar_15m_cache = {"ts": 0.0, "text": "RADAR 15M: ..."}

def get_cached_radar_15m() -> str:
    """Fetches real 15M 4-pillar status for core symbols from MT5, cached for 45s."""
    import time
    now = time.time()
    if now - _radar_15m_cache["ts"] < 45.0 and _radar_15m_cache["ts"] > 0:
        return _radar_15m_cache["text"]

    parts = []
    for sym in ["XAUUSD", "US30", "SPX500", "NAS100", "EURUSD"]:
        try:
            bars = fetch_mt5_history(sym, "M15", count=65)
            if bars and len(bars) >= 35:
                p = evaluate_single_tf_pillars(bars)
                if p["bears"] >= 4:
                    tag = "*SELL"
                elif p["bears"] >= 3:
                    tag = "vSELL"
                elif p["bulls"] >= 4:
                    tag = "*BUY"
                elif p["bulls"] >= 3:
                    tag = "^BUY"
                else:
                    tag = "NEUT"
                parts.append(f"{sym}[{tag}]")
            else:
                parts.append(f"{sym}[--]")
        except Exception:
            parts.append(f"{sym}[--]")
    text = "RADAR 15M: " + " ".join(parts)
    _radar_15m_cache["ts"] = now
    _radar_15m_cache["text"] = text
    return text


def compute_indicator_data(visible: Dict[str, Any]) -> Dict[str, Any]:
    """Computes technical indicator values across the 3 timeframes."""
    output = {}
    tf1_candles = visible.get("tf1", visible.get("H4", []))
    tf2_candles = visible.get("tf2", visible.get("H1", []))
    tf3_candles = visible.get("tf3", visible.get("M15", []))
    tf1_name = str(visible.get("tf1_name", "H4")).upper()
    tf2_name = str(visible.get("tf2_name", "H1")).upper()
    tf3_name = str(visible.get("tf3_name", "M15")).upper()

    for key, cfg in active_indicators.items():
        if not cfg.get("enabled"):
            continue
        tf_target = str(cfg.get("timeframe", "TF3")).upper().strip()
        
        # Select target candles for indicator calculation
        if tf_target in ("TF1", "CHART1"):
            candles = tf1_candles
        elif tf_target in ("TF2", "CHART2"):
            candles = tf2_candles
        elif tf_target in ("TF3", "CHART3"):
            candles = tf3_candles
        elif tf_target in ("H4", "D1", "W1", tf1_name):
            candles = tf1_candles
        elif tf_target in ("H1", tf2_name):
            candles = tf2_candles
        elif tf_target in ("M15", "M5", "M1", tf3_name):
            candles = tf3_candles
        else:
            candles = tf3_candles
            
        ind_type = str(cfg.get("type", "")).upper()
        
        if ind_type == "EMA":
            output[key] = {
                "config": cfg,
                "data": calculate_ema(candles, period=cfg.get("period", 20))
            }
        elif ind_type == "SMA":
            output[key] = {
                "config": cfg,
                "data": calculate_sma(candles, period=cfg.get("period", 20))
            }
        elif ind_type == "BB":
            output[key] = {
                "config": cfg,
                "data": calculate_bollinger_bands(candles, period=cfg.get("period", 20), std_dev=cfg.get("std_dev", 2.0))
            }
        elif ind_type in ("RSI", "RSI_MA9_WMA45"):
            output[key] = {
                "config": cfg,
                "data": calculate_rsi_ma9_wma45(candles, rsi_period=cfg.get("period", 14), ma9_period=cfg.get("ma9_period", 9), wma45_period=cfg.get("wma45_period", 45))
            }
        elif ind_type == "STOCH":
            output[key] = {
                "config": cfg,
                "data": calculate_stochastic(candles, k_period=cfg.get("k", 14), d_period=cfg.get("d", 3), smooth_k=cfg.get("smooth_k", 3))
            }
        elif ind_type == "MACD":
            output[key] = {
                "config": cfg,
                "data": calculate_macd(candles, fast_period=cfg.get("fast", 12), slow_period=cfg.get("slow", 26), signal_period=cfg.get("signal", 9))
            }
        elif ind_type == "MTF_SIGNALS":
            output[key] = {
                "config": cfg,
                "data": calculate_mtf_signals(candles)
            }
        elif ind_type == "ATR":
            output[key] = {
                "config": cfg,
                "data": calculate_atr(candles, period=cfg.get("period", 14))
            }
        elif ind_type == "SUPERTREND":
            output[key] = {
                "config": cfg,
                "data": calculate_supertrend(candles, period=cfg.get("period", 10), multiplier=cfg.get("multiplier", 3.0))
            }
        elif ind_type == "VWAP":
            output[key] = {
                "config": cfg,
                "data": calculate_vwap(candles)
            }
        elif ind_type == "DIVERGENCE":
            output[key] = {
                "config": cfg,
                "data": detect_divergences(candles, lookback=80, order=3)
            }
        elif ind_type == "OB":
            output[key] = {
                "config": cfg,
                "data": detect_key_levels_and_blocks(candles, left_bars=cfg.get("left", 5), right_bars=cfg.get("right", 5))
            }
        elif ind_type == "CUSTOM_SCRIPT":
            script_code = cfg.get("code") or load_saved_script(cfg.get("script_name", "")) or ""
            if script_code:
                output[key] = {
                    "config": cfg,
                    "data": execute_custom_script(script_code, candles)
                }
    return output


@app.get("/api/state")
def get_state():
    visible = simulator.get_visible_candles()
    ind_data = compute_indicator_data(visible)
    
    # Extract latest Copilot divergence setup if any
    latest_div_m15 = ind_data.get("divergence_tf3", ind_data.get("divergence_m15", {})).get("data", {}).get("latest_signal")
    latest_div_h4 = ind_data.get("divergence_tf1", ind_data.get("divergence_h4", {})).get("data", {}).get("latest_signal")
    
    # 4-Pillar MTF Master Dashboard (Real M5, M15, H1, H4, D1 + Cached Live RADAR 15M)
    c_tf1 = visible.get("tf1", [])
    c_tf2 = visible.get("tf2", [])
    c_tf3 = visible.get("tf3", [])
    tf1_n = str(visible.get("tf1_name", "H4")).upper()
    tf2_n = str(visible.get("tf2_name", "H1")).upper()
    tf3_n = str(visible.get("tf3_name", "M15")).upper()
    c_base = visible.get("base_tail_candles", c_tf3)

    # Map real timeframes accurately regardless of selected triplet (H4+H1+M15, H1+M15+M5, D1+H4+H1)
    c_m5 = c_tf3 if tf3_n == "M5" else c_base
    c_m15 = c_tf3 if tf3_n == "M15" else (c_tf2 if tf2_n == "M15" else resample_to_timeframe(c_base, "M15"))
    c_h1 = c_tf2 if tf2_n == "H1" else (c_tf1 if tf1_n == "H1" else (c_tf3 if tf3_n == "H1" else resample_to_timeframe(c_tf3, "H1")))
    c_h4 = c_tf1 if tf1_n == "H4" else (c_tf2 if tf2_n == "H4" else resample_to_timeframe(c_h1, "H4"))
    c_d1 = c_tf1 if tf1_n == "D1" else resample_to_timeframe(c_h4, "D1")

    mtf_dashboard = compute_4pillar_mtf_dashboard(
        symbol=simulator.symbol,
        candles_m5=c_m5,
        candles_m15=c_m15,
        candles_h1=c_h1,
        candles_h4=c_h4,
        candles_d1=c_d1,
        radar_override=get_cached_radar_15m()
    )

    return {
        "symbol": simulator.symbol,
        "symbol_info": simulator.get_symbol_info(),
        "tf1_name": visible.get("tf1_name", "H4"),
        "tf2_name": visible.get("tf2_name", "H1"),
        "tf3_name": visible.get("tf3_name", "M15"),
        "candles_tf1": visible.get("tf1", []),
        "candles_tf2": visible.get("tf2", []),
        "candles_tf3": visible.get("tf3", []),
        # Backward compatibility
        "timeframe_pair": visible.get("timeframe_pair", "H4_M15"),
        "exec_tf": visible.get("exec_tf", "M15"),
        "macro_tf": visible.get("macro_tf", "H4"),
        "candles_m15": visible.get("tf3", visible.get("M15", [])),
        "candles_h4": visible.get("tf1", visible.get("H4", [])),
        "current_index": simulator.current_m15_index,
        "total_bars": visible.get("total_bars", 0),
        "current_time": visible.get("current_time", 0),
        "current_price": visible.get("current_price", 0.0),
        "is_playing": simulator.is_playing,
        "indicators": ind_data,
        "mtf_dashboard": mtf_dashboard,
        "copilot_signals": {
            "M15": latest_div_m15,
            "H4": latest_div_h4
        },
        "account": {
            "balance": round(simulator.balance, 2),
            "equity": round(simulator.equity, 2),
            "initial_balance": simulator.initial_balance,
            "open_positions": simulator.open_positions,
            "pending_orders": simulator.pending_orders,
            "closed_positions": simulator.closed_positions
        },
        "ea_status": visible.get("ea_status"),
        "ea_enabled": visible.get("ea_enabled", False),
        "probabilistic_forecast": visible.get("probabilistic_forecast"),
        "stats": simulator.get_statistics()
    }


class StepRequest(BaseModel):
    steps: int = 1
    direction: str = "forward"

@app.post("/api/step")
def step_bars(req: StepRequest):
    if req.direction == "forward":
        simulator.step_forward(req.steps)
    else:
        simulator.step_backward(req.steps)
    return get_state()



class JumpRequest(BaseModel):
    index: Optional[int] = None
    timestamp: Optional[int] = None
    datetime_str: Optional[str] = None

@app.post("/api/jump")
def jump_to(req: JumpRequest):
    if req.timestamp is None and req.datetime_str:
        try:
            from datetime import timedelta
            vn_tz = timezone(timedelta(hours=7))
            d_str = req.datetime_str.replace("T", " ")
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y.%m.%d %H:%M:%S", "%Y.%m.%d"):
                try:
                    dt = datetime.strptime(d_str, fmt)
                    req.timestamp = int(dt.replace(tzinfo=vn_tz).timestamp())
                    break
                except ValueError:
                    pass
        except Exception as e:
            print("Error parsing jump datetime:", e)
            
    if req.index is not None:
        simulator.jump_to_index(req.index)
    elif req.timestamp is not None:
        simulator.jump_to_date(req.timestamp)
    return {"success": True, "current_index": simulator.current_m15_index, "current_time": simulator.current_time}


class CalcLotsRequest(BaseModel):
    risk_usd: float
    entry_price: float
    sl_price: float

@app.post("/api/calc_lots")
def calculate_lots(req: CalcLotsRequest):
    lots = simulator.calculate_lot_size(req.risk_usd, req.entry_price, req.sl_price)
    return {"success": True, "lots": lots}


class OpenOrderRequest(BaseModel):
    type: str
    lots: float = 0.1
    sl: Optional[float] = None
    tp: Optional[float] = None
    pending_price: Optional[float] = None
    num_positions: int = 1
    rr_list: Optional[List[float]] = None

@app.post("/api/order/open")
def open_order(req: OpenOrderRequest):
    if req.lots <= 0:
        raise HTTPException(status_code=400, detail="Invalid lot size")
        
    if req.num_positions > 1:
        orders = simulator.open_batch_orders(
            order_type=req.type,
            total_lots=req.lots,
            num_positions=req.num_positions,
            entry_price=req.pending_price,
            sl=req.sl,
            rr_list=req.rr_list
        )
        return {"success": True, "positions": orders, "stats": simulator.get_statistics()}
    else:
        pos = simulator.open_order(req.type, req.lots, req.sl, req.tp, req.pending_price)
        return {"success": True, "position": pos, "stats": simulator.get_statistics()}


class CancelPendingRequest(BaseModel):
    id: str

@app.post("/api/order/cancel_pending")
def cancel_pending(req: CancelPendingRequest):
    ok = simulator.cancel_pending_order(req.id)
    return {"success": ok}


class CloseOrderRequest(BaseModel):
    id: str

@app.post("/api/order/close")
def close_order(req: CloseOrderRequest):
    closed = simulator.close_order(req.id)
    if not closed:
        raise HTTPException(status_code=404, detail="Position not found")
    return {"success": True, "closed_position": closed, "stats": simulator.get_statistics()}


class UpdateSLRequest(BaseModel):
    id: str
    new_sl: float

@app.post("/api/order/update_sl")
def update_order_sl(req: UpdateSLRequest):
    ok = simulator.update_position_sl(req.id, req.new_sl)
    return {"success": ok, "open_positions": simulator.open_positions}


@app.post("/api/order/close_all")
def close_all():
    closed_list = simulator.close_all_orders()
    return {"success": True, "closed_count": len(closed_list), "stats": simulator.get_statistics()}



class ResetRequest(BaseModel):
    initial_balance: float = 10000.0
    risk_mode: Optional[str] = "PERCENT"  # "PERCENT", "FIXED_USD", "FIXED_LOT"
    risk_value: Optional[float] = 1.0
    start_point: Optional[str] = "YEAR_2000"  # "YEAR_2000", "CURRENT", "CUSTOM"
    custom_timestamp: Optional[int] = None

@app.post("/api/reset")
def reset_simulation(req: ResetRequest):
    simulator.reset(initial_balance=req.initial_balance)
    if req.start_point == "YEAR_2000":
        if simulator.m15_candles:
            simulator.jump_to_index(100)
    elif req.start_point == "CUSTOM" and req.custom_timestamp:
        simulator.jump_to_date(req.custom_timestamp)
    return {
        "success": True,
        "initial_balance": simulator.initial_balance,
        "balance": simulator.balance,
        "current_index": simulator.current_m15_index,
        "stats": simulator.get_statistics()
    }


@app.get("/api/stats")
def get_full_stats():
    return {
        "stats": simulator.get_statistics(),
        "equity_curve": simulator.equity_curve,
        "trade_history": simulator.closed_positions
    }



# Indicators & Templates Management
@app.get("/api/indicators/available")
def get_available_indicators():
    return {
        "indicators": [
            {"type": "EMA", "name": "Exponential Moving Average (EMA)", "category": "Trend", "overlay": True, "default_period": 21, "default_color": "#00E676"},
            {"type": "SMA", "name": "Simple Moving Average (SMA)", "category": "Trend", "overlay": True, "default_period": 50, "default_color": "#38bdf8"},
            {"type": "BB", "name": "Bollinger Bands (20, 2)", "category": "Volatility", "overlay": True, "default_period": 20, "default_color": "#a855f7"},
            {"type": "SUPERTREND", "name": "SuperTrend (10, 3.0)", "category": "Trend", "overlay": True, "default_period": 10, "default_multiplier": 3.0},
            {"type": "VWAP", "name": "Volume Weighted Average Price (VWAP)", "category": "Volume", "overlay": True, "default_color": "#f59e0b"},
            {"type": "OB", "name": "Order Blocks / Swing Key Levels", "category": "Structure", "overlay": True, "default_left": 5, "default_right": 5},
            {"type": "RSI", "name": "Relative Strength Index (RSI 14)", "category": "Momentum", "overlay": False, "default_period": 14, "default_color": "#38bdf8"},
            {"type": "STOCH", "name": "Stochastic Oscillator (5, 3, 3)", "category": "Momentum", "overlay": False, "default_k": 5, "default_d": 3},
            {"type": "MACD", "name": "MACD (12, 26, 9)", "category": "Momentum", "overlay": False, "default_fast": 12, "default_slow": 26, "default_signal": 9},
            {"type": "ATR", "name": "Average True Range (ATR 14)", "category": "Volatility", "overlay": False, "default_period": 14, "default_color": "#fbbf24"},
            {"type": "DIVERGENCE", "name": "Multi-Oscillator Divergence Scanner", "category": "Signals", "overlay": True}
        ]
    }


@app.get("/api/indicators/config")
def get_indicator_config():
    return {"active_indicators": active_indicators}


@app.post("/api/indicators/config")
def update_indicator_config(config: Dict[str, Any]):
    global active_indicators
    active_indicators = config
    save_active_indicators_to_disk()
    return {"success": True, "active_indicators": active_indicators}


class CustomScriptSaveRequest(BaseModel):
    name: str
    code: str

class CustomScriptRunRequest(BaseModel):
    name: str = "my_script"
    code: str
    timeframe: str = "TF3"  # TF1, TF2, TF3, or ALL
    add_to_chart: bool = True

@app.get("/api/scripts")
def api_list_scripts():
    return {"success": True, "scripts": list_saved_scripts()}

@app.get("/api/scripts/load")
def api_load_script(name: str):
    code = load_saved_script(name)
    if code is None:
        raise HTTPException(status_code=404, detail=f"Script '{name}' not found")
    return {"success": True, "name": name, "code": code}

@app.post("/api/scripts/save")
def api_save_script(req: CustomScriptSaveRequest):
    saved_name = save_script_file(req.name, req.code)
    return {"success": True, "name": saved_name}

@app.delete("/api/scripts/delete")
def api_delete_script(name: str):
    ok = delete_script_file(name)
    # Also remove from active_indicators if attached
    to_del = [k for k, v in active_indicators.items() if v.get("type") == "CUSTOM_SCRIPT" and v.get("script_name") == name]
    for k in to_del:
        del active_indicators[k]
    if to_del:
        save_active_indicators_to_disk()
    return {"success": ok, "removed_keys": to_del}

@app.post("/api/scripts/run")
def api_run_script(req: CustomScriptRunRequest):
    saved_name = save_script_file(req.name, req.code)
    visible = simulator.get_visible_candles()
    tf_target = str(req.timeframe or "TF3").upper().strip()

    # Dry-run on target timeframe to verify syntax & collect console stats
    test_candles = visible.get("tf1", []) if tf_target == "TF1" else (visible.get("tf2", []) if tf_target == "TF2" else visible.get("tf3", []))
    res = execute_custom_script(req.code, test_candles)
    if not res.get("success"):
        return {
            "success": False,
            "error": res.get("error", "Unknown error"),
            "logs": res.get("logs", []),
            "elapsed_ms": res.get("elapsed_ms", 0)
        }

    attached_keys = []
    if req.add_to_chart:
        tfs = ["TF1", "TF2", "TF3"] if tf_target == "ALL" else [tf_target]
        for tf in tfs:
            key = f"script_{saved_name}_{tf.lower()}"
            active_indicators[key] = {
                "enabled": True,
                "type": "CUSTOM_SCRIPT",
                "script_name": saved_name,
                "timeframe": tf,
                "code": req.code
            }
            attached_keys.append(key)
        save_active_indicators_to_disk()

    return {
        "success": True,
        "name": saved_name,
        "attached_keys": attached_keys,
        "plot_count": len(res.get("plots", [])),
        "marker_count": len(res.get("markers", [])),
        "logs": res.get("logs", []),
        "elapsed_ms": res.get("elapsed_ms", 0)
    }


@app.get("/api/templates")
def list_templates():
    templates = []
    for f in os.listdir(TEMPLATES_DIR):
        if f.endswith(".json") or f.endswith(".tpl"):
            name = f.replace(".json", "").replace(".tpl", "")
            if name not in templates:
                templates.append(name)
    if "Divergence" not in templates:
        templates.insert(0, "Divergence")
    return {"templates": templates}


class SaveTemplateRequest(BaseModel):
    name: str
    config: Dict[str, Any]

@app.post("/api/templates/save")
def save_template(req: SaveTemplateRequest):
    clean_name = "".join(c for c in req.name if c.isalnum() or c in ("_", "-")).strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="Invalid template name")
    file_path = os.path.join(TEMPLATES_DIR, f"{clean_name}.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(req.config, f, indent=2)
    return {"success": True, "name": clean_name}


@app.get("/api/templates/load")
def load_template(name: str):
    global active_indicators
    file_path = os.path.join(TEMPLATES_DIR, f"{name}.json")
    if not os.path.exists(file_path):
        if name in ("Divergence", "Divergence.tpl"):
            cfg = {
                "ema21_m15": {"enabled": True, "type": "EMA", "period": 21, "color": "#00E676", "timeframe": "M15"},
                "ema50_m15": {"enabled": True, "type": "EMA", "period": 50, "color": "#FF1744", "timeframe": "M15"},
                "ema200_m15": {"enabled": True, "type": "EMA", "period": 200, "color": "#FFD600", "timeframe": "M15"},
                "ema21_h4": {"enabled": True, "type": "EMA", "period": 21, "color": "#00E676", "timeframe": "H4"},
                "ema50_h4": {"enabled": True, "type": "EMA", "period": 50, "color": "#FF1744", "timeframe": "H4"},
                "ema200_h4": {"enabled": True, "type": "EMA", "period": 200, "color": "#FFD600", "timeframe": "H4"},
                "rsi_m15": {"enabled": True, "type": "RSI", "period": 14, "timeframe": "M15"},
                "stochastic_m15": {"enabled": True, "type": "STOCH", "k": 5, "d": 3, "smooth_k": 3, "timeframe": "M15"},
                "rsi_h4": {"enabled": True, "type": "RSI", "period": 14, "timeframe": "H4"},
                "stochastic_h4": {"enabled": True, "type": "STOCH", "k": 5, "d": 3, "smooth_k": 3, "timeframe": "H4"},
                "divergence_m15": {"enabled": True, "type": "DIVERGENCE", "timeframe": "M15"},
                "divergence_h4": {"enabled": True, "type": "DIVERGENCE", "timeframe": "H4"}
            }
        else:
            cfg = active_indicators
        active_indicators = cfg
        return {"success": True, "config": cfg}
        
    with open(file_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    active_indicators = cfg
    save_active_indicators_to_disk()
    return {"success": True, "config": cfg}


@app.post("/api/import_csv")
@app.post("/api/upload_csv")
async def import_csv(file: UploadFile = File(...), symbol: str = Form("CUSTOM_PAIR")):
    content = (await file.read()).decode("utf-8", errors="ignore")
    candles_base = parse_mt5_csv(content)
    if not candles_base:
        raise HTTPException(status_code=400, detail="Failed to parse CSV file. Ensure standard MT5 format.")

    sym_u = symbol.upper().strip()
    tf1 = simulator.tf1_name or "H4"
    tf2 = simulator.tf2_name or "H1"
    tf3 = simulator.tf3_name or "M15"
    c_tf1 = resample_to_timeframe(candles_base, tf1)
    c_tf2 = resample_to_timeframe(candles_base, tf2)
    c_tf3 = resample_to_timeframe(candles_base, tf3)
    simulator.load_triplet_dataset(sym_u, candles_base, c_tf1, c_tf2, c_tf3, tf1_name=tf1, tf2_name=tf2, tf3_name=tf3)

    cache_path = os.path.join(DATA_DIR, f"{sym_u}_M15.json")
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(candles_base, f)

    return {
        "success": True,
        "symbol": sym_u,
        "candle_count": len(candles_base),
        "m15_count": len(c_tf3),
        "h4_count": len(c_tf1)
    }


# =========================================================================
# SIMPLE DCA EA REST APIS (v1.40 & v1.41)
# =========================================================================

@app.get("/api/ea/presets")
def list_ea_presets():
    presets = get_all_presets()
    return {"success": True, "presets": presets}


@app.get("/api/ea/config")
def get_ea_config():
    if simulator.ea_engine:
        return {"success": True, "config": simulator.ea_engine.config, "ea_enabled": simulator.ea_enabled}
    return {"success": False, "error": "EA engine not initialized"}


class UpdateEAConfigRequest(BaseModel):
    config: Dict[str, Any]

@app.post("/api/ea/config")
def update_ea_config(req: UpdateEAConfigRequest):
    if simulator.ea_engine:
        simulator.ea_engine.set_config(req.config)
        return {"success": True, "config": simulator.ea_engine.config}
    return {"success": False, "error": "EA engine not initialized"}


class SelectPresetRequest(BaseModel):
    preset_name: str

@app.post("/api/ea/select_preset")
def select_ea_preset(req: SelectPresetRequest):
    presets = get_all_presets()
    if req.preset_name in presets:
        selected_cfg = presets[req.preset_name]
        simulator.active_preset_name = req.preset_name
        # Update ProbabilisticContextForecaster parameters dynamically if probabilistic preset is chosen
        if selected_cfg.get("engine_type") == "EMA21_PROBABILISTIC" or req.preset_name.startswith("v3.0"):
            simulator.prob_forecaster.horizon_bars = int(selected_cfg.get("horizon_bars", 8))
            simulator.prob_forecaster.k_neighbors = int(selected_cfg.get("k_neighbors", 35))
            simulator.prob_forecaster.up_barrier_atr = float(selected_cfg.get("up_barrier_atr", 1.25))
            simulator.prob_forecaster.dn_barrier_atr = float(selected_cfg.get("dn_barrier_atr", 1.25))
            simulator.prob_forecaster.adverse_barrier_atr = float(selected_cfg.get("adverse_barrier_atr", 0.95))
            simulator.prob_forecaster.max_memory_bars = int(selected_cfg.get("max_memory_bars", 2500))
            simulator.prob_forecaster._cache.clear()
        if simulator.ea_engine:
            simulator.ea_engine.set_config(selected_cfg)
        fc = simulator.get_current_probabilistic_forecast(include_analogs=True)
        return {
            "success": True,
            "preset_name": req.preset_name,
            "config": selected_cfg,
            "probabilistic_forecast": fc
        }
    raise HTTPException(status_code=404, detail="Preset not found")


class ToggleEARequest(BaseModel):
    enabled: bool

@app.post("/api/ea/toggle")
def toggle_ea(req: ToggleEARequest):
    simulator.ea_enabled = req.enabled
    return {"success": True, "ea_enabled": simulator.ea_enabled}


class FastBacktestRequest(BaseModel):
    symbol: Optional[str] = None
    preset_name: Optional[str] = None
    timeframe_pair: Optional[str] = "H1_M5"
    custom_config: Optional[Dict[str, Any]] = None

@app.post("/api/ea/fast_backtest")
def run_fast_backtest(req: FastBacktestRequest):
    sym = (req.symbol or simulator.symbol).upper().strip()
    tf_pair = req.timeframe_pair or simulator.timeframe_pair or "H1_M5"
    
    # Load dataset
    dataset = get_symbol_dataset(sym, timeframe_pair=tf_pair)
    is_m5 = (tf_pair.upper() == "H1_M5")
    sub_candles = dataset.get("sub_candles", dataset.get("M5" if is_m5 else "M15", []))
    macro_candles = dataset.get("macro_candles", dataset.get("H1" if is_m5 else "H4", []))
    
    if not sub_candles:
        raise HTTPException(status_code=400, detail="No candle data available for backtest")
        
    presets = get_all_presets()
    cfg = None
    if req.preset_name and req.preset_name in presets:
        cfg = dict(presets[req.preset_name])
    elif simulator.ea_engine:
        cfg = dict(simulator.ea_engine.config)
    else:
        cfg = dict(presets.get("v1.41_XAU_Linear_Max4Orders_Continuous", {}))
        
    if req.custom_config:
        cfg.update(req.custom_config)
        
    if (req.preset_name and req.preset_name.startswith("v3.0_EMA21")) or cfg.get("engine_type") == "EMA21_PROBABILISTIC":
        prob_engine = EMA21ProbabilisticSimulatorEngine(symbol=sym, config=cfg, initial_balance=simulator.initial_balance)
        return prob_engine.fast_backtest(sub_candles, macro_candles)
        
    temp_engine = SimpleDCAEngine(symbol=sym, config=cfg, initial_balance=simulator.initial_balance)
    report = temp_engine.fast_backtest(sub_candles, macro_candles)
    return report


@app.get("/api/forecast/current")
def get_current_forecast():
    """Returns live 100% Non-Lookahead probabilistic context forecast (% UP / % DOWN / % SIDEWAY) + future_candles at current bar."""
    fc = simulator.get_current_probabilistic_forecast(include_analogs=True)
    return {
        "success": True,
        "symbol": simulator.symbol,
        "active_preset": getattr(simulator, "active_preset_name", "v3.0_EMA21_Probabilistic_MacroKNN"),
        "current_index": simulator.current_m15_index,
        "current_time": simulator.current_time,
        "forecast": fc
    }


@app.get("/api/forecast/future_candles")
def get_future_candles(preset_name: Optional[str] = None, horizon_bars: Optional[int] = None):
    """
    Dedicated API to project future candles (H bars ahead) and probability distribution (% UP / % DOWN / % SIDEWAY)
    when the user selects or clicks a Probabilistic preset on the Simulator UI.
    """
    if preset_name:
        presets = get_all_presets()
        if preset_name in presets:
            selected_cfg = presets[preset_name]
            simulator.active_preset_name = preset_name
            if selected_cfg.get("engine_type") == "EMA21_PROBABILISTIC" or preset_name.startswith("v3.0"):
                simulator.prob_forecaster.horizon_bars = int(selected_cfg.get("horizon_bars", 8))
                simulator.prob_forecaster.k_neighbors = int(selected_cfg.get("k_neighbors", 35))
                simulator.prob_forecaster.up_barrier_atr = float(selected_cfg.get("up_barrier_atr", 1.25))
                simulator.prob_forecaster.dn_barrier_atr = float(selected_cfg.get("dn_barrier_atr", 1.25))
                simulator.prob_forecaster.adverse_barrier_atr = float(selected_cfg.get("adverse_barrier_atr", 0.95))
                simulator.prob_forecaster.max_memory_bars = int(selected_cfg.get("max_memory_bars", 2500))
                simulator.prob_forecaster._cache.clear()
    if horizon_bars is not None and 2 <= horizon_bars <= 24:
        simulator.prob_forecaster.horizon_bars = int(horizon_bars)
        simulator.prob_forecaster._cache.clear()

    fc = simulator.get_current_probabilistic_forecast(include_analogs=True)
    return {
        "success": True,
        "symbol": simulator.symbol,
        "active_preset": getattr(simulator, "active_preset_name", "v3.0_EMA21_Probabilistic_MacroKNN"),
        "current_index": simulator.current_m15_index,
        "current_time": simulator.current_time,
        "current_price": simulator.current_price,
        "forecast_mode": fc.get("forecast_mode", "COMBINED_HTF_LTF"),
        "prob_up_pct": fc.get("prob_up_pct", 33.3),
        "prob_down_pct": fc.get("prob_down_pct", 33.3),
        "prob_sideway_pct": fc.get("prob_sideway_pct", 33.4),
        "macro_prob_up_pct": fc.get("macro_prob_up_pct", 33.3),
        "macro_prob_down_pct": fc.get("macro_prob_down_pct", 33.3),
        "macro_prob_sideway_pct": fc.get("macro_prob_sideway_pct", 33.4),
        "tactical_status": fc.get("tactical_status", "NEUTRAL"),
        "tactical_badge": fc.get("tactical_badge", ""),
        "dominant_scenario": fc.get("dominant_scenario", "NEUTRAL"),
        "dominant_prob_pct": fc.get("dominant_prob_pct", 33.4),
        "expected_wave_atr": fc.get("expected_wave_atr", 0.0),
        "future_candles": fc.get("future_candles", []),
        "future_up_band": fc.get("future_up_band", []),
        "future_dn_band": fc.get("future_dn_band", []),
        "future_mean_line": fc.get("future_mean_line", []),
        "macro_future_candles": fc.get("macro_future_candles", []),
        "macro_future_up_band": fc.get("macro_future_up_band", []),
        "macro_future_dn_band": fc.get("macro_future_dn_band", []),
        "macro_future_mean_line": fc.get("macro_future_mean_line", []),
        "suggested_setup": fc.get("suggested_setup"),
        "forecast": fc
    }


class ForecastModeRequest(BaseModel):
    forecast_mode: str = "COMBINED_HTF_LTF"  # "COMBINED_HTF_LTF", "HTF_ANCHOR_ONLY", "LTF_MICRO_ONLY"


@app.post("/api/forecast/mode")
def set_forecast_mode(req: ForecastModeRequest):
    """Switches between Combined HTF+LTF (70/30), HTF Anchor Only (100% H4/H1), and LTF Micro Only."""
    mode = req.forecast_mode.upper().strip()
    if mode not in ("COMBINED_HTF_LTF", "HTF_ANCHOR_ONLY", "LTF_MICRO_ONLY"):
        mode = "COMBINED_HTF_LTF"
    simulator.prob_forecaster.forecast_mode = mode
    fc = simulator.get_current_probabilistic_forecast(include_analogs=True)
    return {
        "success": True,
        "forecast_mode": mode,
        "forecast": fc,
    }


@app.get("/api/live/tick")
def get_live_tick(symbol: Optional[str] = None):
    """Ultra-fast (<10ms) live tick endpoint for 1-second real-time candle ticking."""
    sym = (symbol or simulator.symbol or "XAUUSD").upper().strip()
    try:
        import MetaTrader5 as mt5
        from .data_fetcher import _get_mt5_symbol_name
        if mt5.initialize():
            mt5_sym = _get_mt5_symbol_name(sym) or sym
            tick = mt5.symbol_info_tick(mt5_sym)
            if tick and tick.bid > 0:
                return {
                    "success": True,
                    "symbol": sym,
                    "bid": float(tick.bid),
                    "ask": float(tick.ask),
                    "time": int(tick.time)
                }
    except Exception:
        pass
    return {"success": False, "symbol": sym}


@app.get("/api/live/sync")
def sync_live_realtime(symbol: Optional[str] = None, timeframe_pair: Optional[str] = None):
    """
    Real-Time Live Mode:
    Fetches the latest live multi-timeframe candles directly from MT5 Terminal (or Yahoo/Binance fallback),
    loads the full 3-timeframe dataset, jumps simulator cursor to the latest real-time candle,
    and returns the full chart state + Probabilistic Forecast + Server/VN time.
    """
    sym = (symbol or simulator.symbol or "XAUUSD").upper().strip()
    tf_pair = (timeframe_pair or simulator.timeframe_pair or "H4_H1_M15").upper().strip()
    
    tf1, tf2, tf3 = _parse_tf_triplet(tf_pair, "H4", "H1", "M15")
    normalized_triplet = f"{tf1}_{tf2}_{tf3}"

    # Fast incremental live tail update if dataset for same symbol & timeframe_pair is already in memory
    base_tf = "M1" if "M1" in (tf1, tf2, tf3) else "M5"
    live_source = "MT5_TERMINAL"
    if (
        simulator.symbol == sym
        and getattr(simulator, "timeframe_pair", "") == normalized_triplet
        and simulator.base_candles
        and len(simulator.base_candles) >= 500
    ):
        tail_candles = fetch_mt5_history(sym, base_tf, count=150)
        if tail_candles:
            live_source = "MT5_TERMINAL"
            first_tail_t = tail_candles[0]["time"]
            # Trim overlapping tail and append fresh MT5 bars
            idx_keep = len(simulator.base_candles)
            while idx_keep > 0 and simulator.base_candles[idx_keep - 1]["time"] >= first_tail_t:
                idx_keep -= 1
            simulator.base_candles = simulator.base_candles[:idx_keep] + tail_candles
            simulator.m15_candles = simulator.base_candles
            simulator.sub_candles = simulator.base_candles
            # Keep pre-resampled tf1/tf2/tf3 slices fresh across bar rollovers
            for attr_name, tf_code in (("tf1_all_candles", tf1), ("tf2_all_candles", tf2), ("tf3_all_candles", tf3)):
                existing = getattr(simulator, attr_name, None)
                if existing:
                    tail_res = resample_to_timeframe(simulator.base_candles[max(0, idx_keep - 300):], tf_code)
                    if tail_res:
                        t0 = tail_res[0]["time"]
                        k = len(existing)
                        while k > 0 and existing[k - 1]["time"] >= t0:
                            k -= 1
                        setattr(simulator, attr_name, existing[:k] + tail_res)
            simulator.h4_candles = simulator.tf1_all_candles
            simulator.macro_candles = simulator.tf1_all_candles
            simulator.jump_to_index(len(simulator.base_candles) - 1)
        else:
            simulator.jump_to_index(len(simulator.base_candles) - 1)
    else:
        triplet_data = get_triplet_dataset(sym, tf1=tf1, tf2=tf2, tf3=tf3)
        live_source = triplet_data.get("source", "MT5_TERMINAL")
        base_candles = triplet_data.get("base_candles", [])
        if base_candles:
            simulator.load_triplet_dataset(
                symbol=sym,
                base_candles=base_candles,
                tf1_candles=triplet_data["candles_tf1"],
                tf2_candles=triplet_data["candles_tf2"],
                tf3_candles=triplet_data["candles_tf3"],
                tf1_name=triplet_data["tf1"],
                tf2_name=triplet_data["tf2"],
                tf3_name=triplet_data["tf3"]
            )
            simulator.jump_to_index(len(base_candles) - 1)

    state = get_state()
    state["live_mode"] = True
    state["live_source"] = live_source
    state["dna_session"] = evaluate_dna_session_and_time(sym, simulator.current_time)
    return state


@app.get("/api/live/radar_scan")
def scan_live_multi_pair_radar(timeframe_pair: str = "H4_M15", symbols: Optional[str] = None):
    """
    Scans multiple pairs in Real-Time using the Dual-Tier Combined (HTF Anchor + LTF Trigger) Forecaster.
    Returns strategic plans with Server Time & VN Time (UTC+7), HTF/LTF alignment, Entry/SL/TP, DNA Session status,
    and 3-in-1 Accuracy Trust Scorecard (auto-recording & reconciling in SQLite).
    """
    if symbols:
        sym_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    else:
        sym_list = ["XAUUSD", "EURUSD", "GBPUSD", "USDCAD", "USDJPY", "GBPJPY", "BTCUSD"]

    tf_pair = timeframe_pair.upper().strip()
    is_m5 = (tf_pair == "H1_M5")
    is_h1 = (tf_pair == "H4_H1")
    exec_tf = "M5" if is_m5 else ("H1" if is_h1 else "M15")
    macro_tf = "H1" if is_m5 else "H4"

    forecaster = ProbabilisticContextForecaster(
        horizon_bars=8,
        k_neighbors=35,
        forecast_mode=simulator.prob_forecaster.forecast_mode,
        macro_horizon_bars=6,
    )

    results = []
    for sym in sym_list:
        try:
            ds = fetch_realtime_dataset(sym, timeframe_pair=tf_pair, count=2000)
            sub_c = ds.get("sub_candles", [])
            mac_c = ds.get("macro_candles", [])
            if not sub_c or len(sub_c) < 100:
                continue

            # Ensure walk-forward audit is seeded & reconcile matured forecasts
            forecast_calibrator.ensure_walkforward_audit_populated(
                forecaster, sym, tf_pair, sub_c, mac_c, audit_samples=60, stride=6
            )
            scorecard = forecast_calibrator.get_symbol_scorecard(sym, tf_pair)

            fc = forecaster.forecast_at_bar(
                sub_c,
                mac_c,
                curr_idx=len(sub_c) - 1,
                symbol=sym,
                include_analogs=False,
                timeframe_pair=tf_pair,
            )
            forecast_calibrator.record_forecast(
                sym, tf_pair, int(sub_c[-1]["time"]), fc, source_mode="LIVE"
            )

            dna = fc.get("dna_session") or evaluate_dna_session_and_time(sym, sub_c[-1]["time"])
            setup = fc.get("suggested_setup") or {}
            t2 = scorecard.get("tier2_tactical_setup") or {}
            t1 = scorecard.get("tier1_probabilistic") or {}
            results.append(
                {
                    "symbol": sym,
                    "source": ds.get("source", "LIVE"),
                    "timeframe_pair": tf_pair,
                    "macro_tf": macro_tf,
                    "exec_tf": exec_tf,
                    "price": sub_c[-1]["close"],
                    "time_formatted": dna.get("formatted_short", ""),
                    "time_full": dna.get("formatted_full", ""),
                    "session_status": dna.get("session_status", "NORMAL_SESSION"),
                    "session_badge": dna.get("session_badge", ""),
                    "macro_regime": fc.get("macro_regime", "NEUTRAL"),
                    "macro_prob_up_pct": fc.get("macro_prob_up_pct", 33.3),
                    "macro_prob_down_pct": fc.get("macro_prob_down_pct", 33.3),
                    "macro_prob_sideway_pct": fc.get("macro_prob_sideway_pct", 33.4),
                    "prob_up_pct": fc.get("prob_up_pct", 33.3),
                    "prob_down_pct": fc.get("prob_down_pct", 33.3),
                    "prob_sideway_pct": fc.get("prob_sideway_pct", 33.4),
                    "ltf_prob_up_pct": fc.get("ltf_prob_up_pct", 33.3),
                    "ltf_prob_down_pct": fc.get("ltf_prob_down_pct", 33.3),
                    "dominant_scenario": fc.get("dominant_scenario", "NEUTRAL"),
                    "tactical_status": fc.get("tactical_status", "NEUTRAL"),
                    "tactical_badge": fc.get("tactical_badge", ""),
                    "action": fc.get("action", "NEUTRAL"),
                    "expected_wave_atr": fc.get("expected_wave_atr", 1.5),
                    "setup": setup,
                    "trust_score": scorecard.get("trust_score", 75.0),
                    "trust_badge": scorecard.get("trust_badge", "🟢 Trust 75/100"),
                    "guardrail_status": scorecard.get("guardrail_status", "NORMAL"),
                    "guardrail_badge": scorecard.get("guardrail_badge", ""),
                    "model_version": scorecard.get("model_version", "v3.0-Base"),
                    "setup_winrate_pct": t2.get("setup_winrate_pct", 0.0),
                    "expectancy_r": t2.get("expectancy_r", 0.0),
                    "brier_score": t1.get("brier_score", 0.20),
                    "verified_count": scorecard.get("verified_count", 0),
                }
            )
        except Exception as e:
            print(f"Radar scan error for {sym}: {e}")

    now_dna = evaluate_dna_session_and_time("XAUUSD", int(datetime.now(timezone.utc).timestamp()), is_mt5_server_ts=False)
    return {
        "success": True,
        "scan_time_formatted": now_dna["formatted_full"],
        "timeframe_pair": tf_pair,
        "macro_tf": macro_tf,
        "exec_tf": exec_tf,
        "forecast_mode": simulator.prob_forecaster.forecast_mode,
        "results": results,
    }


@app.get("/api/forecast/accuracy")
def get_forecast_accuracy(symbol: Optional[str] = None, timeframe_pair: Optional[str] = None):
    """
    Returns the 3-in-1 Forecast Accuracy Scorecard, Reliability Calibration Buckets,
    Recent Verified Predictions (with Server Time & VN Time), and Champion Model Profile.
    Automatically seeds the Walk-Forward Audit if SQLite has fewer than 25 verified rows.
    """
    sym = (symbol or simulator.symbol or "XAUUSD").upper().strip()
    tf_pair = (timeframe_pair or simulator.timeframe_pair or "H4_M15").upper().strip()

    if sym == simulator.symbol and tf_pair == simulator.timeframe_pair and simulator.sub_candles:
        sub_c = simulator.sub_candles
        mac_c = simulator.macro_candles
    else:
        ds = fetch_realtime_dataset(sym, timeframe_pair=tf_pair, count=2000)
        sub_c = ds.get("sub_candles", [])
        mac_c = ds.get("macro_candles", [])

    if sub_c:
        forecast_calibrator.ensure_walkforward_audit_populated(
            simulator.prob_forecaster, sym, tf_pair, sub_c, mac_c, audit_samples=75, stride=5
        )

    scorecard = forecast_calibrator.get_symbol_scorecard(sym, tf_pair)
    if sub_c and len(sub_c) >= 220:
        scorecard["learning_benchmark"] = forecast_calibrator.evaluate_self_learning_benchmark(
            simulator.prob_forecaster, sym, tf_pair, sub_c, mac_c
        )
        scorecard["strategy_edge_audit"] = forecast_calibrator.audit_quantitative_strategy_edge(
            simulator.prob_forecaster, sym, tf_pair, sub_c, mac_c
        )
    return {"success": True, "scorecard": scorecard}


class CalibrateModelRequest(BaseModel):
    symbol: Optional[str] = None
    timeframe_pair: Optional[str] = None
    calibrate_all_radar_pairs: bool = False


@app.post("/api/forecast/calibrate")
def trigger_adaptive_calibration(req: CalibrateModelRequest):
    """
    Executes the 3-Layer Bounded Self-Improvement Cycle (Champion vs Challenger)
    for either a single symbol or all active Radar pairs.
    """
    tf_pair = (req.timeframe_pair or simulator.timeframe_pair or "H4_M15").upper().strip()
    if req.calibrate_all_radar_pairs:
        sym_list = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "GBPJPY", "BTCUSD"]
    else:
        sym_list = [(req.symbol or simulator.symbol or "XAUUSD").upper().strip()]

    reports = []
    for sym in sym_list:
        if sym == simulator.symbol and tf_pair == simulator.timeframe_pair and len(simulator.sub_candles) >= 250:
            sub_c = simulator.sub_candles
            mac_c = simulator.macro_candles
        else:
            ds = fetch_realtime_dataset(sym, timeframe_pair=tf_pair, count=2500)
            sub_c = ds.get("sub_candles", [])
            mac_c = ds.get("macro_candles", [])

        if not sub_c or len(sub_c) < 220:
            continue

        rep = forecast_calibrator.run_adaptive_calibration_cycle(
            forecaster=simulator.prob_forecaster,
            symbol=sym,
            timeframe_pair=tf_pair,
            sub_candles=sub_c,
            macro_candles=mac_c,
        )
        reports.append(rep)

    if not reports:
        raise HTTPException(status_code=400, detail="Không đủ dữ liệu nến để chạy hiệu chỉnh mô hình.")

    return {
        "success": True,
        "timeframe_pair": tf_pair,
        "calibrated_count": len(reports),
        "primary_report": reports[0],
        "all_reports": reports,
    }


class ForecastBacktestRequest(BaseModel):
    symbol: Optional[str] = None
    timeframe_pair: Optional[str] = None
    use_prob_filter: bool = True
    horizon_bars: int = 8
    k_neighbors: int = 35
    custom_config: Optional[Dict[str, Any]] = None


@app.post("/api/forecast/backtest")
def run_forecast_backtest(req: ForecastBacktestRequest):
    """Runs full Non-Lookahead Probabilistic Context backtest + k-NN Calibration audit."""
    sym = (req.symbol or simulator.symbol).upper().strip()
    tf_pair = req.timeframe_pair or simulator.timeframe_pair or "H1_M5"
    dataset = get_symbol_dataset(sym, timeframe_pair=tf_pair)
    is_m5 = (tf_pair.upper() == "H1_M5")
    sub_candles = dataset.get("sub_candles", dataset.get("M5" if is_m5 else "M15", []))
    macro_candles = dataset.get("macro_candles", dataset.get("H1" if is_m5 else "H4", []))
    if not sub_candles:
        raise HTTPException(status_code=400, detail="No candle data available for forecast backtest")

    cfg = {
        "preset_name": "v3.0 EMA21 Probabilistic Macro k-NN" if req.use_prob_filter else "v3.0 EMA21 Baseline (No Prob Filter)",
        "engine_type": "EMA21_PROBABILISTIC",
        "use_prob_filter": req.use_prob_filter,
        "horizon_bars": req.horizon_bars,
        "k_neighbors": req.k_neighbors
    }
    if req.custom_config:
        cfg.update(req.custom_config)

    prob_engine = EMA21ProbabilisticSimulatorEngine(symbol=sym, config=cfg, initial_balance=simulator.initial_balance)
    return prob_engine.fast_backtest(sub_candles, macro_candles)


@app.post("/api/ea/step")
def ea_step():
    visible = simulator.get_visible_candles()
    sub_c = visible.get("sub_candles", [])
    if not sub_c:
        raise HTTPException(status_code=400, detail="No candles loaded")
    current_candle = sub_c[-1]
    res = simulator.ea_engine.on_subbar(current_candle) if simulator.ea_engine else {}
    return {
        "success": True,
        "step_result": res,
        "ea_status": simulator.ea_engine.get_hud_status(simulator.current_price) if simulator.ea_engine else None
    }


def start():
    """CLI runner with dynamic port detection and fallback."""
    import uvicorn
    import argparse
    import socket
    import os

    parser = argparse.ArgumentParser(description="Trading Simulator Server")
    parser.add_argument("--port", type=int, default=None, help="Port to listen on (default: 8080 or 8000)")
    args, _ = parser.parse_known_args()

    def is_port_free(p: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", p))
                return True
            except OSError:
                return False

    if args.port:
        port = args.port
    elif os.environ.get("PORT"):
        port = int(os.environ.get("PORT"))
    elif is_port_free(8080):
        port = 8080
    elif is_port_free(8000):
        port = 8000
    elif is_port_free(8001):
        port = 8001
    else:
        port = 8080

    triplet_data = get_triplet_dataset("XAUUSD", tf1="H4", tf2="H1", tf3="M15")
    simulator.load_triplet_dataset(
        symbol="XAUUSD",
        base_candles=triplet_data["base_candles"],
        tf1_candles=triplet_data["candles_tf1"],
        tf2_candles=triplet_data["candles_tf2"],
        tf3_candles=triplet_data["candles_tf3"],
        tf1_name="H4",
        tf2_name="H1",
        tf3_name="M15"
    )
    print("=" * 60)
    print(" [TRADING STRATEGY SIMULATOR & REPLAY ENGINE (DUAL TF H1+M5)]")
    print(f" Server running at: http://localhost:{port}")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    start()

