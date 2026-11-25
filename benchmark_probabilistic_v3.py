r"""
Comprehensive Benchmark & Non-Lookahead Calibration Audit for:
ProbabilisticContextForecaster & EMA21ProbabilisticSimulatorEngine (v3.0)
in D:\PROJECT\TRADING\trading-simulator
"""

import os
import sys
import json
import time
from datetime import datetime, timezone

SIM_ROOT = r"D:\PROJECT\TRADING\trading-simulator"
if SIM_ROOT not in sys.path:
    sys.path.insert(0, SIM_ROOT)

from src.data_fetcher import DATA_DIR, resample_candles, fetch_mt5_history, get_symbol_dataset
from src.probabilistic_context_engine import ProbabilisticContextForecaster, EMA21ProbabilisticSimulatorEngine
from src.simulation_engine import TradeSimulator
from src.server import app, get_state, get_current_forecast, run_forecast_backtest, ForecastBacktestRequest


def load_or_fetch_dataset(symbol: str, exec_tf: str, macro_tf: str):
    """Loads cached JSON in trading-simulator/data or fetches from MT5."""
    tf_seconds = {"M5": 300, "M15": 900, "H1": 3600, "H4": 14400, "D1": 86400}
    macro_sec = tf_seconds.get(macro_tf, 14400)

    local_file = os.path.join(DATA_DIR, f"{symbol}_{exec_tf}.json")
    sub_candles = []
    source_tag = ""

    if os.path.exists(local_file):
        with open(local_file, "r", encoding="utf-8") as f:
            sub_candles = json.load(f)
        # Keep most recent 6000 bars if huge (e.g. GBPUSD_H1 has 15MB / 140k bars since 2000)
        if len(sub_candles) > 6000:
            sub_candles = sub_candles[-6000:]
        source_tag = f"trading-simulator/data/{symbol}_{exec_tf}.json ({len(sub_candles)} bars)"

    if not sub_candles:
        sub_candles = fetch_mt5_history(symbol, timeframe_str=exec_tf, count=5000)
        if sub_candles:
            source_tag = f"MT5 Live Terminal {symbol} {exec_tf} ({len(sub_candles)} bars)"

    if not sub_candles:
        ds = get_symbol_dataset(symbol, timeframe_pair="H4_M15" if exec_tf != "M5" else "H1_M5", count=4000)
        sub_candles = ds.get("sub_candles", [])
        source_tag = f"Simulator Dataset {symbol} {exec_tf} ({len(sub_candles)} bars)"

    macro_candles = resample_candles(sub_candles, target_seconds=macro_sec)
    return sub_candles, macro_candles, source_tag


