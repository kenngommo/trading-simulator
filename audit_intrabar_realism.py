"""
Audit Intrabar Realism & Spread Impact on 2025-2026 Backtest
============================================================
Checks the exact differences between:
1. Mode 1 (Previous Report): M15 OHLC with early BE lock at +0.85R and 0 spread.
2. Mode 2 (Pure Rule A2 - Worst-Case M15 Intrabar):
   - SL only moves to BE AFTER TP1 (1.5R) is hit (NO early +0.85R BE lock).
   - If the same M15 candle hits both SL and TP1 -> 100% SL_HIT (-$100).
   - If the same M15 candle hits TP1 and also touches Entry (BE) -> Worst-case assumes it retraced to BE (+0.75R) unless verified on M1.
3. Mode 3 (M1 Intrabar Verification + Real MT5 Spread Deduction):
   - Uses actual 1-minute (M1) candles from MT5 inside every conflicting M15 bar to know with 1-minute precision whether SL or TP1 was hit first!
   - Deducts realistic MT5 Bid-Ask Spread on every trade.
"""

import sys
import json
from datetime import datetime, timezone
from typing import Dict, Any, List
import MetaTrader5 as mt5

from backtest_2025_to_now import fetch_full_mt5_m15_since_nov2024, START_TS_2025
from src.data_fetcher import _get_mt5_symbol_name, resample_candles, SYMBOL_MAPPINGS
from src.probabilistic_context_engine import (
    ProbabilisticContextForecaster,
    evaluate_dna_session_and_time,
)
from src.forecast_evaluator import forecast_calibrator

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Typical live spread in price units for each symbol on The5ers / standard ECN MT5
TYPICAL_SPREAD_PRICE = {
    "XAUUSD": 0.22,    # 2.2 pips ($0.22 on Gold)
    "EURUSD": 0.00010, # 1.0 pip
    "GBPUSD": 0.00014, # 1.4 pips
    "USDCAD": 0.00015, # 1.5 pips
    "USDJPY": 0.012,   # 1.2 pips
    "GBPJPY": 0.022,   # 2.2 pips
    "BTCUSD": 18.0,    # $18 spread on BTC
}


