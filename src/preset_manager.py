"""
Preset Manager for Simple DCA EA v1.40.
Reads MT5 .set presets, defines standard built-in presets, and translates them to EA Engine parameters.
"""

import os
import re
from typing import Dict, Any, List, Optional
from pathlib import Path

SIMULATOR_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = SIMULATOR_ROOT.parent
PRESETS_DIR = PROJECT_ROOT / "simple-dca" / "Presets"
MA_PROBABILISTIC_PRESETS_DIR = PROJECT_ROOT / "moving-average" / "presets" / "v3.0_probabilistic"


def parse_set_file(file_path: Path) -> Dict[str, Any]:
    """Parses MT5 .set parameter file."""
    params = {}
    if not file_path.exists():
        return params
        
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith(";") or line.startswith("#") or line.startswith("//"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.split("||")[0].split(";")[0].strip()  # Remove comments
                    params[k] = v
    except Exception as e:
        print(f"Error parsing .set file {file_path}: {e}")
        
    return params


def convert_set_to_ea_config(set_params: Dict[str, Any], preset_name: str = "") -> Dict[str, Any]:
    """Converts raw MT5 .set parameters into SimpleDCAEngine configuration."""
    # Step pips
    step_pips = float(set_params.get("InpFixedStepPips", 80.0))
    step_seq_str = set_params.get("InpCustomStepSequence", str(step_pips))
    try:
        step_seq = [float(x.strip()) for x in step_seq_str.split(",") if x.strip()]
    except Exception:
        step_seq = [step_pips]
        
    # Lot sequence
    lot_seq_str = set_params.get("InpCustomLotSequence", "0.01,0.02,0.03,0.04,0.05,0.06,0.07,0.08,0.09,0.10")
    try:
        lot_seq = [float(x.strip()) for x in lot_seq_str.split(",") if x.strip()]
    except Exception:
        lot_seq = [0.01, 0.02, 0.03, 0.04, 0.05]
        
    # TP sequence (pips from BE)
    tp_seq_str = set_params.get("InpCustomTPPipsSequence", "10,9,8,7,6,5,5,4,4,3,3")
    try:
        tp_seq = [float(x.strip()) for x in tp_seq_str.split(",") if x.strip()]
    except Exception:
        tp_pips = float(set_params.get("InpBasketTPPips", 10.0))
        tp_seq = [tp_pips]
        
    # Sliding window
    enable_sw = set_params.get("InpEnableSlidingWindowSL", "true").lower() in ("true", "1")
    max_active_orders = int(set_params.get("InpMaxActiveOrders", 3))
    max_orders_per_basket = int(set_params.get("InpMaxOrdersPerBasket", 10))
    
    # Direction: 0=BUY_ONLY, 1=SELL_ONLY, 2=HEDGING_DUAL
    dir_val = int(set_params.get("InpTradeDirection", 2))
    direction_map = {0: "BUY_ONLY", 1: "SELL_ONLY", 2: "HEDGING_DUAL"}
    direction = direction_map.get(dir_val, "HEDGING_DUAL")
    
    # First Order Trigger: 0=IMMEDIATE, 1=RSI, 2=BB
    trig_val = int(set_params.get("InpFirstOrderTrigger", 0))
    trig_map = {0: "IMMEDIATE", 1: "RSI", 2: "BB"}
    first_trigger = trig_map.get(trig_val, "IMMEDIATE")
    
    # RSI & BB filter
    rsi_period = int(set_params.get("InpRsiPeriod", 14))
    rsi_oversold = float(set_params.get("InpRsiOversold", 35.0))
    rsi_overbought = float(set_params.get("InpRsiOverbought", 65.0))
    enable_bb_filter = set_params.get("InpEnableBBDCAFilter", "true").lower() in ("true", "1")
    bb_period = int(set_params.get("InpBBPeriod", 20))
    bb_dev = float(set_params.get("InpBBDeviation", 2.0))
    
    return {
        "preset_name": preset_name,
        "direction": direction,
        "first_order_trigger": first_trigger,
        "step_pips": step_pips,
        "step_sequence": step_seq,
        "lot_sequence": lot_seq,
        "tp_sequence": tp_seq,
        "enable_sliding_window": enable_sw,
        "max_active_orders": max_active_orders,
        "max_orders_per_basket": max_orders_per_basket,
        "rsi_period": rsi_period,
        "rsi_oversold": rsi_oversold,
        "rsi_overbought": rsi_overbought,
        "enable_bb_filter": enable_bb_filter,
        "bb_period": bb_period,
        "bb_dev": bb_dev
    }


BUILTIN_PRESETS = {
    "v3.0_EMA21_Probabilistic_MacroKNN": {
        "preset_name": "v3.0 EMA21 Probabilistic Macro k-NN (Non-Lookahead)",
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
        "climax_tighten_r": 5.0
    },
    "v3.0_EMA21_Baseline_NoProbFilter": {
        "preset_name": "v3.0 EMA21 Baseline (No Prob Filter)",
        "engine_type": "EMA21_PROBABILISTIC",
        "use_prob_filter": False,
        "horizon_bars": 8,
        "k_neighbors": 35,
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
        "climax_tighten_r": 5.0
    },
    "v1.41_XAU_Linear_Max4Orders_Continuous": {
        "preset_name": "v1.41 XAU Linear Micro (Max 4 Orders, Continuous)",
        "direction": "HEDGING_DUAL",
        "first_order_trigger": "IMMEDIATE",
        "step_pips": 80.0,
        "step_sequence": [80.0],
        "lot_sequence": [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10, 0.11, 0.12, 0.13, 0.14, 0.15],
        "tp_sequence": [10.0, 8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 3.0, 3.0, 3.0, 3.0, 2.0, 2.0, 2.0, 2.0, 2.0],
        "enable_sliding_window": True,
        "max_active_orders": 4,
        "max_orders_per_basket": 15,
        "rsi_period": 14,
        "rsi_oversold": 35.0,
        "rsi_overbought": 65.0,
        "enable_bb_filter": True,
        "bb_period": 20,
        "bb_dev": 2.0,
        "aggregate_skipped_steps": False
    },
    "v1.41_XAU_Flat002_Max4Orders_Continuous": {
        "preset_name": "v1.41 XAU Flat 0.02 Lot (Max 4 Orders, Continuous)",
        "direction": "HEDGING_DUAL",
        "first_order_trigger": "IMMEDIATE",
        "step_pips": 80.0,
        "step_sequence": [80.0],
        "lot_sequence": [0.02, 0.02, 0.02, 0.02, 0.02, 0.02, 0.02, 0.02, 0.02, 0.02, 0.02, 0.02, 0.02, 0.02, 0.02],
        "tp_sequence": [10.0, 8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 3.0, 3.0, 3.0, 3.0, 2.0, 2.0, 2.0, 2.0, 2.0],
        "enable_sliding_window": True,
        "max_active_orders": 4,
        "max_orders_per_basket": 15,
        "rsi_period": 14,
        "rsi_oversold": 35.0,
        "rsi_overbought": 65.0,
        "enable_bb_filter": True,
        "bb_period": 20,
        "bb_dev": 2.0,
        "aggregate_skipped_steps": False
    },
    "v1.40_XAU_SlidingWindow_RSI_UltraFastScalp": {
        "preset_name": "v1.40 XAU Sliding Window RSI Ultra-Fast Scalp",
        "direction": "HEDGING_DUAL",
        "first_order_trigger": "RSI",
        "step_pips": 80.0,
        "step_sequence": [80.0],
        "lot_sequence": [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10],
        "tp_sequence": [10.0, 9.0, 8.0, 7.0, 6.0, 5.0, 5.0, 4.0, 4.0, 3.0, 3.0],
        "enable_sliding_window": True,
        "max_active_orders": 3,
        "max_orders_per_basket": 10,
        "rsi_period": 14,
        "rsi_oversold": 35.0,
        "rsi_overbought": 65.0,
        "enable_bb_filter": True,
        "bb_period": 20,
        "bb_dev": 2.0,
        "aggregate_skipped_steps": False
    },
    "v1.40_XAU_SlidingWindow_UltraFastVolume": {
        "preset_name": "v1.40 XAU Sliding Window Ultra-Fast Volume (Flat Lot)",
        "direction": "HEDGING_DUAL",
        "first_order_trigger": "IMMEDIATE",
        "step_pips": 80.0,
        "step_sequence": [80.0],
        "lot_sequence": [0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01],
        "tp_sequence": [10.0, 9.0, 8.0, 7.0, 6.0, 5.0, 5.0, 4.0, 4.0, 3.0, 3.0],
        "enable_sliding_window": True,
        "max_active_orders": 3,
        "max_orders_per_basket": 10,
        "rsi_period": 14,
        "rsi_oversold": 35.0,
        "rsi_overbought": 65.0,
        "enable_bb_filter": True,
        "bb_period": 20,
        "bb_dev": 2.0,
        "aggregate_skipped_steps": False
    },
    "v1.36_Scalper_1H_XAUUSD": {
        "preset_name": "v1.36 Scalper 1H XAUUSD",
        "direction": "HEDGING_DUAL",
        "first_order_trigger": "IMMEDIATE",
        "step_pips": 50.0,
        "step_sequence": [50.0],
        "lot_sequence": [0.01, 0.02, 0.03, 0.05, 0.08, 0.12],
        "tp_sequence": [15.0, 12.0, 10.0, 8.0, 6.0],
        "enable_sliding_window": False,
        "max_active_orders": 5,
        "max_orders_per_basket": 8,
        "rsi_period": 14,
        "rsi_oversold": 30.0,
        "rsi_overbought": 70.0,
        "enable_bb_filter": False,
        "bb_period": 20,
        "bb_dev": 2.0
    }
}


def convert_probabilistic_set_to_config(set_params: Dict[str, Any], preset_name: str = "") -> Dict[str, Any]:
    """Converts moving-average v3.0_probabilistic .set parameters into EMA21ProbabilisticSimulatorEngine config."""
    return {
        "preset_name": preset_name,
        "engine_type": "EMA21_PROBABILISTIC",
        "use_prob_filter": set_params.get("InpUseProbabilisticEngine", "true").lower() in ("true", "1"),
        "max_memory_bars": int(float(set_params.get("InpForecastMemoryBars", 1500))),
        "horizon_bars": int(float(set_params.get("InpForecastHorizonBars", 8))),
        "k_neighbors": int(float(set_params.get("InpKNNNeighbors", 35))),
        "up_barrier_atr": float(set_params.get("InpBarrierWinATR", 1.40)),
        "dn_barrier_atr": float(set_params.get("InpBarrierWinATR", 1.40)),
        "adverse_barrier_atr": float(set_params.get("InpBarrierStopATR", 1.00)),
        "max_sideway_prob_pct": float(set_params.get("InpMaxSidewayProbPct", 46.0)),
        "min_dir_prob_pct": float(set_params.get("InpMinDirectionalProbPct", 42.0)),
        "min_prob_edge_pct": float(set_params.get("InpMinProbEdgePct", 8.0)),
        "risk_percent": float(set_params.get("InpRiskPercent", 1.0)),
        "sl_lookback_bars": int(float(set_params.get("InpSLLookbackBars", 2))),
        "sl_padding_pips": float(set_params.get("InpSLPaddingPips", 3.5)),
        "min_sl_atr": float(set_params.get("InpMinSL_ATR", 0.80)),
        "max_sl_atr": float(set_params.get("InpMaxSL_ATR", 2.80)),
        "tp1_r": float(set_params.get("InpTP1_R", 1.0)),
        "tp2_r": float(set_params.get("InpTP2_R", 2.0)),
        "be_stage1_offset_r": float(set_params.get("InpBEStage1OffsetR", 0.0)),
        "ratchet_lock_r": float(set_params.get("InpRatchetLockR", 1.0)),
        "trail_structure_bars": int(float(set_params.get("InpTrailStructureBars", 4))),
        "trail_atr_mult": float(set_params.get("InpTrailingATRMult", 2.8)),
        "climax_tighten_r": float(set_params.get("InpClimaxTightenR", 5.0)),
        "adx_threshold": float(set_params.get("InpADXThreshold", 18.0)),
        "min_di_spread": float(set_params.get("InpMinDISpread", 2.5)),
        "max_pre_breakout_range_atr": float(set_params.get("InpMaxPreBreakoutRangeATR", 3.20)),
        "min_clv": float(set_params.get("InpMinCloseLocationValue", 0.62)),
    }


def get_all_presets() -> Dict[str, Dict[str, Any]]:
    """Loads all presets from moving-average/presets/v3.0_probabilistic, simple-dca/Presets and combines with built-ins."""
    presets = dict(BUILTIN_PRESETS)

    if MA_PROBABILISTIC_PRESETS_DIR.exists():
        for set_file in MA_PROBABILISTIC_PRESETS_DIR.glob("*.set"):
            key = f"v3.0_{set_file.stem}"
            try:
                raw_params = parse_set_file(set_file)
                if raw_params:
                    presets[key] = convert_probabilistic_set_to_config(raw_params, preset_name=f"v3.0 {set_file.stem}")
            except Exception as e:
                print(f"Error loading probabilistic preset {key}: {e}")

    if PRESETS_DIR.exists():
        for set_file in PRESETS_DIR.glob("*.set"):
            key = set_file.stem
            try:
                raw_params = parse_set_file(set_file)
                if raw_params:
                    converted = convert_set_to_ea_config(raw_params, preset_name=key)
                    presets[key] = converted
            except Exception as e:
                print(f"Error loading preset {key}: {e}")

    return presets
