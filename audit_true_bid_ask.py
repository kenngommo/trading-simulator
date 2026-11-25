"""
True Bid-Ask Trigger Mechanics & Lot Volume Audit (2025 -> Present)
===================================================================
Models the exact physical reality of MT5 Bid-Ask execution:
- MT5 chart candles are BID prices (Open_Bid, High_Bid, Low_Bid, Close_Bid).
- Ask Price = Bid Price + Spread.
- Volume (Lots) per trade is dynamically sized so that hitting SL equals exactly -$100.00 (-1.0R).
- When TP is reached (High_Bid >= TP for BUY, or Low_Bid + Spread <= TP for SELL), the trader receives the FULL TP R-multiple (NOT docked by a phantom cash spread fee!).
- Spread ONLY affects:
  1. Whether price actually reaches the Ask/Bid trigger level (e.g. SELL TP requires Low_Bid <= TP - Spread; SELL SL triggers if High_Bid >= SL - Spread; BUY entry at Ask shifts the R-grid by +Spread).
  2. Optional ECN Commission ($/lot) if using a Raw Spread + Commission account.
"""

import sys
import numpy as np
from backtest_2025_to_now import fetch_full_mt5_m15_since_nov2024, START_TS_2025
from src.data_fetcher import resample_candles, SYMBOL_MAPPINGS
from src.probabilistic_context_engine import (
    ProbabilisticContextForecaster,
    evaluate_dna_session_and_time,
)
from src.forecast_evaluator import forecast_calibrator

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Standard All-In Spread (0 Commission) on MT5 (in price units)
REAL_BID_ASK_SPREAD = {
    "XAUUSD": 0.20,    # 2.0 pips ($0.20)
    "EURUSD": 0.00010, # 1.0 pip
    "GBPUSD": 0.00012, # 1.2 pips
    "USDCAD": 0.00014, # 1.4 pips
    "USDJPY": 0.012,   # 1.2 pips
    "GBPJPY": 0.020,   # 2.0 pips
    "BTCUSD": 15.0,    # $15.00
}

# Contract value per 1.00 Standard Lot per 1.0 price unit move (approx USD)
USD_PER_LOT_PER_PRICE_UNIT = {
    "XAUUSD": 100.0,      # 100 oz -> $1 move = $100 per 1.0 lot
    "EURUSD": 100000.0,   # 100,000 EUR -> 0.0001 (1 pip) = $10 per 1.0 lot
    "GBPUSD": 100000.0,   # 100,000 GBP -> 0.0001 (1 pip) = $10 per 1.0 lot
    "USDCAD": 73000.0,    # 100,000 USD / ~1.37 CAD -> 1 pip ~= $7.30 per 1.0 lot
    "USDJPY": 650.0,      # 100,000 USD / ~154 JPY -> 0.01 (1 pip) ~= $6.50 per 1.0 lot
    "GBPJPY": 650.0,      # 0.01 (1 pip) ~= $6.50 per 1.0 lot
    "BTCUSD": 1.0,        # 1 BTC per 1.0 lot -> $1 move = $1 per 1.0 lot
}