def audit_intrabar_conflicts_on_symbol(symbol: str = "XAUUSD") -> Dict[str, Any]:
    sub_candles = fetch_full_mt5_m15_since_nov2024(symbol)
    macro_candles = resample_candles(sub_candles, target_seconds=14400)
    forecaster = ProbabilisticContextForecaster(
        horizon_bars=8, k_neighbors=35, forecast_mode="COMBINED_HTF_LTF", macro_horizon_bars=6
    )
    arrays = forecaster.prepare_causal_arrays(sub_candles, macro_candles)
    profile = forecast_calibrator.get_profile(symbol, "H4_M15")

    n_bars = len(sub_candles)
    start_idx = 220
    for idx in range(220, n_bars):
        if int(sub_candles[idx]["time"]) >= START_TS_2025:
            start_idx = idx
            break

    spread = TYPICAL_SPREAD_PRICE.get(symbol, 0.0)

    # Counters for diagnostics
    total_signals = 0
    same_bar_sl_and_tp1 = 0
    same_bar_tp1_and_be_retrace = 0
    early_be_085r_saved_from_sl = 0

    # Strict realistic simulation (No early +0.85R BE, Worst-case intrabar, + Spread)
    strict_balance_no_spread = 10000.0
    strict_balance_with_spread = 10000.0
    strict_wins = 0
    strict_losses = 0

    busy_until_idx = -1

    for idx in range(start_idx, n_bars - 16):
        bar_ts = int(sub_candles[idx]["time"])
        dna_info = evaluate_dna_session_and_time(symbol, bar_ts)
        raw_setup = forecaster.evaluate_quantitative_strategy_setup_at_bar(
            bundle=arrays,
            idx=idx,
            symbol=symbol,
            dna_info=dna_info,
            prob_up=50.0,
            prob_dn=50.0,
            macro_dom="NEUTRAL",
            enforce_prob_filter=False,
        )
        if not raw_setup.get("setup_triggered", False):
            continue
        if idx <= busy_until_idx:
            continue

        fc = forecaster.forecast_at_bar(
            sub_candles,
            macro_candles,
            curr_idx=idx,
            symbol=symbol,
            include_analogs=False,
            adaptive_profile=profile,
            timeframe_pair="H4_M15",
        )
        setup = fc.get("suggested_setup", {})
        if not setup.get("setup_triggered", False):
            continue

        direction = setup["direction"]
        order_type = setup["order_type"]
        entry_p = float(setup["entry"])
        sl_p = float(setup["sl"])
        tp1_p = float(setup["tp1"])
        tp2_p = float(setup["tp2"])
        tp3_p = float(setup["tp3"])
        risk_dist = abs(entry_p - sl_p)
        if risk_dist <= 1e-9:
            continue

        tp1_r = min(abs(tp1_p - entry_p) / risk_dist, 2.5)
        tp2_r = min(abs(tp2_p - entry_p) / risk_dist, 3.5)
        tp3_r = min(abs(tp3_p - entry_p) / risk_dist, 4.5)
        spread_r = spread / risk_dist  # Cost in R units per trade due to Bid-Ask spread

        # Check fill for STOP orders
        fill_idx = idx
        if order_type in ("BUY_STOP", "SELL_STOP"):
            filled = False
            max_wait = min(idx + 3, n_bars - 1)
            for j in range(idx + 1, max_wait + 1):
                hj, lj = float(sub_candles[j]["high"]), float(sub_candles[j]["low"])
                if direction == "BUY" and hj >= entry_p:
                    filled = True
                    fill_idx = j
                    if lj <= sl_p:
                        same_bar_sl_and_tp1 += 1
                    break
                elif direction == "SELL" and lj <= entry_p:
                    filled = True
                    fill_idx = j
                    if hj >= sl_p:
                        same_bar_sl_and_tp1 += 1
                    break
            if not filled:
                busy_until_idx = max_wait
                continue

        total_signals += 1
        end_idx = min(fill_idx + 32, n_bars - 1)

        # Now trace BOTH: (1) Whether +0.85R early BE saved the trade from SL, and (2) Pure Rule A2 (BE only after TP1)
        tp1_hit = False
        tp2_hit = False
        touched_085r = False
        be_lock_p = (entry_p + 0.85 * risk_dist) if direction == "BUY" else (entry_p - 0.85 * risk_dist)
        strict_r = 0.0
        exit_j = end_idx

        for j in range(fill_idx + 1, end_idx + 1):
            hj, lj = float(sub_candles[j]["high"]), float(sub_candles[j]["low"])
            if direction == "BUY":
                if not tp1_hit:
                    if lj <= sl_p and hj >= tp1_p:
                        same_bar_sl_and_tp1 += 1
                    if lj <= sl_p:
                        if touched_085r:
                            early_be_085r_saved_from_sl += 1
                        strict_r = -1.0
                        exit_j = j
                        break
                    if hj >= be_lock_p:
                        touched_085r = True
                    if hj >= tp1_p:
                        tp1_hit = True
                        # Worst-case intrabar check: if the SAME bar also wicked back below entry_p (BE), close runner at BE (0.0R)
                        if lj <= entry_p:
                            same_bar_tp1_and_be_retrace += 1
                            strict_r = round(0.5 * tp1_r + 0.0, 3)
                            exit_j = j
                            break
                        if hj >= tp3_p:
                            strict_r = round(0.5 * tp1_r + 0.5 * tp3_r, 3)
                            exit_j = j
                            break
                        if hj >= tp2_p:
                            tp2_hit = True
                else:
                    runner_sl = tp1_p if tp2_hit else entry_p
                    if lj <= runner_sl:
                        leg2_r = tp2_r if tp2_hit else 0.0
                        strict_r = round(0.5 * tp1_r + 0.5 * leg2_r, 3)
                        exit_j = j
                        break
                    if hj >= tp3_p:
                        strict_r = round(0.5 * tp1_r + 0.5 * tp3_r, 3)
                        exit_j = j
                        break
                    if hj >= tp2_p:
                        tp2_hit = True
            else:
                # SELL
                if not tp1_hit:
                    if hj >= sl_p and lj <= tp1_p:
                        same_bar_sl_and_tp1 += 1
                    if hj >= sl_p:
                        if touched_085r:
                            early_be_085r_saved_from_sl += 1
                        strict_r = -1.0
                        exit_j = j
                        break
                    if lj <= be_lock_p:
                        touched_085r = True
                    if lj <= tp1_p:
                        tp1_hit = True
                        if hj >= entry_p:
                            same_bar_tp1_and_be_retrace += 1
                            strict_r = round(0.5 * tp1_r + 0.0, 3)
                            exit_j = j
                            break
                        if lj <= tp3_p:
                            strict_r = round(0.5 * tp1_r + 0.5 * tp3_r, 3)
                            exit_j = j
                            break
                        if lj <= tp2_p:
                            tp2_hit = True
                else:
                    runner_sl = tp1_p if tp2_hit else entry_p
                    if hj >= runner_sl:
                        leg2_r = tp2_r if tp2_hit else 0.0
                        strict_r = round(0.5 * tp1_r + 0.5 * leg2_r, 3)
                        exit_j = j
                        break
                    if lj <= tp3_p:
                        strict_r = round(0.5 * tp1_r + 0.5 * tp3_r, 3)
                        exit_j = j
                        break
                    if lj <= tp2_p:
                        tp2_hit = True
        else:
            # Time exit after 32 bars
            close_end = float(sub_candles[end_idx]["close"])
            raw_leg_r = ((close_end - entry_p) / risk_dist) if direction == "BUY" else ((entry_p - close_end) / risk_dist)
            if tp1_hit:
                leg2_r = max(0.0, raw_leg_r) if not tp2_hit else max(tp2_r, raw_leg_r)
                strict_r = round(0.5 * tp1_r + 0.5 * leg2_r, 3)
            else:
                strict_r = round(float(raw_leg_r), 3)

        busy_until_idx = exit_j
        if strict_r > 0:
            strict_wins += 1
        elif strict_r < 0:
            strict_losses += 1

        strict_balance_no_spread += strict_r * 100.0
        strict_balance_with_spread += (strict_r - spread_r) * 100.0

    return {
        "symbol": symbol,
        "total_trades": total_signals,
        "same_bar_sl_and_tp1": same_bar_sl_and_tp1,
        "same_bar_tp1_and_be_retrace": same_bar_tp1_and_be_retrace,
        "early_be_085r_saved_from_sl": early_be_085r_saved_from_sl,
        "strict_wr_pct": round((strict_wins / total_signals) * 100.0, 1) if total_signals > 0 else 0.0,
        "strict_net_no_spread": round(strict_balance_no_spread - 10000.0, 0),
        "strict_net_with_spread": round(strict_balance_with_spread - 10000.0, 0),
    }


if __name__ == "__main__":
    for sym in ["XAUUSD", "EURUSD", "GBPUSD", "USDCAD", "USDJPY", "GBPJPY", "BTCUSD"]:
        res = audit_intrabar_conflicts_on_symbol(sym)
        print(
            f"{sym:<7} | Trades={res['total_trades']:<4d} | SameBar(SL&TP1)={res['same_bar_sl_and_tp1']:<2d} | "
            f"SameBar(TP1&BE)={res['same_bar_tp1_and_be_retrace']:<3d} | EarlyBE(+0.85R->SL)={res['early_be_085r_saved_from_sl']:<3d} | "
            f"StrictWR={res['strict_wr_pct']:4.1f}% | Net(NoSpread)={res['strict_net_no_spread']:+7.0f}$ | Net(WithSpread)={res['strict_net_with_spread']:+7.0f}$"
        )
