"""
Standalone Real-Time Strategic Quantitative Forecast Radar ("Quân Sư Chiến Lược Realtime")
Operates OUTSIDE the Replay Simulator:
- Connects directly to live MT5 Terminal (or Yahoo Finance / Binance Live API fallback).
- Executes Dual-Tier Combined Forecast + 3-Layer Adaptive Self-Improvement Profile:
    * Tier 1: Macro HTF Anchor (H4 or H1 k-NN) -> Adaptive Weight (default 70%)
    * Tier 2: Micro LTF Trigger (M15 or M5) -> Adaptive Weight (default 30%)
    * Tier 3: Continuous SQLite Ledger Recording, Auto-Reconciliation & Champion vs Challenger Self-Calibration
- Enforces AGENTS.md rules:
    * Dual Time Display: Server Time (MT5) & Vietnam Time (UTC+7)
    * 5-Year DNA Session Filter (Golden Window vs Forbidden Zone vs Silent Mode 22:00-07:00 VN)
    * Optional Windows Desktop Toast Notification when ALIGNED setups appear.
"""

import argparse
import time
import sys
from datetime import datetime, timezone

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from src.data_fetcher import fetch_realtime_dataset
from src.probabilistic_context_engine import (
    ProbabilisticContextForecaster,
    evaluate_dna_session_and_time,
)
from src.forecast_evaluator import forecast_calibrator


