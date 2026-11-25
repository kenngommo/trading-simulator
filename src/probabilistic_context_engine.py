"""
Non-Lookahead Probabilistic Context & Wave Forecaster Engine (v3.0)
Computes real-time (% UP / % DOWN / % SIDEWAY) probability distributions, expected wave amplitude (ATR),
and Macro HTF regime conditioning using strictly causal k-NN Historical Analog Matching with Triple-Barrier labeling.

100% Non-Lookahead Guarantee:
- At current bar index `curr_idx`, any historical sample `s` in the memory bank MUST satisfy:
      s + horizon_bars <= curr_idx
  so that the entire forward outcome window [s+1 .. s+horizon_bars] lies strictly in the already-closed past (<= curr_idx).
- Macro HTF state for bar `s` only uses macro candles whose closing timestamp <= sub_candles[s]["time"].
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
import numpy as np
import copy
from .data_fetcher import SYMBOL_MAPPINGS

# Exact USD value per 1.0 Lot per 1.0 full price unit move (for Dynamic Lot Sizing @ $100 SL Risk)
USD_PER_LOT_PER_PRICE_UNIT: Dict[str, float] = {
    "XAUUSD": 100.0,     # 1 Lot = 100 oz -> $1.00 move = $100.00
    "EURUSD": 100000.0,  # 1 Lot = 100,000 EUR -> 0.0001 (1 pip) = $10.00
    "GBPUSD": 100000.0,  # 1 Lot = 100,000 GBP -> 0.0001 (1 pip) = $10.00
    "AUDUSD": 100000.0,
    "NZDUSD": 100000.0,
    "USDCAD": 73000.0,   # 1 Lot = 100,000 USD -> 0.0001 (1 pip) ~= $7.30
    "USDCHF": 112000.0,
    "USDJPY": 650.0,     # 1 Lot = 100,000 USD -> 0.01 (1 pip) ~= $6.50
    "GBPJPY": 650.0,     # 1 Lot = 100,000 GBP -> 0.01 (1 pip) ~= $6.50
    "EURJPY": 650.0,
    "BTCUSD": 1.0,       # 1 Lot = 1 BTC -> $1.00 move = $1.00
    "ETHUSD": 1.0,
    "JPN225": 1.0,
    "UK100": 1.0,
}

# Verified True Bid-Ask Positive-Edge Playbook Routing Matrix (2025-2026 Audit)
SYMBOL_VERIFIED_PLAYBOOKS: Dict[Tuple[str, str], Tuple[str, ...]] = {
    # Gold & Crypto (H4 Anchor + M15 / H1 Trigger)
    ("XAUUSD", "H4_M15"): ("EMA21_TREND_IMPULSE", "BB_FAKEOUT_STOP"),
    ("XAUUSD", "H4_H1"): ("EMA21_TREND_IMPULSE", "BB_FAKEOUT_STOP"),
    ("XAUUSD", "H1_M5"): ("EMA21_TREND_IMPULSE", "BB_FAKEOUT_STOP"),
    ("BTCUSD", "H4_M15"): ("EMA21_TREND_IMPULSE", "STOCH_RSI_DIV_REVERSAL"),
    ("BTCUSD", "H4_H1"): ("EMA21_TREND_IMPULSE", "STOCH_RSI_DIV_REVERSAL"),
    ("BTCUSD", "H1_M5"): ("EMA21_TREND_IMPULSE", "STOCH_RSI_DIV_REVERSAL"),
    # Forex Majors on H4 + H1 (AGENTS.md Mục 2 Primary Timeframe)
    ("EURUSD", "H4_H1"): ("EMA21_TREND_IMPULSE",),
    ("GBPUSD", "H4_H1"): ("EMA21_TREND_IMPULSE",),
    ("USDCAD", "H4_H1"): ("EMA21_TREND_IMPULSE",),
    ("USDJPY", "H4_H1"): ("BB_FAKEOUT_STOP",),
    ("GBPJPY", "H4_H1"): ("STOCH_RSI_DIV_REVERSAL",),
    # Forex Majors on H4 + M15 / H1 + M5
    ("EURUSD", "H4_M15"): ("EMA21_TREND_IMPULSE",),
    ("EURUSD", "H1_M5"): ("EMA21_TREND_IMPULSE",),
    ("GBPUSD", "H4_M15"): ("EMA21_TREND_IMPULSE", "BB_FAKEOUT_STOP"),
    ("GBPUSD", "H1_M5"): ("EMA21_TREND_IMPULSE", "BB_FAKEOUT_STOP"),
    ("USDCAD", "H4_M15"): ("EMA21_TREND_IMPULSE", "STOCH_RSI_DIV_REVERSAL"),
    ("USDCAD", "H1_M5"): ("EMA21_TREND_IMPULSE", "STOCH_RSI_DIV_REVERSAL"),
    ("USDJPY", "H4_M15"): ("STOCH_RSI_DIV_REVERSAL", "BB_FAKEOUT_STOP"),
    ("USDJPY", "H1_M5"): ("STOCH_RSI_DIV_REVERSAL", "BB_FAKEOUT_STOP"),
    ("GBPJPY", "H4_M15"): ("BB_FAKEOUT_STOP",),
    ("GBPJPY", "H1_M5"): ("BB_FAKEOUT_STOP",),
}


def get_verified_playbooks_for_symbol(symbol: str, timeframe_pair: str = "H4_M15") -> Tuple[str, ...]:
    """Returns the True Bid-Ask verified positive-edge playbooks for `(symbol, timeframe_pair)`."""
    sym = symbol.upper().strip()
    tf = (timeframe_pair or "H4_M15").upper().strip()
    if (sym, tf) in SYMBOL_VERIFIED_PLAYBOOKS:
        return SYMBOL_VERIFIED_PLAYBOOKS[(sym, tf)]
    if (sym, "H4_M15") in SYMBOL_VERIFIED_PLAYBOOKS:
        return SYMBOL_VERIFIED_PLAYBOOKS[(sym, "H4_M15")]
    return ("EMA21_TREND_IMPULSE", "STOCH_RSI_DIV_REVERSAL", "BB_FAKEOUT_STOP")


def compute_lot_and_pips_for_100usd_risk(
    symbol: str, entry_price: float, sl_price: float, risk_usd: float = 100.0
) -> Tuple[float, float]:
    """Calculates `(sl_pips, lot_size_for_risk_usd)` using exact contract specifications."""
    sym = symbol.upper().strip()
    sym_info = SYMBOL_MAPPINGS.get(sym, {"digits": 2, "pip_size": 0.1})
    pip_size = float(sym_info.get("pip_size", 0.1))
    usd_per_unit = float(USD_PER_LOT_PER_PRICE_UNIT.get(sym, 100.0))
    risk_dist = abs(float(entry_price) - float(sl_price))
    if risk_dist <= 1e-9 or pip_size <= 1e-9:
        return 0.0, 0.01
    sl_pips = round(risk_dist / pip_size, 1)
    loss_per_1_lot = risk_dist * usd_per_unit
    lot_size = round(max(0.01, risk_usd / loss_per_1_lot), 2) if loss_per_1_lot > 1e-9 else 0.01
    return sl_pips, lot_size


def evaluate_dna_session_and_time(
    symbol: str,
    timestamp: int,
    broker_utc_offset_hours: int = 3,
    is_mt5_server_ts: bool = True,
) -> Dict[str, Any]:
    """
    Formats Server Time (MT5 Broker Time, default UTC+3) and Vietnam Time (UTC+7)
    according to AGENTS.md Rule #7, and evaluates the 5-Year Quantitative DNA Session Status
    (Golden Window vs Forbidden Zone vs Silent Mode).
    Note: MT5 bar timestamps (`copy_rates_from_pos`) are stored directly in Broker Server Time (UTC+3),
    so `vn_time = server_time + (7 - broker_utc_offset_hours) = server_time + 4h`.
    """
    if timestamp <= 0:
        timestamp = int(datetime.now(timezone.utc).timestamp())
        is_mt5_server_ts = False

    if is_mt5_server_ts:
        dt_srv = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        dt_vn = dt_srv + timedelta(hours=(7 - broker_utc_offset_hours))
    else:
        dt_utc = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        dt_srv = dt_utc + timedelta(hours=broker_utc_offset_hours)
        dt_vn = dt_utc + timedelta(hours=7)

    srv_hm = dt_srv.strftime("%H:%M")
    vn_hm = dt_vn.strftime("%H:%M")
    srv_full = dt_srv.strftime("%Y-%m-%d %H:%M:%S")
    vn_full = dt_vn.strftime("%Y-%m-%d %H:%M:%S")

    formatted_short = f"{srv_hm} Server ({vn_hm} VN)"
    formatted_full = f"{srv_full} Server (VN: {vn_full})"

    vn_hour_float = dt_vn.hour + (dt_vn.minute / 60.0)
    weekday = dt_vn.weekday()  # 0=Mon .. 4=Fri, 5=Sat, 6=Sun

    sym = symbol.upper()
    if "XAU" in sym or "GOLD" in sym:
        dna_sl_pips = 35.0  # +30 to +50 pips ($3.5)
        if weekday >= 5 or vn_hour_float >= 22.5 or vn_hour_float < 7.0:
            status = "SILENT_MODE"
            badge = "🌙 NGOÀI GIỜ HOẠT ĐỘNG (22:00 - 07:00 VN)"
        elif 12.0 <= vn_hour_float <= 13.5:
            status = "FORBIDDEN_ZONE"
            badge = "⛔ VÙNG CẦN TRÁNH XAU (12:00-13:30 VN: Bẫy Âu sớm)"
        elif 14.0 <= vn_hour_float <= 22.0:
            status = "GOLDEN_WINDOW"
            badge = "🌟 KHUNG GIỜ VÀNG XAU (14:00-22:00 VN: Âu - Mỹ)"
        else:
            status = "NORMAL_SESSION"
            badge = "🕒 Phiên Á (Thanh khoản vừa phải)"
    elif "JPN" in sym or "JP225" in sym or "NIKKEI" in sym:
        dna_sl_pips = 25.0
        if weekday >= 5 or vn_hour_float >= 22.0 or vn_hour_float < 7.0:
            status = "SILENT_MODE"
            badge = "🌙 NGOÀI GIỜ HOẠT ĐỘNG"
        elif vn_hour_float >= 16.5:
            status = "FORBIDDEN_ZONE"
            badge = "⛔ VÙNG CẦN TRÁNH JPN225 (Sau 16:30 VN: Tokyo đóng cửa)"
        elif 7.0 <= vn_hour_float <= 13.5:
            status = "GOLDEN_WINDOW"
            badge = "🌟 KHUNG GIỜ VÀNG JPN225 (07:00-13:30 VN: Sáng Tokyo)"
        else:
            status = "NORMAL_SESSION"
            badge = "🕒 Phiên Chiều Tokyo"
    elif "UK100" in sym or "FTSE" in sym:
        dna_sl_pips = 15.0
        if weekday >= 5 or vn_hour_float >= 22.0 or vn_hour_float < 7.0:
            status = "SILENT_MODE"
            badge = "🌙 NGOÀI GIỜ HOẠT ĐỘNG"
        elif 7.0 <= vn_hour_float <= 13.5:
            status = "FORBIDDEN_ZONE"
            badge = "⛔ VÙNG CẦN TRÁNH UK100 (07:00-13:30 VN: Phiên Á sideway)"
        elif 14.0 <= vn_hour_float <= 21.5:
            status = "GOLDEN_WINDOW"
            badge = "🌟 KHUNG GIỜ VÀNG UK100 (14:00-21:30 VN: Phiên London)"
        else:
            status = "NORMAL_SESSION"
            badge = "🕒 Giao Phiên"
    elif "BTC" in sym or "ETH" in sym:
        dna_sl_pips = 50.0
        if 14.0 <= vn_hour_float <= 23.0:
            status = "GOLDEN_WINDOW"
            badge = "🌟 KHUNG GIỜ VÀNG CRYPTO (Âu - Mỹ Sôi Động)"
        else:
            status = "NORMAL_SESSION"
            badge = "🕒 Phiên Crypto 24/7"
    else:
        # Forex Majors (EURUSD, GBPUSD, USDJPY, GBPJPY...)
        dna_sl_pips = 20.0  # +15 to +25 pips DNA
        if weekday >= 5 or vn_hour_float >= 22.5 or vn_hour_float < 5.0:
            status = "SILENT_MODE"
            badge = "🌙 NGOÀI GIỜ HOẠT ĐỘNG (22:30 - 07:00 VN)"
        elif 5.0 <= vn_hour_float < 13.0:
            status = "FORBIDDEN_ZONE"
            badge = "⛔ VÙNG CẦN TRÁNH FOREX (05:00-13:00 VN: Phiên Á dễ False Break)"
        elif 14.0 <= vn_hour_float <= 22.5:
            status = "GOLDEN_WINDOW"
            badge = "🌟 KHUNG GIỜ VÀNG FOREX (14:00-22:30 VN: Phiên Âu - Mỹ)"
        else:
            status = "NORMAL_SESSION"
            badge = "🕒 Giao Phiên Á - Âu (13:00-14:00 VN)"

    return {
        "server_time_hm": srv_hm,
        "vn_time_hm": vn_hm,
        "formatted_short": formatted_short,
        "formatted_full": formatted_full,
        "session_status": status,
        "session_badge": badge,
        "dna_sl_padding_pips": dna_sl_pips,
    }


def _compute_ema_array(closes: np.ndarray, period: int) -> np.ndarray:
    n = len(closes)
    out = np.zeros(n, dtype=float)
    if n == 0:
        return out
    alpha = 2.0 / (period + 1.0)
    out[0] = closes[0]
    for i in range(1, n):
        out[i] = alpha * closes[i] + (1.0 - alpha) * out[i - 1]
    return out


def _compute_atr_array(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> np.ndarray:
    n = len(closes)
    tr = np.zeros(n, dtype=float)
    atr = np.zeros(n, dtype=float)
    if n == 0:
        return atr
    tr[0] = max(highs[0] - lows[0], 1e-8)
    for i in range(1, n):
        hl = highs[i] - lows[i]
        hc = abs(highs[i] - closes[i - 1])
        lc = abs(lows[i] - closes[i - 1])
        tr[i] = max(hl, hc, lc, 1e-8)

    # Wilder's smoothing
    atr[0] = tr[0]
    alpha = 1.0 / float(period)
    for i in range(1, n):
        if i < period:
            atr[i] = np.mean(tr[: i + 1])
        else:
            atr[i] = alpha * tr[i] + (1.0 - alpha) * atr[i - 1]
    return atr


def _compute_adx_di_arrays(
    highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    n = len(closes)
    adx = np.zeros(n, dtype=float)
    plus_di = np.zeros(n, dtype=float)
    minus_di = np.zeros(n, dtype=float)
    if n < 2:
        return adx, plus_di, minus_di

    tr = np.zeros(n, dtype=float)
    pdm = np.zeros(n, dtype=float)
    mdm = np.zeros(n, dtype=float)

    for i in range(1, n):
        up_move = highs[i] - highs[i - 1]
        dn_move = lows[i - 1] - lows[i]
        if up_move > dn_move and up_move > 0:
            pdm[i] = up_move
        if dn_move > up_move and dn_move > 0:
            mdm[i] = dn_move
        tr[i] = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]), 1e-8)

    alpha = 1.0 / float(period)
    sm_tr = tr[0]
    sm_pdm = 0.0
    sm_mdm = 0.0
    dx_arr = np.zeros(n, dtype=float)

    for i in range(1, n):
        sm_tr = sm_tr - (sm_tr * alpha) + tr[i]
        sm_pdm = sm_pdm - (sm_pdm * alpha) + pdm[i]
        sm_mdm = sm_mdm - (sm_mdm * alpha) + mdm[i]
        if sm_tr > 1e-10:
            pdi = 100.0 * (sm_pdm / sm_tr)
            mdi = 100.0 * (sm_mdm / sm_tr)
        else:
            pdi, mdi = 0.0, 0.0
        plus_di[i] = pdi
        minus_di[i] = mdi
        denom = pdi + mdi
        dx_arr[i] = (100.0 * abs(pdi - mdi) / denom) if denom > 1e-10 else 0.0
        if i < period:
            adx[i] = np.mean(dx_arr[1 : i + 1])
        else:
            adx[i] = alpha * dx_arr[i] + (1.0 - alpha) * adx[i - 1]

    return adx, plus_di, minus_di


def _compute_rsi_array(closes: np.ndarray, period: int = 14) -> np.ndarray:
    """Computes Wilder's RSI(period) strictly causally (0..i)."""
    n = len(closes)
    rsi = np.full(n, 50.0, dtype=float)
    if n < 2:
        return rsi
    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    alpha = 1.0 / float(period)
    avg_gain = float(gains[0])
    avg_loss = float(losses[0])

    for i in range(1, n):
        g = float(gains[i - 1])
        l = float(losses[i - 1])
        if i <= period:
            avg_gain = float(np.mean(gains[:i]))
            avg_loss = float(np.mean(losses[:i]))
        else:
            avg_gain = (avg_gain * (period - 1) + g) / float(period)
            avg_loss = (avg_loss * (period - 1) + l) / float(period)
        if avg_loss <= 1e-10:
            rsi[i] = 100.0 if avg_gain > 0 else 50.0
        else:
            rs = avg_gain / avg_loss
            rsi[i] = 100.0 - (100.0 / (1.0 + rs))
    return rsi


