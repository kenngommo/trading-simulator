"""
Sequential Backtest for Forex Pairs on H4 Anchor + H1 Execution (01/01/2025 -> Present)
=======================================================================================
Per AGENTS.md Mục 2 (Bản Đồ DNA Forex Majors):
- Khung Thời Gian Chủ Đạo: H1, H4 (H4 làm Mỏ neo xu hướng, H1 làm khung tín hiệu thực thi).
- Pairs (5): EURUSD, GBPUSD, USDCAD, USDJPY, GBPJPY
- Initial Capital: $10,000.00 | Fixed Risk per Trade: 1R = $100.00
- Concurrency: Max 1 open position per symbol at a time
- Scale-Out (Rule A2): 50% at TP1 (1.5R) + Move SL to BE, 50% runner to TP2 (2.0R) / TP3 (3.0R)
- Includes both Chart Price (0 Spread) and True MT5 Bid-Ask Execution (Ask = Bid + Spread) + Dynamic Lot Sizing!
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List
import numpy as np
import MetaTrader5 as mt5

from src.data_fetcher import _get_mt5_symbol_name, SYMBOL_MAPPINGS
from src.probabilistic_context_engine import (
    ProbabilisticContextForecaster,
    evaluate_dna_session_and_time,
)
from src.forecast_evaluator import forecast_calibrator

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

START_TS_2025 = int(datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp())

REAL_BID_ASK_SPREAD = {
    "EURUSD": 0.00010,  # 1.0 pip
    "GBPUSD": 0.00012,  # 1.2 pips
    "USDCAD": 0.00014,  # 1.4 pips
    "USDJPY": 0.012,    # 1.2 pips
    "GBPJPY": 0.020,    # 2.0 pips
}

USD_PER_LOT_PER_PRICE_UNIT = {
    "EURUSD": 100000.0,
    "GBPUSD": 100000.0,
    "USDCAD": 73000.0,
    "USDJPY": 650.0,
    "GBPJPY": 650.0,
}


def fetch_mt5_tf_history(symbol: str, tf_const: int, count: int = 18000) -> List[Dict[str, Any]]:
    if not mt5.initialize():
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
    mt5_sym = _get_mt5_symbol_name(symbol) or symbol
    mt5.symbol_select(mt5_sym, True)
    rates = mt5.copy_rates_from_pos(mt5_sym, tf_const, 0, count)
    if rates is None or len(rates) == 0:
        return []
    candles = [
        {
            "time": int(r["time"]),
            "open": float(r["open"]),
            "high": float(r["high"]),
            "low": float(r["low"]),
            "close": float(r["close"]),
            "volume": float(r["tick_volume"]),
        }
        for r in rates
    ]
    candles.sort(key=lambda x: x["time"])
    return candles


def simulate_h1_trade_with_bid_ask(
    setup: Dict[str, Any],
    h1_candles: List[Dict[str, Any]],
    signal_idx: int,
    spread_price: float = 0.0,
    max_hold_bars: int = 28,
) -> Dict[str, Any]:
    """
    Simulates a trade on H1 candles with exact MT5 Bid-Ask mechanics and 2-part scale-out (50% TP1 + BE, 50% TP2/TP3).
    """
    n_bars = len(h1_candles)
    direction = setup.get("direction", "BUY")
    order_type = setup.get("order_type", "MARKET_CLOSE")
    entry_chart = float(setup["entry"])
    sl_chart = float(setup["sl"])
    tp1_chart = float(setup["tp1"])
    tp2_chart = float(setup["tp2"])
    tp3_chart = float(setup["tp3"])

    risk_dist = abs(entry_chart - sl_chart)
    if risk_dist <= 1e-9:
        return {"filled": False, "outcome": "INVALID", "realized_r": 0.0, "pnl_usd": 0.0, "exit_idx": signal_idx + 1}

    tp1_r = min(abs(tp1_chart - entry_chart) / risk_dist, 2.5)
    tp2_r = min(abs(tp2_chart - entry_chart) / risk_dist, 3.5)
    tp3_r = min(abs(tp3_chart - entry_chart) / risk_dist, 4.5)

    fill_idx = signal_idx
    if order_type in ("BUY_STOP", "SELL_STOP"):
        filled = False
        max_wait = min(signal_idx + 3, n_bars - 1)
        for j in range(signal_idx + 1, max_wait + 1):
            hj_bid, lj_bid = float(h1_candles[j]["high"]), float(h1_candles[j]["low"])
            hj_ask = hj_bid + spread_price
            if direction == "BUY" and hj_ask >= entry_chart:
                filled = True
                fill_idx = j
                if lj_bid <= sl_chart:
                    return {
                        "filled": True,
                        "fill_idx": fill_idx,
                        "exit_idx": j,
                        "exit_time": int(h1_candles[j]["time"]),
                        "outcome": "SL_HIT",
                        "realized_r": -1.0,
                        "pnl_usd": -100.0,
                    }
                break
            elif direction == "SELL" and lj_bid <= entry_chart:
                filled = True
                fill_idx = j
                if hj_bid + spread_price >= sl_chart:
                    return {
                        "filled": True,
                        "fill_idx": fill_idx,
                        "exit_idx": j,
                        "exit_time": int(h1_candles[j]["time"]),
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
                "exit_time": int(h1_candles[max_wait]["time"]),
                "outcome": "UNFILLED_CANCELLED",
                "realized_r": 0.0,
                "pnl_usd": 0.0,
            }

    tp1_hit = False
    tp2_hit = False
    be_armed = False
    end_idx = min(fill_idx + max_hold_bars, n_bars - 1)

    for j in range(fill_idx + 1, end_idx + 1):
        hj_bid, lj_bid = float(h1_candles[j]["high"]), float(h1_candles[j]["low"])

        if direction == "BUY":
            # Market BUY filled at Ask = entry_chart + spread_price; BUY_STOP filled at entry_chart (Ask)
            s_shift = spread_price if order_type == "MARKET_CLOSE" else 0.0
            sl_trig = (entry_chart + s_shift + 0.15 * risk_dist) if be_armed else (sl_chart + s_shift)
            tp1_trig = tp1_chart + s_shift
            tp2_trig = tp2_chart + s_shift
            tp3_trig = tp3_chart + s_shift
            be_lock_trig = entry_chart + s_shift + 0.85 * risk_dist

            if not tp1_hit:
                if lj_bid <= sl_trig:
                    r_out = 0.15 if be_armed else -1.0
                    lbl_out = "TIME_WIN" if be_armed else "SL_HIT"
                    return {
                        "filled": True,
                        "fill_idx": fill_idx,
                        "exit_idx": j,
                        "exit_time": int(h1_candles[j]["time"]),
                        "outcome": lbl_out,
                        "realized_r": r_out,
                        "pnl_usd": round(r_out * 100.0, 2),
                    }
                if hj_bid >= tp1_trig:
                    tp1_hit = True
                    be_armed = True
                    if lj_bid <= entry_chart + s_shift:
                        tot_r = round(0.5 * tp1_r + 0.5 * 0.15, 3)
                        return {
                            "filled": True,
                            "fill_idx": fill_idx,
                            "exit_idx": j,
                            "exit_time": int(h1_candles[j]["time"]),
                            "outcome": "TP1_BE_HIT",
                            "realized_r": tot_r,
                            "pnl_usd": round(tot_r * 100.0, 2),
                        }
                    if hj_bid >= tp3_trig:
                        tot_r = round(0.5 * tp1_r + 0.5 * tp3_r, 3)
                        return {
                            "filled": True,
                            "fill_idx": fill_idx,
                            "exit_idx": j,
                            "exit_time": int(h1_candles[j]["time"]),
                            "outcome": "TP1_TP3_HIT",
                            "realized_r": tot_r,
                            "pnl_usd": round(tot_r * 100.0, 2),
                        }
                    if hj_bid >= tp2_trig:
                        tp2_hit = True
                elif hj_bid >= be_lock_trig:
                    be_armed = True
            else:
                runner_sl = tp1_trig if tp2_hit else (entry_chart + s_shift + 0.15 * risk_dist)
                if lj_bid <= runner_sl:
                    leg2_r = tp2_r if tp2_hit else 0.15
                    tot_r = round(0.5 * tp1_r + 0.5 * leg2_r, 3)
                    out_lbl = "TP1_TP2_HIT" if tp2_hit else "TP1_BE_HIT"
                    return {
                        "filled": True,
                        "fill_idx": fill_idx,
                        "exit_idx": j,
                        "exit_time": int(h1_candles[j]["time"]),
                        "outcome": out_lbl,
                        "realized_r": tot_r,
                        "pnl_usd": round(tot_r * 100.0, 2),
                    }
                if hj_bid >= tp3_trig:
                    tot_r = round(0.5 * tp1_r + 0.5 * tp3_r, 3)
                    return {
                        "filled": True,
                        "fill_idx": fill_idx,
                        "exit_idx": j,
                        "exit_time": int(h1_candles[j]["time"]),
                        "outcome": "TP1_TP3_HIT",
                        "realized_r": tot_r,
                        "pnl_usd": round(tot_r * 100.0, 2),
                    }
                if hj_bid >= tp2_trig:
                    tp2_hit = True
        else:
            # SELL: enters at Bid = entry_chart, closes at Ask = Bid + spread_price
            sl_trig_bid = (entry_chart - 0.15 * risk_dist - spread_price) if be_armed else (sl_chart - spread_price)
            tp1_trig_bid = tp1_chart - spread_price
            tp2_trig_bid = tp2_chart - spread_price
            tp3_trig_bid = tp3_chart - spread_price
            be_lock_trig_bid = entry_chart - 0.85 * risk_dist - spread_price

            if not tp1_hit:
                if hj_bid >= sl_trig_bid:
                    r_out = 0.15 if be_armed else -1.0
                    lbl_out = "TIME_WIN" if be_armed else "SL_HIT"
                    return {
                        "filled": True,
                        "fill_idx": fill_idx,
                        "exit_idx": j,
                        "exit_time": int(h1_candles[j]["time"]),
                        "outcome": lbl_out,
                        "realized_r": r_out,
                        "pnl_usd": round(r_out * 100.0, 2),
                    }
                if lj_bid <= tp1_trig_bid:
                    tp1_hit = True
                    be_armed = True
                    if hj_bid >= entry_chart - spread_price:
                        tot_r = round(0.5 * tp1_r + 0.5 * 0.15, 3)
                        return {
                            "filled": True,
                            "fill_idx": fill_idx,
                            "exit_idx": j,
                            "exit_time": int(h1_candles[j]["time"]),
                            "outcome": "TP1_BE_HIT",
                            "realized_r": tot_r,
                            "pnl_usd": round(tot_r * 100.0, 2),
                        }
                    if lj_bid <= tp3_trig_bid:
                        tot_r = round(0.5 * tp1_r + 0.5 * tp3_r, 3)
                        return {
                            "filled": True,
                            "fill_idx": fill_idx,
                            "exit_idx": j,
                            "exit_time": int(h1_candles[j]["time"]),
                            "outcome": "TP1_TP3_HIT",
                            "realized_r": tot_r,
                            "pnl_usd": round(tot_r * 100.0, 2),
                        }
                    if lj_bid <= tp2_trig_bid:
                        tp2_hit = True
                elif lj_bid <= be_lock_trig_bid:
                    be_armed = True
            else:
                runner_sl_bid = tp1_trig_bid if tp2_hit else (entry_chart - 0.15 * risk_dist - spread_price)
                if hj_bid >= runner_sl_bid:
                    leg2_r = tp2_r if tp2_hit else 0.15
                    tot_r = round(0.5 * tp1_r + 0.5 * leg2_r, 3)
                    out_lbl = "TP1_TP2_HIT" if tp2_hit else "TP1_BE_HIT"
                    return {
                        "filled": True,
                        "fill_idx": fill_idx,
                        "exit_idx": j,
                        "exit_time": int(h1_candles[j]["time"]),
                        "outcome": out_lbl,
                        "realized_r": tot_r,
                        "pnl_usd": round(tot_r * 100.0, 2),
                    }
                if lj_bid <= tp3_trig_bid:
                    tot_r = round(0.5 * tp1_r + 0.5 * tp3_r, 3)
                    return {
                        "filled": True,
                        "fill_idx": fill_idx,
                        "exit_idx": j,
                        "exit_time": int(h1_candles[j]["time"]),
                        "outcome": "TP1_TP3_HIT",
                        "realized_r": tot_r,
                        "pnl_usd": round(tot_r * 100.0, 2),
                    }
                if lj_bid <= tp2_trig_bid:
                    tp2_hit = True

    close_bid = float(h1_candles[end_idx]["close"])
    if direction == "BUY":
        s_shift = spread_price if order_type == "MARKET_CLOSE" else 0.0
        raw_r = (close_bid - (entry_chart + s_shift)) / risk_dist
    else:
        raw_r = (entry_chart - (close_bid + spread_price)) / risk_dist
    raw_r = float(np.clip(raw_r, -1.0, 3.0))

    if tp1_hit:
        leg2_r = max(0.15, raw_r) if not tp2_hit else max(tp2_r, raw_r)
        tot_r = round(0.5 * tp1_r + 0.5 * leg2_r, 3)
        out_lbl = "TP1_TP2_HIT" if tp2_hit else "TP1_TIME_WIN"
    else:
        tot_r = 0.15 if (be_armed and raw_r < 0.15) else round(raw_r, 3)
        out_lbl = "TIME_WIN" if tot_r > 0 else "TIME_LOSS"

    return {
        "filled": True,
        "fill_idx": fill_idx,
        "exit_idx": end_idx,
        "exit_time": int(h1_candles[end_idx]["time"]),
        "outcome": out_lbl,
        "realized_r": tot_r,
        "pnl_usd": round(tot_r * 100.0, 2),
    }


def run_forex_h4_h1_pair(symbol: str, forecaster: ProbabilisticContextForecaster) -> Dict[str, Any]:
    h1_candles = fetch_mt5_tf_history(symbol, mt5.TIMEFRAME_H1, count=16000)
    h4_candles = fetch_mt5_tf_history(symbol, mt5.TIMEFRAME_H4, count=5000)
    if not h1_candles or len(h1_candles) < 500:
        return {"symbol": symbol, "error": "Insufficient H1 data"}

    arrays = forecaster.prepare_causal_arrays(h1_candles, h4_candles)
    profile = forecast_calibrator.get_profile(symbol, "H4_M15")

    n_bars = len(h1_candles)
    start_idx = 250
    for idx in range(250, n_bars):
        if int(h1_candles[idx]["time"]) >= START_TS_2025:
            start_idx = idx
            break

    spread = REAL_BID_ASK_SPREAD.get(symbol, 0.00012)
    pip_size = SYMBOL_MAPPINGS.get(symbol, {}).get("pip_size", 0.0001)
    unit_val = USD_PER_LOT_PER_PRICE_UNIT.get(symbol, 100000.0)

    initial_balance = 10000.0
    bal_bid_ask = initial_balance
    bal_zero_spread = initial_balance
    peak_bal = initial_balance
    max_dd_usd = 0.0
    max_dd_pct = 0.0

    lots_list = []
    sl_pips_list = []
    trades = []
    unfilled_stop = 0
    whipsaws_vetoed = 0
    miss_tp_spread = 0
    early_sl_spread = 0

    playbook_stats = {
        "EMA21_TREND_IMPULSE": {"n": 0, "wins": 0, "gross_win": 0.0, "gross_loss": 0.0, "net_usd": 0.0},
        "STOCH_RSI_DIV_REVERSAL": {"n": 0, "wins": 0, "gross_win": 0.0, "gross_loss": 0.0, "net_usd": 0.0},
        "BB_FAKEOUT_STOP": {"n": 0, "wins": 0, "gross_win": 0.0, "gross_loss": 0.0, "net_usd": 0.0, "unfilled": 0},
    }

    busy_until_idx = -1

    for idx in range(start_idx, n_bars - 16):
        bar_ts = int(h1_candles[idx]["time"])
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
            timeframe_pair="H4_H1",
        )
        if not raw_setup.get("setup_triggered", False):
            continue
        if idx <= busy_until_idx:
            continue

        fc = forecaster.forecast_at_bar(
            h1_candles,
            h4_candles,
            curr_idx=idx,
            symbol=symbol,
            include_analogs=False,
            adaptive_profile=profile,
            timeframe_pair="H4_H1",
        )
        filt_setup = fc.get("suggested_setup", {})
        if not filt_setup.get("setup_triggered", False):
            whipsaws_vetoed += 1
            continue

        res_0 = simulate_h1_trade_with_bid_ask(filt_setup, h1_candles, idx, spread_price=0.0, max_hold_bars=28)
        res_ba = simulate_h1_trade_with_bid_ask(filt_setup, h1_candles, idx, spread_price=spread, max_hold_bars=28)
        busy_until_idx = res_ba["exit_idx"]

        strat_id = filt_setup.get("strategy_id", "EMA21_TREND_IMPULSE")
        if not res_ba["filled"]:
            unfilled_stop += 1
            if strat_id in playbook_stats and "unfilled" in playbook_stats[strat_id]:
                playbook_stats[strat_id]["unfilled"] += 1
            continue

        entry_p = float(filt_setup["entry"])
        sl_p = float(filt_setup["sl"])
        risk_dist = abs(entry_p - sl_p)
        sl_pips = risk_dist / pip_size
        lot_size = round(100.0 / (risk_dist * unit_val), 2)
        lots_list.append(lot_size)
        sl_pips_list.append(sl_pips)

        if res_0["outcome"].startswith("TP1") and not res_ba["outcome"].startswith("TP1"):
            miss_tp_spread += 1
        if res_0["realized_r"] > -1.0 and res_ba["realized_r"] == -1.0:
            early_sl_spread += 1

        pnl_0 = float(res_0["pnl_usd"])
        pnl_ba = float(res_ba["pnl_usd"])
        r_ba = float(res_ba["realized_r"])

        bal_zero_spread = round(bal_zero_spread + pnl_0, 2)
        bal_bid_ask = round(bal_bid_ask + pnl_ba, 2)

        if bal_bid_ask > peak_bal:
            peak_bal = bal_bid_ask
        dd_usd = round(peak_bal - bal_bid_ask, 2)
        dd_pct = round((dd_usd / peak_bal) * 100.0, 2) if peak_bal > 0 else 0.0
        if dd_usd > max_dd_usd:
            max_dd_usd = dd_usd
        if dd_pct > max_dd_pct:
            max_dd_pct = dd_pct

        if strat_id in playbook_stats:
            pb = playbook_stats[strat_id]
            pb["n"] += 1
            if r_ba > 0:
                pb["wins"] += 1
                pb["gross_win"] += pnl_ba
            elif r_ba < 0:
                pb["gross_loss"] += abs(pnl_ba)
            pb["net_usd"] = round(pb["net_usd"] + pnl_ba, 2)

        trades.append(
            {
                "trade_no": len(trades) + 1,
                "signal_short": dna_info["formatted_short"],
                "signal_full": dna_info["formatted_full"],
                "strategy_id": strat_id,
                "order_type": filt_setup.get("order_type", "MARKET_CLOSE"),
                "direction": filt_setup.get("direction", "BUY"),
                "lot_size": lot_size,
                "sl_pips": round(sl_pips, 1),
                "entry": entry_p,
                "sl": sl_p,
                "tp1": filt_setup.get("tp1"),
                "tp2": filt_setup.get("tp2"),
                "tp3": filt_setup.get("tp3"),
                "outcome": res_ba["outcome"],
                "realized_r": r_ba,
                "pnl_usd": pnl_ba,
                "balance_after": bal_bid_ask,
            }
        )

    total_t = len(trades)
    wins = sum(1 for t in trades if t["realized_r"] > 0)
    gw = sum(t["pnl_usd"] for t in trades if t["pnl_usd"] > 0)
    gl = abs(sum(t["pnl_usd"] for t in trades if t["pnl_usd"] < 0))
    wr_pct = round((wins / total_t) * 100.0, 1) if total_t > 0 else 0.0
    pf = round(gw / gl, 2) if gl > 0 else 9.99
    net_ba = round(bal_bid_ask - initial_balance, 2)
    net_0 = round(bal_zero_spread - initial_balance, 2)
    exp_r = round((net_ba / 100.0) / total_t, 2) if total_t > 0 else 0.0

    for k, pb in playbook_stats.items():
        n_p = pb["n"]
        pb["wr_pct"] = round((pb["wins"] / n_p) * 100.0, 1) if n_p > 0 else 0.0
        pb["pf"] = round(pb["gross_win"] / pb["gross_loss"], 2) if pb["gross_loss"] > 0 else (9.99 if pb["gross_win"] > 0 else 0.0)

    return {
        "symbol": symbol,
        "h1_bars_tested": n_bars - start_idx,
        "total_trades": total_t,
        "winrate_pct": wr_pct,
        "profit_factor": pf,
        "expectancy_r": exp_r,
        "avg_sl_pips": round(float(np.mean(sl_pips_list)), 1) if sl_pips_list else 0.0,
        "avg_lot": round(float(np.mean(lots_list)), 2) if lots_list else 0.0,
        "min_lot": round(float(np.min(lots_list)), 2) if lots_list else 0.0,
        "max_lot": round(float(np.max(lots_list)), 2) if lots_list else 0.0,
        "miss_tp_spread": miss_tp_spread,
        "early_sl_spread": early_sl_spread,
        "max_dd_usd": max_dd_usd,
        "max_dd_pct": max_dd_pct,
        "net_zero_spread_usd": net_0,
        "net_true_bid_ask_usd": net_ba,
        "final_balance_bid_ask": bal_bid_ask,
        "whipsaws_vetoed": whipsaws_vetoed,
        "unfilled_stop": unfilled_stop,
        "playbook_stats": playbook_stats,
        "sample_trades": trades[-4:],
    }


def main():
    forex_pairs = ["EURUSD", "GBPUSD", "USDCAD", "USDJPY", "GBPJPY"]
    forecaster = ProbabilisticContextForecaster(
        horizon_bars=8,
        k_neighbors=35,
        forecast_mode="COMBINED_HTF_LTF",
        macro_horizon_bars=6,
    )

    print("=" * 142)
    print(" 🌍 BÁO CÁO BACKTEST 5 CẶP FOREX TRÊN KHUNG H4 + H1 (01/01/2025 -> HIỆN TẠI) | VỐN: $10,000 | RỦI RO: $100/LỆNH | TRUE BID-ASK")
    print("=" * 142)
    print(
        f" {'Symbol':<7} | {'Nến H1':<6} | {'Số Lệnh':<7} | {'SL TB':<8} | {'Lot TB (Min..Max)':<19} | "
        f"{'WR%':<6} | {'PF':<5} | {'Max DD':<14} | {'Lãi (0 Spread)':<14} | {'Lãi (True Bid-Ask)'}"
    )
    print("-" * 142)

    all_reps = []
    for sym in forex_pairs:
        rep = run_forex_h4_h1_pair(sym, forecaster)
        all_reps.append(rep)
        lot_str = f"{rep['avg_lot']:.2f}L ({rep['min_lot']:.2f}..{rep['max_lot']:.2f}L)"
        dd_str = f"-${rep['max_dd_usd']:,.0f} ({rep['max_dd_pct']:.1f}%)"
        n0_str = f"{rep['net_zero_spread_usd']:+,.0f}$"
        nba_str = f"{rep['net_true_bid_ask_usd']:+,.0f}$ ({rep['net_true_bid_ask_usd']/100:+.1f}%)"
        print(
            f" {sym:<7} | {rep['h1_bars_tested']:<6d} | {rep['total_trades']:<7d} | {rep['avg_sl_pips']:>5.1f}p  | "
            f"{lot_str:<19} | {rep['winrate_pct']:>5.1f}% | {rep['profit_factor']:>5.2f} | {dd_str:<14} | "
            f"{n0_str:<14} | {nba_str}"
        )
        pb = rep["playbook_stats"]
        p1, p2, p3 = pb["EMA21_TREND_IMPULSE"], pb["STOCH_RSI_DIV_REVERSAL"], pb["BB_FAKEOUT_STOP"]
        print(
            f"   ├─ Nhiễu Bid/Ask: MissTP={rep['miss_tp_spread']} lệnh, EarlySL={rep['early_sl_spread']} lệnh | "
            f"[1] EMA21 H1: N={p1['n']:2d}, WR={p1['wr_pct']:4.1f}%, PF={p1['pf']:4.2f}, Lãi={p1['net_usd']:+,.0f}$"
        )
        print(
            f"   └─ [2] Stoch+RSI H1: N={p2['n']:2d}, WR={p2['wr_pct']:4.1f}%, PF={p2['pf']:4.2f}, Lãi={p2['net_usd']:+,.0f}$ | "
            f"[3] BB Fakeout Stop H1: N={p3['n']:2d} (Hủy {p3['unfilled']:2d} Stop), WR={p3['wr_pct']:4.1f}%, PF={p3['pf']:4.2f}, Lãi={p3['net_usd']:+,.0f}$"
        )

    print("=" * 142)
    with open(os.path.join("data", "backtest_forex_h4_h1_report.json"), "w", encoding="utf-8") as f:
        json.dump(all_reps, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