def send_windows_toast(title: str, message: str) -> None:
    """Sends a native Windows Desktop Toast Notification using PowerShell (zero extra dependencies)."""
    try:
        import subprocess
        ps_script = f"""
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
        $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
        $textNodes = $template.GetElementsByTagName("text")
        $textNodes.Item(0).AppendChild($template.CreateTextNode("{title}")) | Out-Null
        $textNodes.Item(1).AppendChild($template.CreateTextNode("{message}")) | Out-Null
        $toast = [Windows.UI.Notifications.ToastNotification]::new($template)
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("QuanSuChienLuoc").Show($toast)
        """
        subprocess.Popen(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def run_radar_scan(
    symbols: list[str],
    timeframe_pair: str = "H4_M15",
    forecast_mode: str = "COMBINED_HTF_LTF",
    enable_toast: bool = False,
    run_calibration: bool = False,
) -> list[dict]:
    now_ts = int(datetime.now(timezone.utc).timestamp())
    header_dna = evaluate_dna_session_and_time("XAUUSD", now_ts, is_mt5_server_ts=False)

    tf_pair = timeframe_pair.upper().strip()
    is_m5 = tf_pair == "H1_M5"
    is_h1 = tf_pair == "H4_H1"
    macro_tf = "H1" if is_m5 else "H4"
    exec_tf = "M5" if is_m5 else ("H1" if is_h1 else "M15")

    forecaster = ProbabilisticContextForecaster(
        horizon_bars=8,
        k_neighbors=35,
        forecast_mode=forecast_mode,
        macro_horizon_bars=6,
    )

    if run_calibration:
        print("\n" + "=" * 126)
        print(f" 🧠 VÒNG LẶP TỰ HỌC & ĐẤU LOẠI CHAMPION vs CHALLENGER (3-LAYER ADAPTIVE CALIBRATION) | Khung: {tf_pair}")
        print(f" 🕒 Thời gian kiểm định: {header_dna['formatted_full']}")
        print("=" * 126)
        print(
            f" {'Cặp Tiền':<8} | {'Phiên Bản':<20} | {'Kết Quả Đấu Loại':<32} | "
            f"{'Trust Score (Trước -> Sau)':<26} | {'Setup WR% -> Sau':<18} | {'Kỳ Vọng R'}"
        )
        print("-" * 126)
        for sym in symbols:
            ds = fetch_realtime_dataset(sym, timeframe_pair=tf_pair, count=2500)
            sub_c = ds.get("sub_candles", [])
            mac_c = ds.get("macro_candles", [])
            if not sub_c or len(sub_c) < 220:
                continue
            rep = forecast_calibrator.run_adaptive_calibration_cycle(
                forecaster=forecaster,
                symbol=sym,
                timeframe_pair=tf_pair,
                sub_candles=sub_c,
                macro_candles=mac_c,
            )
            b_m = rep["before_metrics"]
            a_m = rep["after_metrics"]
            ver_str = f"{rep['version_before']} -> {rep['version_after']}"
            status_str = "🏆 THĂNG HẠNG CHALLENGER" if rep["promoted"] else "🛡️ GIỮ NGUYÊN CHAMPION"
            trust_str = f"{b_m['composite_score']:5.1f} -> {a_m['composite_score']:5.1f}/100"
            wr_str = f"{b_m['setup_winrate_pct']:4.1f}% -> {a_m['setup_winrate_pct']:4.1f}%"
            r_str = f"{b_m['expectancy_r']:+4.2f}R -> {a_m['expectancy_r']:+4.2f}R"
            print(f" {sym:<8} | {ver_str:<20} | {status_str:<32} | {trust_str:<26} | {wr_str:<18} | {r_str}")
        print("=" * 126 + "\n")

    print("\n" + "=" * 126)
    print(f" 📡 QUÂN SƯ CHIẾN LƯỢC REALTIME RADAR | {macro_tf} ANCHOR + {exec_tf} TRIGGER + 3-IN-1 ACCURACY SCORECARD | Mode: {forecast_mode}")
    print(f" 🕒 Thời gian quét: {header_dna['formatted_full']}")
    print("=" * 126)
    print(
        f" {'Cặp Tiền':<8} | {'Thời Gian (Server / VN)':<23} | "
        f"{'Tầng 1 (' + macro_tf + ')':<16} | {'Combine HTF+LTF':<16} | {'Độ Tin Cậy (Trust / WR)':<25} | {'Plan (Entry / SL / TP1)'}"
    )
    print("-" * 126)

    scan_results = []
    for sym in symbols:
        ds = fetch_realtime_dataset(sym, timeframe_pair=tf_pair, count=2000)
        sub_c = ds.get("sub_candles", [])
        mac_c = ds.get("macro_candles", [])
        if not sub_c or len(sub_c) < 100:
            continue

        # Ensure Walk-Forward audit is populated & reconcile matured forecasts
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
            forecast_mode=forecast_mode,
            timeframe_pair=tf_pair,
        )
        # Record live forecast into SQLite ledger ONLY if a Quantitative Strategy Setup genuinely triggered on this bar
        st = fc.get("suggested_setup") or {}
        if st.get("setup_triggered"):
            forecast_calibrator.record_forecast(
                sym, tf_pair, int(sub_c[-1]["time"]), fc, source_mode="LIVE"
            )

        dna = fc.get("dna_session") or evaluate_dna_session_and_time(sym, sub_c[-1]["time"])
        t2 = scorecard.get("tier2_tactical_setup") or {}
        t1 = scorecard.get("tier1_probabilistic") or {}

        m_str = f"U:{fc['macro_prob_up_pct']:4.1f}% D:{fc['macro_prob_down_pct']:4.1f}%"
        c_str = f"U:{fc['prob_up_pct']:4.1f}% D:{fc['prob_down_pct']:4.1f}%"
        tac_str = fc.get("tactical_status", "NEUTRAL")
        n_samp = t2.get("evaluated_setups_count", 0)
        pf_val = t2.get("profit_factor", 1.0)
        trust_str = f"{scorecard['trust_score']:4.1f}/100 (N={n_samp} WR:{t2.get('setup_winrate_pct', 0):4.1f}%)"
        ord_lbl = st.get("order_type", "MKT")
        lot_str = f"{st.get('lot_size_100usd', 0.1):.2f}L/{st.get('sl_pips', 0):.0f}p"
        plan_str = f"{st.get('direction', '--'):<4} ({ord_lbl}) @{st.get('entry', '--')} | SL:{st.get('sl', '--')} ({lot_str}) | TP1:{st.get('tp1', '--')}"

        print(
            f" {sym:<8} | {dna['formatted_short']:<23} | "
            f"{m_str:<16} | {c_str:<16} | {trust_str:<27} | {plan_str}"
        )
        print(
            f"   └─ [{fc.get('model_version', 'v3.0')}] {fc.get('tactical_badge', '')} | "
            f"PF:{pf_val:.2f} | Exp:{t2.get('expectancy_r', 0):+.2f}R | Brier:{t1.get('brier_score', 0.2):.3f} | {dna['session_badge']}"
        )

        if enable_toast and dna["session_status"] != "SILENT_MODE" and "ALIGNED" in tac_str:
            send_windows_toast(
                f"⚡ {sym} [{macro_tf}+{exec_tf}] {st.get('direction', '')} (Trust {scorecard['trust_score']}/100)",
                f"{dna['formatted_short']} | {fc.get('tactical_badge', '')} | Entry: {st.get('entry')} SL: {st.get('sl')} TP1: {st.get('tp1')}",
            )

        scan_results.append({"symbol": sym, "forecast": fc, "dna": dna, "scorecard": scorecard})

    print("=" * 126 + "\n")
    return scan_results


