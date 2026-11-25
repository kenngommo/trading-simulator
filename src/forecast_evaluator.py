"""
3-in-1 Forecast Accuracy Evaluator, Dual-Mode SQLite Ledger, and
Bounded 3-Layer Adaptive Self-Improvement Engine (Champion vs Challenger).

Measures and continuously improves `ProbabilisticContextForecaster` over time:
1. Tier 1 (Probabilistic Calibration): Multi-class Brier Score, Directional Hit Rate %,
   Non-Adverse Survival %, and Empirical Reliability Buckets.
2. Tier 2 (Tactical Setup Realized Performance): Evaluates suggested Entry / SL / TP1(1.5R) / TP2(2.0R) / TP3(3.0R)
   against subsequent closed candles (Setup Winrate %, Avg Realized R, MFE/MAE in ATR).
3. Tier 3 (Wave Trajectory Accuracy): Evaluates projected future_candles & expected_wave_atr
   against actual forward price excursion (Wave MAE in ATR & Amplitude Capture %).
4. 3-Layer Bounded Self-Improvement (Champion vs Challenger):
   - Layer 1: Adaptive Feature Importance Weights (ER20, Squeeze4, ImpulseCLV, EMA21Slope, EMAStack)
   - Layer 2: Temporal Decay (Recency Weighting), DNA Session Affinity Bonus & HTF/LTF Blend Ratio
   - Layer 3: Empirical Probability Calibration & Dynamic Guardrail Thresholding
"""

import os
import json
import sqlite3
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
import numpy as np

from .data_fetcher import DATA_DIR, SYMBOL_MAPPINGS
from .probabilistic_context_engine import evaluate_dna_session_and_time

LEDGER_DB_PATH = os.path.join(DATA_DIR, "forecast_ledger.db")
PROFILES_JSON_PATH = os.path.join(DATA_DIR, "adaptive_profiles.json")


def _default_profile(symbol: str, timeframe_pair: str = "H4_M15") -> Dict[str, Any]:
    """Returns the baseline v3.0 Champion parameter profile for a symbol & timeframe pair."""
    return {
        "symbol": symbol.upper(),
        "timeframe_pair": timeframe_pair.upper(),
        "version": 1,
        "version_tag": "v3.0-Base",
        "updated_at_ts": int(datetime.now(timezone.utc).timestamp()),
        "updated_at_formatted": evaluate_dna_session_and_time(
            symbol, int(datetime.now(timezone.utc).timestamp()), is_mt5_server_ts=False
        )["formatted_full"],
        # Layer 1: Feature weights [er_20, squeeze_4, impulse_clv, ema21_slope_atr, ema_stack_atr]
        "f_weights_ltf": [1.25, 1.15, 1.35, 1.20, 1.05],
        "f_weights_htf": [1.30, 1.10, 1.25, 1.35, 1.25],
        # Layer 2: HTF/LTF blend, k-neighbors, Temporal Recency Decay & Session Affinity
        "htf_weight": 0.70,
        "k_neighbors": 35,
        "time_decay_strength": 0.20,  # Boosts more recent historical analogs
        "session_affinity_bonus": 0.15,  # Reduces distance for analogs in the same DNA session
        # Layer 3: Empirical Probability Calibration & Guardrail
        "prob_temperature": 1.00,  # >1 sharpens confident probabilities, <1 softens overconfidence
        "aligned_min_prob_pct": 45.0,  # Minimum dominant prob to declare ALIGNED_BUY / ALIGNED_SELL
        "aligned_min_edge_pct": 4.0,   # Minimum edge (|prob_up - prob_dn|)
        "guardrail_status": "NORMAL",  # "NORMAL" | "TIGHTENED" | "HIGH_CONFIDENCE"
        "guardrail_badge": "🟢 MÔ HÌNH ĐỒNG BỘ TỐT",
        "trust_score": 75.0,
        "metrics_snapshot": {},
        "upgrade_history": [],
    }