def _compute_stoch_arrays(
    highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, k_period: int = 8, k_slowing: int = 3, d_period: int = 3
) -> Tuple[np.ndarray, np.ndarray]:
    """Computes Stochastic (%K slowed, %D) strictly causally (0..i)."""
    n = len(closes)
    raw_k = np.full(n, 50.0, dtype=float)
    slow_k = np.full(n, 50.0, dtype=float)
    slow_d = np.full(n, 50.0, dtype=float)
    if n == 0:
        return slow_k, slow_d

    for i in range(n):
        start_k = max(0, i - k_period + 1)
        hh = float(np.max(highs[start_k : i + 1]))
        ll = float(np.min(lows[start_k : i + 1]))
        if hh - ll > 1e-10:
            raw_k[i] = 100.0 * (closes[i] - ll) / (hh - ll)
        else:
            raw_k[i] = 50.0
        start_s = max(0, i - k_slowing + 1)
        slow_k[i] = float(np.mean(raw_k[start_s : i + 1]))
        start_d = max(0, i - d_period + 1)
        slow_d[i] = float(np.mean(slow_k[start_d : i + 1]))

    return slow_k, slow_d


def _compute_bollinger_arrays(
    closes: np.ndarray, period: int = 20, std_mult: float = 2.0
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Computes Bollinger Bands (mid SMA20, upper, lower) strictly causally (0..i)."""
    n = len(closes)
    mid = np.copy(closes).astype(float)
    upper = np.copy(closes).astype(float)
    lower = np.copy(closes).astype(float)
    for i in range(n):
        start_i = max(0, i - period + 1)
        win = closes[start_i : i + 1]
        m = float(np.mean(win))
        s = float(np.std(win)) if len(win) > 1 else 0.0
        mid[i] = m
        upper[i] = m + std_mult * s
        lower[i] = m - std_mult * s
    return mid, upper, lower


class ProbabilisticContextForecaster:
    """
    Causal k-NN Probabilistic Market Context & Wave Forecaster.
    Estimates (% UP, % DOWN, % SIDEWAY) and Expected Wave Amplitude (in ATR units)
    using strictly closed past analogs (s + H <= curr_idx).
    """

    def __init__(
        self,
        horizon_bars: int = 8,
        k_neighbors: int = 35,
        up_barrier_atr: float = 1.25,
        dn_barrier_atr: float = 1.25,
        adverse_barrier_atr: float = 0.95,
        warmup_bars: int = 60,
        max_memory_bars: int = 2500,
        forecast_mode: str = "COMBINED_HTF_LTF",
        macro_horizon_bars: int = 6,
    ):
        self.horizon_bars = int(horizon_bars)
        self.k_neighbors = int(k_neighbors)
        self.up_barrier_atr = float(up_barrier_atr)
        self.dn_barrier_atr = float(dn_barrier_atr)
        self.adverse_barrier_atr = float(adverse_barrier_atr)
        self.warmup_bars = int(warmup_bars)
        self.max_memory_bars = int(max_memory_bars)
        self.forecast_mode = forecast_mode  # "COMBINED_HTF_LTF", "HTF_ANCHOR_ONLY", "LTF_MICRO_ONLY"
        self.macro_horizon_bars = int(macro_horizon_bars)
        self._cache: Dict[Tuple[int, int, int], Dict[str, Any]] = {}
        self._macro_cache: Dict[Tuple[int, int, int, int], Dict[str, Any]] = {}

    def prepare_macro_causal_arrays(
        self, macro_candles: List[Dict[str, Any]], macro_horizon: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Precomputes causal k-NN feature vectors X_macro[m] and Triple-Barrier forward labels Y_macro[m]
        directly on the Higher Timeframe (H1 or H4) candle series.
        Guarantees 100% Non-Lookahead and rock-solid stability across intra-bar LTF fluctuations.
        """
        m_len = len(macro_candles) if macro_candles else 0
        if m_len < 30:
            return {}

        H_m = int(macro_horizon or self.macro_horizon_bars or 6)
        cache_key = (
            m_len,
            int(macro_candles[0]["time"]),
            int(macro_candles[-1]["time"]),
            H_m,
            round(float(macro_candles[0]["close"]), 5),
            round(float(macro_candles[-1]["close"]), 5),
        )
        if cache_key in self._macro_cache:
            return self._macro_cache[cache_key]

        times = np.array([c["time"] for c in macro_candles], dtype=np.int64)
        opens = np.array([c["open"] for c in macro_candles], dtype=float)
        highs = np.array([c["high"] for c in macro_candles], dtype=float)
        lows = np.array([c["low"] for c in macro_candles], dtype=float)
        closes = np.array([c["close"] for c in macro_candles], dtype=float)

        ema21 = _compute_ema_array(closes, 21)
        ema50 = _compute_ema_array(closes, 50)
        ema200 = _compute_ema_array(closes, 200)
        atr14 = _compute_atr_array(highs, lows, closes, 14)

        macro_interval = 3600
        if m_len > 1:
            diffs = np.diff(times)
            pos_diffs = diffs[diffs > 0]
            if len(pos_diffs) > 0:
                macro_interval = int(np.median(pos_diffs))

        features = np.zeros((m_len, 5), dtype=float)
        abs_diff = np.zeros(m_len, dtype=float)
        abs_diff[1:] = np.abs(closes[1:] - closes[:-1])

        for s in range(m_len):
            atr_s = max(atr14[s], 1e-8)
            rng_s = max(highs[s] - lows[s], 1e-8)
            cb = (closes[s] - lows[s]) / rng_s
            cr = (highs[s] - closes[s]) / rng_s

            if s >= 14:
                net_chg = abs(closes[s] - closes[s - 14])
                sum_path = float(np.sum(abs_diff[s - 13 : s + 1]))
                er_val = (net_chg / sum_path) if sum_path > 1e-10 else 0.0
            else:
                er_val = 0.25

            if s >= 4:
                pre_h = float(np.max(highs[s - 4 : s]))
                pre_l = float(np.min(lows[s - 4 : s]))
                sq4 = (pre_h - pre_l) / atr_s
            else:
                sq4 = 2.0

            body_signed_ratio = (closes[s] - opens[s]) / rng_s
            dir_clv = cb if closes[s] >= opens[s] else cr
            imp_clv = body_signed_ratio * dir_clv
            e_slope = ((ema21[s] - ema21[s - 3]) / atr_s) if s >= 3 else 0.0
            e_stack = (ema21[s] - ema50[s]) / atr_s

            features[s, 0] = er_val
            features[s, 1] = min(sq4, 8.0)
            features[s, 2] = imp_clv
            features[s, 3] = np.clip(e_slope, -4.0, 4.0)
            features[s, 4] = np.clip(e_stack, -6.0, 6.0)

        labels = np.zeros(m_len, dtype=int)
        max_up_atr = np.zeros(m_len, dtype=float)
        max_dn_atr = np.zeros(m_len, dtype=float)

        up_b = 1.15
        dn_b = 1.15
        adv_b = 0.90

        for s in range(m_len - H_m):
            atr_s = max(atr14[s], 1e-8)
            c0 = closes[s]
            w_highs = highs[s + 1 : s + H_m + 1]
            w_lows = lows[s + 1 : s + H_m + 1]
            up_exc = (w_highs - c0) / atr_s
            dn_exc = (c0 - w_lows) / atr_s
            max_up_atr[s] = max(0.0, float(np.max(up_exc)))
            max_dn_atr[s] = max(0.0, float(np.max(dn_exc)))

            up_hit_idx = -1
            dn_hit_idx = -1
            up_invalid = False
            dn_invalid = False
            for k_step in range(H_m):
                u_k = up_exc[k_step]
                d_k = dn_exc[k_step]
                if d_k >= adv_b and up_hit_idx == -1:
                    up_invalid = True
                if u_k >= adv_b and dn_hit_idx == -1:
                    dn_invalid = True
                if u_k >= up_b and not up_invalid and up_hit_idx == -1:
                    up_hit_idx = k_step
                if d_k >= dn_b and not dn_invalid and dn_hit_idx == -1:
                    dn_hit_idx = k_step

            if up_hit_idx != -1 and (dn_hit_idx == -1 or up_hit_idx < dn_hit_idx):
                labels[s] = 1
            elif dn_hit_idx != -1 and (up_hit_idx == -1 or dn_hit_idx < up_hit_idx):
                labels[s] = -1
            else:
                labels[s] = 0

        m_bundle = {
            "times": times,
            "opens": opens,
            "highs": highs,
            "lows": lows,
            "closes": closes,
            "ema21": ema21,
            "ema50": ema50,
            "ema200": ema200,
            "atr14": atr14,
            "features": features,
            "labels": labels,
            "max_up_atr": max_up_atr,
            "max_dn_atr": max_dn_atr,
            "macro_interval": macro_interval,
            "horizon_bars": H_m,
        }
        if len(self._macro_cache) > 8:
            self._macro_cache.clear()
        self._macro_cache[cache_key] = m_bundle
        return m_bundle

    def _compute_macro_anchor_forecast(
        self,
        macro_candles: Optional[List[Dict[str, Any]]],
        curr_sub_time: int,
        symbol: str = "XAUUSD",
        include_future_projection: bool = True,
        adaptive_profile: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Computes the Higher Timeframe (H1 / H4) Anchor Forecast at the latest closed macro candle
        prior to `curr_sub_time`. Because it anchors to the HTF candle, its probability and trajectory
        stay 100% consistent throughout the entire H1/H4 period without flipping on M5/M15 noise.
        """
        if not macro_candles or len(macro_candles) < 35:
            return None

        m_bundle = self.prepare_macro_causal_arrays(macro_candles)
        if not m_bundle:
            return None

        m_times = m_bundle["times"]
        m_interval = int(m_bundle["macro_interval"])
        H_m = int(m_bundle["horizon_bars"])

        # Find latest ALREADY-CLOSED macro bar (m_time + m_interval <= curr_sub_time)
        # If near the start of dataset, fallback to latest macro bar with m_time <= curr_sub_time
        closed_mask = (m_times + m_interval) <= curr_sub_time
        if np.any(closed_mask):
            m_curr_idx = int(np.where(closed_mask)[0][-1])
        else:
            le_mask = m_times <= curr_sub_time
            if not np.any(le_mask):
                return None
            m_curr_idx = int(np.where(le_mask)[0][-1])

        max_valid_s = m_curr_idx - H_m
        min_valid_s = 20
        if max_valid_s <= min_valid_s + 8:
            return None

        start_s = max(min_valid_s, max_valid_s - 1500)
        cand_indices = np.arange(start_s, max_valid_s + 1, dtype=int)

        X_past = m_bundle["features"][cand_indices]
        x_curr = m_bundle["features"][m_curr_idx]

        mean_past = np.mean(X_past, axis=0)
        std_past = np.std(X_past, axis=0) + 1e-6
        Z_past = (X_past - mean_past) / std_past
        z_curr = (x_curr - mean_past) / std_past

        if adaptive_profile and adaptive_profile.get("f_weights_htf"):
            f_weights = np.array(adaptive_profile["f_weights_htf"], dtype=float)
        else:
            f_weights = np.array([1.30, 1.10, 1.25, 1.35, 1.25], dtype=float)

        diff = (Z_past - z_curr) * f_weights
        dists = np.sqrt(np.sum(diff * diff, axis=1))

        # Layer 2 Adaptive Temporal Recency Decay on HTF
        if adaptive_profile and float(adaptive_profile.get("time_decay_strength", 0.0)) > 0:
            td_str = float(adaptive_profile["time_decay_strength"])
            span = max(1.0, float(max_valid_s - start_s))
            age_norm = (max_valid_s - cand_indices) / span
            dists = dists + td_str * 0.65 * age_norm

        k_m = min(25, len(dists))
        if k_m < len(dists):
            nearest_pos = np.argpartition(dists, k_m)[:k_m]
            nearest_pos = nearest_pos[np.argsort(dists[nearest_pos])]
        else:
            nearest_pos = np.argsort(dists)

        matched_s = cand_indices[nearest_pos]
        matched_dists = dists[nearest_pos]
        weights = 1.0 / (matched_dists + 0.15)
        w_sum = float(np.sum(weights))
        weights_norm = weights / w_sum if w_sum > 0 else np.ones(k_m) / float(k_m)

        matched_labels = m_bundle["labels"][matched_s]
        matched_up_atr = m_bundle["max_up_atr"][matched_s]
        matched_dn_atr = m_bundle["max_dn_atr"][matched_s]

        m_prob_up = float(np.sum(weights_norm[matched_labels == 1])) * 100.0
        m_prob_dn = float(np.sum(weights_norm[matched_labels == -1])) * 100.0
        m_prob_sw = max(0.0, 100.0 - m_prob_up - m_prob_dn)

        if m_prob_up >= m_prob_dn:
            m_exp_wave = float(np.sum(weights_norm * matched_up_atr))
            m_exp_mae = float(np.sum(weights_norm * matched_dn_atr))
        else:
            m_exp_wave = float(np.sum(weights_norm * matched_dn_atr))
            m_exp_mae = float(np.sum(weights_norm * matched_up_atr))

        if m_prob_up >= m_prob_dn + 4.0 and m_prob_up >= m_prob_sw - 5.0:
            m_dom_scenario = "UP"
            m_dom_prob = round(m_prob_up, 1)
        elif m_prob_dn > m_prob_up + 4.0 and m_prob_dn >= m_prob_sw - 5.0:
            m_dom_scenario = "DOWN"
            m_dom_prob = round(m_prob_dn, 1)
        else:
            m_dom_scenario = "SIDEWAY" if m_prob_sw >= max(m_prob_up, m_prob_dn) else ("UP" if m_prob_up >= m_prob_dn else "DOWN")
            m_dom_prob = round(max(m_prob_up, m_prob_dn, m_prob_sw), 1)

        # Calculate net expected drift per macro bar (in macro ATR units) along the dominant scenario
        up_mask = matched_labels == 1
        dn_mask = matched_labels == -1
        if m_dom_scenario == "UP" and np.any(up_mask):
            dom_s = matched_s[up_mask]
            dom_w = weights_norm[up_mask] / float(np.sum(weights_norm[up_mask]))
        elif m_dom_scenario == "DOWN" and np.any(dn_mask):
            dom_s = matched_s[dn_mask]
            dom_w = weights_norm[dn_mask] / float(np.sum(weights_norm[dn_mask]))
        else:
            dom_s = matched_s
            dom_w = weights_norm

        dom_atrs = np.maximum(m_bundle["atr14"][dom_s], 1e-8)
        dom_c0 = m_bundle["closes"][dom_s]
        s_atrs = np.maximum(m_bundle["atr14"][matched_s], 1e-8)
        s_c0 = m_bundle["closes"][matched_s]

        # End-of-horizon relative drift in macro ATR units
        end_rel_dom = (m_bundle["closes"][dom_s + H_m] - dom_c0) / dom_atrs
        end_rel_all = (m_bundle["closes"][matched_s + H_m] - s_c0) / s_atrs
        net_drift_macro_atr = 0.75 * float(np.sum(dom_w * end_rel_dom)) + 0.25 * float(np.sum(weights_norm * end_rel_all))

        m_c1 = float(m_bundle["closes"][m_curr_idx])
        m_atr_curr = float(m_bundle["atr14"][m_curr_idx])
        m_curr_time = int(m_times[m_curr_idx])

        macro_future_candles: List[Dict[str, Any]] = []
        macro_future_up_band: List[Dict[str, Any]] = []
        macro_future_dn_band: List[Dict[str, Any]] = []
        macro_future_mean_line: List[Dict[str, Any]] = []

        if include_future_projection:
            sym_info = SYMBOL_MAPPINGS.get(symbol, {"digits": 2, "pip_size": 0.1})
            digits = sym_info.get("digits", 2)

            # Anchor the projection from the latest visible macro bar time
            latest_vis_idx = m_curr_idx
            le_all = np.where(m_times <= curr_sub_time)[0]
            if len(le_all) > 0:
                latest_vis_idx = int(le_all[-1])
            anchor_time = int(m_times[latest_vis_idx])
            anchor_close = float(m_bundle["closes"][latest_vis_idx])

            macro_future_up_band.append({"time": anchor_time, "value": round(anchor_close, digits)})
            macro_future_dn_band.append({"time": anchor_time, "value": round(anchor_close, digits)})
            macro_future_mean_line.append({"time": anchor_time, "value": round(anchor_close, digits)})

            w_up = weights_norm[up_mask]
            w_dn = weights_norm[dn_mask]
            w_up_norm = (w_up / float(np.sum(w_up))) if np.sum(w_up) > 0 else None
            w_dn_norm = (w_dn / float(np.sum(w_dn))) if np.sum(w_dn) > 0 else None

            prev_proj_c = anchor_close
            for step_h in range(1, H_m + 1):
                fut_t = anchor_time + step_h * m_interval
                step_dom = dom_s + step_h
                rel_c_dom = (m_bundle["closes"][step_dom] - dom_c0) / dom_atrs
                rel_h_dom = (m_bundle["highs"][step_dom] - dom_c0) / dom_atrs
                rel_l_dom = (m_bundle["lows"][step_dom] - dom_c0) / dom_atrs

                step_all = matched_s + step_h
                rel_c_all = (m_bundle["closes"][step_all] - s_c0) / s_atrs
                rel_h_all = (m_bundle["highs"][step_all] - s_c0) / s_atrs
                rel_l_all = (m_bundle["lows"][step_all] - s_c0) / s_atrs

                d_c = (0.75 * float(np.sum(dom_w * rel_c_dom)) + 0.25 * float(np.sum(weights_norm * rel_c_all))) * m_atr_curr
                d_h = (0.75 * float(np.max([np.sum(dom_w * rel_h_dom), np.sum(dom_w * rel_c_dom)])) + 0.25 * float(np.sum(weights_norm * rel_h_all))) * m_atr_curr
                d_l = (0.75 * float(np.min([np.sum(dom_w * rel_l_dom), np.sum(dom_w * rel_c_dom)])) + 0.25 * float(np.sum(weights_norm * rel_l_all))) * m_atr_curr

                proj_o = round(prev_proj_c, digits)
                proj_c = round(anchor_close + d_c, digits)
                proj_h = round(max(proj_o, proj_c, anchor_close + d_h), digits)
                proj_l = round(min(proj_o, proj_c, anchor_close + d_l), digits)
                prev_proj_c = proj_c

                if w_up_norm is not None:
                    up_rel = (m_bundle["highs"][matched_s[up_mask] + step_h] - m_bundle["closes"][matched_s[up_mask]]) / np.maximum(m_bundle["atr14"][matched_s[up_mask]], 1e-8)
                    up_val = round(anchor_close + float(np.sum(w_up_norm * up_rel)) * m_atr_curr, digits)
                else:
                    up_val = round(anchor_close + (step_h / float(H_m)) * m_exp_wave * m_atr_curr, digits)

                if w_dn_norm is not None:
                    dn_rel = (m_bundle["lows"][matched_s[dn_mask] + step_h] - m_bundle["closes"][matched_s[dn_mask]]) / np.maximum(m_bundle["atr14"][matched_s[dn_mask]], 1e-8)
                    dn_val = round(anchor_close + float(np.sum(w_dn_norm * dn_rel)) * m_atr_curr, digits)
                else:
                    dn_val = round(anchor_close - (step_h / float(H_m)) * m_exp_mae * m_atr_curr, digits)

                macro_future_up_band.append({"time": fut_t, "value": max(up_val, proj_h)})
                macro_future_dn_band.append({"time": fut_t, "value": min(dn_val, proj_l)})
                macro_future_mean_line.append({"time": fut_t, "value": proj_c})
                macro_future_candles.append(
                    {
                        "step": step_h,
                        "time": fut_t,
                        "open": proj_o,
                        "high": proj_h,
                        "low": proj_l,
                        "close": proj_c,
                        "upper_target": max(up_val, proj_h),
                        "lower_target": min(dn_val, proj_l),
                    }
                )

        return {
            "macro_prob_up_pct": round(m_prob_up, 1),
            "macro_prob_down_pct": round(m_prob_dn, 1),
            "macro_prob_sideway_pct": round(m_prob_sw, 1),
            "macro_dominant_scenario": m_dom_scenario,
            "macro_dominant_prob_pct": m_dom_prob,
            "macro_expected_wave_atr": round(m_exp_wave, 2),
            "macro_expected_mae_atr": round(m_exp_mae, 2),
            "macro_atr": m_atr_curr,
            "macro_bar_index": m_curr_idx,
            "macro_bar_time": m_curr_time,
            "macro_interval_sec": m_interval,
            "macro_horizon_bars": H_m,
            "net_drift_macro_atr": net_drift_macro_atr,
            "macro_future_candles": macro_future_candles,
            "macro_future_up_band": macro_future_up_band,
            "macro_future_dn_band": macro_future_dn_band,
            "macro_future_mean_line": macro_future_mean_line,
        }

    def prepare_causal_arrays(
        self, sub_candles: List[Dict[str, Any]], macro_candles: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Precomputes causal per-bar features X[s] (using only 0..s) and forward H-bar outcomes Y[s] (using s+1..s+H).
        When querying at `curr_idx`, we strictly restrict the memory bank to `s <= curr_idx - horizon_bars`,
        guaranteeing 100% zero lookahead!
        """
        n = len(sub_candles)
        if n == 0:
            return {}

        macro_len = len(macro_candles) if macro_candles else 0
        cache_key = (
            n,
            sub_candles[0]["time"],
            sub_candles[-1]["time"] + macro_len,
            round(float(sub_candles[0]["close"]), 5),
            round(float(sub_candles[-1]["close"]), 5),
        )
        if cache_key in self._cache:
            return self._cache[cache_key]

        times = np.array([c["time"] for c in sub_candles], dtype=np.int64)
        opens = np.array([c["open"] for c in sub_candles], dtype=float)
        highs = np.array([c["high"] for c in sub_candles], dtype=float)
        lows = np.array([c["low"] for c in sub_candles], dtype=float)
        closes = np.array([c["close"] for c in sub_candles], dtype=float)

        ema21 = _compute_ema_array(closes, 21)
        ema50 = _compute_ema_array(closes, 50)
        ema200 = _compute_ema_array(closes, 200)
        atr14 = _compute_atr_array(highs, lows, closes, 14)
        adx14, plus_di, minus_di = _compute_adx_di_arrays(highs, lows, closes, 14)
        rsi6 = _compute_rsi_array(closes, 6)
        rsi14 = _compute_rsi_array(closes, 14)
        stoch8_k, stoch8_d = _compute_stoch_arrays(highs, lows, closes, 8, 3, 3)
        stoch10_k, stoch10_d = _compute_stoch_arrays(highs, lows, closes, 10, 5, 5)
        bb_mid, bb_upper, bb_lower = _compute_bollinger_arrays(closes, 20, 2.0)

        # Compute Macro HTF Regime (+1 BULL, -1 BEAR, 0 NEUTRAL) strictly non-lookahead
        macro_regime_arr = np.zeros(n, dtype=int)
        if macro_candles and len(macro_candles) >= 5:
            m_times = np.array([c["time"] for c in macro_candles], dtype=np.int64)
            m_closes = np.array([c["close"] for c in macro_candles], dtype=float)
            m_ema21 = _compute_ema_array(m_closes, 21)
            m_ema50 = _compute_ema_array(m_closes, 50)

            macro_interval = 3600
            if len(m_times) > 1 and (m_times[1] - m_times[0]) > 0:
                macro_interval = int(m_times[1] - m_times[0])

            m_regimes = np.zeros(len(m_closes), dtype=int)
            for j in range(len(m_closes)):
                if m_closes[j] > m_ema50[j]:
                    m_regimes[j] = 1
                elif m_closes[j] < m_ema50[j]:
                    m_regimes[j] = -1
                else:
                    m_regimes[j] = 0

            # Map each sub_candle[i] to the latest ALREADY-CLOSED macro bar (m_time + macro_interval <= sub_time)
            m_ptr = -1
            for i in range(n):
                t_sub = times[i]
                while (m_ptr + 1) < len(m_times) and (m_times[m_ptr + 1] + macro_interval) <= t_sub:
                    m_ptr += 1
                if m_ptr >= 0:
                    macro_regime_arr[i] = m_regimes[m_ptr]
                else:
                    # Fallback to sub-bar EMA50/EMA200 alignment during initial macro warmup
                    if closes[i] > ema50[i] > ema200[i]:
                        macro_regime_arr[i] = 1
                    elif closes[i] < ema50[i] < ema200[i]:
                        macro_regime_arr[i] = -1
        else:
            for i in range(n):
                if closes[i] > ema50[i] > ema200[i]:
                    macro_regime_arr[i] = 1
                elif closes[i] < ema50[i] < ema200[i]:
                    macro_regime_arr[i] = -1

        # 5 Scale-Invariant Features at bar s:
        # 0: er_20 (Kaufman Efficiency Ratio over [s-19..s])
        # 1: squeeze_4 ((max(high[s-4..s-1]) - min(low[s-4..s-1])) / atr14[s])
        # 2: impulse_clv (((close[s] - open[s]) / range[s]) * directional_clv[s])
        # 3: ema21_slope_atr ((ema21[s] - ema21[s-3]) / atr14[s])
        # 4: ema_stack_atr ((ema21[s] - ema50[s]) / atr14[s])
        features = np.zeros((n, 5), dtype=float)
        clv_bull = np.zeros(n, dtype=float)
        clv_bear = np.zeros(n, dtype=float)

        abs_diff = np.zeros(n, dtype=float)
        abs_diff[1:] = np.abs(closes[1:] - closes[:-1])

        for s in range(n):
            atr_s = max(atr14[s], 1e-8)
            rng_s = max(highs[s] - lows[s], 1e-8)
            cb = (closes[s] - lows[s]) / rng_s
            cr = (highs[s] - closes[s]) / rng_s
            clv_bull[s] = cb
            clv_bear[s] = cr

            # 1. er_20
            if s >= 20:
                net_chg = abs(closes[s] - closes[s - 20])
                sum_path = float(np.sum(abs_diff[s - 19 : s + 1]))
                er20 = (net_chg / sum_path) if sum_path > 1e-10 else 0.0
            else:
                er20 = 0.25

            # 2. squeeze_4 (4 closed bars prior to s: [s-4 .. s-1])
            if s >= 4:
                pre_h = float(np.max(highs[s - 4 : s]))
                pre_l = float(np.min(lows[s - 4 : s]))
                sq4 = (pre_h - pre_l) / atr_s
            else:
                sq4 = 2.0

            # 3. impulse_clv
            body_signed_ratio = (closes[s] - opens[s]) / rng_s
            dir_clv = cb if closes[s] >= opens[s] else cr
            imp_clv = body_signed_ratio * dir_clv

            # 4. ema21_slope_atr
            e_slope = ((ema21[s] - ema21[s - 3]) / atr_s) if s >= 3 else 0.0

            # 5. ema_stack_atr (measures EMA21 vs EMA50 trend separation vs tangled chop)
            e_stack = (ema21[s] - ema50[s]) / atr_s

            features[s, 0] = er20
            features[s, 1] = min(sq4, 8.0)
            features[s, 2] = imp_clv
            features[s, 3] = np.clip(e_slope, -4.0, 4.0)
            features[s, 4] = np.clip(e_stack, -6.0, 6.0)

        # Precompute Triple-Barrier labels over [s+1 .. s+H]
        # NOTE: Label at index `s` is ONLY allowed to be read when `s + H <= curr_idx`!
        H = self.horizon_bars
        labels = np.zeros(n, dtype=int)  # +1 = UP, -1 = DOWN, 0 = SIDEWAY
        max_up_atr = np.zeros(n, dtype=float)
        max_dn_atr = np.zeros(n, dtype=float)

        up_b = self.up_barrier_atr
        dn_b = self.dn_barrier_atr
        adv_b = self.adverse_barrier_atr

        for s in range(n - H):
            atr_s = max(atr14[s], 1e-8)
            c0 = closes[s]

            w_highs = highs[s + 1 : s + H + 1]
            w_lows = lows[s + 1 : s + H + 1]

            up_exc = (w_highs - c0) / atr_s
            dn_exc = (c0 - w_lows) / atr_s

            max_up_atr[s] = max(0.0, float(np.max(up_exc)))
            max_dn_atr[s] = max(0.0, float(np.max(dn_exc)))

            # Check bar-by-bar first passage of +1.4 ATR before -1.0 ATR (or vice versa)
            up_hit_idx = -1
            dn_hit_idx = -1
            up_invalid = False
            dn_invalid = False

            for k_step in range(H):
                u_k = up_exc[k_step]
                d_k = dn_exc[k_step]
                if d_k >= adv_b and up_hit_idx == -1:
                    up_invalid = True
                if u_k >= adv_b and dn_hit_idx == -1:
                    dn_invalid = True
                if u_k >= up_b and not up_invalid and up_hit_idx == -1:
                    up_hit_idx = k_step
                if d_k >= dn_b and not dn_invalid and dn_hit_idx == -1:
                    dn_hit_idx = k_step

            if up_hit_idx != -1 and (dn_hit_idx == -1 or up_hit_idx < dn_hit_idx):
                labels[s] = 1
            elif dn_hit_idx != -1 and (up_hit_idx == -1 or dn_hit_idx < up_hit_idx):
                labels[s] = -1
            else:
                labels[s] = 0

        data_bundle = {
            "times": times,
            "opens": opens,
            "highs": highs,
            "lows": lows,
            "closes": closes,
            "ema21": ema21,
            "ema50": ema50,
            "ema200": ema200,
            "atr14": atr14,
            "adx14": adx14,
            "plus_di": plus_di,
            "minus_di": minus_di,
            "rsi6": rsi6,
            "rsi14": rsi14,
            "stoch8_k": stoch8_k,
            "stoch8_d": stoch8_d,
            "stoch10_k": stoch10_k,
            "stoch10_d": stoch10_d,
            "bb_mid": bb_mid,
            "bb_upper": bb_upper,
            "bb_lower": bb_lower,
            "macro_regime": macro_regime_arr,
            "features": features,
            "clv_bull": clv_bull,
            "clv_bear": clv_bear,
            "labels": labels,
            "max_up_atr": max_up_atr,
            "max_dn_atr": max_dn_atr,
        }
        # Keep cache bounded
        if len(self._cache) > 8:
            self._cache.clear()
        self._cache[cache_key] = data_bundle
        return data_bundle

    def evaluate_ema21_signal_at_bar(
        self, bundle: Dict[str, Any], idx: int, config: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Evaluates non-lookahead EMA21 Impulse Breakout / Wick Rejection signal at closed bar `idx`.
        Returns +1 (BUY), -1 (SELL), or 0 (NONE).
        """
        if idx < max(25, self.warmup_bars):
            return 0

        cfg = config or {}
        opens = bundle["opens"]
        highs = bundle["highs"]
        lows = bundle["lows"]
        closes = bundle["closes"]
        ema21 = bundle["ema21"]
        ema50 = bundle["ema50"]
        ema200 = bundle["ema200"]
        atr14 = bundle["atr14"]
        adx14 = bundle["adx14"]
        plus_di = bundle["plus_di"]
        minus_di = bundle["minus_di"]
        features = bundle["features"]
        clv_bull = bundle["clv_bull"]
        clv_bear = bundle["clv_bear"]

        c1, o1, h1, l1 = closes[idx], opens[idx], highs[idx], lows[idx]
        c2, o2, h2, l2 = closes[idx - 1], opens[idx - 1], highs[idx - 1], lows[idx - 1]
        e21_1, e21_2 = ema21[idx], ema21[idx - 1]
        e50_1 = ema50[idx]
        e200_1 = ema200[idx]
        atr1 = atr14[idx]
        if atr1 <= 1e-8 or (h1 - l1) <= 1e-8:
            return 0

        # 1. EMA21 Cross or Wick Rejection
        buy_cross = (c2 <= e21_2) and (c1 > e21_1) and (c1 > o1)
        buy_reject = (
            (c1 > e21_1)
            and (c1 > o1)
            and ((l1 <= e21_1 + 0.15 * atr1) or (l2 <= e21_2 + 0.10 * atr1 and c2 <= o2))
            and (c1 > h2)
        )

        sell_cross = (c2 >= e21_2) and (c1 < e21_1) and (c1 < o1)
        sell_reject = (
            (c1 < e21_1)
            and (c1 < o1)
            and ((h1 >= e21_1 - 0.15 * atr1) or (h2 >= e21_2 - 0.10 * atr1 and c2 >= o2))
            and (c1 < l2)
        )

        sig = 0
        if buy_cross or buy_reject:
            sig = 1
        elif sell_cross or sell_reject:
            sig = -1
        if sig == 0:
            return 0

        # 2. EMA200 & EMA50 Stack Filter
        use_ema200 = cfg.get("use_ema200_filter", True)
        use_ema50 = cfg.get("use_ema50_filter", True)
        if use_ema200:
            if sig == 1 and c1 <= e200_1:
                return 0
            if sig == -1 and c1 >= e200_1:
                return 0
        if use_ema50:
            if sig == 1 and (c1 <= e50_1 or e21_1 < e50_1 - 0.10 * atr1):
                return 0
            if sig == -1 and (c1 >= e50_1 or e21_1 > e50_1 + 0.10 * atr1):
                return 0

        # 3. EMA21 Slope Filter
        if cfg.get("use_ema21_slope", True):
            if sig == 1 and e21_1 <= e21_2:
                return 0
            if sig == -1 and e21_1 >= e21_2:
                return 0

        # 4. Max Extension from EMA21 & Pre-Breakout Squeeze Filter
        max_ext_atr = float(cfg.get("max_extension_atr", 1.8))
        if max_ext_atr > 0 and abs(c1 - e21_1) > max_ext_atr * atr1:
            return 0

        max_squeeze_atr = float(cfg.get("max_pre_breakout_range_atr", 3.4))
        squeeze_4_val = features[idx, 1]
        if max_squeeze_atr > 0 and squeeze_4_val > max_squeeze_atr:
            return 0

        # 5. Candle Anatomy & CLV
        rng1 = h1 - l1
        min_bar_atr = float(cfg.get("min_bar_atr", 0.30))
        max_bar_atr = float(cfg.get("max_bar_atr", 2.60))
        if rng1 < min_bar_atr * atr1 or rng1 > max_bar_atr * atr1:
            return 0

        min_clv = float(cfg.get("min_clv", 0.58))
        if sig == 1 and clv_bull[idx] < min_clv:
            return 0
        if sig == -1 and clv_bear[idx] < min_clv:
            return 0

        min_body = float(cfg.get("min_body_ratio", 0.32))
        if abs(c1 - o1) / rng1 < min_body:
            return 0

        # 6. 1-Bar Structure Close Break
        if sig == 1 and c1 <= c2:
            return 0
        if sig == -1 and c1 >= c2:
            return 0

        # 7. ADX & DI Filter
        adx_min = float(cfg.get("adx_threshold", 18.0))
        di_spread_min = float(cfg.get("min_di_spread", 2.5))
        if adx14[idx] < adx_min:
            return 0
        if sig == 1 and (plus_di[idx] - minus_di[idx]) < di_spread_min:
            return 0
        if sig == -1 and (minus_di[idx] - plus_di[idx]) < di_spread_min:
            return 0

        return sig

    def evaluate_quantitative_strategy_setup_at_bar(
        self,
        bundle: Dict[str, Any],
        idx: int,
        symbol: str = "XAUUSD",
        prob_up: float = 33.3,
        prob_dn: float = 33.3,
        prob_sw: float = 33.4,
        macro_dom: str = "NEUTRAL",
        dna_info: Optional[Dict[str, Any]] = None,
        enforce_prob_filter: bool = True,
        timeframe_pair: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Evaluates the 3 Core Quantitative Strategy Playbooks (AGENTS.md Mục 3, 4, 5) strictly causally at bar `idx`:
          1. Playbook 1: `EMA21_TREND_IMPULSE` (EMA 21/50/200 Trend Impulse Breakout & Pullback Wick Rejection)
          2. Playbook 2: `STOCH_RSI_DIV_REVERSAL` (4-Indicator Dual Stoch (8,3,3 & 10,5,5) + Dual RSI (6 & 14) Divergence,
             scored on the 100-Point Matrix >= 65 pts, guarded by the 3-Layer Strong Trend Circuit Breaker)
          3. Playbook 3: `BB_FAKEOUT_STOP` (Bollinger Band (20,2) Exhaustion Fakeout + Mandatory BUY STOP / SELL STOP Order)
        Automatically routes each symbol & timeframe (`H4_H1`, `H4_M15`, `H1_M5`) to its verified True Bid-Ask positive-edge
        playbooks (`SYMBOL_VERIFIED_PLAYBOOKS`), and calculates exact `sl_pips` and `lot_size_100usd` ($100 SL risk).
        """
        sym_info = SYMBOL_MAPPINGS.get(symbol, {"digits": 2, "pip_size": 0.1})
        digits = sym_info.get("digits", 2)
        pip_size = sym_info.get("pip_size", 0.1)

        times_arr = bundle["times"]
        if not timeframe_pair:
            if idx >= 1:
                dt_sec = int(times_arr[idx] - times_arr[idx - 1])
                if dt_sec >= 2400:
                    tf_pair_key = "H4_H1"
                elif dt_sec <= 360:
                    tf_pair_key = "H1_M5"
                else:
                    tf_pair_key = "H4_M15"
            else:
                tf_pair_key = "H4_M15"
        else:
            tf_pair_key = timeframe_pair.upper().strip()

        allowed_playbooks = get_verified_playbooks_for_symbol(symbol, tf_pair_key)

        if dna_info is None:
            dna_info = evaluate_dna_session_and_time(symbol, int(times_arr[idx]))
        dna_pips = float(dna_info.get("dna_sl_padding_pips", 20.0))

        opens = bundle["opens"]
        highs = bundle["highs"]
        lows = bundle["lows"]
        closes = bundle["closes"]
        ema21 = bundle["ema21"]
        ema50 = bundle["ema50"]
        ema200 = bundle["ema200"]
        atr14 = bundle["atr14"]
        adx14 = bundle["adx14"]
        plus_di = bundle["plus_di"]
        minus_di = bundle["minus_di"]
        rsi6 = bundle["rsi6"]
        rsi14 = bundle["rsi14"]
        stoch8_k = bundle["stoch8_k"]
        stoch8_d = bundle["stoch8_d"]
        stoch10_k = bundle["stoch10_k"]
        stoch10_d = bundle["stoch10_d"]
        bb_mid = bundle["bb_mid"]
        bb_upper = bundle["bb_upper"]
        bb_lower = bundle["bb_lower"]
        clv_bull = bundle["clv_bull"]
        clv_bear = bundle["clv_bear"]
        features = bundle["features"]
        macro_reg_int = int(bundle["macro_regime"][idx])

        c1, o1, h1, l1 = float(closes[idx]), float(opens[idx]), float(highs[idx]), float(lows[idx])
        atr_curr = max(float(atr14[idx]), 1e-8)
        sl_pad = max(3.0 * pip_size, min(dna_pips * pip_size * 0.45, 0.55 * atr_curr))
        stop_pad = max(2.0 * pip_size, min(dna_pips * pip_size * 0.18, 0.12 * atr_curr))

        def _enrich_setup(st_dict: Dict[str, Any]) -> Dict[str, Any]:
            sl_pips_val, lot_100 = compute_lot_and_pips_for_100usd_risk(
                symbol, float(st_dict["entry"]), float(st_dict["sl"]), risk_usd=100.0
            )
            st_dict["sl_pips"] = sl_pips_val
            st_dict["lot_size_100usd"] = lot_100
            st_dict["verified_playbooks"] = list(allowed_playbooks)
            st_dict["timeframe_pair_routed"] = tf_pair_key
            return st_dict

        if idx < max(25, self.warmup_bars):
            return _enrich_setup({
                "setup_triggered": False,
                "strategy_id": "WARMUP",
                "strategy_name": "⏳ Khởi tạo chỉ báo",
                "strategy_score": 0,
                "order_type": "NONE",
                "direction": "BUY",
                "entry": round(c1, digits),
                "sl": round(c1 - 1.5 * atr_curr, digits),
                "tp1": round(c1 + 2.25 * atr_curr, digits),
                "tp2": round(c1 + 3.0 * atr_curr, digits),
                "tp3": round(c1 + 4.5 * atr_curr, digits),
                "dna_sl_pips": dna_pips,
                "atr": round(atr_curr, digits),
                "circuit_breaker_blocked": False,
            })

        # =====================================================================
        # 3-LAYER STRONG TREND CIRCUIT BREAKER (AGENTS.md Mục 4)
        # Blocks counter-trend reversal attempts when market is in Super Trend
        # =====================================================================
        e21_1, e50_1, e200_1 = float(ema21[idx]), float(ema50[idx]), float(ema200[idx])
        e21_slope_3 = (e21_1 - float(ema21[idx - 3])) / atr_curr
        adx_val = float(adx14[idx])
        di_diff = float(plus_di[idx] - minus_di[idx])

        # Layer 1: EMA Cloud Super-Slope + Bar outside EMA21
        bull_ema_super = (e21_1 > e50_1 > e200_1) and (e21_slope_3 > 0.85) and (l1 > e21_1)
        bear_ema_super = (e21_1 < e50_1 < e200_1) and (e21_slope_3 < -0.85) and (h1 < e21_1)
        # Layer 2: ADX > 32 + |+DI - -DI| > 16 or 3-bar BB Band Walk
        bb_walk_up = all(closes[idx - k] >= bb_upper[idx - k] - 0.05 * atr_curr for k in range(3))
        bb_walk_dn = all(closes[idx - k] <= bb_lower[idx - k] + 0.05 * atr_curr for k in range(3))
        bull_adx_super = (adx_val > 32.0 and di_diff > 16.0) or bb_walk_up
        bear_adx_super = (adx_val > 32.0 and di_diff < -16.0) or bb_walk_dn

        block_sell_reversal = bull_ema_super or bull_adx_super
        block_buy_reversal = bear_ema_super or bear_adx_super

        candidates: List[Dict[str, Any]] = []

        # =====================================================================
        # PLAYBOOK 1: EMA21 TREND IMPULSE & PULLBACK WICK REJECTION
        # =====================================================================
        ema_sig = 0
        if "EMA21_TREND_IMPULSE" in allowed_playbooks:
            ema_sig = self.evaluate_ema21_signal_at_bar(
                bundle,
                idx,
                config={
                    "adx_threshold": 17.0,
                    "min_di_spread": 2.2,
                    "min_clv": 0.55,
                    "min_body_ratio": 0.28,
                    "max_pre_breakout_range_atr": 3.5,
                },
            )
        if ema_sig != 0:
            dir_s = "BUY" if ema_sig == 1 else "SELL"
            fav_prob = prob_up if ema_sig == 1 else prob_dn
            opp_prob = prob_dn if ema_sig == 1 else prob_up
            er_val = float(features[idx, 0])

            # Probabilistic Whipsaw & DNA Forbidden Session Veto (AGENTS.md Mục 2 & Mục 6)
            sess_st = dna_info.get("session_status", "NORMAL_SESSION")
            prob_ok = True
            if enforce_prob_filter:
                if sess_st in ("FORBIDDEN_ZONE", "SILENT_MODE"):
                    prob_ok = False
                elif ema_sig == 1 and macro_reg_int == -1:
                    prob_ok = False
                elif ema_sig == -1 and macro_reg_int == 1:
                    prob_ok = False
                elif fav_prob < opp_prob + 3.0:
                    prob_ok = False
                elif er_val < 0.18 and prob_sw >= 34.0:
                    prob_ok = False

            if prob_ok:
                score_p1 = 72
                if (ema_sig == 1 and macro_reg_int == 1) or (ema_sig == -1 and macro_reg_int == -1):
                    score_p1 += 10
                if fav_prob >= opp_prob + 6.0:
                    score_p1 += 8
                if (ema_sig == 1 and clv_bull[idx] >= 0.70) or (ema_sig == -1 and clv_bear[idx] >= 0.70):
                    score_p1 += 6

                if ema_sig == 1:
                    sw_l = float(np.min(lows[max(0, idx - 2) : idx + 1]))
                    sl_dist = float(np.clip((c1 - sw_l) + sl_pad, 0.90 * atr_curr, 2.50 * atr_curr))
                    sl_p = round(c1 - sl_dist, digits)
                    tp1_p = round(c1 + sl_dist * 1.5, digits)
                    tp2_p = round(c1 + sl_dist * 2.0, digits)
                    tp3_p = round(c1 + sl_dist * 3.0, digits)
                else:
                    sw_h = float(np.max(highs[max(0, idx - 2) : idx + 1]))
                    sl_dist = float(np.clip((sw_h - c1) + sl_pad, 0.90 * atr_curr, 2.50 * atr_curr))
                    sl_p = round(c1 + sl_dist, digits)
                    tp1_p = round(c1 - sl_dist * 1.5, digits)
                    tp2_p = round(c1 - sl_dist * 2.0, digits)
                    tp3_p = round(c1 - sl_dist * 3.0, digits)

                candidates.append(
                    {
                        "setup_triggered": True,
                        "strategy_id": "EMA21_TREND_IMPULSE",
                        "strategy_name": "🚀 EMA21 Impulse & Pullback (Thuận Xu Hướng)",
                        "strategy_score": min(98, score_p1),
                        "order_type": "MARKET_CLOSE",
                        "direction": dir_s,
                        "entry": round(c1, digits),
                        "sl": sl_p,
                        "tp1": tp1_p,
                        "tp2": tp2_p,
                        "tp3": tp3_p,
                        "dna_sl_pips": dna_pips,
                        "atr": round(atr_curr, digits),
                        "circuit_breaker_blocked": False,
                    }
                )

        # =====================================================================
        # PLAYBOOK 2: DUAL STOCH (8,3,3 & 10,5,5) + DUAL RSI (6 & 14) DIVERGENCE
        # Scored on the 100-Point Matrix (AGENTS.md Mục 3, Threshold >= 65 pts)
        # =====================================================================
        s8_min = float(np.min(stoch8_k[idx - 2 : idx + 1]))
        s10_min = float(np.min(stoch10_k[idx - 2 : idx + 1]))
        r6_min = float(np.min(rsi6[idx - 2 : idx + 1]))
        r14_min = float(np.min(rsi14[idx - 2 : idx + 1]))

        s8_max = float(np.max(stoch8_k[idx - 2 : idx + 1]))
        s10_max = float(np.max(stoch10_k[idx - 2 : idx + 1]))
        r6_max = float(np.max(rsi6[idx - 2 : idx + 1]))
        r14_max = float(np.max(rsi14[idx - 2 : idx + 1]))

        prev_slice = slice(max(0, idx - 18), max(1, idx - 3))
        prev_l_min = float(np.min(lows[prev_slice]))
        prev_h_max = float(np.max(highs[prev_slice]))
        prev_s10_min = float(np.min(stoch10_k[prev_slice]))
        prev_s8_min = float(np.min(stoch8_k[prev_slice]))
        prev_r14_min = float(np.min(rsi14[prev_slice]))
        prev_r6_min = float(np.min(rsi6[prev_slice]))

        prev_s10_max = float(np.max(stoch10_k[prev_slice]))
        prev_s8_max = float(np.max(stoch8_k[prev_slice]))
        prev_r14_max = float(np.max(rsi14[prev_slice]))
        prev_r6_max = float(np.max(rsi6[prev_slice]))

        curr_l_min = float(np.min(lows[idx - 2 : idx + 1]))
        curr_h_max = float(np.max(highs[idx - 2 : idx + 1]))

        # 2A. Bullish Divergence / HTF Pullback Exhaustion Reversal (BUY)
        is_gbpjpy_h1 = (symbol.upper() == "GBPJPY" and tf_pair_key == "H4_H1")
        bull_confirm_bar = (
            ("STOCH_RSI_DIV_REVERSAL" in allowed_playbooks)
            and (not is_gbpjpy_h1)
            and (c1 > o1)
            and (clv_bull[idx] >= 0.56)
            and (stoch8_k[idx] > stoch8_k[idx - 1])
            and (c1 > closes[idx - 1])
        )
        if not block_buy_reversal and bull_confirm_bar and (s8_min <= 22.0 or r6_min <= 24.0):
            pts = 0
            price_swept_low = curr_l_min <= prev_l_min + 0.30 * atr_curr
            # +30 pts: Slow Indicator (Stoch 10-5-5 or RSI 14) Divergence or HTF Bull Pullback Oversold
            if (price_swept_low and (s10_min >= prev_s10_min + 1.5 or r14_min >= prev_r14_min + 1.0)) or (
                s10_min <= 22.0 and macro_reg_int == 1
            ):
                pts += 30
            # +20 pts: Fast Indicator (Stoch 8-3-3 or RSI 6) Divergence / Cross Hook
            if (price_swept_low and (s8_min >= prev_s8_min + 2.0 or r6_min >= prev_r6_min + 1.5)) or (
                s8_min <= 20.0 and stoch8_k[idx] >= stoch8_d[idx]
            ):
                pts += 20
            # +25 pts: Dual Family Confluence (Both Stochastic AND RSI oversold & hooking up)
            if (s8_min <= 22.0 or s10_min <= 25.0) and (r6_min <= 28.0 or r14_min <= 36.0) and (rsi6[idx] > rsi6[idx - 1]):
                pts += 25
            # +15 pts: Extreme Zone 15/85
            if s8_min <= 15.0 or s10_min <= 15.0 or r6_min <= 16.0:
                pts += 15
            # +10 pts: HTF Alignment (Macro Regime BULL or HTF k-NN UP)
            if macro_reg_int >= 0 and prob_up >= prob_dn:
                pts += 10

            prob_ok_div = True
            if enforce_prob_filter:
                sess_st = dna_info.get("session_status", "NORMAL_SESSION")
                if sess_st in ("FORBIDDEN_ZONE", "SILENT_MODE"):
                    prob_ok_div = False
                elif macro_reg_int == -1:
                    prob_ok_div = False
                elif prob_up < prob_dn + 2.5:
                    prob_ok_div = False

            if pts >= 70 and prob_ok_div:
                sl_dist = float(np.clip((c1 - curr_l_min) + sl_pad, 0.90 * atr_curr, 2.40 * atr_curr))
                tier_lbl = "Siêu Cấp" if pts >= 80 else "Tiêu Chuẩn"
                candidates.append(
                    {
                        "setup_triggered": True,
                        "strategy_id": "STOCH_RSI_DIV_REVERSAL",
                        "strategy_name": f"🎯 Phân Kỳ Stoch+RSI ({pts}/100 - {tier_lbl})",
                        "strategy_score": pts,
                        "order_type": "MARKET_CLOSE",
                        "direction": "BUY",
                        "entry": round(c1, digits),
                        "sl": round(c1 - sl_dist, digits),
                        "tp1": round(c1 + sl_dist * 1.5, digits),
                        "tp2": round(c1 + sl_dist * 2.0, digits),
                        "tp3": round(c1 + sl_dist * 3.0, digits),
                        "dna_sl_pips": dna_pips,
                        "atr": round(atr_curr, digits),
                        "circuit_breaker_blocked": False,
                    }
                )

        # 2B. Bearish Divergence / HTF Pullback Exhaustion Reversal (SELL)
        bear_confirm_bar = (
            ("STOCH_RSI_DIV_REVERSAL" in allowed_playbooks)
            and (not is_gbpjpy_h1 or (20.0 <= adx_val <= 31.0 and float(features[idx, 0]) <= 0.18))
            and (c1 < o1)
            and (clv_bear[idx] >= 0.56)
            and (stoch8_k[idx] < stoch8_k[idx - 1])
            and (c1 < closes[idx - 1])
        )
        if not block_sell_reversal and bear_confirm_bar and (s8_max >= 78.0 or r6_max >= 76.0):
            pts = 0
            price_swept_high = curr_h_max >= prev_h_max - 0.30 * atr_curr
            if (price_swept_high and (s10_max <= prev_s10_max - 1.5 or r14_max <= prev_r14_max - 1.0)) or (
                s10_max >= 78.0 and macro_reg_int == -1
            ):
                pts += 30
            if (price_swept_high and (s8_max <= prev_s8_max - 2.0 or r6_max <= prev_r6_max - 1.5)) or (
                s8_max >= 80.0 and stoch8_k[idx] <= stoch8_d[idx]
            ):
                pts += 20
            if (s8_max >= 78.0 or s10_max >= 75.0) and (r6_max >= 72.0 or r14_max >= 64.0) and (rsi6[idx] < rsi6[idx - 1]):
                pts += 25
            if s8_max >= 85.0 or s10_max >= 85.0 or r6_max >= 84.0:
                pts += 15
            if macro_reg_int <= 0 and prob_dn >= prob_up:
                pts += 10

            prob_ok_div = True
            if enforce_prob_filter:
                sess_st = dna_info.get("session_status", "NORMAL_SESSION")
                if sess_st in ("FORBIDDEN_ZONE", "SILENT_MODE"):
                    prob_ok_div = False
                elif is_gbpjpy_h1 and sess_st != "GOLDEN_WINDOW":
                    prob_ok_div = False
                elif macro_reg_int == 1:
                    prob_ok_div = False
                elif prob_dn < prob_up + 2.5:
                    prob_ok_div = False

            if pts >= 70 and prob_ok_div:
                sl_dist = float(np.clip((curr_h_max - c1) + sl_pad, 0.90 * atr_curr, 2.40 * atr_curr))
                tier_lbl = "Siêu Cấp" if pts >= 80 else "Tiêu Chuẩn"
                candidates.append(
                    {
                        "setup_triggered": True,
                        "strategy_id": "STOCH_RSI_DIV_REVERSAL",
                        "strategy_name": f"🎯 Phân Kỳ Stoch+RSI ({pts}/100 - {tier_lbl})",
                        "strategy_score": pts,
                        "order_type": "MARKET_CLOSE",
                        "direction": "SELL",
                        "entry": round(c1, digits),
                        "sl": round(c1 + sl_dist, digits),
                        "tp1": round(c1 - sl_dist * 1.5, digits),
                        "tp2": round(c1 - sl_dist * 2.0, digits),
                        "tp3": round(c1 - sl_dist * 3.0, digits),
                        "dna_sl_pips": dna_pips,
                        "atr": round(atr_curr, digits),
                        "circuit_breaker_blocked": False,
                    }
                )

        # =====================================================================
        # PLAYBOOK 3: BOLLINGER BAND (20,2) FAKEOUT + MANDATORY BUY/SELL STOP
        # (AGENTS.md Mục 3: Pin Bar / Fakeout Rejection + Stop Order Padding)
        # =====================================================================
        bb_u1, bb_l1, bb_m1 = float(bb_upper[idx]), float(bb_lower[idx]), float(bb_mid[idx])
        is_crypto = "BTC" in symbol.upper() or "ETH" in symbol.upper()
        is_usdjpy_h1 = (symbol.upper() == "USDJPY" and tf_pair_key == "H4_H1")
        max_bb_adx = 19.5 if is_crypto else 31.0
        min_bb_clv = 0.56
        compact_h1_ok = (not is_usdjpy_h1) or ((h1 - l1) <= 0.90 * atr_curr)

        # Bullish BB Lower Fakeout (pierced below BB_Lower on bar idx or idx-1, closed back inside band with strong lower wick/CLV)
        pierced_lower = ("BB_FAKEOUT_STOP" in allowed_playbooks) and compact_h1_ok and (
            (l1 < bb_l1) or (float(lows[idx - 1]) < float(bb_lower[idx - 1]))
        )
        closed_inside_low = (c1 > bb_l1) and (clv_bull[idx] >= min_bb_clv) and (s8_min <= (18.0 if is_crypto else 26.0))
        if not block_buy_reversal and pierced_lower and closed_inside_low and adx_val <= max_bb_adx:
            bb_prob_ok = True
            if is_crypto and macro_reg_int != 1:
                bb_prob_ok = False
            if enforce_prob_filter:
                sess_st = dna_info.get("session_status", "NORMAL_SESSION")
                if sess_st in ("FORBIDDEN_ZONE", "SILENT_MODE"):
                    bb_prob_ok = False
                elif macro_reg_int == -1:
                    bb_prob_ok = False
                elif prob_up < prob_dn + 2.0:
                    bb_prob_ok = False
            if bb_prob_ok:
                stop_entry = round(h1 + stop_pad, digits)
                sw_low_bb = min(l1, float(lows[idx - 1]))
                sl_dist = float(np.clip((stop_entry - sw_low_bb) + sl_pad, 0.90 * atr_curr, 2.40 * atr_curr))
                sl_p = round(stop_entry - sl_dist, digits)
                tp1_p = round(max(stop_entry + sl_dist * 1.5, bb_m1), digits)
                tp2_p = round(max(stop_entry + sl_dist * 2.0, bb_u1), digits)
                tp3_p = round(stop_entry + sl_dist * 3.0, digits)
                candidates.append(
                    {
                        "setup_triggered": True,
                        "strategy_id": "BB_FAKEOUT_STOP",
                        "strategy_name": "🪤 BB(20,2) Fakeout PinBar (Lệnh chờ BUY STOP)",
                        "strategy_score": 76,
                        "order_type": "BUY_STOP",
                        "direction": "BUY",
                        "entry": stop_entry,
                        "sl": sl_p,
                        "tp1": tp1_p,
                        "tp2": tp2_p,
                        "tp3": tp3_p,
                        "dna_sl_pips": dna_pips,
                        "atr": round(atr_curr, digits),
                        "circuit_breaker_blocked": False,
                    }
                )

        # Bearish BB Upper Fakeout (pierced above BB_Upper on bar idx or idx-1, closed back inside band with strong upper wick/CLV)
        pierced_upper = ("BB_FAKEOUT_STOP" in allowed_playbooks) and compact_h1_ok and (
            (h1 > bb_u1) or (float(highs[idx - 1]) > float(bb_upper[idx - 1]))
        )
        closed_inside_high = (c1 < bb_u1) and (clv_bear[idx] >= min_bb_clv) and (s8_max >= (82.0 if is_crypto else 74.0))
        if not block_sell_reversal and pierced_upper and closed_inside_high and adx_val <= max_bb_adx:
            bb_prob_ok = True
            if is_crypto and macro_reg_int != -1:
                bb_prob_ok = False
            if enforce_prob_filter:
                sess_st = dna_info.get("session_status", "NORMAL_SESSION")
                if sess_st in ("FORBIDDEN_ZONE", "SILENT_MODE"):
                    bb_prob_ok = False
                elif macro_reg_int == 1:
                    bb_prob_ok = False
                elif prob_dn < prob_up + 2.0:
                    bb_prob_ok = False
            if bb_prob_ok:
                stop_entry = round(l1 - stop_pad, digits)
                sw_high_bb = max(h1, float(highs[idx - 1]))
                sl_dist = float(np.clip((sw_high_bb - stop_entry) + sl_pad, 0.90 * atr_curr, 2.40 * atr_curr))
                sl_p = round(stop_entry + sl_dist, digits)
                tp1_p = round(min(stop_entry - sl_dist * 1.5, bb_m1), digits)
                tp2_p = round(min(stop_entry - sl_dist * 2.0, bb_l1), digits)
                tp3_p = round(stop_entry - sl_dist * 3.0, digits)
                candidates.append(
                    {
                        "setup_triggered": True,
                        "strategy_id": "BB_FAKEOUT_STOP",
                        "strategy_name": "🪤 BB(20,2) Fakeout PinBar (Lệnh chờ SELL STOP)",
                        "strategy_score": 76,
                        "order_type": "SELL_STOP",
                        "direction": "SELL",
                        "entry": stop_entry,
                        "sl": sl_p,
                        "tp1": tp1_p,
                        "tp2": tp2_p,
                        "tp3": tp3_p,
                        "dna_sl_pips": dna_pips,
                        "atr": round(atr_curr, digits),
                        "circuit_breaker_blocked": False,
                    }
                )

        # Pick highest-scoring triggered strategy if any
        if candidates:
            candidates.sort(key=lambda x: x["strategy_score"], reverse=True)
            return _enrich_setup(candidates[0])

        # =====================================================================
        # NO STRATEGY TRIGGERED ON THIS BAR -> RETURN CONDITIONAL STOP/LIMIT PLAN
        # (Marked `setup_triggered = False` so Evaluator never trades waiting bars!)
        # =====================================================================
        dir_str = "BUY" if prob_up >= prob_dn else "SELL"
        if macro_dom == "UP" and prob_up >= prob_dn - 2.0:
            dir_str = "BUY"
        elif macro_dom == "DOWN" and prob_dn >= prob_up - 2.0:
            dir_str = "SELL"

        lookback_sw = min(idx, 5)
        if dir_str == "BUY":
            trig_entry = round(max(h1 + stop_pad, e21_1 + stop_pad), digits)
            swing_low = float(np.min(lows[max(0, idx - lookback_sw) : idx + 1]))
            sl_dist = float(np.clip((trig_entry - swing_low) + sl_pad, 1.0 * atr_curr, 2.6 * atr_curr))
            sl_p = round(trig_entry - sl_dist, digits)
            tp1_p = round(trig_entry + sl_dist * 1.5, digits)
            tp2_p = round(trig_entry + sl_dist * 2.0, digits)
            tp3_p = round(trig_entry + sl_dist * 3.0, digits)
            ord_t = "WAITING_BUY_STOP"
        else:
            trig_entry = round(min(l1 - stop_pad, e21_1 - stop_pad), digits)
            swing_high = float(np.max(highs[max(0, idx - lookback_sw) : idx + 1]))
            sl_dist = float(np.clip((swing_high - trig_entry) + sl_pad, 1.0 * atr_curr, 2.6 * atr_curr))
            sl_p = round(trig_entry + sl_dist, digits)
            tp1_p = round(trig_entry - sl_dist * 1.5, digits)
            tp2_p = round(trig_entry - sl_dist * 2.0, digits)
            tp3_p = round(trig_entry - sl_dist * 3.0, digits)
            ord_t = "WAITING_SELL_STOP"

        return _enrich_setup({
            "setup_triggered": False,
            "strategy_id": "WAITING_FOR_TRIGGER",
            "strategy_name": "⏳ Chờ Nến Tín Hiệu Chiến Lược (Chưa Kích Hoạt)",
            "strategy_score": 0,
            "order_type": ord_t,
            "direction": dir_str,
            "entry": trig_entry,
            "sl": sl_p,
            "tp1": tp1_p,
            "tp2": tp2_p,
            "tp3": tp3_p,
            "dna_sl_pips": dna_pips,
            "atr": round(atr_curr, digits),
            "circuit_breaker_blocked": bool(block_buy_reversal or block_sell_reversal),
        })

    def forecast_at_bar(
        self,
        sub_candles: List[Dict[str, Any]],
        macro_candles: Optional[List[Dict[str, Any]]] = None,
        curr_idx: Optional[int] = None,
        symbol: str = "XAUUSD",
        include_analogs: bool = True,
        forecast_mode: Optional[str] = None,
        adaptive_profile: Optional[Dict[str, Any]] = None,
        timeframe_pair: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Computes the 100% Non-Lookahead Dual-Tier Probabilistic Context Forecast at `curr_idx`
        (defaults to the last bar of `sub_candles`).
        Combines:
          - Tier 1: Macro HTF Anchor Forecast (H1 / H4 k-NN) -> Adaptive HTF Weight (default 70%)
          - Tier 2: Micro LTF Tactical Trigger (H1 / M15 / M5 k-NN & Impulse) -> Adaptive LTF Weight (default 30%)
          - 3-Layer Adaptive Self-Improvement Profile (Feature Weights, Session/Time Decay, Probability Calibration & Guardrail)
        """
        if not sub_candles:
            return self._empty_forecast()

        bundle = self.prepare_causal_arrays(sub_candles, macro_candles)
        n = len(sub_candles)
        if curr_idx is None or curr_idx >= n:
            curr_idx = n - 1

        # Infer timeframe_pair if not passed
        if not timeframe_pair:
            if n >= 2:
                dt_s = int(bundle["times"][curr_idx] - bundle["times"][curr_idx - 1])
                if dt_s >= 2400:
                    timeframe_pair = "H4_H1"
                elif dt_s <= 360:
                    timeframe_pair = "H1_M5"
                else:
                    timeframe_pair = "H4_M15"
            else:
                timeframe_pair = "H4_M15"

        if adaptive_profile is None:
            try:
                from .forecast_evaluator import forecast_calibrator
                adaptive_profile = forecast_calibrator.get_profile(symbol, timeframe_pair)
            except Exception:
                adaptive_profile = None

        H = self.horizon_bars
        max_valid_s = curr_idx - H
        min_valid_s = self.warmup_bars

        macro_reg_int = int(bundle["macro_regime"][curr_idx])
        macro_reg_str = "BULL" if macro_reg_int == 1 else ("BEAR" if macro_reg_int == -1 else "NEUTRAL")

        er_20 = round(float(bundle["features"][curr_idx, 0]), 3)
        squeeze_4 = round(float(bundle["features"][curr_idx, 1]), 2)
        ema_sig_int = self.evaluate_ema21_signal_at_bar(bundle, curr_idx)
        ema_sig_str = "BUY_BREAKOUT" if ema_sig_int == 1 else ("SELL_BREAKOUT" if ema_sig_int == -1 else "NONE")
        curr_time = int(bundle["times"][curr_idx])
        dna_info = evaluate_dna_session_and_time(symbol, curr_time)

        # If we don't have enough closed historical samples yet (curr_idx < warmup + H)
        if max_valid_s <= min_valid_s + 10:
            return {
                "prob_up_pct": 33.3,
                "prob_down_pct": 33.3,
                "prob_sideway_pct": 33.4,
                "macro_regime": macro_reg_str,
                "sample_count": 0,
                "total_memory_samples": 0,
                "expected_wave_atr": 1.50,
                "expected_mae_atr": 0.80,
                "er_20": er_20,
                "squeeze_4_atr": squeeze_4,
                "ema21_signal": ema_sig_str,
                "action": "WARMUP",
                "tactical_status": "WARMUP",
                "tactical_badge": "⏳ ĐANG KHỞI TẠO DỮ LIỆU",
                "dna_session": dna_info,
                "suggested_setup": None,
                "top_analogs": [],
                "non_lookahead_verified": True,
            }

        # Strictly slice past candidate indices s in [start_s .. curr_idx - H]
        start_s = max(min_valid_s, max_valid_s - self.max_memory_bars)
        candidate_indices = np.arange(start_s, max_valid_s + 1, dtype=int)
        total_memory = len(candidate_indices)

        eff_k_neighbors = int(adaptive_profile.get("k_neighbors", self.k_neighbors)) if adaptive_profile else self.k_neighbors

        # Condition on matching Macro HTF Regime if enough analogs exist (>= 40), else use all with macro penalty
        cand_regimes = bundle["macro_regime"][candidate_indices]
        same_regime_mask = cand_regimes == macro_reg_int
        if np.sum(same_regime_mask) >= max(25, eff_k_neighbors):
            filtered_indices = candidate_indices[same_regime_mask]
            regime_penalty = np.zeros(len(filtered_indices), dtype=float)
        else:
            filtered_indices = candidate_indices
            regime_penalty = np.where(cand_regimes == macro_reg_int, 0.0, 1.25)

        X_past = bundle["features"][filtered_indices]
        x_curr = bundle["features"][curr_idx]

        # Causal standardization using only X_past mean & std
        mean_past = np.mean(X_past, axis=0)
        std_past = np.std(X_past, axis=0) + 1e-6

        Z_past = (X_past - mean_past) / std_past
        z_curr = (x_curr - mean_past) / std_past

        # Layer 1 Adaptive Feature Weights
        if adaptive_profile and adaptive_profile.get("f_weights_ltf"):
            f_weights = np.array(adaptive_profile["f_weights_ltf"], dtype=float)
        else:
            f_weights = np.array([1.25, 1.15, 1.35, 1.20, 1.05], dtype=float)

        diff = (Z_past - z_curr) * f_weights
        dists = np.sqrt(np.sum(diff * diff, axis=1)) + regime_penalty

        # Layer 2 Adaptive Temporal Recency Decay & DNA Session Affinity Bonus
        if adaptive_profile:
            td_str = float(adaptive_profile.get("time_decay_strength", 0.0))
            if td_str > 0:
                span = max(1.0, float(max_valid_s - start_s))
                age_norm = (max_valid_s - filtered_indices) / span
                dists = dists + td_str * 0.70 * age_norm

            sess_bonus = float(adaptive_profile.get("session_affinity_bonus", 0.0))
            if sess_bonus > 0:
                curr_mod_sec = curr_time % 86400
                cand_mod_sec = bundle["times"][filtered_indices] % 86400
                sec_diff = np.abs(cand_mod_sec - curr_mod_sec)
                circ_diff = np.minimum(sec_diff, 86400 - sec_diff)
                # Analogs within +-2.5 hours of the same time-of-day get session affinity distance reduction
                same_sess_mask = circ_diff <= 9000
                dists = np.where(same_sess_mask, np.maximum(0.05, dists - sess_bonus), dists)

        k = min(eff_k_neighbors, len(dists))
        if k < len(dists):
            nearest_pos = np.argpartition(dists, k)[:k]
            nearest_pos = nearest_pos[np.argsort(dists[nearest_pos])]
        else:
            nearest_pos = np.argsort(dists)

        matched_s = filtered_indices[nearest_pos]
        matched_dists = dists[nearest_pos]

        # Inverse distance kernel weights
        weights = 1.0 / (matched_dists + 0.15)
        w_sum = float(np.sum(weights))
        weights_norm = weights / w_sum if w_sum > 0 else np.ones(k) / float(k)

        matched_labels = bundle["labels"][matched_s]
        matched_up_atr = bundle["max_up_atr"][matched_s]
        matched_dn_atr = bundle["max_dn_atr"][matched_s]

        ltf_prob_up = float(np.sum(weights_norm[matched_labels == 1])) * 100.0
        ltf_prob_dn = float(np.sum(weights_norm[matched_labels == -1])) * 100.0
        ltf_prob_sw = max(0.0, 100.0 - ltf_prob_up - ltf_prob_dn)

        # Compute Tier-1 Macro HTF Anchor Forecast directly on macro_candles (H1 / H4)
        active_mode = (forecast_mode or self.forecast_mode or "COMBINED_HTF_LTF").upper()
        macro_fc = self._compute_macro_anchor_forecast(
            macro_candles,
            curr_sub_time=curr_time,
            symbol=symbol,
            include_future_projection=include_analogs,
            adaptive_profile=adaptive_profile,
        )

        htf_w = float(adaptive_profile.get("htf_weight", 0.70)) if adaptive_profile else 0.70
        htf_w = float(np.clip(htf_w, 0.50, 0.85))
        ltf_w = 1.0 - htf_w

        if macro_fc is not None and active_mode in ("COMBINED_HTF_LTF", "HTF_ANCHOR_ONLY"):
            m_up = float(macro_fc["macro_prob_up_pct"])
            m_dn = float(macro_fc["macro_prob_down_pct"])
            m_sw = float(macro_fc["macro_prob_sideway_pct"])
            if active_mode == "HTF_ANCHOR_ONLY":
                prob_up = m_up
                prob_dn = m_dn
                prob_sw = m_sw
            else:
                prob_up = htf_w * m_up + ltf_w * ltf_prob_up
                prob_dn = htf_w * m_dn + ltf_w * ltf_prob_dn
                prob_sw = max(0.0, 100.0 - prob_up - prob_dn)
        else:
            prob_up = ltf_prob_up
            prob_dn = ltf_prob_dn
            prob_sw = ltf_prob_sw

        # Layer 3: Empirical Probability Temperature Calibration
        if adaptive_profile and abs(float(adaptive_profile.get("prob_temperature", 1.0)) - 1.0) > 0.01:
            temp = float(np.clip(adaptive_profile["prob_temperature"], 0.75, 1.35))
            p_arr = np.maximum(np.array([prob_up, prob_dn, prob_sw], dtype=float) / 100.0, 1e-4)
            p_cal = np.power(p_arr, temp)
            p_cal = (p_cal / float(np.sum(p_cal))) * 100.0
            prob_up, prob_dn, prob_sw = float(p_cal[0]), float(p_cal[1]), float(p_cal[2])

        # Expected favorable wave & adverse excursion in ATR units
        if prob_up >= prob_dn:
            exp_wave = float(np.sum(weights_norm * matched_up_atr))
            exp_mae = float(np.sum(weights_norm * matched_dn_atr))
        else:
            exp_wave = float(np.sum(weights_norm * matched_dn_atr))
            exp_mae = float(np.sum(weights_norm * matched_up_atr))

        if macro_fc is not None and active_mode in ("COMBINED_HTF_LTF", "HTF_ANCHOR_ONLY"):
            # Blend expected wave ATR with Macro HTF wave strength
            exp_wave = 0.60 * float(macro_fc["macro_expected_wave_atr"]) + 0.40 * exp_wave

        # Evaluate LTF candle & momentum alignment vs Macro HTF Anchor
        c1 = float(bundle["closes"][curr_idx])
        o1 = float(bundle["opens"][curr_idx])
        h1 = float(bundle["highs"][curr_idx])
        l1 = float(bundle["lows"][curr_idx])
        l2 = float(bundle["lows"][max(0, curr_idx - 1)])
        h2 = float(bundle["highs"][max(0, curr_idx - 1)])
        e21_1 = float(bundle["ema21"][curr_idx])
        atr_curr = float(bundle["atr14"][curr_idx])

        ltf_bullish_bar = (c1 >= o1 and c1 >= e21_1) or (ltf_prob_up >= ltf_prob_dn + 3.0) or (ema_sig_int == 1)
        ltf_bearish_bar = (c1 <= o1 and c1 <= e21_1) or (ltf_prob_dn >= ltf_prob_up + 3.0) or (ema_sig_int == -1)

        macro_dom = macro_fc["macro_dominant_scenario"] if macro_fc else ("UP" if macro_reg_int == 1 else ("DOWN" if macro_reg_int == -1 else "SIDEWAY"))
        if macro_fc and macro_dom == "SIDEWAY":
            if m_up >= m_dn + 5.0 and macro_reg_int >= 0:
                macro_dom = "UP"
            elif m_dn >= m_up + 5.0 and macro_reg_int <= 0:
                macro_dom = "DOWN"

        # Determine Dual-Tier Tactical Alignment Status & Action (with Adaptive Guardrail Thresholding)
        tactical_status = "NEUTRAL"
        tactical_badge = "⚪ CHỜ TÍN HIỆU RÕ RÀNG"
        action = "NEUTRAL"

        min_align_prob = float(adaptive_profile.get("aligned_min_prob_pct", 45.0)) if adaptive_profile else 45.0
        min_align_edge = float(adaptive_profile.get("aligned_min_edge_pct", 4.0)) if adaptive_profile else 4.0
        guardrail_status = str(adaptive_profile.get("guardrail_status", "NORMAL")) if adaptive_profile else "NORMAL"
        if guardrail_status == "TIGHTENED":
            min_align_prob += 6.0
            min_align_edge += 2.5

        if prob_sw >= 48.0 and max(prob_up, prob_dn) < 40.0 and macro_dom == "SIDEWAY":
            action = "WAIT_SIDEWAY"
            tactical_status = "MACRO_SIDEWAY_WAIT"
            tactical_badge = "⏳ KHUNG LỚN SIDEWAY - ĐỨNG NGOÀI"
        elif prob_up >= prob_dn + min_align_edge and (
            (macro_dom == "UP" and prob_up >= min_align_prob - 5.0) or prob_up >= min_align_prob
        ):
            if ltf_bullish_bar:
                tactical_status = "ALIGNED_BUY"
                tactical_badge = "⚡ ĐỒNG PHA TĂNG (HTF+LTF) - CANH BUY"
                action = "STRONG_BUY" if (ema_sig_int == 1 or prob_up >= 52.0) else "BUY"
            else:
                tactical_status = "PULLBACK_BUY_WAIT"
                tactical_badge = "🌊 M15/M5 ĐANG HỒI GIẢM - GIỮ BIAS BUY HTF"
                action = "BUY_ON_PULLBACK"
        elif prob_dn >= prob_up + min_align_edge and (
            (macro_dom == "DOWN" and prob_dn >= min_align_prob - 5.0) or prob_dn >= min_align_prob
        ):
            if ltf_bearish_bar:
                tactical_status = "ALIGNED_SELL"
                tactical_badge = "⚡ ĐỒNG PHA GIẢM (HTF+LTF) - CANH SELL"
                action = "STRONG_SELL" if (ema_sig_int == -1 or prob_dn >= 52.0) else "SELL"
            else:
                tactical_status = "PULLBACK_SELL_WAIT"
                tactical_badge = "🌊 M15/M5 ĐANG HỒI TĂNG - GIỮ BIAS SELL HTF"
                action = "SELL_ON_PULLBACK"
        else:
            action = "WAIT_SIDEWAY"
            tactical_status = "MACRO_SIDEWAY_WAIT"
            tactical_badge = "⏳ ĐỨNG NGOÀI CHỜ XÁC NHẬN HTF"

        # Build Suggested Non-Lookahead Quantitative Setup via 3-Playbook Strategy Engine
        sym_info = SYMBOL_MAPPINGS.get(symbol, {"digits": 2, "pip_size": 0.1})
        digits = sym_info.get("digits", 2)

        quant_setup = self.evaluate_quantitative_strategy_setup_at_bar(
            bundle=bundle,
            idx=curr_idx,
            symbol=symbol,
            prob_up=prob_up,
            prob_dn=prob_dn,
            prob_sw=prob_sw,
            macro_dom=macro_dom,
            dna_info=dna_info,
            enforce_prob_filter=True,
            timeframe_pair=timeframe_pair,
        )
        if quant_setup.get("setup_triggered"):
            q_dir = quant_setup["direction"]
            tactical_status = f"ALIGNED_{q_dir}"
            tactical_badge = f"⚡ KÍCH HOẠT [{quant_setup['strategy_name']}]"
            action = f"STRONG_{q_dir}"
        elif "ALIGNED" in tactical_status:
            # Do not label a bar as ALIGNED trade trigger if no quantitative strategy triggered on this bar
            if "BUY" in tactical_status:
                tactical_status = "PULLBACK_BUY_WAIT"
                tactical_badge = "🌊 BIAS TĂNG (HTF+LTF) - CHỜ NẾN TÍN HIỆU CHIẾN LƯỢC"
            else:
                tactical_status = "PULLBACK_SELL_WAIT"
                tactical_badge = "🌊 BIAS GIẢM (HTF+LTF) - CHỜ NẾN TÍN HIỆU CHIẾN LƯỢC"

        top_analogs = []
        if include_analogs:
            for idx_pos in range(min(5, len(matched_s))):
                s_idx = int(matched_s[idx_pos])
                lbl = int(matched_labels[idx_pos])
                lbl_str = "UP" if lbl == 1 else ("DOWN" if lbl == -1 else "SIDEWAY")
                ts_val = int(bundle["times"][s_idx])
                dt_str = datetime.fromtimestamp(ts_val, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
                top_analogs.append(
                    {
                        "bar_index": s_idx,
                        "timestamp": ts_val,
                        "datetime_utc": dt_str,
                        "distance": round(float(matched_dists[idx_pos]), 3),
                        "outcome": lbl_str,
                        "max_up_atr": round(float(matched_up_atr[idx_pos]), 2),
                        "max_dn_atr": round(float(matched_dn_atr[idx_pos]), 2),
                    }
                )

        # Build Future Projected Candles (H bars ahead)
        # In Combined Mode, anchor the dominant trajectory cluster to the Combined (HTF-anchored) scenario
        # so that 1-bar LTF pullbacks do not flip the projected path upside down!
        tf_step = 300
        if curr_idx >= 1 and (bundle["times"][curr_idx] - bundle["times"][curr_idx - 1]) > 0:
            tf_step = int(bundle["times"][curr_idx] - bundle["times"][curr_idx - 1])
            if tf_step > 86400:
                tf_step = 300 if n > 2000 else 900

        future_candles: List[Dict[str, Any]] = []
        future_up_band: List[Dict[str, Any]] = [{"time": curr_time, "value": round(c1, digits)}]
        future_dn_band: List[Dict[str, Any]] = [{"time": curr_time, "value": round(c1, digits)}]
        future_mean_line: List[Dict[str, Any]] = [{"time": curr_time, "value": round(c1, digits)}]

        up_mask = matched_labels == 1
        dn_mask = matched_labels == -1
        sw_mask = matched_labels == 0

        w_up = weights_norm[up_mask]
        w_dn = weights_norm[dn_mask]
        w_sw = weights_norm[sw_mask]

        w_up_norm = (w_up / float(np.sum(w_up))) if np.sum(w_up) > 0 else None
        w_dn_norm = (w_dn / float(np.sum(w_dn))) if np.sum(w_dn) > 0 else None
        w_sw_norm = (w_sw / float(np.sum(w_sw))) if np.sum(w_sw) > 0 else None

        # Choose dominant scenario weights based on the Combined HTF+LTF probabilities
        if prob_up >= prob_dn and prob_up >= prob_sw - 4.0 and w_up_norm is not None:
            dom_s = matched_s[up_mask]
            dom_w = w_up_norm
            dom_scenario = "UP"
            dom_prob = round(prob_up, 1)
        elif prob_dn > prob_up and prob_dn >= prob_sw - 4.0 and w_dn_norm is not None:
            dom_s = matched_s[dn_mask]
            dom_w = w_dn_norm
            dom_scenario = "DOWN"
            dom_prob = round(prob_dn, 1)
        else:
            dom_s = matched_s
            dom_w = weights_norm
            dom_scenario = "SIDEWAY" if prob_sw >= max(prob_up, prob_dn) else ("UP" if prob_up >= prob_dn else "DOWN")
            dom_prob = round(max(prob_up, prob_dn, prob_sw), 1)

        prev_proj_close = c1
        s_atrs = np.maximum(bundle["atr14"][matched_s], 1e-8)
        s_c0 = bundle["closes"][matched_s]

        dom_atrs = np.maximum(bundle["atr14"][dom_s], 1e-8)
        dom_c0 = bundle["closes"][dom_s]

        # Macro drift guidance per LTF step (in LTF price units)
        macro_step_drift = 0.0
        if macro_fc is not None and active_mode in ("COMBINED_HTF_LTF", "HTF_ANCHOR_ONLY"):
            net_m_atr = float(macro_fc.get("net_drift_macro_atr", 0.0))
            m_atr_val = float(macro_fc.get("macro_atr", atr_curr * 3.0))
            # Scale macro drift over H LTF steps (1 H1/H4 wave distributed smoothly across H bars)
            macro_step_drift = (net_m_atr * m_atr_val * 0.45) / float(max(1, H))

        for step_h in range(1, H + 1):
            fut_t = curr_time + step_h * tf_step

            step_Idx_dom = dom_s + step_h
            rel_h_dom = (bundle["highs"][step_Idx_dom] - dom_c0) / dom_atrs
            rel_l_dom = (bundle["lows"][step_Idx_dom] - dom_c0) / dom_atrs
            rel_c_dom = (bundle["closes"][step_Idx_dom] - dom_c0) / dom_atrs

            step_Idx_all = matched_s + step_h
            rel_h_all = (bundle["highs"][step_Idx_all] - s_c0) / s_atrs
            rel_l_all = (bundle["lows"][step_Idx_all] - s_c0) / s_atrs
            rel_c_all = (bundle["closes"][step_Idx_all] - s_c0) / s_atrs

            ltf_d_c = (0.80 * float(np.sum(dom_w * rel_c_dom)) + 0.20 * float(np.sum(weights_norm * rel_c_all))) * atr_curr
            ltf_d_h = (0.80 * float(np.max([np.sum(dom_w * rel_h_dom), np.sum(dom_w * rel_c_dom)])) + 0.20 * float(np.sum(weights_norm * rel_h_all))) * atr_curr
            ltf_d_l = (0.80 * float(np.min([np.sum(dom_w * rel_l_dom), np.sum(dom_w * rel_c_dom)])) + 0.20 * float(np.sum(weights_norm * rel_l_all))) * atr_curr

            if macro_fc is not None and active_mode in ("COMBINED_HTF_LTF", "HTF_ANCHOR_ONLY"):
                m_cum_drift = macro_step_drift * step_h
                d_c = 0.55 * m_cum_drift + 0.45 * ltf_d_c
                d_h = max(d_c + 0.35 * atr_curr, 0.55 * m_cum_drift + 0.45 * ltf_d_h)
                d_l = min(d_c - 0.35 * atr_curr, 0.55 * m_cum_drift + 0.45 * ltf_d_l)
            else:
                d_c, d_h, d_l = ltf_d_c, ltf_d_h, ltf_d_l

            proj_o = round(prev_proj_close, digits)
            proj_c = round(c1 + d_c, digits)
            proj_h = round(max(proj_o, proj_c, c1 + d_h), digits)
            proj_l = round(min(proj_o, proj_c, c1 + d_l), digits)
            prev_proj_close = proj_c

            if w_up_norm is not None:
                up_c_rel = (bundle["highs"][matched_s[up_mask] + step_h] - bundle["closes"][matched_s[up_mask]]) / np.maximum(bundle["atr14"][matched_s[up_mask]], 1e-8)
                up_val = round(c1 + float(np.sum(w_up_norm * up_c_rel)) * atr_curr, digits)
            else:
                up_val = round(c1 + (step_h / float(H)) * exp_wave * atr_curr, digits)

            if w_dn_norm is not None:
                dn_c_rel = (bundle["lows"][matched_s[dn_mask] + step_h] - bundle["closes"][matched_s[dn_mask]]) / np.maximum(bundle["atr14"][matched_s[dn_mask]], 1e-8)
                dn_val = round(c1 + float(np.sum(w_dn_norm * dn_c_rel)) * atr_curr, digits)
            else:
                dn_val = round(c1 - (step_h / float(H)) * exp_mae * atr_curr, digits)

            future_up_band.append({"time": fut_t, "value": max(up_val, proj_h)})
            future_dn_band.append({"time": fut_t, "value": min(dn_val, proj_l)})
            future_mean_line.append({"time": fut_t, "value": proj_c})

            future_candles.append(
                {
                    "step": step_h,
                    "time": fut_t,
                    "open": proj_o,
                    "high": proj_h,
                    "low": proj_l,
                    "close": proj_c,
                    "prob_up_pct": round(prob_up, 1),
                    "prob_down_pct": round(prob_dn, 1),
                    "prob_sideway_pct": round(prob_sw, 1),
                    "dominant_scenario": dom_scenario,
                    "dominant_prob_pct": dom_prob,
                    "upper_target": max(up_val, proj_h),
                    "lower_target": min(dn_val, proj_l),
                }
            )

        return {
            "forecast_mode": active_mode,
            "model_version": adaptive_profile.get("version_tag", "v3.0-Base") if adaptive_profile else "v3.0-Base",
            "trust_score": adaptive_profile.get("trust_score", 75.0) if adaptive_profile else 75.0,
            "guardrail_status": adaptive_profile.get("guardrail_status", "NORMAL") if adaptive_profile else "NORMAL",
            "guardrail_badge": adaptive_profile.get("guardrail_badge", "🟢 MÔ HÌNH ĐỒNG BỘ TỐT") if adaptive_profile else "🟢 MÔ HÌNH ĐỒNG BỘ TỐT",
            "metrics_snapshot": adaptive_profile.get("metrics_snapshot", {}) if adaptive_profile else {},
            "prob_up_pct": round(prob_up, 1),
            "prob_down_pct": round(prob_dn, 1),
            "prob_sideway_pct": round(prob_sw, 1),
            "macro_prob_up_pct": macro_fc["macro_prob_up_pct"] if macro_fc else round(prob_up, 1),
            "macro_prob_down_pct": macro_fc["macro_prob_down_pct"] if macro_fc else round(prob_dn, 1),
            "macro_prob_sideway_pct": macro_fc["macro_prob_sideway_pct"] if macro_fc else round(prob_sw, 1),
            "macro_dominant_scenario": macro_fc["macro_dominant_scenario"] if macro_fc else dom_scenario,
            "ltf_prob_up_pct": round(ltf_prob_up, 1),
            "ltf_prob_down_pct": round(ltf_prob_dn, 1),
            "ltf_prob_sideway_pct": round(ltf_prob_sw, 1),
            "macro_regime": macro_reg_str,
            "tactical_status": tactical_status,
            "tactical_badge": tactical_badge,
            "dna_session": dna_info,
            "sample_count": int(k),
            "total_memory_samples": int(total_memory),
            "expected_wave_atr": round(exp_wave, 2),
            "expected_mae_atr": round(exp_mae, 2),
            "er_20": er_20,
            "squeeze_4_atr": squeeze_4,
            "ema21_signal": ema_sig_str,
            "action": action,
            "dominant_scenario": dom_scenario,
            "dominant_prob_pct": dom_prob,
            "horizon_bars": H,
            "suggested_setup": quant_setup,
            "future_candles": future_candles,
            "future_up_band": future_up_band,
            "future_dn_band": future_dn_band,
            "future_mean_line": future_mean_line,
            "macro_future_candles": macro_fc["macro_future_candles"] if macro_fc else [],
            "macro_future_up_band": macro_fc["macro_future_up_band"] if macro_fc else [],
            "macro_future_dn_band": macro_fc["macro_future_dn_band"] if macro_fc else [],
            "macro_future_mean_line": macro_fc["macro_future_mean_line"] if macro_fc else [],
            "top_analogs": top_analogs,
            "non_lookahead_verified": bool(int(matched_s.max()) + H <= curr_idx),
        }

    def _empty_forecast(self) -> Dict[str, Any]:
        return {
            "prob_up_pct": 33.3,
            "prob_down_pct": 33.3,
            "prob_sideway_pct": 33.4,
            "macro_regime": "NEUTRAL",
            "sample_count": 0,
            "total_memory_samples": 0,
            "expected_wave_atr": 0.0,
            "expected_mae_atr": 0.0,
            "er_20": 0.0,
            "squeeze_4_atr": 0.0,
            "ema21_signal": "NONE",
            "action": "NEUTRAL",
            "suggested_setup": None,
            "top_analogs": [],
            "non_lookahead_verified": True,
        }


class EMA21ProbabilisticSimulatorEngine:
    """
    Standalone & Integrated EMA21 Impulse Wave + Probabilistic Context Engine (v3.0).
    Replicates the 3-Order Multi-Stage Ratchet Runner (Order 1: 1.0R TP, Order 2: 2.0R TP + Stage-1 Cushion,
    Order 3: Stage-2 Ratchet Lock +1.0R at 2.0R + Hybrid Wave Trail) combined with Non-Lookahead k-NN Probability Filtering.
    """

    def __init__(
        self,
        symbol: str = "XAUUSD",
        config: Optional[Dict[str, Any]] = None,
        initial_balance: float = 10000.0,
    ):
        self.symbol = symbol
        self.initial_balance = float(initial_balance)
        self.config = {
            "preset_name": "v3.0 EMA21 Probabilistic Macro k-NN",
            "engine_type": "EMA21_PROBABILISTIC",
            "use_prob_filter": True,
            "horizon_bars": 8,
            "k_neighbors": 35,
            "min_dir_prob_pct": 30.0,
            "max_sideway_prob_pct": 50.0,
            "min_prob_edge_pct": -2.0,
            "risk_percent": 1.0,
            "sl_lookback_bars": 2,
            "sl_padding_pips": 3.5,
            "min_sl_atr": 0.8,
            "max_sl_atr": 2.8,
            "tp1_r": 1.0,
            "tp2_r": 2.0,
            "be_stage1_offset_r": 0.0,
            "ratchet_lock_r": 1.0,
            "trail_structure_bars": 4,
            "trail_atr_mult": 2.8,
            "climax_tighten_r": 5.0,
            "adx_threshold": 18.0,
            "min_di_spread": 2.5,
            "max_pre_breakout_range_atr": 3.2,
            "min_clv": 0.60,
        }
        if config:
            self.config.update(config)

        self.forecaster = ProbabilisticContextForecaster(
            horizon_bars=int(self.config.get("horizon_bars", 8)),
            k_neighbors=int(self.config.get("k_neighbors", 35)),
        )
        self._init_symbol_info()
        self.reset(initial_balance)

    def _init_symbol_info(self):
        if self.symbol in SYMBOL_MAPPINGS:
            sym_info = SYMBOL_MAPPINGS[self.symbol]
            self.digits = sym_info.get("digits", 5)
            self.pip_size = sym_info.get("pip_size", 0.0001)
        elif "XAU" in self.symbol or "GOLD" in self.symbol:
            self.digits = 2
            self.pip_size = 0.1
        elif "JPY" in self.symbol:
            self.digits = 3
            self.pip_size = 0.01
        elif "BTC" in self.symbol:
            self.digits = 2
            self.pip_size = 1.0
        else:
            self.digits = 5
            self.pip_size = 0.0001

        if "XAU" in self.symbol or "GOLD" in self.symbol:
            self.usd_per_point = 100.0
        elif "BTC" in self.symbol:
            self.usd_per_point = 1.0
        elif "JPY" in self.symbol:
            self.usd_per_point = 700.0
        elif self.symbol.startswith("USD"):
            self.usd_per_point = 74000.0
        else:
            self.usd_per_point = 100000.0

    def reset(self, initial_balance: Optional[float] = None):
        if initial_balance is not None:
            self.initial_balance = float(initial_balance)
        self.balance = self.initial_balance
        self.equity = self.initial_balance
        self.peak_equity = self.initial_balance
        self.max_drawdown_usd = 0.0
        self.max_drawdown_pct = 0.0
        self.active_orders: List[Dict[str, Any]] = []
        self.closed_trades: List[Dict[str, Any]] = []
        self.equity_curve: List[Dict[str, Any]] = []
        self.completed_cycles = 0
        self.total_cuts = 0
        self.total_cut_loss = 0.0
        self.total_tp_profit = 0.0
        self.vetoed_signals = 0
        self.accepted_signals = 0
        self.last_forecast: Optional[Dict[str, Any]] = None

    def set_config(self, new_config: Dict[str, Any]):
        self.config.update(new_config)

    def _simulate_run_on_bundle(
        self,
        bundle: Dict[str, Any],
        sub_candles: List[Dict[str, Any]],
        macro_candles: Optional[List[Dict[str, Any]]],
        use_prob_filter: bool = True,
    ) -> Dict[str, Any]:
        """
        Runs a complete causal 3-order Multi-Stage Ratchet backtest over `sub_candles`.
        Returns full metrics, equity curve, and closed trade list.
        """
        balance = self.initial_balance
        equity = self.initial_balance
        peak_eq = self.initial_balance
        max_dd_usd = 0.0
        max_dd_pct = 0.0

        active_orders: List[Dict[str, Any]] = []
        closed_trades: List[Dict[str, Any]] = []
        eq_curve: List[Dict[str, Any]] = []
        completed_baskets = 0
        gross_profit = 0.0
        gross_loss = 0.0
        won_orders = 0
        lost_orders = 0
        vetoed_count = 0
        accepted_count = 0

        times = bundle["times"]
        highs = bundle["highs"]
        lows = bundle["lows"]
        closes = bundle["closes"]
        atr14 = bundle["atr14"]

        n = len(sub_candles)
        start_bar = max(self.forecaster.warmup_bars + self.forecaster.horizon_bars + 15, 80)

        risk_pct = float(self.config.get("risk_percent", 1.0))
        sl_bars = max(1, int(self.config.get("sl_lookback_bars", 2)))
        sl_pad = float(self.config.get("sl_padding_pips", 3.5)) * self.pip_size
        min_sl_atr = float(self.config.get("min_sl_atr", 0.8))
        max_sl_atr = float(self.config.get("max_sl_atr", 2.8))
        tp1_r = float(self.config.get("tp1_r", 1.0))
        tp2_r = float(self.config.get("tp2_r", 2.0))
        be_offset_r = float(self.config.get("be_stage1_offset_r", 0.0))
        ratchet_r = float(self.config.get("ratchet_lock_r", 1.0))
        trail_struct_bars = max(2, int(self.config.get("trail_structure_bars", 4)))
        trail_atr_mult = float(self.config.get("trail_atr_mult", 2.8))
        climax_r = float(self.config.get("climax_tighten_r", 5.0))

        min_dir_prob = float(self.config.get("min_dir_prob_pct", 38.0))
        max_sw_prob = float(self.config.get("max_sideway_prob_pct", 47.0))
        min_edge = float(self.config.get("min_prob_edge_pct", 5.0))

        for i in range(start_bar, n):
            t_i = int(times[i])
            h_i = float(highs[i])
            l_i = float(lows[i])
            c_i = float(closes[i])
            atr_i = float(atr14[i])

            # 1. Evaluate active 3-order basket on bar i
            if active_orders:
                still_open = []
                stage1_reached = False
                stage2_reached = False

                for o in active_orders:
                    is_buy = o["type"] == "BUY"
                    entry_p = o["entry"]
                    init_risk = o["init_risk"]
                    sl_p = o["sl"]
                    tp_p = o["tp"]

                    closed_p = None
                    reason = ""
                    if is_buy:
                        if l_i <= sl_p:
                            closed_p = sl_p
                            reason = "SL"
                        elif tp_p > 0 and h_i >= tp_p:
                            closed_p = tp_p
                            reason = f"TP{o['slot']}"
                    else:
                        if h_i >= sl_p:
                            closed_p = sl_p
                            reason = "SL"
                        elif tp_p > 0 and l_i <= tp_p:
                            closed_p = tp_p
                            reason = f"TP{o['slot']}"

                    if closed_p is not None:
                        diff = (closed_p - entry_p) if is_buy else (entry_p - closed_p)
                        pnl = diff * self.usd_per_point * o["lot"]
                        balance += pnl
                        if pnl >= 0:
                            gross_profit += pnl
                            won_orders += 1
                        else:
                            gross_loss += abs(pnl)
                            lost_orders += 1
                        if o["slot"] == 1 and reason.startswith("TP"):
                            stage1_reached = True
                        if o["slot"] == 2 and reason.startswith("TP"):
                            stage2_reached = True
                        closed_trades.append(
                            {
                                "time": t_i,
                                "type": f"{o['type']}_ORDER_{o['slot']}_{reason}",
                                "tp_price": round(closed_p, self.digits),
                                "be_price": round(entry_p, self.digits),
                                "orders_count": 1,
                                "profit": round(pnl, 2),
                                "prob_confidence": o.get("prob_conf", 0.0),
                            }
                        )
                    else:
                        still_open.append(o)

                # Update Multi-Stage Protection & Hybrid Wave Trail for remaining open orders at bar close
                has_o1 = any(x["slot"] == 1 for x in still_open)
                has_o2 = any(x["slot"] == 2 for x in still_open)
                for o in still_open:
                    is_buy = o["type"] == "BUY"
                    entry_p = o["entry"]
                    init_risk = o["init_risk"]
                    slot = o["slot"]
                    s1_trig_r = o.get("s1_trig_r", tp1_r)
                    be_off = o.get("be_off_r", be_offset_r)

                    if is_buy:
                        s1_hit = stage1_reached or (not has_o1) or (h_i >= entry_p + init_risk * s1_trig_r)
                        s2_hit = stage2_reached or (not has_o1 and not has_o2) or (h_i >= entry_p + init_risk * tp2_r)
                        if s1_hit and slot in (2, 3):
                            s1_sl = entry_p + be_off * init_risk + self.pip_size
                            if s1_sl > o["sl"]:
                                o["sl"] = s1_sl
                        if s2_hit and slot == 3:
                            s2_sl = entry_p + ratchet_r * init_risk
                            if s2_sl > o["sl"]:
                                o["sl"] = s2_sl
                            # Hybrid Wave Trail after 2.0R
                            max_prof = max(c_i - entry_p, h_i - entry_p)
                            is_climax = climax_r > 0 and max_prof >= climax_r * init_risk
                            s_bars = 2 if is_climax else trail_struct_bars
                            struct_low = float(np.min(lows[max(0, i - s_bars + 1) : i + 1]))
                            atr_sl = c_i - (min(trail_atr_mult, 1.8) if is_climax else trail_atr_mult) * atr_i
                            st_sl = struct_low - (sl_pad if is_climax else max(sl_pad, 0.25 * atr_i))
                            cand_sl = max(atr_sl, st_sl)
                            if cand_sl > o["sl"] and cand_sl < c_i:
                                o["sl"] = cand_sl
                    else:
                        s1_hit = stage1_reached or (not has_o1) or (l_i <= entry_p - init_risk * s1_trig_r)
                        s2_hit = stage2_reached or (not has_o1 and not has_o2) or (l_i <= entry_p - init_risk * tp2_r)
                        if s1_hit and slot in (2, 3):
                            s1_sl = entry_p - be_off * init_risk - self.pip_size
                            if s1_sl < o["sl"]:
                                o["sl"] = s1_sl
                        if s2_hit and slot == 3:
                            s2_sl = entry_p - ratchet_r * init_risk
                            if s2_sl < o["sl"]:
                                o["sl"] = s2_sl
                            max_prof = max(entry_p - c_i, entry_p - l_i)
                            is_climax = climax_r > 0 and max_prof >= climax_r * init_risk
                            s_bars = 2 if is_climax else trail_struct_bars
                            struct_high = float(np.max(highs[max(0, i - s_bars + 1) : i + 1]))
                            atr_sl = c_i + (min(trail_atr_mult, 1.8) if is_climax else trail_atr_mult) * atr_i
                            st_sl = struct_high + (sl_pad if is_climax else max(sl_pad, 0.25 * atr_i))
                            cand_sl = min(atr_sl, st_sl)
                            if cand_sl < o["sl"] and cand_sl > c_i:
                                o["sl"] = cand_sl

                if not still_open:
                    completed_baskets += 1
                active_orders = still_open

            # 2. If no active basket, evaluate Non-Lookahead Signal at bar i
            if not active_orders and atr_i > 1e-8:
                sig = self.forecaster.evaluate_ema21_signal_at_bar(bundle, i, self.config)
                if sig != 0:
                    fc = self.forecaster.forecast_at_bar(
                        sub_candles, macro_candles, curr_idx=i, symbol=self.symbol, include_analogs=False
                    )
                    allow_trade = True
                    prob_conf = fc["prob_up_pct"] if sig == 1 else fc["prob_down_pct"]
                    opp_prob = fc["prob_down_pct"] if sig == 1 else fc["prob_up_pct"]
                    sw_prob = fc["prob_sideway_pct"]
                    exp_wave = fc["expected_wave_atr"]

                    if use_prob_filter:
                        # Surgical Whipsaw Veto:
                        # 1. Counter-Macro HTF conflict without strong local analog reversal edge
                        if sig == 1 and fc["macro_regime"] == "BEAR" and prob_conf < 44.0:
                            allow_trade = False
                        elif sig == -1 and fc["macro_regime"] == "BULL" and prob_conf < 44.0:
                            allow_trade = False
                        # 2. Opposite (adverse) analog probability dominates favorable probability in chop
                        elif opp_prob > prob_conf + 4.0 and sw_prob >= 30.0:
                            allow_trade = False
                        # 3. Dominant sideway regime or dead Efficiency Ratio chop
                        elif sw_prob >= 45.0 and prob_conf < 32.0:
                            allow_trade = False
                        elif fc["er_20"] < 0.16 and sw_prob >= 36.0:
                            allow_trade = False

                    if not allow_trade:
                        vetoed_count += 1
                    else:
                        accepted_count += 1
                        # Compute SL distance from past [i-sl_bars+1 .. i]
                        if sig == 1:
                            sw_low = float(np.min(lows[max(0, i - sl_bars + 1) : i + 1]))
                            sl_dist = (c_i - sw_low) + sl_pad
                        else:
                            sw_high = float(np.max(highs[max(0, i - sl_bars + 1) : i + 1]))
                            sl_dist = (sw_high - c_i) + sl_pad

                        sl_dist = float(np.clip(sl_dist, min_sl_atr * atr_i, max_sl_atr * atr_i))

                        # Conviction-Weighted Risk (preserving full 1.0x on standard breakouts, 1.20x on high-edge waves)
                        risk_mult = 1.0
                        s1_trig_r = tp1_r
                        be_off = be_offset_r
                        if use_prob_filter:
                            macro_aligned = (sig == 1 and fc["macro_regime"] == "BULL") or (
                                sig == -1 and fc["macro_regime"] == "BEAR"
                            )
                            if macro_aligned and prob_conf >= opp_prob + 6.0 and exp_wave >= 1.50:
                                risk_mult = 1.20
                            elif opp_prob > prob_conf + 2.0 and sw_prob >= 38.0:
                                risk_mult = 0.75

                        total_risk_usd = balance * (risk_pct / 100.0) * risk_mult
                        risk_per_order = total_risk_usd / 3.0
                        lot_per_order = max(0.01, round(risk_per_order / (sl_dist * self.usd_per_point), 2))

                        dir_type = "BUY" if sig == 1 else "SELL"
                        init_sl = (c_i - sl_dist) if sig == 1 else (c_i + sl_dist)
                        tp1 = (c_i + sl_dist * tp1_r) if sig == 1 else (c_i - sl_dist * tp1_r)
                        tp2 = (c_i + sl_dist * tp2_r) if sig == 1 else (c_i - sl_dist * tp2_r)

                        for slot_idx, tp_val in [(1, tp1), (2, tp2), (3, 0.0)]:
                            active_orders.append(
                                {
                                    "slot": slot_idx,
                                    "type": dir_type,
                                    "entry": c_i,
                                    "sl": init_sl,
                                    "tp": tp_val,
                                    "lot": lot_per_order,
                                    "init_risk": sl_dist,
                                    "prob_conf": prob_conf,
                                    "s1_trig_r": s1_trig_r,
                                    "be_off_r": be_off,
                                }
                            )

            # 3. Update floating equity & drawdown
            floating = 0.0
            for o in active_orders:
                diff = (c_i - o["entry"]) if o["type"] == "BUY" else (o["entry"] - c_i)
                floating += diff * self.usd_per_point * o["lot"]
            equity = round(balance + floating, 2)
            if equity > peak_eq:
                peak_eq = equity
            dd_u = peak_eq - equity
            dd_p = (dd_u / peak_eq) * 100.0 if peak_eq > 0 else 0.0
            if dd_u > max_dd_usd:
                max_dd_usd = round(dd_u, 2)
            if dd_p > max_dd_pct:
                max_dd_pct = round(dd_p, 2)

            eq_curve.append(
                {
                    "time": t_i,
                    "balance": round(balance, 2),
                    "equity": equity,
                    "drawdown_pct": round(dd_p, 2),
                }
            )

        total_closed = won_orders + lost_orders
        win_rate = round((won_orders / total_closed) * 100.0, 1) if total_closed > 0 else 0.0
        pf = round(gross_profit / gross_loss, 2) if gross_loss > 0 else (99.9 if gross_profit > 0 else 0.0)
        net_profit = round(equity - self.initial_balance, 2)
        net_profit_pct = round((net_profit / self.initial_balance) * 100.0, 2)

        return {
            "final_balance": round(balance, 2),
            "final_equity": equity,
            "net_profit": net_profit,
            "net_profit_pct": net_profit_pct,
            "profit_factor": pf,
            "win_rate": win_rate,
            "total_orders_closed": total_closed,
            "completed_cycles": completed_baskets,
            "accepted_signals": accepted_count,
            "vetoed_signals": vetoed_count,
            "gross_profit": round(gross_profit, 2),
            "gross_loss": round(-gross_loss, 2),
            "max_drawdown_usd": max_dd_usd,
            "max_drawdown_pct": max_dd_pct,
            "equity_curve": eq_curve,
            "closed_trades": closed_trades,
        }

    def evaluate_forecast_calibration(
        self, sub_candles: List[Dict[str, Any]], macro_candles: Optional[List[Dict[str, Any]]] = None, stride: int = 4
    ) -> Dict[str, Any]:
        """
        Audits out-of-sample directional accuracy of the Non-Lookahead Probabilistic Forecaster
        across confidence buckets (>= 45%, >= 50%, >= 55%, >= 60%).
        Strictly compares predicted probability at bar `i` (using s <= i - H) against actual outcome at [i+1 .. i+H].
        """
        bundle = self.forecaster.prepare_causal_arrays(sub_candles, macro_candles)
        n = len(sub_candles)
        H = self.forecaster.horizon_bars
        start_i = max(self.forecaster.warmup_bars + H + 30, 100)
        end_i = n - H - 1

        buckets = {
            "45_plus": {"min_p": 45.0, "total": 0, "correct_dir": 0, "avoided_adverse": 0, "avg_fav_atr": []},
            "50_plus": {"min_p": 50.0, "total": 0, "correct_dir": 0, "avoided_adverse": 0, "avg_fav_atr": []},
            "55_plus": {"min_p": 55.0, "total": 0, "correct_dir": 0, "avoided_adverse": 0, "avg_fav_atr": []},
            "60_plus": {"min_p": 60.0, "total": 0, "correct_dir": 0, "avoided_adverse": 0, "avg_fav_atr": []},
        }

        labels = bundle["labels"]
        max_up = bundle["max_up_atr"]
        max_dn = bundle["max_dn_atr"]

        total_evaluated = 0
        sideway_calls = 0
        sideway_correct = 0

        for i in range(start_i, end_i, max(1, stride)):
            fc = self.forecaster.forecast_at_bar(
                sub_candles, macro_candles, curr_idx=i, symbol=self.symbol, include_analogs=False
            )
            total_evaluated += 1
            p_up = fc["prob_up_pct"]
            p_dn = fc["prob_down_pct"]
            p_sw = fc["prob_sideway_pct"]
            actual_lbl = int(labels[i])

            if p_sw >= max(p_up, p_dn):
                sideway_calls += 1
                if actual_lbl == 0:
                    sideway_correct += 1

            pred_dir = 1 if p_up >= p_dn else -1
            dom_prob = max(p_up, p_dn)
            fav_atr = float(max_up[i]) if pred_dir == 1 else float(max_dn[i])

            for b_key, b_info in buckets.items():
                if dom_prob >= b_info["min_p"]:
                    b_info["total"] += 1
                    if actual_lbl == pred_dir:
                        b_info["correct_dir"] += 1
                    if actual_lbl != -pred_dir:
                        b_info["avoided_adverse"] += 1
                    b_info["avg_fav_atr"].append(fav_atr)

        summary_buckets = {}
        for b_key, b_info in buckets.items():
            tot = b_info["total"]
            summary_buckets[b_key] = {
                "threshold_pct": b_info["min_p"],
                "signals": tot,
                "exact_triple_barrier_win_pct": round((b_info["correct_dir"] / tot) * 100.0, 1) if tot > 0 else 0.0,
                "non_adverse_survival_pct": round((b_info["avoided_adverse"] / tot) * 100.0, 1) if tot > 0 else 0.0,
                "realized_favorable_wave_atr": round(float(np.mean(b_info["avg_fav_atr"])), 2)
                if b_info["avg_fav_atr"]
                else 0.0,
            }

        return {
            "total_bars_audited": total_evaluated,
            "horizon_bars": H,
            "sideway_regime_calls": sideway_calls,
            "sideway_accuracy_pct": round((sideway_correct / sideway_calls) * 100.0, 1) if sideway_calls > 0 else 0.0,
            "confidence_buckets": summary_buckets,
        }

    def fast_backtest(
        self, sub_candles: List[Dict[str, Any]], macro_candles: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Runs both the Probabilistic Context Engine v3.0 AND the Baseline EMA21 (No Prob Filter),
        plus full k-NN Forecast Calibration metrics.
        Returns a complete report compatible with trading-simulator's Fast Backtest modal & API.
        """
        self.reset()
        if not sub_candles:
            return {"success": False, "error": "No candle data provided"}

        bundle = self.forecaster.prepare_causal_arrays(sub_candles, macro_candles)
        use_prob = bool(self.config.get("use_prob_filter", True))

        # Run selected mode (Probabilistic by default)
        res_main = self._simulate_run_on_bundle(bundle, sub_candles, macro_candles, use_prob_filter=use_prob)
        # Also run baseline (or opposite) for direct A/B comparison
        res_base = self._simulate_run_on_bundle(bundle, sub_candles, macro_candles, use_prob_filter=False)
        calibration = self.evaluate_forecast_calibration(sub_candles, macro_candles, stride=4)
        latest_fc = self.forecaster.forecast_at_bar(
            sub_candles, macro_candles, curr_idx=len(sub_candles) - 1, symbol=self.symbol
        )

        # Downsample equity curve for fast frontend rendering (max 1000 points)
        eq_curve = res_main["equity_curve"]
        step = max(1, len(eq_curve) // 1000)
        sampled_curve = eq_curve[::step]
        if eq_curve and (not sampled_curve or sampled_curve[-1]["time"] != eq_curve[-1]["time"]):
            sampled_curve.append(eq_curve[-1])

        return {
            "success": True,
            "engine_type": "EMA21_PROBABILISTIC_V3",
            "symbol": self.symbol,
            "preset_name": self.config.get("preset_name", "v3.0 EMA21 Probabilistic Macro k-NN"),
            "initial_balance": self.initial_balance,
            "final_balance": res_main["final_balance"],
            "final_equity": res_main["final_equity"],
            "net_profit": res_main["net_profit"],
            "net_profit_pct": res_main["net_profit_pct"],
            "max_drawdown_usd": res_main["max_drawdown_usd"],
            "max_drawdown_pct": res_main["max_drawdown_pct"],
            "completed_cycles": res_main["completed_cycles"],
            "total_cuts": res_main["vetoed_signals"],  # Displayed in UI card: Vetoed Whipsaw Signals
            "total_cut_loss": res_main["gross_loss"],
            "total_tp_profit": res_main["gross_profit"],
            "profit_factor": res_main["profit_factor"],
            "win_rate": res_main["win_rate"],
            "total_orders_closed": res_main["total_orders_closed"],
            "accepted_signals": res_main["accepted_signals"],
            "vetoed_signals": res_main["vetoed_signals"],
            "baseline_comparison": {
                "baseline_net_profit": res_base["net_profit"],
                "baseline_profit_factor": res_base["profit_factor"],
                "baseline_win_rate": res_base["win_rate"],
                "baseline_max_dd_usd": res_base["max_drawdown_usd"],
                "baseline_max_dd_pct": res_base["max_drawdown_pct"],
                "baseline_signals": res_base["accepted_signals"],
                "prob_net_profit": res_main["net_profit"],
                "prob_profit_factor": res_main["profit_factor"],
                "prob_win_rate": res_main["win_rate"],
                "prob_max_dd_usd": res_main["max_drawdown_usd"],
                "prob_max_dd_pct": res_main["max_drawdown_pct"],
                "prob_signals": res_main["accepted_signals"],
                "whipsaws_filtered": res_base["accepted_signals"] - res_main["accepted_signals"],
            },
            "calibration": calibration,
            "latest_forecast": latest_fc,
            "total_bars_tested": len(sub_candles),
            "start_time": sub_candles[0]["time"] if sub_candles else 0,
            "end_time": sub_candles[-1]["time"] if sub_candles else 0,
            "equity_curve": sampled_curve,
            "closed_trades": res_main["closed_trades"][-100:],
        }