def run_self_learning_benchmark_cli(symbols: List[str], timeframe_pair: str = "H4_M15") -> None:
    """
    Runs the 4-Pillar Self-Learning Meta-Evaluation Benchmark across `symbols` and prints a detailed audit table.
    """
    if timeframe_pair == "H1_M5":
        macro_tf, exec_tf = "H1", "M5"
    else:
        macro_tf, exec_tf = "H4", "M15"

    forecaster = ProbabilisticContextForecaster(
        horizon_bars=8,
        k_neighbors=35,
        forecast_mode="COMBINED_HTF_LTF",
        macro_horizon_bars=6,
    )

    print("\n" + "=" * 126)
    print(f"🧪 BẢNG KIỂM ĐỊNH KHẢ NĂNG TỰ HỌC 4 TRỤ CỘT (4-PILLAR SELF-LEARNING BENCHMARK) | [{macro_tf}+{exec_tf}]")
    print("=" * 126)
    print(
        f" {'Symbol':<8} | {'Phiên Bản':<14} | {'Trust (Gốc -> Học)':<22} | "
        f"{'WR% (Gốc -> Học)':<20} | {'Exp R (Gốc -> Học)':<20} | {'Chặng Thắng':<11} | {'Giữ Phong Độ OOS':<16}"
    )
    print("-" * 126)

    for sym in symbols:
        ds = fetch_realtime_dataset(sym, timeframe_pair=timeframe_pair, count=2500)
        sub_c = ds.get("sub_candles", [])
        mac_c = ds.get("macro_candles", [])
        if not sub_c or len(sub_c) < 220:
            continue
        bench = forecast_calibrator.evaluate_self_learning_benchmark(
            forecaster, sym, timeframe_pair, sub_c, mac_c
        )
        p1 = bench["pillar1_oos_gain"]
        p3 = bench["pillar3_generalization"]
        p4 = bench["pillar4_learned_dna"]

        t_str = f"{p1['baseline_trust']:4.1f} -> {p1['adaptive_trust']:4.1f} ({p1['delta_trust']:+.1f})"
        w_str = f"{p1['baseline_wr_pct']:4.1f}% -> {p1['adaptive_wr_pct']:4.1f}% ({p1['delta_wr_pct']:+.1f}%)"
        r_str = f"{p1['baseline_exp_r']:+.2f}R -> {p1['adaptive_exp_r']:+.2f}R ({p1['delta_exp_r']:+.2f}R)"
        ret_str = f"{p3['oos_retention_pct']:5.1f}% ({p3['overfit_status'].split(' ')[0]})"

        print(
            f" {sym:<8} | {bench['active_version']:<14} | {t_str:<22} | "
            f"{w_str:<20} | {r_str:<20} | {bench['folds_won_ratio']:<11} | {ret_str:<16}"
        )
        print(
            f"   ├─ Xếp hạng tự học: {bench['learning_grade']} | Đặc trưng trội nhất: {p4['top_discriminative_feature']} | Tỷ trọng: {p4['htf_ltf_blend']} (k={p4['k_neighbors']})"
        )
        folds_line = " | ".join(
            [
                f"{f['fold_name'].split(' ')[0]} {f['fold_name'].split(' ')[1]}: {f['baseline_trust']:.1f}->{f['adaptive_trust']:.1f} ({f['delta_trust']:+.1f})"
                for f in bench["pillar2_rolling_folds"]
            ]
        )
        print(f"   └─ Đường cong 3 chặng OOS: {folds_line}")
    print("=" * 126 + "\n")

    print("\n" + "=" * 126)
    print(f"📊 BẢNG KIỂM ĐỊNH ĐỊNH LƯỢNG 3 CHIẾN LƯỢC CÓ EDGE (QUANTITATIVE STRATEGY EDGE AUDIT) | [{macro_tf}+{exec_tf}]")
    print("=" * 126)
    print(
        f" {'Symbol':<8} | {'Số Nến Quét':<12} | {'Tổng Mẫu (Thô -> Lọc)':<22} | "
        f"{'Winrate% (Thô -> Lọc)':<22} | {'Profit Factor (PF)':<20} | {'Kỳ Vọng E[R]':<16} | {'Tổng Lãi R'}"
    )
    print("-" * 126)

    for sym in symbols:
        ds = fetch_realtime_dataset(sym, timeframe_pair=timeframe_pair, count=2500)
        sub_c = ds.get("sub_candles", [])
        mac_c = ds.get("macro_candles", [])
        if not sub_c or len(sub_c) < 220:
            continue
        edge = forecast_calibrator.audit_quantitative_strategy_edge(
            forecaster, sym, timeframe_pair, sub_c, mac_c
        )
        tr = edge["total_raw"]
        tf = edge["total_filtered"]
        pb = edge["playbooks"]

        n_str = f"N={tr['n']:3d} -> N={tf['n']:3d} (-{edge['whipsaws_vetoed']})"
        wr_str = f"{tr['wr_pct']:4.1f}% -> {tf['wr_pct']:4.1f}%"
        pf_str = f"{tr['pf']:4.2f} -> {tf['pf']:4.2f}"
        exp_str = f"{tr['exp_r']:+.2f}R -> {tf['exp_r']:+.2f}R"
        net_str = f"{tf['net_r']:+6.1f}R"

        print(
            f" {sym:<8} | {edge['bars_scanned']:<12d} | {n_str:<22} | "
            f"{wr_str:<22} | {pf_str:<20} | {exp_str:<16} | {net_str}"
        )
        p1_f = pb["EMA21_TREND_IMPULSE"]["filtered"]
        p2_f = pb["STOCH_RSI_DIV_REVERSAL"]["filtered"]
        p3_f = pb["BB_FAKEOUT_STOP"]["filtered"]
        p3_un = pb["BB_FAKEOUT_STOP"]["unfilled_stop_cancelled"]
        print(
            f"   ├─ [1] EMA21 Impulse: N={p1_f['n']:2d}, WR={p1_f['wr_pct']:4.1f}%, PF={p1_f['pf']:4.2f}, E={p1_f['exp_r']:+.2f}R | "
            f"[2] Stoch+RSI Div: N={p2_f['n']:2d}, WR={p2_f['wr_pct']:4.1f}%, PF={p2_f['pf']:4.2f}, E={p2_f['exp_r']:+.2f}R"
        )
        print(
            f"   └─ [3] BB(20,2) Fakeout Stop: N={p3_f['n']:2d} khớp (Đã lọc {p3_un:2d} lệnh Stop không khớp), "
            f"WR={p3_f['wr_pct']:4.1f}%, PF={p3_f['pf']:4.2f}, E={p3_f['exp_r']:+.2f}R"
        )
        if edge["recent_verified_samples"]:
            for s_idx, last_s in enumerate(edge["recent_verified_samples"][-2:], 1):
                print(
                    f"      🎯 Mẫu #{s_idx}: [{last_s['server_vn_time']}] {last_s['strategy_id']} ({last_s['order_type']}) "
                    f"{last_s['direction']} @{last_s['entry']} | SL:{last_s['sl']} TP1:{last_s['tp1']} -> {last_s['outcome']} ({last_s['realized_r']:+.2f}R)"
                )
    print("=" * 126 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Standalone Real-Time HTF+LTF Strategic Forecast Radar & Self-Calibrator")
    parser.add_argument(
        "--symbols",
        type=str,
        default="XAUUSD,EURUSD,GBPUSD,USDCAD,USDJPY,GBPJPY,BTCUSD",
        help="Comma-separated list of symbols",
    )
    parser.add_argument(
        "--tf",
        type=str,
        default="H4_M15",
        choices=["H4_M15", "H4_H1", "H1_M5"],
        help="Timeframe pair: H4_M15 (Macro H4 + Trigger M15), H4_H1 (Macro H4 + Trigger H1 Forex Majors), or H1_M5",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="COMBINED_HTF_LTF",
        choices=["COMBINED_HTF_LTF", "HTF_ANCHOR_ONLY", "LTF_MICRO_ONLY"],
        help="Forecast weighting mode",
    )
    parser.add_argument(
        "--calibrate",
        action="store_true",
        help="Run 3-Layer Bounded Self-Improvement (Champion vs Challenger) before scanning",
    )
    parser.add_argument(
        "--eval-learning",
        action="store_true",
        help="Run 4-Pillar Self-Learning Meta-Evaluation Benchmark (Pre vs Post Learning Curve)",
    )
    parser.add_argument(
        "--loop",
        type=int,
        default=0,
        help="Continuous polling interval in seconds (0 = run once and exit)",
    )
    parser.add_argument(
        "--notify",
        action="store_true",
        help="Enable Windows Desktop Toast Notifications on ALIGNED setups (respects 07:00-22:00 VN Silent Mode)",
    )
    args = parser.parse_args()
    sym_list = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]

    if args.loop <= 0:
        run_radar_scan(
            sym_list,
            timeframe_pair=args.tf,
            forecast_mode=args.mode,
            enable_toast=args.notify,
            run_calibration=args.calibrate,
        )
        if args.eval_learning:
            run_self_learning_benchmark_cli(sym_list, timeframe_pair=args.tf)
    else:
        print(f"🔄 Đang chạy Radar Realtime liên tục mỗi {args.loop} giây (Nhấn Ctrl+C để dừng)...")
        first_iter = True
        try:
            while True:
                run_radar_scan(
                    sym_list,
                    timeframe_pair=args.tf,
                    forecast_mode=args.mode,
                    enable_toast=args.notify,
                    run_calibration=(args.calibrate and first_iter),
                )
                first_iter = False
                time.sleep(max(5, args.loop))
        except KeyboardInterrupt:
            print("\n🛑 Đã dừng Radar Realtime.")
            sys.exit(0)


if __name__ == "__main__":
    main()