def main():
    print("=" * 110)
    print(" 1. VERIFYING TRADING-SIMULATOR API & NON-LOOKAHEAD INVARIANT")
    print("=" * 110)

    sim = TradeSimulator(initial_balance=10000.0)
    xau_m5, xau_h1, _ = load_or_fetch_dataset("XAUUSD", "M5", "H1")
    sim.load_dataset("XAUUSD", xau_m5, xau_h1, timeframe_pair="H1_M5", exec_tf="M5", macro_tf="H1")

    vis = sim.get_visible_candles()
    fc_live = vis.get("probabilistic_forecast", {})
    assert fc_live.get("non_lookahead_verified") is True, "Non-lookahead check failed!"
    print(
        f"[OK] TradeSimulator.get_visible_candles() -> Index={sim.current_m15_index} | "
        f"UP={fc_live['prob_up_pct']}% | SW={fc_live['prob_sideway_pct']}% | DN={fc_live['prob_down_pct']}% | "
        f"HTF={fc_live['macro_regime']} | Wave={fc_live['expected_wave_atr']} ATR | Action={fc_live['action']} | "
        f"Non-Lookahead={fc_live['non_lookahead_verified']}"
    )

    # Step forward 5 bars and verify dynamic update
    sim.step_forward(5)
    fc_step = sim.get_current_probabilistic_forecast()
    assert fc_step.get("non_lookahead_verified") is True
    print(
        f"[OK] After step_forward(5) -> Index={sim.current_m15_index} | "
        f"UP={fc_step['prob_up_pct']}% | SW={fc_step['prob_sideway_pct']}% | DN={fc_step['prob_down_pct']}% | "
        f"Analogs={len(fc_step['top_analogs'])} (Max analog bar={max(a['bar_index'] for a in fc_step['top_analogs'])} <= {sim.current_m15_index - 8})"
    )

    test_matrix = [
        ("XAUUSD", "M5", "H1"),
        ("XAUUSD", "M15", "H4"),
        ("EURUSD", "M15", "H4"),
        ("GBPUSD", "H1", "H4"),
        ("XAUUSD", "H1", "H4"),
        ("EURUSD", "H1", "H4"),
        ("USDCAD", "H1", "H4"),
        ("USDJPY", "H1", "H4"),
    ]

    rows = []
    print("\n" + "=" * 110)
    print(" 2. RUNNING NON-LOOKAHEAD PROBABILISTIC vs BASELINE EMA21 BENCHMARK ACROSS DATASETS")
    print("=" * 110)

    for sym, exec_tf, macro_tf in test_matrix:
        t0 = time.time()
        sub_c, macro_c, src_tag = load_or_fetch_dataset(sym, exec_tf, macro_tf)
        if not sub_c or len(sub_c) < 300:
            continue

        engine = EMA21ProbabilisticSimulatorEngine(symbol=sym, initial_balance=10000.0)
        report = engine.fast_backtest(sub_c, macro_c)
        elapsed = time.time() - t0

        comp = report["baseline_comparison"]
        cal = report["calibration"]
        b50 = cal["confidence_buckets"]["50_plus"]
        b55 = cal["confidence_buckets"]["55_plus"]
        b60 = cal["confidence_buckets"]["60_plus"]

        print(
            f"[{sym} {exec_tf}/{macro_tf}] ({len(sub_c)} bars, {elapsed:.2f}s) | "
            f"Baseline: Net ${comp['baseline_net_profit']:>+8.2f} (PF {comp['baseline_profit_factor']:.2f}, DD {comp['baseline_max_dd_pct']:.2f}%, {comp['baseline_signals']} sig) -> "
            f"Prob v3.0: Net ${comp['prob_net_profit']:>+8.2f} (PF {comp['prob_profit_factor']:.2f}, DD {comp['prob_max_dd_pct']:.2f}%, {comp['prob_signals']} sig, -{comp['whipsaws_filtered']} whipsaws) | "
            f"Cal >=55% Non-Adverse: {b55['non_adverse_survival_pct']:.1f}% (Wave {b55['realized_favorable_wave_atr']:.2f} ATR)"
        )

        rows.append(
            {
                "symbol": sym,
                "exec_tf": exec_tf,
                "macro_tf": macro_tf,
                "bars": len(sub_c),
                "source": src_tag,
                "comp": comp,
                "cal": cal,
                "latest_fc": report["latest_forecast"],
                "start_dt": datetime.fromtimestamp(sub_c[0]["time"], tz=timezone.utc).strftime("%Y-%m-%d"),
                "end_dt": datetime.fromtimestamp(sub_c[-1]["time"], tz=timezone.utc).strftime("%Y-%m-%d"),
            }
        )

    # Generate Markdown Report
    md_lines = [
        "# Non-Lookahead Probabilistic Context & Wave Forecaster Engine (v3.0) — Benchmark & Calibration Report",
        "",
        "## 1. Architecture & 100% Non-Lookahead Mathematical Proof",
        "- **Module**: [`D:\\PROJECT\\TRADING\\trading-simulator\\src\\probabilistic_context_engine.py`](file:///D:/PROJECT/TRADING/trading-simulator/src/probabilistic_context_engine.py)",
        "- **Simulator Integration**: [`D:\\PROJECT\\TRADING\\trading-simulator\\src\\simulation_engine.py`](file:///D:/PROJECT/TRADING/trading-simulator/src/simulation_engine.py) & [`D:\\PROJECT\\TRADING\\trading-simulator\\src\\server.py`](file:///D:/PROJECT/TRADING/trading-simulator/src/server.py)",
        "- **Frontend Live HUD**: [`D:\\PROJECT\\TRADING\\trading-simulator\\static\\index.html`](file:///D:/PROJECT/TRADING/trading-simulator/static/index.html) & [`D:\\PROJECT\\TRADING\\trading-simulator\\static\\js\\app.js`](file:///D:/PROJECT/TRADING/trading-simulator/static/js/app.js)",
        "",
        "### Strict Causal Memory Bank Invariant",
        "At any replay or backtest bar index `curr_idx`, a historical sample $s$ is eligible for the $k$-NN analog pool **if and only if**:",
        "$$s + H \\le \\text{curr\\_idx} \\quad (H = 8 \\text{ bars})$$",
        "1. **Feature Vector $\\mathbf{X}_s$** uses only closed bars $[0 \\dots s]$ (`er_20`, `squeeze_4`, `impulse_clv`, `ema21_slope_atr`, `ema_stack_atr`) plus the most recent **already-closed** Macro HTF candle ($t_{\\text{macro}} + \\Delta_{\\text{macro}} \\le t_s$).",
        "2. **Triple-Barrier Outcome $Y_s \\in \\{\\text{UP}, \\text{DOWN}, \\text{SIDEWAY}\\}$** over $[s+1 \\dots s+H]$ uses only bars $\\le s+H \\le \\text{curr\\_idx}$. Zero future bars ($> \\text{curr\\_idx}$) can ever enter the feature scaler or neighbor pool.",
        "",
        "---",
        "",
        "## 2. Direct A/B Benchmark: Baseline EMA21 (No Prob Filter) vs Probabilistic Context Engine v3.0",
        "",
        "| Dataset (`Symbol TF/Macro`) | Date Range | Bars | Baseline Net ($) | Baseline PF | Baseline WR% | Baseline MaxDD% | Baseline Setups | **Prob v3.0 Net ($)** | **Prob v3.0 PF** | **Prob v3.0 WR%** | **Prob v3.0 MaxDD%** | **Prob Setups** | **Whipsaws Vetoed** |",
        "| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]

    for r in rows:
        c = r["comp"]
        md_lines.append(
            f"| **{r['symbol']} {r['exec_tf']}/{r['macro_tf']}** | `{r['start_dt']}..{r['end_dt']}` | {r['bars']} | "
            f"${c['baseline_net_profit']:>+9.2f} | {c['baseline_profit_factor']:.2f} | {c['baseline_win_rate']:.1f}% | {c['baseline_max_dd_pct']:.2f}% | {c['baseline_signals']} | "
            f"**${c['prob_net_profit']:>+9.2f}** | **{c['prob_profit_factor']:.2f}** | **{c['prob_win_rate']:.1f}%** | **{c['prob_max_dd_pct']:.2f}%** | **{c['prob_signals']}** | "
            f"**-{c['whipsaws_filtered']} ({round(100.0 * c['whipsaws_filtered'] / max(1, c['baseline_signals']), 1)}%)** |"
        )

    md_lines.extend(
        [
            "",
            "---",
            "",
            "## 3. Out-of-Sample Probabilistic Forecast Calibration Audit (`H = 8` Bars)",
            "",
            "| Dataset (`Symbol TF/Macro`) | Audited Bars | Sideway Calls | Sideway Accuracy | `>=50%` Exact TB Win% | `>=50%` Non-Adverse% | `>=55%` Exact TB Win% | `>=55%` Non-Adverse% | `>=60%` Non-Adverse% | Realized Wave (`>=55%`) |",
            "| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )

    for r in rows:
        cal = r["cal"]
        b50 = cal["confidence_buckets"]["50_plus"]
        b55 = cal["confidence_buckets"]["55_plus"]
        b60 = cal["confidence_buckets"]["60_plus"]
        md_lines.append(
            f"| **{r['symbol']} {r['exec_tf']}/{r['macro_tf']}** | {cal['total_bars_audited']} | {cal['sideway_regime_calls']} | "
            f"**{cal['sideway_accuracy_pct']:.1f}%** | {b50['exact_triple_barrier_win_pct']:.1f}% | **{b50['non_adverse_survival_pct']:.1f}%** | "
            f"{b55['exact_triple_barrier_win_pct']:.1f}% | **{b55['non_adverse_survival_pct']:.1f}%** | "
            f"**{b60['non_adverse_survival_pct']:.1f}%** | **{b55['realized_favorable_wave_atr']:.2f} ATR** |"
        )

    md_lines.extend(
        [
            "",
            "---",
            "",
            "## 4. Sample Live Forecast Output (`/api/state` & `/api/forecast/current`)",
            "```json",
            json.dumps(fc_step, indent=2),
            "```",
        ]
    )

    report_content = "\n".join(md_lines) + "\n"

    out_paths = [
        r"D:\PROJECT\TRADING\moving-average\Report\moving-average\TRADING_SIMULATOR_PROBABILISTIC_REPORT.md",
        r"D:\PROJECT\TRADING\mt5-tester\Report\moving-average\TRADING_SIMULATOR_PROBABILISTIC_REPORT.md",
    ]
    for p in out_paths:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(report_content)
        print(f"[SAVED REPORT] -> {p}")


if __name__ == "__main__":
    main()
