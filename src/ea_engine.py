"""
Simple DCA EA Engine (v1.40 Sliding Window & Basket Grid) for Python Trading Simulator.
Accurately replicates MQL5 Simple DCA EA execution with Dual Timeframe (H1 Filter + M5 Sub-bar Execution).
"""

from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import copy
from .data_fetcher import SYMBOL_MAPPINGS
from .preset_manager import BUILTIN_PRESETS, get_all_presets


class SimpleDCAEngine:
    def __init__(self, symbol: str = "XAUUSD", config: Optional[Dict[str, Any]] = None, initial_balance: float = 10000.0):
        self.symbol = symbol
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.equity = initial_balance
        self.peak_equity = initial_balance
        self.max_drawdown_usd = 0.0
        self.max_drawdown_pct = 0.0
        
        # Load config or default to v1.41 Linear Micro (Max 4 Orders, Continuous)
        default_cfg = BUILTIN_PRESETS.get("v1.41_XAU_Linear_Max4Orders_Continuous", BUILTIN_PRESETS["v1.40_XAU_SlidingWindow_RSI_UltraFastScalp"])
        self.config = dict(default_cfg)
        if config:
            self.config.update(config)
            
        self._init_symbol_info()
        self.reset(initial_balance)

    def _init_symbol_info(self):
        sym_info = SYMBOL_MAPPINGS.get(self.symbol, {"digits": 2, "pip_size": 0.1})
        self.digits = sym_info.get("digits", 2)
        self.pip_size = sym_info.get("pip_size", 0.1)
        
        if "XAU" in self.symbol or "GOLD" in self.symbol:
            self.contract_size = 100.0
            self.usd_per_point = 100.0
        elif "BTC" in self.symbol:
            self.contract_size = 1.0
            self.usd_per_point = 1.0
        elif "JPY" in self.symbol:
            self.contract_size = 100000.0
            self.usd_per_point = 1000.0
        else:
            self.contract_size = 100000.0
            self.usd_per_point = 100000.0

    def reset(self, initial_balance: Optional[float] = None):
        """Resets engine state, balance and position baskets."""
        if initial_balance is not None:
            self.initial_balance = initial_balance
        self.balance = self.initial_balance
        self.equity = self.initial_balance
        self.peak_equity = self.initial_balance
        self.max_drawdown_usd = 0.0
        self.max_drawdown_pct = 0.0
        
        self.buy_basket: List[Dict[str, Any]] = []
        self.sell_basket: List[Dict[str, Any]] = []
        self.buy_cycle_tiers: int = 0
        self.sell_cycle_tiers: int = 0
        self.ticket_counter: int = 1
        
        self.completed_cycles: int = 0
        self.total_cuts: int = 0
        self.total_cut_loss: float = 0.0
        self.total_tp_profit: float = 0.0
        
        self.closed_trades: List[Dict[str, Any]] = []
        self.event_log: List[Dict[str, Any]] = []
        self.equity_curve: List[Dict[str, Any]] = []

    def set_config(self, new_config: Dict[str, Any]):
        """Updates EA configuration."""
        self.config.update(new_config)

    def calc_basket_be_tp(self, orders: List[Dict[str, Any]], direction: str) -> Tuple[float, float]:
        """Calculates Volume-Weighted Break-Even Price and Target TP Price."""
        if not orders:
            return 0.0, 0.0
            
        sum_vol_price = sum(o["price"] * o["lot"] for o in orders)
        tot_lot = sum(o["lot"] for o in orders)
        if tot_lot <= 0:
            return 0.0, 0.0
            
        be = sum_vol_price / tot_lot
        
        tp_seq = self.config.get("tp_sequence", [10.0])
        tp_idx = min(len(orders) - 1, len(tp_seq) - 1)
        tp_pips = tp_seq[tp_idx] if tp_idx >= 0 else 10.0
        tp_offset = tp_pips * self.pip_size
        
        if direction.upper() == "BUY":
            tp_price = be + tp_offset
        else:
            tp_price = be - tp_offset
            
        return round(be, self.digits), round(tp_price, self.digits)

    def calc_floating_pnl(self, current_price: float) -> Tuple[float, float, float]:
        """Calculates floating PnL for BUY basket, SELL basket, and total."""
        buy_pnl = 0.0
        for o in self.buy_basket:
            diff = current_price - o["price"]
            buy_pnl += diff * self.usd_per_point * o["lot"]
            
        sell_pnl = 0.0
        for o in self.sell_basket:
            diff = o["price"] - current_price
            sell_pnl += diff * self.usd_per_point * o["lot"]
            
        return round(buy_pnl, 2), round(sell_pnl, 2), round(buy_pnl + sell_pnl, 2)

    def on_subbar(self, candle_m5: Dict[str, Any], h1_indicators: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Executes one M5 sub-bar step:
        1. Checks intra-bar TP hits using candle High/Low.
        2. Checks Realtime M5 Step price expansion for active baskets.
        3. Applies Sliding Window FIFO cuts if max_active_orders is exceeded.
        4. Kicks off new cycle seed orders if basket is empty based on trigger filters.
        5. Updates equity curve and drawdown metrics.
        """
        t = candle_m5["time"]
        b_open = candle_m5["open"]
        b_high = candle_m5["high"]
        b_low = candle_m5["low"]
        b_close = candle_m5["close"]
        
        step_pips = float(self.config.get("step_pips", 80.0))
        step_price = step_pips * self.pip_size
        lot_seq = self.config.get("lot_sequence", [0.01, 0.02, 0.03, 0.04, 0.05])
        enable_sw = self.config.get("enable_sliding_window", True)
        max_active = int(self.config.get("max_active_orders", 3))
        max_orders = int(self.config.get("max_orders_per_basket", 10))
        direction_mode = self.config.get("direction", "HEDGING_DUAL")
        allow_buy_mode = direction_mode in ("BUY_ONLY", "HEDGING_DUAL")
        allow_sell_mode = direction_mode in ("SELL_ONLY", "HEDGING_DUAL")
        
        # Indicator state from H1 (Bollinger Bands, RSI)
        h1_ind = h1_indicators or {}
        bb_upper = h1_ind.get("bb_upper", 0.0)
        bb_lower = h1_ind.get("bb_lower", 0.0)
        rsi_val = h1_ind.get("rsi", 50.0)
        enable_bb_filter = self.config.get("enable_bb_filter", True)
        
        events = []
        
        # =====================================================================
        # 1. INTRA-BAR TAKE PROFIT CHECK
        # =====================================================================
        # BUY BASKET TP CHECK
        if self.buy_basket:
            be, tp = self.calc_basket_be_tp(self.buy_basket, "BUY")
            if b_high >= tp:
                profit = sum((tp - o["price"]) * self.usd_per_point * o["lot"] for o in self.buy_basket)
                self.balance += profit
                self.total_tp_profit += profit
                self.completed_cycles += 1
                
                closed_info = {
                    "time": t,
                    "type": "BUY_BASKET_TP",
                    "tp_price": tp,
                    "be_price": be,
                    "orders_count": len(self.buy_basket),
                    "profit": round(profit, 2),
                    "tiers_in_cycle": self.buy_cycle_tiers
                }
                self.closed_trades.append(closed_info)
                events.append(f"BUY Basket TP Hit @ {tp} | +${round(profit, 2)} ({len(self.buy_basket)} orders)")
                self.buy_basket.clear()
                self.buy_cycle_tiers = 0

        # SELL BASKET TP CHECK
        if self.sell_basket:
            be, tp = self.calc_basket_be_tp(self.sell_basket, "SELL")
            if b_low <= tp:
                profit = sum((o["price"] - tp) * self.usd_per_point * o["lot"] for o in self.sell_basket)
                self.balance += profit
                self.total_tp_profit += profit
                self.completed_cycles += 1
                
                closed_info = {
                    "time": t,
                    "type": "SELL_BASKET_TP",
                    "tp_price": tp,
                    "be_price": be,
                    "orders_count": len(self.sell_basket),
                    "profit": round(profit, 2),
                    "tiers_in_cycle": self.sell_cycle_tiers
                }
                self.closed_trades.append(closed_info)
                events.append(f"SELL Basket TP Hit @ {tp} | +${round(profit, 2)} ({len(self.sell_basket)} orders)")
                self.sell_basket.clear()
                self.sell_cycle_tiers = 0

        # =====================================================================
        # 2. REALTIME M5 STEP DCA EXPANSION & SLIDING WINDOW CUT
        # =====================================================================
        # BUY DCA EXPANSION (Strict 1 order max per trigger)
        if allow_buy_mode and self.buy_basket and self.buy_cycle_tiers < max_orders:
            lowest_buy = min(o["price"] for o in self.buy_basket)
            next_step_price = lowest_buy - step_price
            if b_low <= next_step_price:
                allow_add = True
                if enable_bb_filter and bb_lower > 0.0 and b_close <= bb_lower:
                    allow_add = False  # Filter blocks buying when price breaches BB lower
                    
                if allow_add:
                    # Skip step advance if configured
                    if self.config.get("aggregate_skipped_steps", False) and step_price > 0:
                        skipped = int((lowest_buy - b_low) / step_price)
                        if skipped > 1:
                            self.buy_cycle_tiers = min(self.buy_cycle_tiers + skipped - 1, max_orders - 1)
                            
                    entry_p = min(b_open, next_step_price)
                    next_lot = lot_seq[min(self.buy_cycle_tiers, len(lot_seq) - 1)]
                    new_order = {
                        "ticket": self.ticket_counter,
                        "type": "BUY",
                        "price": round(entry_p, self.digits),
                        "lot": round(next_lot, 2),
                        "time": t,
                        "tier": self.buy_cycle_tiers + 1
                    }
                    self.ticket_counter += 1
                    self.buy_basket.append(new_order)
                    self.buy_cycle_tiers += 1
                    events.append(f"BUY Tier {new_order['tier']} Opened @ {entry_p} ({next_lot} lots)")
                    
                    # Sliding Window FIFO Cut
                    if enable_sw and len(self.buy_basket) > max_active:
                        oldest = self.buy_basket.pop(0)
                        cut_loss = (entry_p - oldest["price"]) * self.usd_per_point * oldest["lot"]
                        self.balance += cut_loss
                        self.total_cuts += 1
                        self.total_cut_loss += cut_loss
                        events.append(f"BUY Sliding Window Cut Order #{oldest['ticket']} @ {entry_p} | -${round(abs(cut_loss), 2)}")

        # SELL DCA EXPANSION (Strict 1 order max per trigger)
        if allow_sell_mode and self.sell_basket and self.sell_cycle_tiers < max_orders:
            highest_sell = max(o["price"] for o in self.sell_basket)
            next_step_price = highest_sell + step_price
            if b_high >= next_step_price:
                allow_add = True
                if enable_bb_filter and bb_upper > 0.0 and b_close >= bb_upper:
                    allow_add = False  # Filter blocks selling when price breaches BB upper
                    
                if allow_add:
                    # Skip step advance if configured
                    if self.config.get("aggregate_skipped_steps", False) and step_price > 0:
                        skipped = int((b_high - highest_sell) / step_price)
                        if skipped > 1:
                            self.sell_cycle_tiers = min(self.sell_cycle_tiers + skipped - 1, max_orders - 1)
                            
                    entry_p = max(b_open, next_step_price)
                    next_lot = lot_seq[min(self.sell_cycle_tiers, len(lot_seq) - 1)]
                    new_order = {
                        "ticket": self.ticket_counter,
                        "type": "SELL",
                        "price": round(entry_p, self.digits),
                        "lot": round(next_lot, 2),
                        "time": t,
                        "tier": self.sell_cycle_tiers + 1
                    }
                    self.ticket_counter += 1
                    self.sell_basket.append(new_order)
                    self.sell_cycle_tiers += 1
                    events.append(f"SELL Tier {new_order['tier']} Opened @ {entry_p} ({next_lot} lots)")
                    
                    # Sliding Window FIFO Cut
                    if enable_sw and len(self.sell_basket) > max_active:
                        oldest = self.sell_basket.pop(0)
                        cut_loss = (oldest["price"] - entry_p) * self.usd_per_point * oldest["lot"]
                        self.balance += cut_loss
                        self.total_cuts += 1
                        self.total_cut_loss += cut_loss
                        events.append(f"SELL Sliding Window Cut Order #{oldest['ticket']} @ {entry_p} | -${round(abs(cut_loss), 2)}")

        # =====================================================================
        # 3. INITIAL SEED ORDERS (NEW CYCLES)
        # =====================================================================
        first_trigger = self.config.get("first_order_trigger", "IMMEDIATE")
        rsi_os = float(self.config.get("rsi_oversold", 35.0))
        rsi_ob = float(self.config.get("rsi_overbought", 65.0))
        
        # BUY SEED TRIGGER
        if allow_buy_mode and not self.buy_basket and self.buy_cycle_tiers == 0:
            should_seed_buy = False
            if first_trigger == "IMMEDIATE":
                should_seed_buy = True
            elif first_trigger == "RSI" and rsi_val <= rsi_os:
                should_seed_buy = True
            elif first_trigger == "BB" and bb_lower > 0.0 and b_close <= bb_lower:
                should_seed_buy = True
                
            if should_seed_buy:
                seed_lot = lot_seq[0]
                new_order = {
                    "ticket": self.ticket_counter,
                    "type": "BUY",
                    "price": round(b_close, self.digits),
                    "lot": round(seed_lot, 2),
                    "time": t,
                    "tier": 1
                }
                self.ticket_counter += 1
                self.buy_basket.append(new_order)
                self.buy_cycle_tiers = 1
                events.append(f"BUY Seed (Tier 1) Triggered @ {b_close} ({seed_lot} lot)")

        # SELL SEED TRIGGER
        if allow_sell_mode and not self.sell_basket and self.sell_cycle_tiers == 0:
            should_seed_sell = False
            if first_trigger == "IMMEDIATE":
                should_seed_sell = True
            elif first_trigger == "RSI" and rsi_val >= rsi_ob:
                should_seed_sell = True
            elif first_trigger == "BB" and bb_upper > 0.0 and b_close >= bb_upper:
                should_seed_sell = True
                
            if should_seed_sell:
                seed_lot = lot_seq[0]
                new_order = {
                    "ticket": self.ticket_counter,
                    "type": "SELL",
                    "price": round(b_close, self.digits),
                    "lot": round(seed_lot, 2),
                    "time": t,
                    "tier": 1
                }
                self.ticket_counter += 1
                self.sell_basket.append(new_order)
                self.sell_cycle_tiers = 1
                events.append(f"SELL Seed (Tier 1) Triggered @ {b_close} ({seed_lot} lot)")

        # =====================================================================
        # 4. RECALCULATE EQUITY & DRAWDOWN
        # =====================================================================
        buy_pnl, sell_pnl, tot_floating = self.calc_floating_pnl(b_close)
        self.equity = round(self.balance + tot_floating, 2)
        if self.equity > self.peak_equity:
            self.peak_equity = self.equity
            
        dd_usd = self.peak_equity - self.equity
        dd_pct = (dd_usd / self.peak_equity) * 100.0 if self.peak_equity > 0 else 0.0
        if dd_usd > self.max_drawdown_usd:
            self.max_drawdown_usd = round(dd_usd, 2)
        if dd_pct > self.max_drawdown_pct:
            self.max_drawdown_pct = round(dd_pct, 2)
            
        # Append equity point
        if not self.equity_curve or self.equity_curve[-1]["time"] != t:
            self.equity_curve.append({
                "time": t,
                "balance": round(self.balance, 2),
                "equity": self.equity,
                "drawdown_pct": round(dd_pct, 2)
            })

        buy_be, buy_tp = self.calc_basket_be_tp(self.buy_basket, "BUY")
        sell_be, sell_tp = self.calc_basket_be_tp(self.sell_basket, "SELL")

        return {
            "time": t,
            "events": events,
            "buy_be": buy_be,
            "buy_tp": buy_tp,
            "sell_be": sell_be,
            "sell_tp": sell_tp,
            "balance": round(self.balance, 2),
            "equity": self.equity,
            "buy_pnl": buy_pnl,
            "sell_pnl": sell_pnl,
            "total_floating_pnl": tot_floating
        }

    def get_hud_status(self, current_price: float) -> Dict[str, Any]:
        """Returns comprehensive status for on-chart HUD / Dashboard."""
        buy_be, buy_tp = self.calc_basket_be_tp(self.buy_basket, "BUY")
        sell_be, sell_tp = self.calc_basket_be_tp(self.sell_basket, "SELL")
        buy_pnl, sell_pnl, tot_pnl = self.calc_floating_pnl(current_price)
        
        buy_dist_pips = round((buy_tp - current_price) / self.pip_size, 1) if buy_tp > 0 else 0.0
        sell_dist_pips = round((current_price - sell_tp) / self.pip_size, 1) if sell_tp > 0 else 0.0
        
        max_active = int(self.config.get("max_active_orders", 3))
        max_orders = int(self.config.get("max_orders_per_basket", 10))
        
        return {
            "preset_name": self.config.get("preset_name", "v1.40 Sliding Window"),
            "balance": round(self.balance, 2),
            "equity": round(self.equity, 2),
            "net_profit": round(self.equity - self.initial_balance, 2),
            "net_profit_pct": round(((self.equity - self.initial_balance) / self.initial_balance) * 100, 2),
            "max_drawdown_usd": self.max_drawdown_usd,
            "max_drawdown_pct": self.max_drawdown_pct,
            "completed_cycles": self.completed_cycles,
            "total_cuts": self.total_cuts,
            "total_cut_loss": round(self.total_cut_loss, 2),
            "total_tp_profit": round(self.total_tp_profit, 2),
            "buy_basket": {
                "active_orders": len(self.buy_basket),
                "max_active": max_active,
                "current_tier": self.buy_cycle_tiers,
                "max_tiers": max_orders,
                "be_price": buy_be,
                "tp_price": buy_tp,
                "floating_pnl": buy_pnl,
                "dist_to_tp_pips": buy_dist_pips,
                "orders": copy.deepcopy(self.buy_basket)
            },
            "sell_basket": {
                "active_orders": len(self.sell_basket),
                "max_active": max_active,
                "current_tier": self.sell_cycle_tiers,
                "max_tiers": max_orders,
                "be_price": sell_be,
                "tp_price": sell_tp,
                "floating_pnl": sell_pnl,
                "dist_to_tp_pips": sell_dist_pips,
                "orders": copy.deepcopy(self.sell_basket)
            }
        }

    def fast_backtest(self, sub_candles: List[Dict[str, Any]], macro_candles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Executes ultra-fast vectorized / streaming backtest across the complete dataset.
        Zero future information / zero lookahead bias.
        """
        self.reset()
        if not sub_candles:
            return {"success": False, "error": "No candle data provided"}
            
        # Precompute H1 indicators (BB and RSI) mapped by timestamp
        h1_closes = []
        h1_times = []
        for c in macro_candles:
            h1_closes.append(c["close"])
            h1_times.append(c["time"])
            
        closes_arr = np.array(h1_closes, dtype=float)
        times_arr = np.array(h1_times, dtype=int)
        
        # Simple fast RSI 14 on H1
        rsi_period = int(self.config.get("rsi_period", 14))
        bb_period = int(self.config.get("bb_period", 20))
        bb_dev = float(self.config.get("bb_dev", 2.0))
        
        # Build lookup table for H1 indicators at any timestamp
        # For each sub-bar, find the latest closed H1 bar (t_h1 <= t - 3600)
        h1_indicator_cache = {}
        for i in range(len(macro_candles)):
            c_time = macro_candles[i]["time"]
            # Slice up to this closed bar
            sub_c = closes_arr[:i+1]
            if len(sub_c) >= bb_period:
                recent_c = sub_c[-bb_period:]
                sma = float(np.mean(recent_c))
                std = float(np.std(recent_c))
                bb_up = sma + (bb_dev * std)
                bb_lo = sma - (bb_dev * std)
            else:
                bb_up = 0.0
                bb_lo = 0.0
                
            # Quick RSI
            if len(sub_c) > rsi_period:
                deltas = np.diff(sub_c[-rsi_period-1:])
                gains = np.maximum(deltas, 0)
                losses = np.maximum(-deltas, 0)
                avg_gain = np.mean(gains)
                avg_loss = np.mean(losses)
                if avg_loss == 0:
                    rsi = 100.0
                else:
                    rs = avg_gain / avg_loss
                    rsi = 100.0 - (100.0 / (1.0 + rs))
            else:
                rsi = 50.0
                
            h1_indicator_cache[c_time] = {
                "bb_upper": bb_up,
                "bb_lower": bb_lo,
                "rsi": rsi
            }

        # Streaming loop over sub-bars (M5 / M15)
        curr_h1_idx = 0
        h1_state = {"bb_upper": 0.0, "bb_lower": 0.0, "rsi": 50.0}
        macro_interval = 3600
        if len(macro_candles) > 1:
            diff_t = int(macro_candles[1]["time"] - macro_candles[0]["time"])
            if diff_t > 0:
                macro_interval = diff_t
        
        for bar in sub_candles:
            b_t = bar["time"]
            # Update latest completed macro indicator
            while curr_h1_idx < len(macro_candles) and macro_candles[curr_h1_idx]["time"] + macro_interval <= b_t:
                h_t = macro_candles[curr_h1_idx]["time"]
                if h_t in h1_indicator_cache:
                    h1_state = h1_indicator_cache[h_t]
                curr_h1_idx += 1
                
            self.on_subbar(bar, h1_indicators=h1_state)

        # Build backtest summary report
        net_profit = self.equity - self.initial_balance
        net_profit_pct = (net_profit / self.initial_balance) * 100.0
        
        # Downsample equity curve for fast frontend chart rendering (max 1000 points)
        step = max(1, len(self.equity_curve) // 1000)
        sampled_curve = self.equity_curve[::step]
        if self.equity_curve and (not sampled_curve or sampled_curve[-1]["time"] != self.equity_curve[-1]["time"]):
            sampled_curve.append(self.equity_curve[-1])

        return {
            "success": True,
            "symbol": self.symbol,
            "preset_name": self.config.get("preset_name", "Simple DCA v1.40"),
            "initial_balance": self.initial_balance,
            "final_balance": round(self.balance, 2),
            "final_equity": round(self.equity, 2),
            "net_profit": round(net_profit, 2),
            "net_profit_pct": round(net_profit_pct, 2),
            "max_drawdown_usd": self.max_drawdown_usd,
            "max_drawdown_pct": self.max_drawdown_pct,
            "completed_cycles": self.completed_cycles,
            "total_cuts": self.total_cuts,
            "total_cut_loss": round(self.total_cut_loss, 2),
            "total_tp_profit": round(self.total_tp_profit, 2),
            "profit_factor": round(self.total_tp_profit / abs(self.total_cut_loss), 2) if self.total_cut_loss < 0 else 999.0,
            "total_bars_tested": len(sub_candles),
            "start_time": sub_candles[0]["time"] if sub_candles else 0,
            "end_time": sub_candles[-1]["time"] if sub_candles else 0,
            "equity_curve": sampled_curve,
            "closed_trades": self.closed_trades[-100:]  # last 100 trades for log
        }