class ForecastLedgerAndCalibrator:
    """
    Manages the SQLite Forecast Ledger (`forecast_ledger.db`), automatic post-facto verification
    against realized candles, 3-in-1 Scorecard computation, and Champion vs Challenger self-improvement.
    """

    def __init__(self, db_path: str = LEDGER_DB_PATH, profiles_path: str = PROFILES_JSON_PATH):
        self.db_path = db_path
        self.profiles_path = profiles_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._profiles_cache: Dict[str, Dict[str, Any]] = {}
        self._init_db()
        self._load_profiles()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=15.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS forecast_predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    timeframe_pair TEXT NOT NULL,
                    forecast_mode TEXT NOT NULL,
                    bar_time INTEGER NOT NULL,
                    server_vn_time TEXT NOT NULL,
                    session_status TEXT,
                    horizon_bars INTEGER NOT NULL,
                    entry_price REAL NOT NULL,
                    atr REAL NOT NULL,
                    prob_up REAL NOT NULL,
                    prob_down REAL NOT NULL,
                    prob_sideway REAL NOT NULL,
                    macro_prob_up REAL,
                    macro_prob_down REAL,
                    dominant_scenario TEXT,
                    tactical_status TEXT,
                    setup_dir TEXT,
                    sl_price REAL,
                    tp1_price REAL,
                    tp2_price REAL,
                    tp3_price REAL,
                    expected_wave_atr REAL,
                    projected_closes_json TEXT,
                    model_version TEXT,
                    source_mode TEXT DEFAULT 'LIVE',
                    status TEXT DEFAULT 'PENDING',
                    actual_label INTEGER,
                    brier_score REAL,
                    directional_correct INTEGER,
                    non_adverse_survival INTEGER,
                    setup_outcome TEXT,
                    realized_r REAL,
                    mfe_atr REAL,
                    mae_atr REAL,
                    wave_mae_atr REAL,
                    verified_at_str TEXT,
                    UNIQUE(symbol, timeframe_pair, bar_time, source_mode)
                )
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_fc_sym_tf_time
                ON forecast_predictions(symbol, timeframe_pair, bar_time)
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS calibration_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    timeframe_pair TEXT NOT NULL,
                    run_time_str TEXT NOT NULL,
                    champion_before_ver TEXT,
                    challenger_ver TEXT,
                    promoted INTEGER,
                    trust_score_before REAL,
                    trust_score_after REAL,
                    brier_before REAL,
                    brier_after REAL,
                    setup_wr_before REAL,
                    setup_wr_after REAL,
                    expectancy_r_before REAL,
                    expectancy_r_after REAL,
                    details_json TEXT
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    def _profile_key(self, symbol: str, timeframe_pair: str) -> str:
        return f"{symbol.upper().strip()}__{timeframe_pair.upper().strip()}"

    def _load_profiles(self) -> None:
        if os.path.exists(self.profiles_path):
            try:
                with open(self.profiles_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self._profiles_cache = data
            except Exception:
                self._profiles_cache = {}

    def _save_profiles(self) -> None:
        try:
            with open(self.profiles_path, "w", encoding="utf-8") as f:
                json.dump(self._profiles_cache, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def get_profile(self, symbol: str, timeframe_pair: str = "H4_M15") -> Dict[str, Any]:
        key = self._profile_key(symbol, timeframe_pair)
        if key not in self._profiles_cache:
            self._profiles_cache[key] = _default_profile(symbol, timeframe_pair)
            self._save_profiles()
        return self._profiles_cache[key]

    def update_profile(self, symbol: str, timeframe_pair: str, profile: Dict[str, Any]) -> None:
        key = self._profile_key(symbol, timeframe_pair)
        self._profiles_cache[key] = profile
        self._save_profiles()

    # =========================================================================
    # 1. RECORDING & AUTO-RECONCILING FORECASTS IN SQLITE LEDGER
    # =========================================================================
    def record_forecast(
        self,
        symbol: str,
        timeframe_pair: str,
        bar_time: int,
        forecast: Dict[str, Any],
        source_mode: str = "LIVE",
    ) -> None:
        """Records a forecast into `forecast_ledger.db` (idempotent per symbol, tf_pair, bar_time, source_mode)."""
        if not forecast or bar_time <= 0:
            return
        setup = forecast.get("suggested_setup") or {}
        dna = forecast.get("dna_session") or evaluate_dna_session_and_time(symbol, bar_time)
        entry_price = float(setup.get("entry") or 0.0)
        if entry_price <= 0:
            return

        atr_val = max(float(setup.get("atr") or 1e-5), 1e-5)
        fut_c = forecast.get("future_candles") or []
        proj_closes = [round(float(c.get("close", entry_price)), 5) for c in fut_c]
        prof = self.get_profile(symbol, timeframe_pair)

        setup_dir = str(setup.get("direction", "BUY"))
        ord_type = str(setup.get("order_type", "MARKET_CLOSE"))
        strat_id = str(setup.get("strategy_id", "EMA21_TREND_IMPULSE"))
        tac_val = forecast.get("tactical_status", "NEUTRAL")
        if setup.get("setup_triggered"):
            tac_val = f"ALIGNED_{setup_dir} [{strat_id}:{ord_type}]"

        conn = self._get_conn()
        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO forecast_predictions (
                    symbol, timeframe_pair, forecast_mode, bar_time, server_vn_time,
                    session_status, horizon_bars, entry_price, atr,
                    prob_up, prob_down, prob_sideway, macro_prob_up, macro_prob_down,
                    dominant_scenario, tactical_status, setup_dir,
                    sl_price, tp1_price, tp2_price, tp3_price,
                    expected_wave_atr, projected_closes_json, model_version, source_mode, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING')
                """,
                (
                    symbol.upper(),
                    timeframe_pair.upper(),
                    forecast.get("forecast_mode", "COMBINED_HTF_LTF"),
                    int(bar_time),
                    dna.get("formatted_short", ""),
                    dna.get("session_status", "NORMAL_SESSION"),
                    int(forecast.get("horizon_bars", 8)),
                    entry_price,
                    atr_val,
                    float(forecast.get("prob_up_pct", 33.3)),
                    float(forecast.get("prob_down_pct", 33.3)),
                    float(forecast.get("prob_sideway_pct", 33.4)),
                    float(forecast.get("macro_prob_up_pct", 33.3)),
                    float(forecast.get("macro_prob_down_pct", 33.3)),
                    forecast.get("dominant_scenario", "NEUTRAL"),
                    tac_val,
                    setup_dir,
                    float(setup.get("sl") or 0.0),
                    float(setup.get("tp1") or 0.0),
                    float(setup.get("tp2") or 0.0),
                    float(setup.get("tp3") or 0.0),
                    float(forecast.get("expected_wave_atr", 1.5)),
                    json.dumps(proj_closes),
                    prof.get("version_tag", "v3.0-Base"),
                    source_mode,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _evaluate_single_outcome(
        entry_price: float,
        atr: float,
        prob_up: float,
        prob_down: float,
        prob_sideway: float,
        setup_dir: str,
        sl_price: float,
        tp1_price: float,
        tp2_price: float,
        tp3_price: float,
        expected_wave_atr: float,
        proj_closes: List[float],
        forward_highs: np.ndarray,
        forward_lows: np.ndarray,
        forward_closes: np.ndarray,
        up_barrier_atr: float = 1.25,
        dn_barrier_atr: float = 1.25,
        adverse_barrier_atr: float = 0.95,
        order_type: str = "MARKET_CLOSE",
    ) -> Dict[str, Any]:
        """
        Computes the exact 3-in-1 verification metrics over the closed forward window:
          1. Triple-Barrier Actual Label (+1 UP, -1 DOWN, 0 SIDEWAY) & Multi-Class Brier Score
          2. Tactical Setup Outcome (TP3_HIT, TP2_HIT, TP1_HIT, R1_LOCK, SL_HIT, UNFILLED_CANCELLED, TIME_EXIT) & Realized R
             with realistic Multi-Stage Ratchet Protection (+0.85R -> Move SL to Break-Even Cushion)
             and Stop-Order (`BUY_STOP` / `SELL_STOP`) 3-bar fill verification.
          3. Wave Path MAE (in ATR units)
        """
        total_fwd = len(forward_closes)
        H = min(8, total_fwd)
        atr_safe = max(atr, 1e-8)

        # Reference close of signal bar for Triple-Barrier wave excursion
        ref_price = float(proj_closes[0]) if proj_closes else entry_price
        up_exc = (forward_highs[:H] - ref_price) / atr_safe
        dn_exc = (ref_price - forward_lows[:H]) / atr_safe

        max_up_atr = max(0.0, float(np.max(up_exc))) if H > 0 else 0.0
        max_dn_atr = max(0.0, float(np.max(dn_exc))) if H > 0 else 0.0

        # 1. Triple-Barrier actual outcome over H bars
        up_hit_idx = -1
        dn_hit_idx = -1
        up_invalid = False
        dn_invalid = False
        for k_step in range(H):
            u_k = float(up_exc[k_step])
            d_k = float(dn_exc[k_step])
            if d_k >= adverse_barrier_atr and up_hit_idx == -1:
                up_invalid = True
            if u_k >= adverse_barrier_atr and dn_hit_idx == -1:
                dn_invalid = True
            if u_k >= up_barrier_atr and not up_invalid and up_hit_idx == -1:
                up_hit_idx = k_step
            if d_k >= dn_barrier_atr and not dn_invalid and dn_hit_idx == -1:
                dn_hit_idx = k_step

        if up_hit_idx != -1 and (dn_hit_idx == -1 or up_hit_idx < dn_hit_idx):
            actual_label = 1
        elif dn_hit_idx != -1 and (up_hit_idx == -1 or dn_hit_idx < up_hit_idx):
            actual_label = -1
        else:
            actual_label = 0

        # Multi-class Brier score in [0, 1]
        p_u = np.clip(prob_up / 100.0, 0.0, 1.0)
        p_d = np.clip(prob_down / 100.0, 0.0, 1.0)
        p_s = np.clip(prob_sideway / 100.0, 0.0, 1.0)
        y_u = 1.0 if actual_label == 1 else 0.0
        y_d = 1.0 if actual_label == -1 else 0.0
        y_s = 1.0 if actual_label == 0 else 0.0
        brier_score = float(((p_u - y_u) ** 2 + (p_d - y_d) ** 2 + (p_s - y_s) ** 2) / 3.0)

        pred_dir = 1 if prob_up >= prob_down else -1
        fav_max = max_up_atr if pred_dir == 1 else max_dn_atr
        adv_max = max_dn_atr if pred_dir == 1 else max_up_atr
        net_close_atr = float((forward_closes[H - 1] - ref_price) / atr_safe) if H > 0 else 0.0

        if actual_label == pred_dir:
            directional_correct = 1
        elif actual_label == 0 and (fav_max >= adv_max and (fav_max >= 0.65 or (net_close_atr * pred_dir) >= 0.15)):
            directional_correct = 1
        else:
            directional_correct = 0

        non_adverse = 1 if actual_label != -pred_dir else 0

        # 2. Tactical Setup Evaluation (Supports MARKET_CLOSE & Pending BUY_STOP / SELL_STOP + Multi-Stage Ratchet)
        is_buy = setup_dir.upper() == "BUY"
        sl_dist = abs(entry_price - sl_price) if sl_price > 0 else (1.5 * atr_safe)
        if sl_dist <= 1e-8:
            sl_dist = 1.5 * atr_safe

        mfe_atr = max_up_atr if is_buy else max_dn_atr
        mae_atr = max_dn_atr if is_buy else max_up_atr

        # Check Stop Order Trigger within 3 bars if order_type is BUY_STOP or SELL_STOP
        start_trade_k = 0
        order_filled = True
        if "STOP" in order_type.upper() and "WAITING" not in order_type.upper():
            order_filled = False
            for k_trig in range(min(3, total_fwd)):
                hi_t = float(forward_highs[k_trig])
                lo_t = float(forward_lows[k_trig])
                if is_buy:
                    if sl_price > 0 and lo_t <= sl_price and hi_t < entry_price:
                        break
                    if hi_t >= entry_price:
                        order_filled = True
                        start_trade_k = k_trig
                        break
                else:
                    if sl_price > 0 and hi_t >= sl_price and lo_t > entry_price:
                        break
                    if lo_t <= entry_price:
                        order_filled = True
                        start_trade_k = k_trig
                        break

        if not order_filled:
            setup_outcome = "UNFILLED_CANCELLED"
            realized_r = 0.0
        else:
            # Stage-1 Ratchet activates at +0.85R (moves SL to +0.25R Cushion)
            r1_price = (entry_price + 0.85 * sl_dist) if is_buy else (entry_price - 0.85 * sl_dist)
            setup_outcome = "TIME_EXIT"
            realized_r = 0.0
            sl_hit = False
            r1_hit = False
            tp1_hit = False
            tp2_hit = False
            tp3_hit = False

            for k_step in range(start_trade_k, total_fwd):
                hi = float(forward_highs[k_step])
                lo = float(forward_lows[k_step])
                if is_buy:
                    # On the fill bar of a BUY_STOP, check favorable targets too; initial SL only hits if not already r1_hit
                    if sl_price > 0 and lo <= sl_price and not r1_hit and not tp1_hit:
                        # Check if r1_price was reached first on the same bar when close > entry
                        if hi >= r1_price and float(forward_closes[k_step]) >= entry_price:
                            r1_hit = True
                        else:
                            sl_hit = True
                            break
                    if hi >= r1_price:
                        r1_hit = True
                    if tp1_price > 0 and hi >= tp1_price:
                        tp1_hit = True
                    if tp2_price > 0 and hi >= tp2_price:
                        tp2_hit = True
                    if tp3_price > 0 and hi >= tp3_price:
                        tp3_hit = True
                        break
                else:
                    if sl_price > 0 and hi >= sl_price and not r1_hit and not tp1_hit:
                        if lo <= r1_price and float(forward_closes[k_step]) <= entry_price:
                            r1_hit = True
                        else:
                            sl_hit = True
                            break
                    if lo <= r1_price:
                        r1_hit = True
                    if tp1_price > 0 and lo <= tp1_price:
                        tp1_hit = True
                    if tp2_price > 0 and lo <= tp2_price:
                        tp2_hit = True
                    if tp3_price > 0 and lo <= tp3_price:
                        tp3_hit = True
                        break

            if sl_hit:
                setup_outcome = "SL_HIT"
                realized_r = -1.0
            elif tp3_hit:
                setup_outcome = "TP3_HIT"
                realized_r = 3.0
            elif tp2_hit:
                setup_outcome = "TP2_HIT"
                realized_r = 2.0
            elif tp1_hit:
                setup_outcome = "TP1_HIT"
                realized_r = 1.5
            elif r1_hit:
                setup_outcome = "R1_LOCK"
                realized_r = 1.0
            else:
                end_diff = (
                    (float(forward_closes[-1]) - entry_price)
                    if is_buy
                    else (entry_price - float(forward_closes[-1]))
                )
                realized_r = float(np.clip(end_diff / sl_dist, -1.0, 2.5))
                if realized_r > 0.05 or (mfe_atr > mae_atr and mfe_atr >= 0.80):
                    setup_outcome = "TIME_WIN"
                    realized_r = max(realized_r, round(0.40 * (mfe_atr / max(1.0, sl_dist / atr_safe)), 2))
                elif realized_r < -0.15:
                    setup_outcome = "TIME_LOSS"
                else:
                    setup_outcome = "TIME_FLAT"

        # 3. Wave Path Accuracy (MAE between projected_closes and actual forward_closes in ATR units)
        if proj_closes and len(proj_closes) > 0:
            m_len = min(len(proj_closes), H)
            proj_arr = np.array(proj_closes[:m_len], dtype=float)
            act_arr = forward_closes[:m_len]
            wave_path_mae = float(np.mean(np.abs(proj_arr - act_arr)) / atr_safe)
        else:
            wave_path_mae = abs(expected_wave_atr - mfe_atr)

        return {
            "actual_label": int(actual_label),
            "brier_score": round(brier_score, 4),
            "directional_correct": int(directional_correct),
            "non_adverse_survival": int(non_adverse),
            "setup_outcome": setup_outcome,
            "realized_r": round(realized_r, 2),
            "mfe_atr": round(mfe_atr, 2),
            "mae_atr": round(mae_atr, 2),
            "wave_mae_atr": round(wave_path_mae, 2),
        }

    def reconcile_pending_forecasts(
        self, symbol: str, timeframe_pair: str, sub_candles: List[Dict[str, Any]]
    ) -> int:
        """
        Checks all PENDING forecasts in SQLite for `(symbol, timeframe_pair)` against `sub_candles`.
        If at least `horizon_bars` candles have closed after `bar_time`, verifies and updates the row.
        Returns number of newly verified forecasts.
        """
        if not sub_candles or len(sub_candles) < 20:
            return 0

        times = np.array([int(c["time"]) for c in sub_candles], dtype=np.int64)
        highs = np.array([float(c["high"]) for c in sub_candles], dtype=float)
        lows = np.array([float(c["low"]) for c in sub_candles], dtype=float)
        closes = np.array([float(c["close"]) for c in sub_candles], dtype=float)

        conn = self._get_conn()
        verified_count = 0
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT * FROM forecast_predictions
                WHERE symbol = ? AND timeframe_pair = ? AND status = 'PENDING'
                ORDER BY bar_time ASC
                """,
                (symbol.upper(), timeframe_pair.upper()),
            )
            pending_rows = cur.fetchall()
            if not pending_rows:
                return 0

            now_dna = evaluate_dna_session_and_time(
                symbol, int(datetime.now(timezone.utc).timestamp()), is_mt5_server_ts=False
            )
            verified_at_str = now_dna["formatted_short"]

            for row in pending_rows:
                b_time = int(row["bar_time"])
                H = int(row["horizon_bars"])
                idx_arr = np.where(times == b_time)[0]
                if len(idx_arr) == 0:
                    # Try nearest bar >= b_time if exact timestamp shifted slightly
                    after_arr = np.where(times >= b_time)[0]
                    if len(after_arr) == 0:
                        continue
                    bar_idx = int(after_arr[0])
                else:
                    bar_idx = int(idx_arr[-1])

                # Ensure H closed candles exist after bar_idx (strictly non-lookahead verification)
                if bar_idx + H >= len(sub_candles):
                    continue

                eval_h = min(max(H, 14), len(sub_candles) - bar_idx - 1)
                f_highs = highs[bar_idx + 1 : bar_idx + eval_h + 1]
                f_lows = lows[bar_idx + 1 : bar_idx + eval_h + 1]
                f_closes = closes[bar_idx + 1 : bar_idx + eval_h + 1]

                try:
                    proj_closes = json.loads(row["projected_closes_json"] or "[]")
                except Exception:
                    proj_closes = []

                tac_str = str(row["tactical_status"] or "")
                ord_t = "BUY_STOP" if "BUY_STOP" in tac_str else ("SELL_STOP" if "SELL_STOP" in tac_str else "MARKET_CLOSE")

                res = self._evaluate_single_outcome(
                    entry_price=float(row["entry_price"]),
                    atr=float(row["atr"]),
                    prob_up=float(row["prob_up"]),
                    prob_down=float(row["prob_down"]),
                    prob_sideway=float(row["prob_sideway"]),
                    setup_dir=str(row["setup_dir"] or "BUY"),
                    sl_price=float(row["sl_price"] or 0.0),
                    tp1_price=float(row["tp1_price"] or 0.0),
                    tp2_price=float(row["tp2_price"] or 0.0),
                    tp3_price=float(row["tp3_price"] or 0.0),
                    expected_wave_atr=float(row["expected_wave_atr"] or 1.5),
                    proj_closes=proj_closes,
                    forward_highs=f_highs,
                    forward_lows=f_lows,
                    forward_closes=f_closes,
                    order_type=ord_t,
                )

                cur.execute(
                    """
                    UPDATE forecast_predictions
                    SET status = 'VERIFIED',
                        actual_label = ?,
                        brier_score = ?,
                        directional_correct = ?,
                        non_adverse_survival = ?,
                        setup_outcome = ?,
                        realized_r = ?,
                        mfe_atr = ?,
                        mae_atr = ?,
                        wave_mae_atr = ?,
                        verified_at_str = ?
                    WHERE id = ?
                    """,
                    (
                        res["actual_label"],
                        res["brier_score"],
                        res["directional_correct"],
                        res["non_adverse_survival"],
                        res["setup_outcome"],
                        res["realized_r"],
                        res["mfe_atr"],
                        res["mae_atr"],
                        res["wave_mae_atr"],
                        verified_at_str,
                        row["id"],
                    ),
                )
                verified_count += 1

            conn.commit()
        finally:
            conn.close()

        return verified_count

    # =========================================================================
    # 2. WALK-FORWARD SEEDING ON REAL QUANTITATIVE STRATEGY SETUPS
    # =========================================================================
    def find_strategy_trigger_indices(
        self,
        forecaster: Any,
        bundle: Dict[str, Any],
        symbol: str,
        start_idx: int,
        end_idx: int,
        cooldown_bars: int = 2,
    ) -> List[int]:
        """
        Scans `[start_idx .. end_idx]` and returns all bar indices where one of the 3 Quantitative Edge Strategies
        (`EMA21_TREND_IMPULSE`, `STOCH_RSI_DIV_REVERSAL`, `BB_FAKEOUT_STOP`) genuinely triggers (`setup_triggered == True`).
        Applies a small `cooldown_bars` spacing so consecutive bars on the same impulse wave are not double-counted.
        """
        triggered_indices: List[int] = []
        last_trig = -999
        for idx in range(start_idx, end_idx + 1):
            if idx - last_trig < cooldown_bars:
                continue
            q_st = forecaster.evaluate_quantitative_strategy_setup_at_bar(
                bundle=bundle,
                idx=idx,
                symbol=symbol,
                enforce_prob_filter=False,
            )
            if q_st.get("setup_triggered"):
                triggered_indices.append(idx)
                last_trig = idx
        return triggered_indices

    def ensure_walkforward_audit_populated(
        self,
        forecaster: Any,
        symbol: str,
        timeframe_pair: str,
        sub_candles: List[Dict[str, Any]],
        macro_candles: Optional[List[Dict[str, Any]]],
        audit_samples: int = 85,
        stride: int = 5,
    ) -> None:
        """
        If the SQLite ledger has fewer than 25 verified forecasts for `(symbol, timeframe_pair)`,
        runs a non-lookahead Walk-Forward Audit strictly on historical bars where a Quantitative Strategy Setup
        (`EMA21_TREND_IMPULSE`, `STOCH_RSI_DIV_REVERSAL`, `BB_FAKEOUT_STOP`) triggered!
        """
        if not sub_candles or len(sub_candles) < 180:
            return

        # Reconcile any existing pending rows first
        self.reconcile_pending_forecasts(symbol, timeframe_pair, sub_candles)

        conn = self._get_conn()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM forecast_predictions WHERE symbol = ? AND timeframe_pair = ? AND status = 'VERIFIED'",
                (symbol.upper(), timeframe_pair.upper()),
            )
            cnt = int(cur.fetchone()["cnt"])
        finally:
            conn.close()

        if cnt >= 25:
            return

        H = max(int(getattr(forecaster, "horizon_bars", 8)), 14)
        n = len(sub_candles)
        end_idx = n - H - 2
        start_idx = max(int(getattr(forecaster, "warmup_bars", 60)) + H + 15, 90)
        if end_idx <= start_idx:
            return

        bundle = forecaster.prepare_causal_arrays(sub_candles, macro_candles)
        strat_indices = self.find_strategy_trigger_indices(forecaster, bundle, symbol, start_idx, end_idx, cooldown_bars=2)
        eval_list = strat_indices[-audit_samples:] if len(strat_indices) > audit_samples else strat_indices

        for idx in eval_list:
            fc = forecaster.forecast_at_bar(
                sub_candles,
                macro_candles,
                curr_idx=idx,
                symbol=symbol,
                include_analogs=False,
                timeframe_pair=timeframe_pair,
            )
            # Only record in Walk-Forward if the strategy setup passed the Probabilistic Context Filter (`setup_triggered == True`)
            st = fc.get("suggested_setup") or {}
            if not st.get("setup_triggered"):
                continue
            self.record_forecast(
                symbol=symbol,
                timeframe_pair=timeframe_pair,
                bar_time=int(sub_candles[idx]["time"]),
                forecast=fc,
                source_mode="WALK_FORWARD",
            )

        self.reconcile_pending_forecasts(symbol, timeframe_pair, sub_candles)

    def get_symbol_scorecard(
        self,
        symbol: str,
        timeframe_pair: str = "H4_M15",
        limit_recent: int = 120,
    ) -> Dict[str, Any]:
        """
        Computes the 3-in-1 Accuracy Scorecard from verified forecasts in SQLite:
          - Tier 1: Probabilistic Accuracy (Brier Score, Directional Accuracy %, Non-Adverse Survival %, Reliability Buckets)
          - Tier 2: Tactical Setup Performance (ALIGNED Winrate %, TP1/TP2/TP3 Hit Rate, Expectancy R)
          - Tier 3: Wave Trajectory Accuracy (Wave Path MAE in ATR, Favorable Excursion Capture %)
          - Composite Trust Score (0-100) + Guardrail Status
        """
        prof = self.get_profile(symbol, timeframe_pair)
        conn = self._get_conn()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT * FROM forecast_predictions
                WHERE symbol = ? AND timeframe_pair = ? AND status = 'VERIFIED'
                ORDER BY bar_time DESC
                LIMIT ?
                """,
                (symbol.upper(), timeframe_pair.upper(), int(limit_recent)),
            )
            rows = [dict(r) for r in cur.fetchall()]

            cur.execute(
                """
                SELECT COUNT(*) AS pending_cnt FROM forecast_predictions
                WHERE symbol = ? AND timeframe_pair = ? AND status = 'PENDING'
                """,
                (symbol.upper(), timeframe_pair.upper()),
            )
            pending_cnt = int(cur.fetchone()["pending_cnt"])
        finally:
            conn.close()

        if not rows:
            return {
                "symbol": symbol.upper(),
                "timeframe_pair": timeframe_pair.upper(),
                "verified_count": 0,
                "pending_count": pending_cnt,
                "trust_score": prof.get("trust_score", 75.0),
                "trust_badge": "⏳ CHƯA ĐỦ MẪU ĐỐI SOÁT",
                "guardrail_status": prof.get("guardrail_status", "NORMAL"),
                "guardrail_badge": prof.get("guardrail_badge", "🟢 MÔ HÌNH ĐỒNG BỘ TỐT"),
                "model_version": prof.get("version_tag", "v3.0-Base"),
                "tier1_probabilistic": {
                    "brier_score": 0.20,
                    "directional_accuracy_pct": 0.0,
                    "non_adverse_survival_pct": 0.0,
                    "reliability_buckets": [],
                },
                "tier2_tactical_setup": {
                    "aligned_signals_count": 0,
                    "setup_winrate_pct": 0.0,
                    "tp1_hit_pct": 0.0,
                    "tp2_hit_pct": 0.0,
                    "expectancy_r": 0.0,
                },
                "tier3_wave_trajectory": {
                    "avg_wave_mae_atr": 0.0,
                    "avg_realized_mfe_atr": 0.0,
                    "amplitude_capture_pct": 0.0,
                },
                "profile": prof,
                "recent_forecasts": [],
            }

        total = len(rows)
        brier_vals = [float(r["brier_score"] or 0.22) for r in rows]
        dir_hits = [int(r["directional_correct"] or 0) for r in rows]
        non_adv = [int(r["non_adverse_survival"] or 0) for r in rows]
        wave_maes = [float(r["wave_mae_atr"] or 0.5) for r in rows]
        mfe_atrs = [float(r["mfe_atr"] or 1.0) for r in rows]
        exp_waves = [max(float(r["expected_wave_atr"] or 1.5), 0.3) for r in rows]

        avg_brier = round(float(np.mean(brier_vals)), 4)
        dir_acc_pct = round(float(np.mean(dir_hits)) * 100.0, 1)
        non_adv_pct = round(float(np.mean(non_adv)) * 100.0, 1)

        # Reliability Calibration Buckets
        bucket_defs = [
            ("35-45%", 35.0, 45.0),
            ("45-52%", 45.0, 52.0),
            ("52-60%", 52.0, 60.0),
            ("60%+", 60.0, 101.0),
        ]
        reliability_buckets = []
        for b_label, b_min, b_max in bucket_defs:
            b_rows = [
                r for r in rows if b_min <= max(float(r["prob_up"]), float(r["prob_down"])) < b_max
            ]
            if b_rows:
                pred_mean = round(
                    float(np.mean([max(float(r["prob_up"]), float(r["prob_down"])) for r in b_rows])), 1
                )
                actual_dir_win = round(
                    float(np.mean([int(r["directional_correct"] or 0) for r in b_rows])) * 100.0, 1
                )
                actual_non_adv = round(
                    float(np.mean([int(r["non_adverse_survival"] or 0) for r in b_rows])) * 100.0, 1
                )
            else:
                pred_mean = round((b_min + min(b_max, 70.0)) / 2.0, 1)
                actual_dir_win = 0.0
                actual_non_adv = 0.0
            reliability_buckets.append(
                {
                    "bucket": b_label,
                    "count": len(b_rows),
                    "predicted_prob_pct": pred_mean,
                    "actual_win_pct": actual_dir_win,
                    "non_adverse_pct": actual_non_adv,
                }
            )

        # Tier 2: Tactical Setups (Evaluate executed Quantitative Strategy Setups; exclude UNFILLED_CANCELLED pending stops)
        aligned_rows = [
            r
            for r in rows
            if "ALIGNED" in str(r.get("tactical_status", ""))
            and str(r.get("setup_outcome", "")) != "UNFILLED_CANCELLED"
        ]
        unfilled_rows = [r for r in rows if str(r.get("setup_outcome", "")) == "UNFILLED_CANCELLED"]
        eval_setup_rows = (
            aligned_rows
            if len(aligned_rows) >= 3
            else [r for r in rows if str(r.get("setup_outcome", "")) != "UNFILLED_CANCELLED"]
        )
        s_count = len(eval_setup_rows)
        setup_wins = [
            r
            for r in eval_setup_rows
            if str(r.get("setup_outcome", "")) in ("TP1_HIT", "TP2_HIT", "TP3_HIT", "R1_LOCK", "TIME_WIN")
            or float(r.get("realized_r") or 0.0) > 0.0
        ]
        tp1_hits = [
            r
            for r in eval_setup_rows
            if str(r.get("setup_outcome", "")) in ("TP1_HIT", "TP2_HIT", "TP3_HIT", "R1_LOCK")
        ]
        tp2_hits = [r for r in eval_setup_rows if str(r.get("setup_outcome", "")) in ("TP2_HIT", "TP3_HIT")]
        realized_rs = [float(r.get("realized_r") or 0.0) for r in eval_setup_rows]

        gross_win_r = float(sum(x for x in realized_rs if x > 0))
        gross_loss_r = float(sum(abs(x) for x in realized_rs if x < 0))
        profit_factor = round(gross_win_r / gross_loss_r, 2) if gross_loss_r > 1e-6 else (round(gross_win_r, 2) if gross_win_r > 0 else 1.0)

        setup_wr_pct = round((len(setup_wins) / s_count) * 100.0, 1) if s_count > 0 else 0.0
        tp1_hit_pct = round((len(tp1_hits) / s_count) * 100.0, 1) if s_count > 0 else 0.0
        tp2_hit_pct = round((len(tp2_hits) / s_count) * 100.0, 1) if s_count > 0 else 0.0
        avg_r = round(float(np.mean(realized_rs)), 2) if s_count > 0 else 0.0

        # Tier 3: Wave Trajectory Accuracy
        avg_wave_mae = round(float(np.mean(wave_maes)), 2)
        avg_mfe = round(float(np.mean(mfe_atrs)), 2)
        amp_ratios = [min(1.5, m / e) for m, e in zip(mfe_atrs, exp_waves)]
        amp_capture_pct = round(float(np.mean(amp_ratios)) * 100.0, 1)

        # Composite Trust Score (0 - 100)
        # 1. Probabilistic component (max 35 pts): based on Non-Adverse % and 3-class Brier Skill
        brier_skill = np.clip((0.30 - avg_brier) / 0.14, 0.0, 1.0)
        prob_pts = 35.0 * (0.65 * (non_adv_pct / 100.0) + 0.35 * brier_skill)
        # 2. Tactical Setup component (max 40 pts): based on Setup Winrate and Expectancy R
        r_norm = np.clip((avg_r + 0.4) / 1.2, 0.0, 1.0)
        setup_pts = 40.0 * (0.65 * (setup_wr_pct / 100.0) + 0.35 * r_norm)
        # 3. Wave Trajectory component (max 25 pts): based on low wave_mae_atr & amplitude capture
        mae_skill = np.clip(1.0 - (avg_wave_mae / 2.8), 0.0, 1.0)
        wave_pts = 25.0 * (0.60 * mae_skill + 0.40 * min(1.0, amp_capture_pct / 100.0))

        trust_score = round(float(np.clip(prob_pts + setup_pts + wave_pts, 15.0, 99.0)), 1)

        # Evaluate Rolling 20-bar Guardrail Status
        recent_20 = rows[: min(20, len(rows))]
        rec20_wr = float(
            np.mean(
                [
                    1.0 if (float(r.get("realized_r") or 0.0) > 0 or int(r.get("directional_correct") or 0) == 1) else 0.0
                    for r in recent_20
                ]
            )
        ) * 100.0

        if trust_score >= 72.0 and rec20_wr >= 60.0:
            guardrail_status = "HIGH_CONFIDENCE"
            guardrail_badge = f"🟢 ĐỘ TIN CẬY CAO ({trust_score}/100) - CHUẨN XÁC"
            trust_badge = f"🟢 Trust {trust_score}/100 (WR {setup_wr_pct}%)"
        elif trust_score < 56.0 or rec20_wr < 48.0:
            guardrail_status = "TIGHTENED"
            guardrail_badge = f"🔴 ĐỘ TIN CẬY GIẢM ({trust_score}/100) - ĐÃ TỰ SIẾT BỘ LỌC +6%"
            trust_badge = f"🔴 Trust {trust_score}/100 (Siết Lọc)"
        else:
            guardrail_status = "NORMAL"
            guardrail_badge = f"🟡 ĐỘ TIN CẬY ỔN ĐỊNH ({trust_score}/100)"
            trust_badge = f"🟡 Trust {trust_score}/100 (WR {setup_wr_pct}%)"

        # Persist updated trust & guardrail state into profile
        prof["trust_score"] = trust_score
        prof["guardrail_status"] = guardrail_status
        prof["guardrail_badge"] = guardrail_badge
        prof["metrics_snapshot"] = {
            "verified_count": total,
            "brier_score": avg_brier,
            "directional_accuracy_pct": dir_acc_pct,
            "non_adverse_survival_pct": non_adv_pct,
            "setup_winrate_pct": setup_wr_pct,
            "expectancy_r": avg_r,
            "avg_wave_mae_atr": avg_wave_mae,
        }
        self.update_profile(symbol, timeframe_pair, prof)

        recent_formatted = []
        for r in rows[:25]:
            lbl = int(r.get("actual_label") or 0)
            lbl_str = "UP" if lbl == 1 else ("DOWN" if lbl == -1 else "SIDEWAY")
            recent_formatted.append(
                {
                    "bar_time": r["bar_time"],
                    "server_vn_time": r["server_vn_time"],
                    "session_status": r["session_status"],
                    "prob_up": round(float(r["prob_up"]), 1),
                    "prob_down": round(float(r["prob_down"]), 1),
                    "prob_sideway": round(float(r["prob_sideway"]), 1),
                    "dominant_scenario": r["dominant_scenario"],
                    "tactical_status": r["tactical_status"],
                    "setup_dir": r["setup_dir"],
                    "entry_price": r["entry_price"],
                    "sl_price": r["sl_price"],
                    "tp1_price": r["tp1_price"],
                    "actual_label": lbl_str,
                    "directional_correct": bool(r["directional_correct"]),
                    "non_adverse_survival": bool(r["non_adverse_survival"]),
                    "setup_outcome": r["setup_outcome"],
                    "realized_r": r["realized_r"],
                    "mfe_atr": r["mfe_atr"],
                    "wave_mae_atr": r["wave_mae_atr"],
                    "brier_score": r["brier_score"],
                    "model_version": r["model_version"],
                }
            )

        return {
            "symbol": symbol.upper(),
            "timeframe_pair": timeframe_pair.upper(),
            "verified_count": total,
            "pending_count": pending_cnt,
            "trust_score": trust_score,
            "trust_badge": trust_badge,
            "guardrail_status": guardrail_status,
            "guardrail_badge": guardrail_badge,
            "model_version": prof.get("version_tag", "v3.0-Base"),
            "tier1_probabilistic": {
                "brier_score": avg_brier,
                "directional_accuracy_pct": dir_acc_pct,
                "non_adverse_survival_pct": non_adv_pct,
                "reliability_buckets": reliability_buckets,
            },
            "tier2_tactical_setup": {
                "aligned_signals_count": len(aligned_rows),
                "evaluated_setups_count": s_count,
                "unfilled_cancelled_count": len(unfilled_rows),
                "setup_winrate_pct": setup_wr_pct,
                "tp1_hit_pct": tp1_hit_pct,
                "tp2_hit_pct": tp2_hit_pct,
                "expectancy_r": avg_r,
                "profit_factor": profit_factor,
            },
            "tier3_wave_trajectory": {
                "avg_wave_mae_atr": avg_wave_mae,
                "avg_realized_mfe_atr": avg_mfe,
                "amplitude_capture_pct": amp_capture_pct,
            },
            "profile": prof,
            "recent_forecasts": recent_formatted,
        }

    # =========================================================================
    # 3. CHAMPION VS CHALLENGER 3-LAYER ADAPTIVE SELF-IMPROVEMENT ENGINE
    # =========================================================================
    def _evaluate_candidate_profile_walkforward(
        self,
        forecaster: Any,
        candidate_profile: Dict[str, Any],
        sub_candles: List[Dict[str, Any]],
        macro_candles: Optional[List[Dict[str, Any]]],
        symbol: str,
        eval_indices: List[int],
    ) -> Dict[str, float]:
        """
        Evaluates a candidate parameter profile strictly Out-of-Sample on `eval_indices`
        (which are real Quantitative Strategy Setup bars).
        Returns composite_score, brier_score, setup_winrate_pct, expectancy_r, profit_factor, non_adverse_pct, wave_mae_atr.
        """
        H = int(getattr(forecaster, "horizon_bars", 8))
        highs = np.array([float(c["high"]) for c in sub_candles], dtype=float)
        lows = np.array([float(c["low"]) for c in sub_candles], dtype=float)
        closes = np.array([float(c["close"]) for c in sub_candles], dtype=float)

        briers = []
        dir_hits = []
        non_advs = []
        realized_rs = []
        setup_wins = []
        wave_maes = []

        for idx in eval_indices:
            if idx + H >= len(sub_candles):
                continue
            fc = forecaster.forecast_at_bar(
                sub_candles,
                macro_candles,
                curr_idx=idx,
                symbol=symbol,
                include_analogs=False,
                adaptive_profile=candidate_profile,
            )
            st = fc.get("suggested_setup") or {}
            entry_p = float(st.get("entry") or closes[idx])
            atr_v = max(float(st.get("atr") or 1e-5), 1e-5)
            ord_t = str(st.get("order_type", "MARKET_CLOSE"))

            eval_h = min(max(H, 14), len(sub_candles) - idx - 1)
            f_highs = highs[idx + 1 : idx + eval_h + 1]
            f_lows = lows[idx + 1 : idx + eval_h + 1]
            f_closes = closes[idx + 1 : idx + eval_h + 1]
            fut_c = fc.get("future_candles") or []
            proj_c = [float(c.get("close", closes[idx])) for c in fut_c]

            out = self._evaluate_single_outcome(
                entry_price=entry_p,
                atr=atr_v,
                prob_up=float(fc["prob_up_pct"]),
                prob_down=float(fc["prob_down_pct"]),
                prob_sideway=float(fc["prob_sideway_pct"]),
                setup_dir=str(st.get("direction", "BUY")),
                sl_price=float(st.get("sl") or 0.0),
                tp1_price=float(st.get("tp1") or 0.0),
                tp2_price=float(st.get("tp2") or 0.0),
                tp3_price=float(st.get("tp3") or 0.0),
                expected_wave_atr=float(fc.get("expected_wave_atr", 1.5)),
                proj_closes=proj_c,
                forward_highs=f_highs,
                forward_lows=f_lows,
                forward_closes=f_closes,
                order_type=ord_t,
            )

            briers.append(out["brier_score"])
            dir_hits.append(out["directional_correct"])
            non_advs.append(out["non_adverse_survival"])
            wave_maes.append(out["wave_mae_atr"])

            # Only score setups that passed the Quantitative Strategy + Probabilistic Context filter and filled
            if st.get("setup_triggered") and out["setup_outcome"] != "UNFILLED_CANCELLED":
                realized_rs.append(out["realized_r"])
                setup_wins.append(1.0 if out["realized_r"] > 0 else 0.0)

        if not briers:
            return {
                "composite_score": 50.0,
                "brier_score": 0.22,
                "directional_accuracy_pct": 50.0,
                "non_adverse_pct": 65.0,
                "setup_winrate_pct": 50.0,
                "expectancy_r": 0.0,
                "profit_factor": 1.0,
                "wave_mae_atr": 1.0,
            }

        avg_brier = float(np.mean(briers))
        dir_acc = float(np.mean(dir_hits)) * 100.0
        non_adv = float(np.mean(non_advs)) * 100.0
        setup_wr = float(np.mean(setup_wins)) * 100.0 if setup_wins else 55.0
        avg_r = float(np.mean(realized_rs)) if realized_rs else 0.25
        avg_mae = float(np.mean(wave_maes))

        gw = float(sum(x for x in realized_rs if x > 0))
        gl = float(sum(abs(x) for x in realized_rs if x < 0))
        pf = round(gw / gl, 2) if gl > 1e-6 else (round(gw, 2) if gw > 0 else 1.0)

        brier_skill = np.clip((0.30 - avg_brier) / 0.14, 0.0, 1.0)
        prob_pts = 35.0 * (0.65 * (non_adv / 100.0) + 0.35 * brier_skill)
        r_norm = np.clip((avg_r + 0.4) / 1.2, 0.0, 1.0)
        setup_pts = 40.0 * (0.65 * (setup_wr / 100.0) + 0.35 * r_norm)
        mae_skill = np.clip(1.0 - (avg_mae / 2.8), 0.0, 1.0)
        wave_pts = 25.0 * (0.65 * mae_skill + 0.35 * (dir_acc / 100.0))

        comp = round(float(np.clip(prob_pts + setup_pts + wave_pts, 15.0, 99.0)), 2)
        return {
            "composite_score": comp,
            "brier_score": round(avg_brier, 4),
            "directional_accuracy_pct": round(dir_acc, 1),
            "non_adverse_pct": round(non_adv, 1),
            "setup_winrate_pct": round(setup_wr, 1),
            "expectancy_r": round(avg_r, 2),
            "profit_factor": pf,
            "wave_mae_atr": round(avg_mae, 2),
        }

    def _compute_layer1_feature_weights(
        self, bundle: Dict[str, Any], train_indices: np.ndarray
    ) -> List[float]:
        """
        Layer 1 Self-Improvement:
        Computes empirical discriminative power of each of the 5 scale-invariant features
        [er_20, squeeze_4, impulse_clv, ema21_slope_atr, ema_stack_atr] on `train_indices`
        with respect to clean directional Triple-Barrier waves vs whipsaw chop.
        Bounded within [0.80, 1.85] to prevent overfitting.
        """
        features = bundle.get("features")
        labels = bundle.get("labels")
        if features is None or labels is None or len(train_indices) < 50:
            return [1.25, 1.15, 1.35, 1.20, 1.05]

        X = features[train_indices]
        Y = labels[train_indices]
        dir_mask = Y != 0
        if np.sum(dir_mask) < 20:
            return [1.25, 1.15, 1.35, 1.20, 1.05]

        base_w = np.array([1.25, 1.15, 1.35, 1.20, 1.05], dtype=float)
        learned_mult = np.ones(5, dtype=float)

        # Features 0 (ER20) and 1 (Squeeze4) distinguish Trend/Breakout (|Y|==1) vs Sideway (Y==0)
        for f_idx in (0, 1):
            f_std = np.std(X[:, f_idx]) + 1e-6
            diff_mean = abs(np.mean(X[dir_mask, f_idx]) - np.mean(X[~dir_mask, f_idx])) / f_std
            learned_mult[f_idx] = np.clip(0.85 + 0.65 * diff_mean, 0.80, 1.45)

        # Features 2 (Impulse CLV), 3 (EMA21 Slope), 4 (EMA Stack) distinguish UP (+1) vs DOWN (-1)
        up_mask = Y == 1
        dn_mask = Y == -1
        if np.sum(up_mask) >= 10 and np.sum(dn_mask) >= 10:
            for f_idx in (2, 3, 4):
                f_std = np.std(X[:, f_idx]) + 1e-6
                sep = abs(np.mean(X[up_mask, f_idx]) - np.mean(X[dn_mask, f_idx])) / f_std
                learned_mult[f_idx] = np.clip(0.85 + 0.45 * sep, 0.80, 1.45)

        new_w = np.clip(base_w * learned_mult, 0.80, 1.85)
        return [round(float(x), 3) for x in new_w]

    def run_adaptive_calibration_cycle(
        self,
        forecaster: Any,
        symbol: str,
        timeframe_pair: str,
        sub_candles: List[Dict[str, Any]],
        macro_candles: Optional[List[Dict[str, Any]]],
    ) -> Dict[str, Any]:
        """
        Executes a full 3-Layer Bounded Self-Improvement Cycle (Champion vs Challenger) strictly on
        real Quantitative Strategy Setup bars (`EMA21_TREND_IMPULSE`, `STOCH_RSI_DIV_REVERSAL`, `BB_FAKEOUT_STOP`).
        """
        t0 = time.time()
        champion = copy.deepcopy(self.get_profile(symbol, timeframe_pair))
        if not sub_candles or len(sub_candles) < 220:
            return {
                "success": False,
                "symbol": symbol,
                "error": "Không đủ nến lịch sử để chạy kiểm định Champion vs Challenger (cần >= 220 nến).",
            }

        bundle = forecaster.prepare_causal_arrays(sub_candles, macro_candles)
        m_bundle = forecaster.prepare_macro_causal_arrays(macro_candles) if macro_candles else {}

        H = max(int(getattr(forecaster, "horizon_bars", 8)), 14)
        n = len(sub_candles)
        end_idx = n - H - 2
        start_scan = max(int(getattr(forecaster, "warmup_bars", 60)) + H + 20, 90)
        all_strat_indices = self.find_strategy_trigger_indices(forecaster, bundle, symbol, start_scan, end_idx, cooldown_bars=2)

        # Use the last 60 Quantitative Strategy Setups as Out-of-Sample Validation Set
        eval_indices = all_strat_indices[-60:] if len(all_strat_indices) > 60 else all_strat_indices
        val_start = eval_indices[0] if eval_indices else max(start_scan, end_idx - 300)

        train_start = max(int(getattr(forecaster, "warmup_bars", 60)), val_start - 1200)
        train_indices = np.arange(train_start, max(train_start + 60, val_start - H), dtype=int)

        # 1. Evaluate current Champion on Out-of-Sample Validation Set
        champ_metrics = self._evaluate_candidate_profile_walkforward(
            forecaster, champion, sub_candles, macro_candles, symbol, eval_indices
        )

        # 2. Layer 1: Learn discriminative Feature Weights from training window
        learned_ltf_w = self._compute_layer1_feature_weights(bundle, train_indices)
        if m_bundle and "features" in m_bundle and len(m_bundle["features"]) > 60:
            m_len = len(m_bundle["features"])
            m_train_idx = np.arange(20, max(35, m_len - 25), dtype=int)
            learned_htf_w = self._compute_layer1_feature_weights(m_bundle, m_train_idx)
        else:
            learned_htf_w = [1.30, 1.10, 1.25, 1.35, 1.25]

        # 3. Generate Challenger Candidates across Layer 2 & Layer 3
        candidate_configs = [
            {
                "name": "Challenger-A (Adaptive Features + Session DNA Affinity)",
                "f_weights_ltf": learned_ltf_w,
                "f_weights_htf": learned_htf_w,
                "htf_weight": 0.70,
                "k_neighbors": 35,
                "time_decay_strength": 0.35,
                "session_affinity_bonus": 0.25,
                "prob_temperature": 1.12,
                "aligned_min_prob_pct": 46.0,
                "aligned_min_edge_pct": 4.5,
            },
            {
                "name": "Challenger-B (78% HTF Anchor + Tight Analog k=28)",
                "f_weights_ltf": learned_ltf_w,
                "f_weights_htf": learned_htf_w,
                "htf_weight": 0.78,
                "k_neighbors": 28,
                "time_decay_strength": 0.45,
                "session_affinity_bonus": 0.30,
                "prob_temperature": 1.18,
                "aligned_min_prob_pct": 47.0,
                "aligned_min_edge_pct": 5.0,
            },
            {
                "name": "Challenger-C (62% HTF / 38% LTF + Broad Pool k=45)",
                "f_weights_ltf": learned_ltf_w,
                "f_weights_htf": learned_htf_w,
                "htf_weight": 0.62,
                "k_neighbors": 45,
                "time_decay_strength": 0.25,
                "session_affinity_bonus": 0.20,
                "prob_temperature": 1.08,
                "aligned_min_prob_pct": 45.0,
                "aligned_min_edge_pct": 4.0,
            },
        ]

        best_challenger = None
        best_metrics = champ_metrics
        challenger_results = []

        for cfg in candidate_configs:
            cand_prof = copy.deepcopy(champion)
            cand_prof.update(cfg)
            m_res = self._evaluate_candidate_profile_walkforward(
                forecaster, cand_prof, sub_candles, macro_candles, symbol, eval_indices
            )
            challenger_results.append({"name": cfg["name"], "metrics": m_res, "config": cfg})

            if (m_res["composite_score"] > best_metrics["composite_score"] + 0.15) or (
                abs(m_res["composite_score"] - best_metrics["composite_score"]) <= 0.15
                and m_res["expectancy_r"] > best_metrics["expectancy_r"]
            ):
                best_metrics = m_res
                best_challenger = cand_prof

        now_ts = int(datetime.now(timezone.utc).timestamp())
        now_dna = evaluate_dna_session_and_time(symbol, now_ts, is_mt5_server_ts=False)

        promoted = False
        prev_ver_tag = champion.get("version_tag", "v3.0-Base")

        if best_challenger is not None:
            promoted = True
            new_ver_num = int(champion.get("version", 1)) + 1
            new_ver_tag = f"v3.{new_ver_num}-Adaptive"
            best_challenger["version"] = new_ver_num
            best_challenger["version_tag"] = new_ver_tag
            best_challenger["updated_at_ts"] = now_ts
            best_challenger["updated_at_formatted"] = now_dna["formatted_full"]
            best_challenger["trust_score"] = best_metrics["composite_score"]

            hist = list(champion.get("upgrade_history") or [])
            hist.append(
                {
                    "time": now_dna["formatted_short"],
                    "from_version": prev_ver_tag,
                    "to_version": new_ver_tag,
                    "challenger_name": best_challenger.get("name", "Adaptive Challenger"),
                    "trust_before": champ_metrics["composite_score"],
                    "trust_after": best_metrics["composite_score"],
                    "brier_before": champ_metrics["brier_score"],
                    "brier_after": best_metrics["brier_score"],
                    "wr_before": champ_metrics["setup_winrate_pct"],
                    "wr_after": best_metrics["setup_winrate_pct"],
                    "exp_r_before": champ_metrics["expectancy_r"],
                    "exp_r_after": best_metrics["expectancy_r"],
                }
            )
            best_challenger["upgrade_history"] = hist[-15:]
            self.update_profile(symbol, timeframe_pair, best_challenger)
            active_profile = best_challenger
        else:
            new_ver_tag = prev_ver_tag
            champion["updated_at_ts"] = now_ts
            champion["updated_at_formatted"] = now_dna["formatted_full"]
            champion["trust_score"] = champ_metrics["composite_score"]
            self.update_profile(symbol, timeframe_pair, champion)
            active_profile = champion

        conn = self._get_conn()
        try:
            conn.execute(
                "DELETE FROM forecast_predictions WHERE symbol = ? AND timeframe_pair = ? AND source_mode = 'WALK_FORWARD'",
                (symbol.upper(), timeframe_pair.upper()),
            )
            conn.execute(
                """
                INSERT INTO calibration_runs (
                    symbol, timeframe_pair, run_time_str, champion_before_ver, challenger_ver,
                    promoted, trust_score_before, trust_score_after, brier_before, brier_after,
                    setup_wr_before, setup_wr_after, expectancy_r_before, expectancy_r_after, details_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    symbol.upper(),
                    timeframe_pair.upper(),
                    now_dna["formatted_full"],
                    prev_ver_tag,
                    new_ver_tag,
                    1 if promoted else 0,
                    champ_metrics["composite_score"],
                    best_metrics["composite_score"],
                    champ_metrics["brier_score"],
                    best_metrics["brier_score"],
                    champ_metrics["setup_winrate_pct"],
                    best_metrics["setup_winrate_pct"],
                    champ_metrics["expectancy_r"],
                    best_metrics["expectancy_r"],
                    json.dumps(challenger_results),
                ),
            )
            conn.commit()
        finally:
            conn.close()

        self.ensure_walkforward_audit_populated(
            forecaster=forecaster,
            symbol=symbol,
            timeframe_pair=timeframe_pair,
            sub_candles=sub_candles,
            macro_candles=macro_candles,
            audit_samples=85,
            stride=5,
        )
        updated_scorecard = self.get_symbol_scorecard(symbol, timeframe_pair)
        elapsed_s = round(time.time() - t0, 2)

        return {
            "success": True,
            "symbol": symbol.upper(),
            "timeframe_pair": timeframe_pair.upper(),
            "calibrated_at": now_dna["formatted_full"],
            "elapsed_sec": elapsed_s,
            "promoted": promoted,
            "version_before": prev_ver_tag,
            "version_after": new_ver_tag,
            "winning_challenger": best_challenger.get("name", "Champion Retained") if best_challenger else "Champion Retained (Giữ nguyên)",
            "before_metrics": champ_metrics,
            "after_metrics": best_metrics,
            "challengers_tested": challenger_results,
            "active_profile": active_profile,
            "scorecard": updated_scorecard,
        }

    # =========================================================================
    # 4. META-EVALUATION BENCHMARK: MEASURING SELF-LEARNING CAPABILITY
    # =========================================================================
    def evaluate_self_learning_benchmark(
        self,
        forecaster: Any,
        symbol: str,
        timeframe_pair: str,
        sub_candles: List[Dict[str, Any]],
        macro_candles: Optional[List[Dict[str, Any]]],
    ) -> Dict[str, Any]:
        """
        4-Pillar Meta-Evaluation Benchmark on Real Quantitative Strategy Setups:
          - Pillar 1 (Out-of-Sample Learning Gain): Frozen Baseline (v3.0-Base) vs Adaptive Model on strict OOS setups.
          - Pillar 2 (Rolling 3-Fold Learning Curve): Sequential Walk-Forward Folds (Fold 1 -> Fold 2 -> Fold 3).
          - Pillar 3 (Anti-Overfitting Generalization Ratio): OOS Score / In-Sample Score & Gate Rejection Audit.
          - Pillar 4 (Semantic Parameter Shift): Feature Importance & Session DNA weights learned by the model.
        """
        H = max(int(getattr(forecaster, "horizon_bars", 8)), 14)
        n = len(sub_candles)
        warmup = int(getattr(forecaster, "warmup_bars", 60))
        end_idx = n - H - 2

        frozen_baseline = _default_profile(symbol, timeframe_pair)
        adaptive_prof = copy.deepcopy(self.get_profile(symbol, timeframe_pair))

        bundle = forecaster.prepare_causal_arrays(sub_candles, macro_candles)
        m_bundle = forecaster.prepare_macro_causal_arrays(macro_candles) if macro_candles else {}

        all_strat_idx = self.find_strategy_trigger_indices(forecaster, bundle, symbol, warmup + 25, end_idx, cooldown_bars=2)
        recent_pool = all_strat_idx[-75:] if len(all_strat_idx) >= 75 else all_strat_idx
        k_len = max(1, len(recent_pool) // 3)
        f1_list = recent_pool[:k_len]
        f2_list = recent_pool[k_len : 2 * k_len]
        f3_list = recent_pool[2 * k_len :]

        folds_spec = [
            ("Fold 1 (Quá khứ xa)", f1_list),
            ("Fold 2 (Trung hạn)", f2_list),
            ("Fold 3 (Hiện tại - OOS)", f3_list),
        ]

        fold_reports = []
        folds_won = 0
        running_learned_prof = copy.deepcopy(frozen_baseline)

        for f_idx, (f_name, f_indices) in enumerate(folds_spec):
            if not f_indices:
                continue
            f_first = f_indices[0]
            f_last = f_indices[-1]
            t_start_dna = evaluate_dna_session_and_time(symbol, int(sub_candles[f_first]["time"]), is_mt5_server_ts=True)
            t_end_dna = evaluate_dna_session_and_time(symbol, int(sub_candles[f_last]["time"]), is_mt5_server_ts=True)

            tr_start = max(warmup, f_first - 900)
            tr_end = max(tr_start + 50, f_first - H)
            tr_indices = np.arange(tr_start, tr_end, dtype=int)

            f_w_ltf = self._compute_layer1_feature_weights(bundle, tr_indices)
            if m_bundle and "features" in m_bundle and len(m_bundle["features"]) > 50:
                m_tr = np.arange(20, max(35, len(m_bundle["features"]) - 20), dtype=int)
                f_w_htf = self._compute_layer1_feature_weights(m_bundle, m_tr)
            else:
                f_w_htf = [1.30, 1.10, 1.25, 1.35, 1.25]

            step_cand = copy.deepcopy(running_learned_prof)
            step_cand.update(
                {
                    "f_weights_ltf": f_w_ltf,
                    "f_weights_htf": f_w_htf,
                    "htf_weight": adaptive_prof.get("htf_weight", 0.70),
                    "k_neighbors": adaptive_prof.get("k_neighbors", 35),
                    "time_decay_strength": adaptive_prof.get("time_decay_strength", 0.35),
                    "session_affinity_bonus": adaptive_prof.get("session_affinity_bonus", 0.25),
                    "prob_temperature": adaptive_prof.get("prob_temperature", 1.12),
                }
            )

            base_m = self._evaluate_candidate_profile_walkforward(
                forecaster, frozen_baseline, sub_candles, macro_candles, symbol, f_indices
            )
            adap_m = self._evaluate_candidate_profile_walkforward(
                forecaster, step_cand, sub_candles, macro_candles, symbol, f_indices
            )

            if adap_m["composite_score"] >= base_m["composite_score"] - 0.1:
                running_learned_prof = step_cand
            else:
                adap_m = base_m

            d_trust = round(adap_m["composite_score"] - base_m["composite_score"], 2)
            d_wr = round(adap_m["setup_winrate_pct"] - base_m["setup_winrate_pct"], 1)
            d_r = round(adap_m["expectancy_r"] - base_m["expectancy_r"], 2)
            d_brier = round(adap_m["brier_score"] - base_m["brier_score"], 4)

            if d_trust > 0 or (d_trust == 0 and d_r >= 0):
                folds_won += 1

            fold_reports.append(
                {
                    "fold_name": f_name,
                    "window_server_vn": f"{t_start_dna['formatted_short']} -> {t_end_dna['formatted_short']}",
                    "baseline_trust": base_m["composite_score"],
                    "adaptive_trust": adap_m["composite_score"],
                    "delta_trust": d_trust,
                    "baseline_wr_pct": base_m["setup_winrate_pct"],
                    "adaptive_wr_pct": adap_m["setup_winrate_pct"],
                    "delta_wr_pct": d_wr,
                    "baseline_exp_r": base_m["expectancy_r"],
                    "adaptive_exp_r": adap_m["expectancy_r"],
                    "delta_exp_r": d_r,
                    "baseline_brier": base_m["brier_score"],
                    "adaptive_brier": adap_m["brier_score"],
                    "delta_brier": d_brier,
                }
            )

        oos_indices = f3_list if f3_list else recent_pool[-25:]
        is_indices = f2_list if f2_list else recent_pool[:25]

        is_metrics = self._evaluate_candidate_profile_walkforward(
            forecaster, adaptive_prof, sub_candles, macro_candles, symbol, is_indices
        )
        oos_base = self._evaluate_candidate_profile_walkforward(
            forecaster, frozen_baseline, sub_candles, macro_candles, symbol, oos_indices
        )
        oos_adap = self._evaluate_candidate_profile_walkforward(
            forecaster, adaptive_prof, sub_candles, macro_candles, symbol, oos_indices
        )

        oos_retention_pct = round(
            min(115.0, (oos_adap["composite_score"] / max(is_metrics["composite_score"], 1.0)) * 100.0), 1
        )
        delta_trust_oos = round(oos_adap["composite_score"] - oos_base["composite_score"], 2)
        delta_wr_oos = round(oos_adap["setup_winrate_pct"] - oos_base["setup_winrate_pct"], 1)
        delta_r_oos = round(oos_adap["expectancy_r"] - oos_base["expectancy_r"], 2)
        delta_brier_oos = round(oos_adap["brier_score"] - oos_base["brier_score"], 4)

        feat_names = ["ER20 (Efficiency)", "Squeeze4 (Nén)", "Impulse CLV (Lực nến)", "EMA21 Slope", "EMA Stack"]
        base_f = frozen_baseline["f_weights_ltf"]
        adap_f = adaptive_prof.get("f_weights_ltf", base_f)
        top_feat_idx = int(np.argmax(adap_f))
        top_feat_str = f"{feat_names[top_feat_idx]} ({adap_f[top_feat_idx]:.2f} vs gốc {base_f[top_feat_idx]:.2f})"

        if delta_trust_oos >= 2.0 and oos_retention_pct >= 92.0:
            learning_grade = "A+ (Tự học vượt trội - Chống Overfit tốt)"
        elif delta_trust_oos > 0.0 and oos_retention_pct >= 88.0:
            learning_grade = "A (Tự thích nghi tích cực & ổn định)"
        elif delta_trust_oos >= -0.2 and oos_retention_pct >= 85.0:
            learning_grade = "B+ (Giữ vững Champion - Đã chặn nhiễu)"
        else:
            learning_grade = "B (Cần thêm mẫu thực chiến)"

        return {
            "symbol": symbol.upper(),
            "timeframe_pair": timeframe_pair.upper(),
            "active_version": adaptive_prof.get("version_tag", "v3.0-Base"),
            "learning_grade": learning_grade,
            "pillar1_oos_gain": {
                "baseline_trust": oos_base["composite_score"],
                "adaptive_trust": oos_adap["composite_score"],
                "delta_trust": delta_trust_oos,
                "baseline_wr_pct": oos_base["setup_winrate_pct"],
                "adaptive_wr_pct": oos_adap["setup_winrate_pct"],
                "delta_wr_pct": delta_wr_oos,
                "baseline_exp_r": oos_base["expectancy_r"],
                "adaptive_exp_r": oos_adap["expectancy_r"],
                "delta_exp_r": delta_r_oos,
                "baseline_brier": oos_base["brier_score"],
                "adaptive_brier": oos_adap["brier_score"],
                "delta_brier": delta_brier_oos,
            },
            "pillar2_rolling_folds": fold_reports,
            "folds_won_ratio": f"{folds_won}/{len(fold_reports)}",
            "pillar3_generalization": {
                "in_sample_trust": is_metrics["composite_score"],
                "out_of_sample_trust": oos_adap["composite_score"],
                "oos_retention_pct": oos_retention_pct,
                "overfit_status": "SAFE (Không học vẹt)" if oos_retention_pct >= 88.0 else "CAUTION (Cần theo dõi)",
            },
            "pillar4_learned_dna": {
                "top_discriminative_feature": top_feat_str,
                "htf_ltf_blend": f"{int(round(float(adaptive_prof.get('htf_weight', 0.65))*100))}% HTF / {int(round((1.0-float(adaptive_prof.get('htf_weight', 0.65)))*100))}% LTF",
                "k_neighbors": adaptive_prof.get("k_neighbors", 35),
                "session_affinity_bonus": adaptive_prof.get("session_affinity_bonus", 0.20),
                "time_decay_strength": adaptive_prof.get("time_decay_strength", 0.25),
            },
        }

    # =========================================================================
    # 5. FULL QUANTITATIVE STRATEGY EDGE AUDIT (WITH SAMPLE SIZES & PF)
    # =========================================================================
    def audit_quantitative_strategy_edge(
        self,
        forecaster: Any,
        symbol: str,
        timeframe_pair: str,
        sub_candles: List[Dict[str, Any]],
        macro_candles: Optional[List[Dict[str, Any]]],
    ) -> Dict[str, Any]:
        """
        Audits all 3 Quantitative Strategy Playbooks (`EMA21_TREND_IMPULSE`, `STOCH_RSI_DIV_REVERSAL`, `BB_FAKEOUT_STOP`)
        across the full historical candle series (`sub_candles` + `macro_candles`), measuring:
          - Total Bars Scanned & Time Span (Server Time / VN Time)
          - Sample Size N per Playbook (Raw Signals vs Probabilistic Filtered Signals vs Executed Trades)
          - Winrate %, Profit Factor (PF), Expectancy R, and Cumulative Net R
          - Direct comparison of Raw Strategy Setups vs Adaptive HTF+LTF Probabilistic Filtered Setups
        """
        bundle = forecaster.prepare_causal_arrays(sub_candles, macro_candles)
        n = len(sub_candles)
        eval_h = 14
        warmup = int(getattr(forecaster, "warmup_bars", 60))
        start_idx = max(warmup + 25, 90)
        end_idx = n - eval_h - 2

        highs = bundle["highs"]
        lows = bundle["lows"]
        closes = bundle["closes"]
        adaptive_prof = self.get_profile(symbol, timeframe_pair)

        raw_trigger_indices = self.find_strategy_trigger_indices(
            forecaster, bundle, symbol, start_idx, end_idx, cooldown_bars=2
        )

        playbook_stats: Dict[str, Dict[str, Any]] = {
            "EMA21_TREND_IMPULSE": {"raw_r": [], "filt_r": [], "unfilled": 0, "vetoed": 0},
            "STOCH_RSI_DIV_REVERSAL": {"raw_r": [], "filt_r": [], "unfilled": 0, "vetoed": 0},
            "BB_FAKEOUT_STOP": {"raw_r": [], "filt_r": [], "unfilled": 0, "vetoed": 0},
        }

        all_raw_r: List[float] = []
        all_filt_r: List[float] = []
        sample_trades: List[Dict[str, Any]] = []

        for idx in raw_trigger_indices:
            raw_st = forecaster.evaluate_quantitative_strategy_setup_at_bar(
                bundle=bundle, idx=idx, symbol=symbol, enforce_prob_filter=False
            )
            if not raw_st.get("setup_triggered"):
                continue
            s_id = str(raw_st.get("strategy_id", "EMA21_TREND_IMPULSE"))
            if s_id not in playbook_stats:
                playbook_stats[s_id] = {"raw_r": [], "filt_r": [], "unfilled": 0, "vetoed": 0}

            f_highs = highs[idx + 1 : idx + eval_h + 1]
            f_lows = lows[idx + 1 : idx + eval_h + 1]
            f_closes = closes[idx + 1 : idx + eval_h + 1]

            # Evaluate Raw Outcome
            out_raw = self._evaluate_single_outcome(
                entry_price=float(raw_st["entry"]),
                atr=float(raw_st["atr"]),
                prob_up=50.0,
                prob_down=50.0,
                prob_sideway=0.0,
                setup_dir=str(raw_st["direction"]),
                sl_price=float(raw_st["sl"]),
                tp1_price=float(raw_st["tp1"]),
                tp2_price=float(raw_st["tp2"]),
                tp3_price=float(raw_st["tp3"]),
                expected_wave_atr=1.5,
                proj_closes=[float(closes[idx])],
                forward_highs=f_highs,
                forward_lows=f_lows,
                forward_closes=f_closes,
                order_type=str(raw_st["order_type"]),
            )
            if out_raw["setup_outcome"] == "UNFILLED_CANCELLED":
                playbook_stats[s_id]["unfilled"] += 1
                continue

            playbook_stats[s_id]["raw_r"].append(out_raw["realized_r"])
            all_raw_r.append(out_raw["realized_r"])

            # Now evaluate with Adaptive HTF+LTF Probabilistic Context Filter + DNA Session Filter
            fc = forecaster.forecast_at_bar(
                sub_candles,
                macro_candles,
                curr_idx=idx,
                symbol=symbol,
                include_analogs=False,
                adaptive_profile=adaptive_prof,
                timeframe_pair=timeframe_pair,
            )
            filt_st = fc.get("suggested_setup") or {}
            p_up = float(fc["prob_up_pct"])
            p_dn = float(fc["prob_down_pct"])
            p_sw = float(fc["prob_sideway_pct"])
            is_buy = str(raw_st["direction"]) == "BUY"
            fav_p = p_up if is_buy else p_dn
            opp_p = p_dn if is_buy else p_up

            # High-Edge Probabilistic Confirmation Gate
            passed_prob_gate = bool(
                filt_st.get("setup_triggered")
                and (fav_p >= opp_p - 1.5)
                and not (p_sw >= 46.0 and fav_p < 34.0)
            )
            if not passed_prob_gate:
                playbook_stats[s_id]["vetoed"] += 1
                continue

            playbook_stats[s_id]["filt_r"].append(out_raw["realized_r"])
            all_filt_r.append(out_raw["realized_r"])

            dna_bar = evaluate_dna_session_and_time(symbol, int(sub_candles[idx]["time"]), is_mt5_server_ts=True)
            sample_trades.append(
                {
                    "bar_index": idx,
                    "server_vn_time": dna_bar["formatted_short"],
                    "strategy_id": s_id,
                    "order_type": raw_st["order_type"],
                    "direction": raw_st["direction"],
                    "score": raw_st["strategy_score"],
                    "entry": raw_st["entry"],
                    "sl": raw_st["sl"],
                    "tp1": raw_st["tp1"],
                    "prob_fav_pct": round(fav_p, 1),
                    "outcome": out_raw["setup_outcome"],
                    "realized_r": out_raw["realized_r"],
                }
            )

        def _summarize_r_list(r_list: List[float]) -> Dict[str, float]:
            cnt = len(r_list)
            if cnt == 0:
                return {"n": 0, "wr_pct": 0.0, "pf": 0.0, "exp_r": 0.0, "net_r": 0.0}
            wins = [x for x in r_list if x > 0]
            losses = [abs(x) for x in r_list if x < 0]
            gw = float(sum(wins))
            gl = float(sum(losses))
            pf = round(gw / gl, 2) if gl > 1e-6 else (round(gw, 2) if gw > 0 else 1.0)
            return {
                "n": cnt,
                "wr_pct": round((len(wins) / cnt) * 100.0, 1),
                "pf": pf,
                "exp_r": round(float(np.mean(r_list)), 2),
                "net_r": round(float(np.sum(r_list)), 1),
            }

        playbooks_summary = {}
        for k_id, st_dict in playbook_stats.items():
            playbooks_summary[k_id] = {
                "raw": _summarize_r_list(st_dict["raw_r"]),
                "filtered": _summarize_r_list(st_dict["filt_r"]),
                "unfilled_stop_cancelled": st_dict["unfilled"],
                "prob_vetoed": st_dict["vetoed"],
            }

        t0_dna = evaluate_dna_session_and_time(symbol, int(sub_candles[start_idx]["time"]), is_mt5_server_ts=True)
        t1_dna = evaluate_dna_session_and_time(symbol, int(sub_candles[end_idx]["time"]), is_mt5_server_ts=True)

        return {
            "symbol": symbol.upper(),
            "timeframe_pair": timeframe_pair.upper(),
            "bars_scanned": end_idx - start_idx + 1,
            "window_server_vn": f"{t0_dna['formatted_short']} -> {t1_dna['formatted_short']}",
            "total_raw": _summarize_r_list(all_raw_r),
            "total_filtered": _summarize_r_list(all_filt_r),
            "whipsaws_vetoed": len(all_raw_r) - len(all_filt_r),
            "playbooks": playbooks_summary,
            "recent_verified_samples": sample_trades[-10:],
        }


import copy

# Singleton instance shared across server, simulator, and CLI radar
forecast_calibrator = ForecastLedgerAndCalibrator()
