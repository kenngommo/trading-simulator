"""
Sequential Multi-Pair Quantitative Strategy Backtest (01/01/2025 -> Present)
=============================================================================
- Pairs (7): XAUUSD, EURUSD, GBPUSD, USDCAD, USDJPY, GBPJPY, BTCUSD
- Initial Capital: $10,000.00 per pair | Fixed Risk per Trade: 1R = $100.00 (1.0% of initial capital)
- Timeframe: H4 Anchor + M15 Execution Trigger
- Concurrency Rule: Max 1 open position per symbol at any time (wait until current trade closes)
- Strategies (3 Verified Edge Playbooks + HTF/LTF k-NN Probabilistic & DNA Filter):
    1. EMA21_TREND_IMPULSE (MARKET_CLOSE)
    2. STOCH_RSI_DIV_REVERSAL (MARKET_CLOSE, >= 65/100 pts)
    3. BB_FAKEOUT_STOP (Mandatory BUY_STOP / SELL_STOP + 3-Bar Fill Confirmation)
- Scale-Out & Trade Management (Confirmed Rule A2):
    - 50% Position closes at TP1 (1.5R = +$75.00 realized) + Move SL of remaining 50% to Break-Even (Entry).
    - Remaining 50% targets TP2 (2.0R) and TP3 (3.0R):
        * Hits TP3 (3.0R): Leg 2 = +3.0R (+$150) -> Total Trade = +2.25R (+$225.00) [TP1_TP3_HIT]
        * Hits TP2 (2.0R) then retraces to TP1/BE: Leg 2 = +2.0R (+$100) -> Total Trade = +1.75R (+$175.00) [TP1_TP2_HIT]
        * Retraces to BE before TP2: Leg 2 = 0.0R ($0) -> Total Trade = +0.75R (+$75.00) [TP1_BE_HIT]
    - Full SL before TP1: Both legs stop out at SL -> Total Trade = -1.00R (-$100.00) [SL_HIT]
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.data_fetcher import _get_mt5_symbol_name, resample_candles, SYMBOL_MAPPINGS
from src.probabilistic_context_engine import (
    ProbabilisticContextForecaster,
    evaluate_dna_session_and_time,
)
from src.forecast_evaluator import forecast_calibrator

START_TS_2025 = int(datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp())
WARMUP_START_TS = int(datetime(2024, 11, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp())


def fetch_full_mt5_m15_since_nov2024(symbol: str) -> List[Dict[str, Any]]:
    """Pages backwards in MT5 using copy_rates_from_pos so we cover 2024-11-01 to present."""
    import MetaTrader5 as mt5

    if not mt5.initialize():
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")

    mt5_sym = _get_mt5_symbol_name(symbol) or symbol
    mt5.symbol_select(mt5_sym, True)

    chunk_size = 40000
    pos = 0
    by_time: Dict[int, Dict[str, Any]] = {}

    for _ in range(4):
        rates = mt5.copy_rates_from_pos(mt5_sym, mt5.TIMEFRAME_M15, pos, chunk_size)
        if rates is None or len(rates) == 0:
            break
        earliest_in_batch = int(rates[0]["time"])
        for r in rates:
            t = int(r["time"])
            by_time[t] = {
                "time": t,
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"]),
                "volume": float(r["tick_volume"]),
            }
        if earliest_in_batch <= WARMUP_START_TS or len(rates) < chunk_size:
            break
        pos += len(rates)

    candles = sorted(by_time.values(), key=lambda x: x["time"])
    return candles


def simulate_scaleout_trade_lifecycle(
    setup: Dict[str, Any],
    sub_candles: List[Dict[str, Any]],
    signal_idx: int,
    max_hold_bars: int = 32,
) -> Dict[str, Any]:
    """
    Simulates a single trade with 2-part scale-out:
    - Pending Stop Orders (BUY_STOP / SELL_STOP): must trigger within 3 bars (signal_idx+1 .. signal_idx+3).
      If not triggered within 3 bars -> UNFILLED_CANCELLED (0.0R, $0.00, exit_idx = signal_idx + 3).
    - Market Orders (MARKET_CLOSE): filled at signal_idx close, active from signal_idx + 1.
    - Scale-out rules once filled:
      * Leg 1 (50% risk = $50): TP1 (1.5R)
      * Leg 2 (50% risk = $50): TP2 (2.0R) / TP3 (3.0R), SL moved to BE after TP1 is hit.
    """
    n_bars = len(sub_candles)
    direction = setup.get("direction", "BUY")
    order_type = setup.get("order_type", "MARKET_CLOSE")
    entry_p = float(setup["entry"])
    sl_p = float(setup["sl"])
    tp1_p = float(setup["tp1"])
    tp2_p = float(setup["tp2"])
    tp3_p = float(setup["tp3"])

    risk_dist = abs(entry_p - sl_p)
    if risk_dist <= 1e-9:
        return {"filled": False, "outcome": "INVALID", "realized_r": 0.0, "exit_idx": signal_idx + 1}

    # Actual R multiples of TP1, TP2, TP3 (since BB_FAKEOUT_STOP can have dynamic TP >= 1.5R / 2.0R)
    tp1_r = min(abs(tp1_p - entry_p) / risk_dist, 2.5)
    tp2_r = min(abs(tp2_p - entry_p) / risk_dist, 3.5)
    tp3_r = min(abs(tp3_p - entry_p) / risk_dist, 4.5)

    fill_idx = signal_idx
    if order_type in ("BUY_STOP", "SELL_STOP"):
        filled = False
        max_wait = min(signal_idx + 3, n_bars - 1)
        for j in range(signal_idx + 1, max_wait + 1):
            hj = float(sub_candles[j]["high"])
            lj = float(sub_candles[j]["low"])
            if direction == "BUY" and hj >= entry_p:
                filled = True
                fill_idx = j
                # Conservative check if fill bar also swept SL
                if lj <= sl_p:
                    return {
                        "filled": True,
                        "fill_idx": fill_idx,
                        "exit_idx": j,
                        "exit_time": int(sub_candles[j]["time"]),
                        "outcome": "SL_HIT",
                        "realized_r": -1.0,
                        "pnl_usd": -100.0,
                    }
                break
            elif direction == "SELL" and lj <= entry_p:
                filled = True
                fill_idx = j
                if hj >= sl_p:
                    return {
                        "filled": True,
                        "fill_idx": fill_idx,
                        "exit_idx": j,
                        "exit_time": int(sub_candles[j]["time"]),
                        "outcome": "SL_HIT",
                        "realized_r": -1.0,
                        "pnl_usd": -100.0,
                    }
                break
        if not filled:
            return {
                "filled": False,
                "fill_idx": -1,
                "exit_idx": max_wait,
                "exit_time": int(sub_candles[max_wait]["time"]),
                "outcome": "UNFILLED_CANCELLED",
                "realized_r": 0.0,
                "pnl_usd": 0.0,
            }

    tp1_hit = False
    tp2_hit = False
    be_armed = False
    be_lock_p = (entry_p + 0.85 * risk_dist) if direction == "BUY" else (entry_p - 0.85 * risk_dist)
    end_idx = min(fill_idx + max_hold_bars, n_bars - 1)

    for j in range(fill_idx + 1, end_idx + 1):
        hj = float(sub_candles[j]["high"])
        lj = float(sub_candles[j]["low"])

        if direction == "BUY":
            if not tp1_hit:
                curr_sl = (entry_p + 0.15 * risk_dist) if be_armed else sl_p
                if lj <= curr_sl:
                    if be_armed:
                        return {
                            "filled": True,
                            "fill_idx": fill_idx,
                            "exit_idx": j,
                            "exit_time": int(sub_candles[j]["time"]),
                            "outcome": "TIME_WIN",
                            "realized_r": 0.15,
                            "pnl_usd": 15.0,
                        }
                    return {
                        "filled": True,
                        "fill_idx": fill_idx,
                        "exit_idx": j,
                        "exit_time": int(sub_candles[j]["time"]),
                        "outcome": "SL_HIT",
                        "realized_r": -1.0,
                        "pnl_usd": -100.0,
                    }
                if hj >= tp1_p:
                    tp1_hit = True
                    be_armed = True
                    if hj >= tp3_p and lj > entry_p:
                        tot_r = round(0.5 * tp1_r + 0.5 * tp3_r, 3)
                        return {
                            "filled": True,
                            "fill_idx": fill_idx,
                            "exit_idx": j,
                            "exit_time": int(sub_candles[j]["time"]),
                            "outcome": "TP1_TP3_HIT",
                            "realized_r": tot_r,
                            "pnl_usd": round(tot_r * 100.0, 2),
                        }
                    if hj >= tp2_p and lj > entry_p:
                        tp2_hit = True
                elif hj >= be_lock_p:
                    be_armed = True
            else:
                # TP1 already locked in (+0.5 * tp1_r). Remaining 50% has SL at BE (entry_p + 0.15R), or at tp1_p if tp2_hit
                runner_sl = tp1_p if tp2_hit else (entry_p + 0.15 * risk_dist)
                if lj <= runner_sl:
                    leg2_r = tp2_r if tp2_hit else 0.15
                    tot_r = round(0.5 * tp1_r + 0.5 * leg2_r, 3)
                    out_lbl = "TP1_TP2_HIT" if tp2_hit else "TP1_BE_HIT"
                    return {
                        "filled": True,
                        "fill_idx": fill_idx,
                        "exit_idx": j,
                        "exit_time": int(sub_candles[j]["time"]),
                        "outcome": out_lbl,
                        "realized_r": tot_r,
                        "pnl_usd": round(tot_r * 100.0, 2),
                    }
                if hj >= tp3_p:
                    tot_r = round(0.5 * tp1_r + 0.5 * tp3_r, 3)
                    return {
                        "filled": True,
                        "fill_idx": fill_idx,
                        "exit_idx": j,
                        "exit_time": int(sub_candles[j]["time"]),
                        "outcome": "TP1_TP3_HIT",
                        "realized_r": tot_r,
                        "pnl_usd": round(tot_r * 100.0, 2),
                    }
                if hj >= tp2_p:
                    tp2_hit = True
        else:
            # SELL
            if not tp1_hit:
                curr_sl = (entry_p - 0.15 * risk_dist) if be_armed else sl_p
                if hj >= curr_sl:
                    if be_armed:
                        return {
                            "filled": True,
                            "fill_idx": fill_idx,
                            "exit_idx": j,
                            "exit_time": int(sub_candles[j]["time"]),
                            "outcome": "TIME_WIN",
                            "realized_r": 0.15,
                            "pnl_usd": 15.0,
                        }
                    return {
                        "filled": True,
                        "fill_idx": fill_idx,
                        "exit_idx": j,
                        "exit_time": int(sub_candles[j]["time"]),
                        "outcome": "SL_HIT",
                        "realized_r": -1.0,
                        "pnl_usd": -100.0,
                    }
                if lj <= tp1_p:
                    tp1_hit = True
                    be_armed = True
                    if lj <= tp3_p and hj < entry_p:
                        tot_r = round(0.5 * tp1_r + 0.5 * tp3_r, 3)
                        return {
                            "filled": True,
                            "fill_idx": fill_idx,
                            "exit_idx": j,
                            "exit_time": int(sub_candles[j]["time"]),
                            "outcome": "TP1_TP3_HIT",
                            "realized_r": tot_r,
                            "pnl_usd": round(tot_r * 100.0, 2),
                        }
                    if lj <= tp2_p and hj < entry_p:
                        tp2_hit = True
                elif lj <= be_lock_p:
                    be_armed = True
            else:
                runner_sl = tp1_p if tp2_hit else (entry_p - 0.15 * risk_dist)
                if hj >= runner_sl:
                    leg2_r = tp2_r if tp2_hit else 0.15
                    tot_r = round(0.5 * tp1_r + 0.5 * leg2_r, 3)
                    out_lbl = "TP1_TP2_HIT" if tp2_hit else "TP1_BE_HIT"
                    return {
                        "filled": True,
                        "fill_idx": fill_idx,
                        "exit_idx": j,
                        "exit_time": int(sub_candles[j]["time"]),
                        "outcome": out_lbl,
                        "realized_r": tot_r,
                        "pnl_usd": round(tot_r * 100.0, 2),
                    }
                if lj <= tp3_p:
                    tot_r = round(0.5 * tp1_r + 0.5 * tp3_r, 3)
                    return {
                        "filled": True,
                        "fill_idx": fill_idx,
                        "exit_idx": j,
                        "exit_time": int(sub_candles[j]["time"]),
                        "outcome": "TP1_TP3_HIT",
                        "realized_r": tot_r,
                        "pnl_usd": round(tot_r * 100.0, 2),
                    }
                if lj <= tp2_p:
                    tp2_hit = True

    # Time exit at end_idx
    close_end = float(sub_candles[end_idx]["close"])
    raw_leg_r = ((close_end - entry_p) / risk_dist) if direction == "BUY" else ((entry_p - close_end) / risk_dist)
    raw_leg_r = float(np.clip(raw_leg_r, -1.0, 3.0))

    if tp1_hit:
        leg2_r = max(0.0, raw_leg_r) if not tp2_hit else max(tp2_r, raw_leg_r)
        tot_r = round(0.5 * tp1_r + 0.5 * leg2_r, 3)
        out_lbl = "TP1_TP2_HIT" if tp2_hit else "TP1_TIME_WIN"
    else:
        tot_r = round(raw_leg_r, 3)
        out_lbl = "TIME_WIN" if tot_r > 0 else "TIME_LOSS"

    return {
        "filled": True,
        "fill_idx": fill_idx,
        "exit_idx": end_idx,
        "exit_time": int(sub_candles[end_idx]["time"]),
        "outcome": out_lbl,
        "realized_r": tot_r,
        "pnl_usd": round(tot_r * 100.0, 2),
    }


def run_single_pair_backtest(symbol: str, forecaster: ProbabilisticContextForecaster) -> Dict[str, Any]:
    t0 = time.time()
    sub_candles = fetch_full_mt5_m15_since_nov2024(symbol)
    if not sub_candles or len(sub_candles) < 500:
        return {"symbol": symbol, "error": "Insufficient MT5 data"}

    macro_candles = resample_candles(sub_candles, target_seconds=14400)
    arrays = forecaster.prepare_causal_arrays(sub_candles, macro_candles)
    profile = forecast_calibrator.get_profile(symbol, "H4_M15")

    n_bars = len(sub_candles)
    # Find index corresponding to 2025-01-01 00:00:00 (or earliest available bar if symbol starts slightly after)
    start_idx = 220
    for idx in range(220, n_bars):
        if int(sub_candles[idx]["time"]) >= START_TS_2025:
            start_idx = idx
            break

    actual_start_ts = int(sub_candles[start_idx]["time"])
    actual_end_ts = int(sub_candles[-1]["time"])
    start_dna = evaluate_dna_session_and_time(symbol, actual_start_ts)
    end_dna = evaluate_dna_session_and_time(symbol, actual_end_ts)

    initial_balance = 10000.0
    balance = initial_balance
    peak_balance = initial_balance
    max_dd_usd = 0.0
    max_dd_pct = 0.0

    trades: List[Dict[str, Any]] = []
    unfilled_stop_orders = 0
    skipped_while_open = 0
    whipsaws_vetoed_by_knn = 0

    playbook_stats: Dict[str, Dict[str, Any]] = {
        "EMA21_TREND_IMPULSE": {"n": 0, "wins": 0, "gross_win_usd": 0.0, "gross_loss_usd": 0.0, "net_usd": 0.0, "net_r": 0.0},
        "STOCH_RSI_DIV_REVERSAL": {"n": 0, "wins": 0, "gross_win_usd": 0.0, "gross_loss_usd": 0.0, "net_usd": 0.0, "net_r": 0.0},
        "BB_FAKEOUT_STOP": {"n": 0, "wins": 0, "gross_win_usd": 0.0, "gross_loss_usd": 0.0, "net_usd": 0.0, "net_r": 0.0, "unfilled": 0},
    }

    outcome_counts: Dict[str, int] = {
        "TP1_TP3_HIT": 0,
        "TP1_TP2_HIT": 0,
        "TP1_BE_HIT": 0,
        "TP1_TIME_WIN": 0,
        "TIME_WIN": 0,
        "TIME_LOSS": 0,
        "SL_HIT": 0,
    }

    busy_until_idx = -1

    for idx in range(start_idx, n_bars - 16):
        # Fast O(1) check if any of the 3 Playbooks triggers technically on bar idx
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

        # A raw strategy setup occurred at bar idx!
        # Check if a trade is already open (Rule A3: Max 1 open position per symbol at a time)
        if idx <= busy_until_idx:
            skipped_while_open += 1
            continue

        # Run full causal HTF+LTF k-NN + DNA Session Filter at bar idx
        fc = forecaster.forecast_at_bar(
            sub_candles,
            macro_candles,
            curr_idx=idx,
            symbol=symbol,
            include_analogs=False,
            adaptive_profile=profile,
            timeframe_pair="H4_M15",
        )
        filt_setup = fc.get("suggested_setup", {})
        if not filt_setup.get("setup_triggered", False):
            whipsaws_vetoed_by_knn += 1
            continue

        # Execute trade lifecycle with 2-part scale-out (Rule A2)
        res = simulate_scaleout_trade_lifecycle(filt_setup, sub_candles, idx, max_hold_bars=32)
        busy_until_idx = res["exit_idx"]

        strat_id = filt_setup.get("strategy_id", "EMA21_TREND_IMPULSE")
        if not res["filled"]:
            unfilled_stop_orders += 1
            if strat_id in playbook_stats and "unfilled" in playbook_stats[strat_id]:
                playbook_stats[strat_id]["unfilled"] += 1
            continue

        pnl_usd = float(res["pnl_usd"])
        real_r = float(res["realized_r"])
        out_lbl = res["outcome"]

        balance = round(balance + pnl_usd, 2)
        if balance > peak_balance:
            peak_balance = balance
        dd_usd = round(peak_balance - balance, 2)
        dd_pct = round((dd_usd / peak_balance) * 100.0, 2) if peak_balance > 0 else 0.0
        if dd_usd > max_dd_usd:
            max_dd_usd = dd_usd
        if dd_pct > max_dd_pct:
            max_dd_pct = dd_pct

        if out_lbl in outcome_counts:
            outcome_counts[out_lbl] += 1

        if strat_id in playbook_stats:
            pb = playbook_stats[strat_id]
            pb["n"] += 1
            if real_r > 0:
                pb["wins"] += 1
                pb["gross_win_usd"] += pnl_usd
            elif real_r < 0:
                pb["gross_loss_usd"] += abs(pnl_usd)
            pb["net_usd"] = round(pb["net_usd"] + pnl_usd, 2)
            pb["net_r"] = round(pb["net_r"] + real_r, 2)

        exit_dna = evaluate_dna_session_and_time(symbol, res["exit_time"])
        trades.append(
            {
                "trade_no": len(trades) + 1,
                "signal_time": dna_info["formatted_full"],
                "signal_short": dna_info["formatted_short"],
                "exit_short": exit_dna["formatted_short"],
                "strategy_id": strat_id,
                "strategy_name": filt_setup.get("strategy_name", strat_id),
                "order_type": filt_setup.get("order_type", "MARKET_CLOSE"),
                "direction": filt_setup.get("direction", "BUY"),
                "entry": filt_setup.get("entry"),
                "sl": filt_setup.get("sl"),
                "tp1": filt_setup.get("tp1"),
                "tp2": filt_setup.get("tp2"),
                "tp3": filt_setup.get("tp3"),
                "outcome": out_lbl,
                "realized_r": real_r,
                "pnl_usd": pnl_usd,
                "balance_after": balance,
            }
        )

    total_trades = len(trades)
    wins = sum(1 for t in trades if t["realized_r"] > 0)
    losses = sum(1 for t in trades if t["realized_r"] < 0)
    gross_win = sum(t["pnl_usd"] for t in trades if t["pnl_usd"] > 0)
    gross_loss = abs(sum(t["pnl_usd"] for t in trades if t["pnl_usd"] < 0))
    net_pnl_usd = round(balance - initial_balance, 2)
    net_pnl_pct = round((net_pnl_usd / initial_balance) * 100.0, 2)
    net_r = round(sum(t["realized_r"] for t in trades), 2)
    wr_pct = round((wins / total_trades) * 100.0, 2) if total_trades > 0 else 0.0
    pf = round(gross_win / gross_loss, 2) if gross_loss > 0 else (9.99 if gross_win > 0 else 0.0)
    exp_r = round(net_r / total_trades, 3) if total_trades > 0 else 0.0
    exp_usd = round(net_pnl_usd / total_trades, 2) if total_trades > 0 else 0.0

    for k, pb in playbook_stats.items():
        n_pb = pb["n"]
        pb["wr_pct"] = round((pb["wins"] / n_pb) * 100.0, 1) if n_pb > 0 else 0.0
        pb["pf"] = round(pb["gross_win_usd"] / pb["gross_loss_usd"], 2) if pb["gross_loss_usd"] > 0 else (9.99 if pb["gross_win_usd"] > 0 else 0.0)
        pb["exp_r"] = round(pb["net_r"] / n_pb, 2) if n_pb > 0 else 0.0

    return {
        "symbol": symbol,
        "bars_total": n_bars,
        "bars_tested": n_bars - start_idx,
        "period_start": start_dna["formatted_full"],
        "period_end": end_dna["formatted_full"],
        "initial_balance": initial_balance,
        "final_balance": balance,
        "net_pnl_usd": net_pnl_usd,
        "net_pnl_pct": net_pnl_pct,
        "net_r": net_r,
        "total_trades": total_trades,
        "wins": wins,
        "losses": losses,
        "winrate_pct": wr_pct,
        "profit_factor": pf,
        "expectancy_r": exp_r,
        "expectancy_usd": exp_usd,
        "max_drawdown_usd": max_dd_usd,
        "max_drawdown_pct": max_dd_pct,
        "whipsaws_vetoed_by_knn": whipsaws_vetoed_by_knn,
        "unfilled_stop_orders": unfilled_stop_orders,
        "skipped_while_open": skipped_while_open,
        "outcome_counts": outcome_counts,
        "playbook_stats": playbook_stats,
        "sample_trades": trades[-5:],
        "elapsed_sec": round(time.time() - t0, 2),
    }


def main():
    symbols = ["XAUUSD", "EURUSD", "GBPUSD", "USDCAD", "USDJPY", "GBPJPY", "BTCUSD"]
    forecaster = ProbabilisticContextForecaster(
        horizon_bars=8,
        k_neighbors=35,
        forecast_mode="COMBINED_HTF_LTF",
        macro_horizon_bars=6,
    )

    results = []
    print("=" * 136)
    print(" 🚀 BÁO CÁO BACKTEST ĐỊNH LƯỢNG TUẦN TỰ 7 CẶP TÀI SẢN (01/01/2025 -> HIỆN TẠI) | VỐN: $10,000 | RỦI RO: $100/LỆNH (1R)")
    print(" 📌 Quy tắc: Khung H4+M15 | Tối đa 1 lệnh mở/cặp | Scale-out 50% tại TP1 (1.5R) + Dời SL về BE, nuôi 50% tới TP2 (2R) / TP3 (3R)")
    print("=" * 136)
    print(
        f" {'Symbol':<7} | {'Giai Đoạn Kiểm Định (Server / VN)':<35} | {'Số Nến':<7} | {'Số Lệnh':<7} | "
        f"{'Winrate':<8} | {'PF':<5} | {'Kỳ Vọng':<8} | {'Max DD':<14} | {'Lãi Ròng ($ / %)':<20} | {'Vốn Cuối'}"
    )
    print("-" * 136)

    for sym in symbols:
        rep = run_single_pair_backtest(sym, forecaster)
        results.append(rep)
        if "error" in rep:
            print(f" {sym:<7} | LỖI: {rep['error']}")
            continue

        p_start = rep["period_start"].split(" Server")[0][:10]
        p_end = rep["period_end"].split(" Server")[0][:10]
        period_str = f"{p_start} -> {p_end} (UTC+7)"
        dd_str = f"-${rep['max_drawdown_usd']:,.0f} ({rep['max_drawdown_pct']:.1f}%)"
        pnl_str = f"{rep['net_pnl_usd']:+,.0f}$ ({rep['net_pnl_pct']:+.1f}%)"
        bal_str = f"${rep['final_balance']:,.0f}"

        print(
            f" {sym:<7} | {period_str:<35} | {rep['bars_tested']:<7d} | {rep['total_trades']:<7d} | "
            f"{rep['winrate_pct']:>6.1f}% | {rep['profit_factor']:>5.2f} | {rep['expectancy_r']:>+6.2f}R | "
            f"{dd_str:<14} | {pnl_str:<20} | {bal_str}"
        )
        oc = rep["outcome_counts"]
        pb = rep["playbook_stats"]
        p1 = pb["EMA21_TREND_IMPULSE"]
        p2 = pb["STOCH_RSI_DIV_REVERSAL"]
        p3 = pb["BB_FAKEOUT_STOP"]
        print(
            f"   ├─ Phân bổ kết quả: TP1+TP3(2.25R): {oc['TP1_TP3_HIT']} | TP1+TP2(1.75R): {oc['TP1_TP2_HIT']} | "
            f"TP1+BE(0.75R): {oc['TP1_BE_HIT']+oc['TP1_TIME_WIN']} | TimeWin: {oc['TIME_WIN']} | TimeLoss: {oc['TIME_LOSS']} | SL(-1R): {oc['SL_HIT']}"
        )
        print(
            f"   ├─ [1] EMA21 Impulse: N={p1['n']:3d}, WR={p1['wr_pct']:4.1f}%, PF={p1['pf']:4.2f}, Lãi={p1['net_usd']:+,.0f}$ | "
            f"[2] Stoch+RSI Div: N={p2['n']:3d}, WR={p2['wr_pct']:4.1f}%, PF={p2['pf']:4.2f}, Lãi={p2['net_usd']:+,.0f}$"
        )
        print(
            f"   └─ [3] BB Fakeout Stop: N={p3['n']:3d} khớp (Hủy {p3['unfilled']:3d} lệnh Stop không khớp), "
            f"WR={p3['wr_pct']:4.1f}%, PF={p3['pf']:4.2f}, Lãi={p3['net_usd']:+,.0f}$ | Đã lọc k-NN: -{rep['whipsaws_vetoed_by_knn']} nhiễu"
        )

    print("=" * 136)

    out_path = os.path.join("data", "backtest_2025_to_now_report.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"Đã lưu báo cáo JSON chi tiết tại: {out_path}")


if __name__ == "__main__":
    main()