def run_true_bid_ask_audit(symbol: str):
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

    spread = REAL_BID_ASK_SPREAD.get(symbol, 0.0)
    pip_size = SYMBOL_MAPPINGS.get(symbol, {}).get("pip_size", 0.0001)
    unit_val = USD_PER_LOT_PER_PRICE_UNIT.get(symbol, 100000.0)

    lots_list = []
    sl_pips_list = []

    # Compare:
    # A) Pure Chart Bid prices (0 Spread)
    # B) True Bid-Ask Trigger Mechanics (BUY enters at Ask = Bid+Spread, closes at Bid; SELL enters at Bid, closes at Ask = Bid+Spread)
    bal_chart_bid = 10000.0
    bal_true_bid_ask = 10000.0
    tp_missed_due_to_spread = 0
    sl_triggered_early_by_spread = 0
    total_trades = 0

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
        if not raw_setup.get("setup_triggered", False) or idx <= busy_until_idx:
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
        entry_chart = float(setup["entry"])
        sl_chart = float(setup["sl"])
        tp1_chart = float(setup["tp1"])
        tp2_chart = float(setup["tp2"])
        tp3_chart = float(setup["tp3"])
        risk_dist = abs(entry_chart - sl_chart)
        if risk_dist <= 1e-9:
            continue

        # Calculate exact Lot size for $100 risk (1R = $100)
        sl_pips = risk_dist / pip_size
        lot_size = 100.0 / (risk_dist * unit_val)
        lots_list.append(lot_size)
        sl_pips_list.append(sl_pips)

        # Check Stop Order Fill (with Bid/Ask awareness)
        fill_idx = idx
        if order_type in ("BUY_STOP", "SELL_STOP"):
            filled = False
            max_wait = min(idx + 3, n_bars - 1)
            for j in range(idx + 1, max_wait + 1):
                hj_bid, lj_bid = float(sub_candles[j]["high"]), float(sub_candles[j]["low"])
                hj_ask = hj_bid + spread
                if direction == "BUY" and hj_ask >= entry_chart:
                    filled = True
                    fill_idx = j
                    break
                elif direction == "SELL" and lj_bid <= entry_chart:
                    filled = True
                    fill_idx = j
                    break
            if not filled:
                busy_until_idx = max_wait
                continue

        total_trades += 1
        end_idx = min(fill_idx + 32, n_bars - 1)

        # Helper to simulate trade with given spread s_val
        def sim_with_bid_ask(s_val: float):
            # If BUY: we enter at Ask = entry_chart + s_val (for Market) or at entry_chart (for Buy Stop),
            # so keeping R-ratios fixed from actual fill price means Bid must reach entry_actual + 1.5*risk_dist for TP1,
            # and Bid touching entry_actual - risk_dist hits SL.
            # If SELL: we enter at Bid = entry_chart, and exit at Ask = Bid + s_val.
            # So Ask hits TP1 when Low_Bid + s_val <= tp1_chart (i.e. Low_Bid <= tp1_chart - s_val),
            # and Ask hits SL when High_Bid + s_val >= sl_chart (i.e. High_Bid >= sl_chart - s_val).
            tp1_hit = False
            tp2_hit = False
            be_armed = False
            tp1_r = min(abs(tp1_chart - entry_chart) / risk_dist, 2.5)
            tp2_r = min(abs(tp2_chart - entry_chart) / risk_dist, 3.5)
            tp3_r = min(abs(tp3_chart - entry_chart) / risk_dist, 4.5)

            for j in range(fill_idx + 1, end_idx + 1):
                hj_bid, lj_bid = float(sub_candles[j]["high"]), float(sub_candles[j]["low"])
                if direction == "BUY":
                    # Actual fill was shifted up by s_val (Ask), so all Bid targets shift by +s_val
                    sl_trig = (entry_chart + s_val + 0.15 * risk_dist) if be_armed else (sl_chart + s_val)
                    tp1_trig = tp1_chart + s_val
                    tp2_trig = tp2_chart + s_val
                    tp3_trig = tp3_chart + s_val
                    be_lock_trig = entry_chart + s_val + 0.85 * risk_dist

                    if not tp1_hit:
                        if lj_bid <= sl_trig:
                            return (0.15 if be_armed else -1.0), j, tp1_hit
                        if hj_bid >= tp1_trig:
                            tp1_hit = True
                            be_armed = True
                            if lj_bid <= entry_chart + s_val:
                                return round(0.5 * tp1_r, 3), j, tp1_hit
                            if hj_bid >= tp3_trig:
                                return round(0.5 * tp1_r + 0.5 * tp3_r, 3), j, tp1_hit
                            if hj_bid >= tp2_trig:
                                tp2_hit = True
                        elif hj_bid >= be_lock_trig:
                            be_armed = True
                    else:
                        runner_sl = tp1_trig if tp2_hit else (entry_chart + s_val + 0.15 * risk_dist)
                        if lj_bid <= runner_sl:
                            leg2_r = tp2_r if tp2_hit else 0.15
                            return round(0.5 * tp1_r + 0.5 * leg2_r, 3), j, tp1_hit
                        if hj_bid >= tp3_trig:
                            return round(0.5 * tp1_r + 0.5 * tp3_r, 3), j, tp1_hit
                        if hj_bid >= tp2_trig:
                            tp2_hit = True
                else:
                    # SELL: enters at Bid = entry_chart, closes at Ask = Bid + s_val
                    sl_trig_bid = (entry_chart - 0.15 * risk_dist - s_val) if be_armed else (sl_chart - s_val)
                    tp1_trig_bid = tp1_chart - s_val
                    tp2_trig_bid = tp2_chart - s_val
                    tp3_trig_bid = tp3_chart - s_val
                    be_lock_trig_bid = entry_chart - 0.85 * risk_dist - s_val

                    if not tp1_hit:
                        if hj_bid >= sl_trig_bid:
                            return (0.15 if be_armed else -1.0), j, tp1_hit
                        if lj_bid <= tp1_trig_bid:
                            tp1_hit = True
                            be_armed = True
                            if hj_bid >= entry_chart - s_val:
                                return round(0.5 * tp1_r, 3), j, tp1_hit
                            if lj_bid <= tp3_trig_bid:
                                return round(0.5 * tp1_r + 0.5 * tp3_r, 3), j, tp1_hit
                            if lj_bid <= tp2_trig_bid:
                                tp2_hit = True
                        elif lj_bid <= be_lock_trig_bid:
                            be_armed = True
                    else:
                        runner_sl_bid = tp1_trig_bid if tp2_hit else (entry_chart - 0.15 * risk_dist - s_val)
                        if hj_bid >= runner_sl_bid:
                            leg2_r = tp2_r if tp2_hit else 0.15
                            return round(0.5 * tp1_r + 0.5 * leg2_r, 3), j, tp1_hit
                        if lj_bid <= tp3_trig_bid:
                            return round(0.5 * tp1_r + 0.5 * tp3_r, 3), j, tp1_hit
                        if lj_bid <= tp2_trig_bid:
                            tp2_hit = True

            close_bid = float(sub_candles[end_idx]["close"])
            if direction == "BUY":
                raw_r = (close_bid - (entry_chart + s_val)) / risk_dist
            else:
                raw_r = (entry_chart - (close_bid + s_val)) / risk_dist
            raw_r = float(np.clip(raw_r, -1.0, 3.0))
            if tp1_hit:
                leg2_r = max(0.15, raw_r) if not tp2_hit else max(tp2_r, raw_r)
                return round(0.5 * tp1_r + 0.5 * leg2_r, 3), end_idx, tp1_hit
            return round(raw_r, 3), end_idx, tp1_hit

        r_0, exit_0, tp1_0 = sim_with_bid_ask(0.0)
        r_sp, exit_sp, tp1_sp = sim_with_bid_ask(spread)

        if tp1_0 and not tp1_sp:
            tp_missed_due_to_spread += 1
        if r_0 > -1.0 and r_sp == -1.0:
            sl_triggered_early_by_spread += 1

        bal_chart_bid += r_0 * 100.0
        bal_true_bid_ask += r_sp * 100.0
        busy_until_idx = exit_sp

    avg_lot = float(np.mean(lots_list)) if lots_list else 0.0
    min_lot = float(np.min(lots_list)) if lots_list else 0.0
    max_lot = float(np.max(lots_list)) if lots_list else 0.0
    avg_sl_pips = float(np.mean(sl_pips_list)) if sl_pips_list else 0.0

    print(
        f"{symbol:<7} | Trades={total_trades:<4d} | SL_TB={avg_sl_pips:5.1f}p | "
        f"Lot_TB={avg_lot:4.2f}L ({min_lot:.2f}..{max_lot:.2f}L) | "
        f"MissTP_DoSpread={tp_missed_due_to_spread:<2d} | EarlySL_DoSpread={sl_triggered_early_by_spread:<2d} | "
        f"Net(0_Spread)={bal_chart_bid-10000:+7.0f}$ | Net(True_BidAsk)={bal_true_bid_ask-10000:+7.0f}$"
    )


if __name__ == "__main__":
    for s in ["XAUUSD", "EURUSD", "GBPUSD", "USDCAD", "USDJPY", "GBPJPY", "BTCUSD"]:
        run_true_bid_ask_audit(s)
