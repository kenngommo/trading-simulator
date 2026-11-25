"""
Simulation Engine for Replay, State Management, Pending Orders, and Smart Risk/Multi-Position Management.
"""

from typing import List, Dict, Any, Optional
import uuid
import time
from .data_fetcher import SYMBOL_MAPPINGS
from .ea_engine import SimpleDCAEngine
from .probabilistic_context_engine import ProbabilisticContextForecaster


class TradeSimulator:
    def __init__(self, initial_balance: float = 10000.0, leverage: int = 100):
        self.initial_balance = initial_balance
        self.leverage = leverage
        self.balance = initial_balance
        self.equity = initial_balance
        
        self.symbol: str = "XAUUSD"
        self.timeframe: str = "M5"
        self.timeframe_pair: str = "H1_M5"
        self.exec_tf: str = "M5"
        self.macro_tf: str = "H1"
        self.tf1_name: str = "H4"
        self.tf2_name: str = "H1"
        self.tf3_name: str = "M15"
        self.base_candles: List[Dict[str, Any]] = []
        self.tf1_all_candles: List[Dict[str, Any]] = []
        self.tf2_all_candles: List[Dict[str, Any]] = []
        self.tf3_all_candles: List[Dict[str, Any]] = []
        self.m15_candles: List[Dict[str, Any]] = []
        self.h4_candles: List[Dict[str, Any]] = []
        self.sub_candles: List[Dict[str, Any]] = []
        self.macro_candles: List[Dict[str, Any]] = []
        
        # EA Engine & Probabilistic Context Forecaster integration
        self.ea_engine: Optional[SimpleDCAEngine] = SimpleDCAEngine(symbol="XAUUSD", initial_balance=initial_balance)
        self.ea_enabled: bool = False
        self.active_preset_name: str = "v3.0_EMA21_Probabilistic_MacroKNN"
        self.prob_forecaster: ProbabilisticContextForecaster = ProbabilisticContextForecaster(horizon_bars=8, k_neighbors=35)
        
        # Minimum warmup bars for indicator continuity (e.g., EMA200 needs 200 bars)
        self.warmup_bars: int = 200
        self.current_m15_index: int = 200
        self.is_playing: bool = False
        self.play_speed_ms: int = 400
        
        self.open_positions: List[Dict[str, Any]] = []
        self.pending_orders: List[Dict[str, Any]] = []
        self.closed_positions: List[Dict[str, Any]] = []
        self.equity_curve: List[Dict[str, Any]] = [
            {"time": 0, "balance": initial_balance, "equity": initial_balance}
        ]
        
    def reset(self, initial_balance: float = 10000.0):
        """Resets the simulation account and positions."""
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.equity = initial_balance
        self.open_positions = []
        self.pending_orders = []
        self.closed_positions = []
        
        if self.ea_engine:
            self.ea_engine.reset(initial_balance=initial_balance)
        
        if self.m15_candles:
            # Prefer starting with warmup bars (e.g., 200 bars) or 40% through data
            if len(self.m15_candles) >= 3500:
                self.current_m15_index = min(3200, len(self.m15_candles) - 100)
            else:
                self.current_m15_index = max(10, int(len(self.m15_candles) * 0.4))
        else:
            self.current_m15_index = 0
            
        self.is_playing = False
        first_time = self.m15_candles[self.current_m15_index]["time"] if self.m15_candles else 0
        self.equity_curve = [{"time": first_time, "balance": self.balance, "equity": self.equity}]

    def load_triplet_dataset(
        self,
        symbol: str,
        base_candles: List[Dict[str, Any]],
        tf1_candles: List[Dict[str, Any]],
        tf2_candles: List[Dict[str, Any]],
        tf3_candles: List[Dict[str, Any]],
        tf1_name: str = "H4",
        tf2_name: str = "H1",
        tf3_name: str = "M15"
    ):
        """Loads candles dataset for 3 simultaneous timeframes with base tick/candle replay."""
        self.symbol = symbol
        self.tf1_name = tf1_name
        self.tf2_name = tf2_name
        self.tf3_name = tf3_name
        self.base_candles = base_candles
        self.tf1_all_candles = tf1_candles
        self.tf2_all_candles = tf2_candles
        self.tf3_all_candles = tf3_candles
        
        # Backward compatibility + full 3-TF triplet tracking
        self.m15_candles = base_candles
        self.sub_candles = base_candles
        self.h4_candles = tf1_candles
        self.macro_candles = tf1_candles
        self.exec_tf = tf3_name
        self.macro_tf = tf1_name
        self.timeframe_pair = f"{tf1_name}_{tf2_name}_{tf3_name}"
        
        if self.ea_engine:
            self.ea_engine.symbol = symbol
            self.ea_engine._init_symbol_info()
            self.ea_engine.reset(initial_balance=self.initial_balance)
            
        if len(self.base_candles) >= 3500:
            self.current_m15_index = min(3200, len(self.base_candles) - 100)
        else:
            self.current_m15_index = max(10, int(len(self.base_candles) * 0.4)) if self.base_candles else 0
            
        self.is_playing = False
        first_time = self.base_candles[self.current_m15_index]["time"] if self.base_candles else 0
        self.equity_curve = [{"time": first_time, "balance": self.balance, "equity": self.equity}]

    def load_dataset(self, symbol: str, m15_candles: List[Dict[str, Any]], h4_candles: List[Dict[str, Any]],
                     timeframe_pair: str = "H1_M5", exec_tf: str = "M5", macro_tf: str = "H1"):
        """Loads candles dataset for execution and macro timeframes with ample historical warmup."""
        self.symbol = symbol
        self.timeframe_pair = timeframe_pair
        self.exec_tf = exec_tf
        self.macro_tf = macro_tf
        self.timeframe = exec_tf
        
        self.m15_candles = m15_candles
        self.sub_candles = m15_candles
        self.h4_candles = h4_candles
        self.macro_candles = h4_candles
        
        if self.ea_engine:
            self.ea_engine.symbol = symbol
            self.ea_engine._init_symbol_info()
            self.ea_engine.reset(initial_balance=self.initial_balance)
        
        if len(self.m15_candles) >= 3500:
            self.current_m15_index = min(3200, len(self.m15_candles) - 100)
        else:
            self.current_m15_index = max(10, int(len(self.m15_candles) * 0.4))
            
        self.is_playing = False
        first_time = self.m15_candles[self.current_m15_index]["time"] if self.m15_candles else 0
        self.equity_curve = [{"time": first_time, "balance": self.balance, "equity": self.equity}]

    @property
    def current_time(self) -> int:
        if not self.m15_candles or self.current_m15_index >= len(self.m15_candles):
            return 0
        return self.m15_candles[self.current_m15_index]["time"]

    @property
    def current_price(self) -> float:
        if not self.m15_candles or self.current_m15_index >= len(self.m15_candles):
            return 0.0
        return self.m15_candles[self.current_m15_index]["close"]

    def get_visible_candles(self) -> Dict[str, Any]:
        """Returns sliced candles up to current_m15_index for all 3 timeframes with real-time forming candles."""
        effective_base = self.base_candles if self.base_candles else self.m15_candles
        if not effective_base:
            return {
                "M15": [], "H4": [], "sub_candles": [], "macro_candles": [],
                "tf1": [], "tf2": [], "tf3": [],
                "tf1_name": self.tf1_name, "tf2_name": self.tf2_name, "tf3_name": self.tf3_name,
                "current_time": 0, "current_price": 0.0,
                "timeframe_pair": self.timeframe_pair,
                "exec_tf": self.exec_tf, "macro_tf": self.macro_tf,
                "ea_status": None, "ea_enabled": self.ea_enabled
            }
            
        curr_t = effective_base[self.current_m15_index]["time"]
        curr_p = effective_base[self.current_m15_index]["close"]
        
        # Only need recent tail of base candles (up to 400 bars) to build forming H4/H1/M15 candle!
        tail_start = max(0, self.current_m15_index - 400)
        base_tail = effective_base[tail_start : self.current_m15_index + 1]
        
        # Build 3-timeframe slices with real-time forming candles
        from .data_fetcher import build_forming_candle, resample_to_timeframe
        
        if self.tf1_all_candles:
            tf1_slice = build_forming_candle(self.tf1_all_candles, base_tail, self.tf1_name)
        else:
            tf1_slice = resample_to_timeframe(effective_base[: self.current_m15_index + 1], self.tf1_name)[-1500:]
            
        if self.tf2_all_candles:
            tf2_slice = build_forming_candle(self.tf2_all_candles, base_tail, self.tf2_name)
        else:
            tf2_slice = resample_to_timeframe(effective_base[: self.current_m15_index + 1], self.tf2_name)[-1500:]
            
        if self.tf3_all_candles:
            tf3_slice = build_forming_candle(self.tf3_all_candles, base_tail, self.tf3_name)
        else:
            tf3_slice = resample_to_timeframe(effective_base[: self.current_m15_index + 1], self.tf3_name)[-1500:]
                    
        ea_status = self.ea_engine.get_hud_status(curr_p) if self.ea_engine else None

        # Cache prob_forecast if at the exact same bar & price (avoids slow k-NN when toggling indicators)
        fc_cache_key = (self.symbol, self.timeframe_pair, self.current_m15_index, round(curr_p, 5))
        if getattr(self, "_last_fc_cache_key", None) == fc_cache_key and getattr(self, "_last_fc_cache_val", None) is not None:
            prob_forecast = self._last_fc_cache_val
        else:
            prob_forecast = self.get_current_probabilistic_forecast(include_analogs=True)
            self._last_fc_cache_key = fc_cache_key
            self._last_fc_cache_val = prob_forecast
        
        return {
            # 3 simultaneous timeframes
            "tf1": tf1_slice,
            "tf2": tf2_slice,
            "tf3": tf3_slice,
            "base_tail_candles": base_tail,
            "tf1_name": self.tf1_name,
            "tf2_name": self.tf2_name,
            "tf3_name": self.tf3_name,
            # Backward compatibility keys
            "M15": tf3_slice,
            "H4": tf1_slice,
            "sub_candles": tf3_slice,
            "macro_candles": tf1_slice,
            "current_time": curr_t,
            "current_price": curr_p,
            "index": self.current_m15_index,
            "total_bars": len(effective_base),
            "timeframe_pair": self.timeframe_pair,
            "exec_tf": self.exec_tf,
            "macro_tf": self.macro_tf,
            "ea_status": ea_status,
            "ea_enabled": self.ea_enabled,
            "probabilistic_forecast": prob_forecast
        }

    def get_current_probabilistic_forecast(self, include_analogs: bool = True) -> Dict[str, Any]:
        """Returns 100% Non-Lookahead probabilistic context forecast (% UP / % DOWN / % SIDEWAY) at current_m15_index."""
        if not self.m15_candles:
            return self.prob_forecaster._empty_forecast()
        return self.prob_forecaster.forecast_at_bar(
            self.m15_candles,
            self.h4_candles,
            curr_idx=self.current_m15_index,
            symbol=self.symbol,
            include_analogs=include_analogs,
            timeframe_pair=self.timeframe_pair,
        )

    def step_forward(self, steps: int = 1) -> bool:
        """Advance simulator by N bars, evaluating Pending triggers, SL/TP and EA logic."""
        if not self.m15_candles:
            return False
            
        advanced = False
        for _ in range(steps):
            if self.current_m15_index < len(self.m15_candles) - 1:
                self.current_m15_index += 1
                candle = self.m15_candles[self.current_m15_index]
                self._evaluate_pending_orders_on_candle(candle)
                self._evaluate_positions_on_candle(candle)
                
                # If EA replay mode is enabled, execute EA on sub-bar
                if self.ea_enabled and self.ea_engine:
                    self.ea_engine.on_subbar(candle)
                    
                advanced = True
            else:
                self.is_playing = False
                break
                
        self._update_account_state()
        return advanced

    def step_backward(self, steps: int = 1) -> bool:
        """Step back by N bars."""
        if self.current_m15_index > 10:
            self.current_m15_index = max(10, self.current_m15_index - steps)
            self._update_account_state()
            return True
        return False

    def jump_to_index(self, index: int):
        """Jump directly to a specific bar index."""
        if self.m15_candles:
            self.current_m15_index = max(0, min(len(self.m15_candles) - 1, index))
            self._update_account_state()

    def jump_to_date(self, target_timestamp: int):
        """Jump to the nearest bar matching the target timestamp."""
        if not self.m15_candles:
            return
        for i, c in enumerate(self.m15_candles):
            if c["time"] >= target_timestamp:
                self.current_m15_index = i
                self._update_account_state()
                return
        self.current_m15_index = len(self.m15_candles) - 1
        self._update_account_state()

    def get_symbol_info(self) -> Dict[str, Any]:
        """Returns symbol precision, pip size, and description."""
        if self.symbol in SYMBOL_MAPPINGS:
            return dict(SYMBOL_MAPPINGS[self.symbol])
        try:
            import MetaTrader5 as mt5
            s = mt5.symbol_info(self.symbol)
            if s:
                d = s.digits
                p = round(s.point * 10 if d in (3, 5) else s.point, 6)
                return {"digits": d, "pip_size": p, "name": s.description or self.symbol}
        except Exception:
            pass
        return {"digits": 2, "pip_size": 0.01, "name": self.symbol}

    # =========================================================================
    # ORDER EXECUTION & PENDING ORDERS
    # =========================================================================
    def _contract_multiplier(self, ref_price: float) -> float:
        """Returns USD value per 1.0 full price unit move for 1.0 lot."""
        s = self.symbol.upper()
        if any(k in s for k in ("NAS", "USTEC", "US30", "DJ30", "WS30", "SPX", "US500", "UK100", "FTSE", "GER40", "DAX", "JPN225", "NIKKEI", "AUS200", "HK50")):
            return 1.0
        if "XAU" in s or "GOLD" in s:
            return 100.0
        if "XAG" in s or "SILVER" in s:
            return 5000.0
        if any(k in s for k in ("OIL", "WTI", "BRENT", "XTI", "XBR")):
            return 1000.0
        if any(k in s for k in ("BTC", "ETH", "SOL", "BNB", "XRP")):
            return 1.0
        if "JPY" in s:
            return (100000.0 / ref_price) if ref_price > 0 else 650.0
        return 100000.0

    def calculate_lot_size(self, risk_usd: float, entry_price: float, sl_price: float) -> float:
        """
        Calculates optimal lot size based on fixed dollar risk and SL distance across FX, Metals, Indices & Crypto.
        """
        if risk_usd <= 0 or entry_price <= 0 or sl_price <= 0 or entry_price == sl_price:
            return 0.1

        price_diff = abs(entry_price - sl_price)
        usd_per_unit_per_lot = self._contract_multiplier(entry_price)
        loss_per_lot = price_diff * usd_per_unit_per_lot
        if loss_per_lot <= 0:
            return 0.1

        calculated_lots = risk_usd / loss_per_lot
        return max(0.01, round(calculated_lots, 2))

    def open_order(
        self,
        order_type: str,
        lots: float,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
        pending_price: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Opens a Market Order (BUY/SELL) or places a Pending Order (BUY_LIMIT, BUY_STOP, SELL_LIMIT, SELL_STOP).
        """
        price = self.current_price
        curr_t = self.current_time
        pos_id = str(uuid.uuid4())[:8]
        order_type = order_type.upper().strip()
        
        is_pending = order_type in ("BUY_LIMIT", "BUY_STOP", "SELL_LIMIT", "SELL_STOP")
        
        if is_pending:
            target_price = pending_price if pending_price and pending_price > 0 else price
            pending_order = {
                "id": pos_id,
                "symbol": self.symbol,
                "type": order_type,
                "lots": round(lots, 2),
                "target_price": target_price,
                "placed_time": curr_t,
                "sl": sl if sl and sl > 0 else None,
                "tp": tp if tp and tp > 0 else None,
                "status": "PENDING"
            }
            self.pending_orders.append(pending_order)
            return pending_order
        else:
            position = {
                "id": pos_id,
                "symbol": self.symbol,
                "type": "BUY" if "BUY" in order_type else "SELL",
                "lots": round(lots, 2),
                "open_price": price,
                "open_time": curr_t,
                "sl": sl if sl and sl > 0 else None,
                "tp": tp if tp and tp > 0 else None,
                "pnl": 0.0,
                "pnl_pips": 0.0
            }
            self.open_positions.append(position)
            self._update_account_state()
            return position

    def open_batch_orders(
        self,
        order_type: str,
        total_lots: float,
        num_positions: int,
        entry_price: Optional[float] = None,
        sl: Optional[float] = None,
        rr_list: Optional[List[float]] = None
    ) -> List[Dict[str, Any]]:
        """
        Splits order into N multiple positions with progressive Take-Profit targets (e.g. TP 1:1, 1:2, 1:3).
        """
        if num_positions <= 1:
            num_positions = 1
            
        base_lots = max(0.01, round(total_lots / num_positions, 2))
        created = []
        
        actual_entry = entry_price if entry_price and entry_price > 0 else self.current_price
        is_buy = "BUY" in order_type.upper()
        sl_distance = abs(actual_entry - sl) if sl and sl > 0 else None
        
        for i in range(num_positions):
            # Calculate TP for each split based on RR
            this_tp = None
            if sl_distance:
                rr = rr_list[i] if rr_list and i < len(rr_list) else (1.0 + (i * 1.0))
                if is_buy:
                    this_tp = round(actual_entry + (sl_distance * rr), 5)
                else:
                    this_tp = round(actual_entry - (sl_distance * rr), 5)
                    
            order = self.open_order(
                order_type=order_type,
                lots=base_lots,
                sl=sl,
                tp=this_tp,
                pending_price=entry_price
            )
            created.append(order)
            
        return created

    def cancel_pending_order(self, order_id: str) -> bool:
        """Cancels a pending order."""
        for i, order in enumerate(self.pending_orders):
            if order["id"] == order_id:
                self.pending_orders.pop(i)
                return True
        return False

    def update_position_sl(self, pos_id: str, new_sl: float) -> bool:
        """Updates the stop loss price of an active position for trailing stop / BE."""
        for pos in self.open_positions:
            if pos["id"] == pos_id:
                pos["sl"] = round(new_sl, 5)
                self._update_account_state()
                return True
        return False

    def close_order(self, pos_id: str, exit_reason: str = "MANUAL", close_price: Optional[float] = None) -> Optional[Dict[str, Any]]:

        """Closes an active position."""
        target_pos = None
        for i, pos in enumerate(self.open_positions):
            if pos["id"] == pos_id:
                target_pos = self.open_positions.pop(i)
                break
                
        if not target_pos:
            return None
            
        c_price = close_price if close_price is not None else self.current_price
        c_time = self.current_time
        
        pnl, pips = self._calc_pnl(target_pos["type"], target_pos["open_price"], c_price, target_pos["lots"])
        
        closed = dict(target_pos)
        closed["close_price"] = c_price
        closed["close_time"] = c_time
        closed["pnl"] = round(pnl, 2)
        closed["pnl_pips"] = round(pips, 1)
        closed["exit_reason"] = exit_reason
        
        self.balance += closed["pnl"]
        self.closed_positions.append(closed)
        self._update_account_state()
        return closed

    def close_all_orders(self) -> List[Dict[str, Any]]:
        """Closes all active positions and cancels pending orders."""
        closed_list = []
        pos_ids = [p["id"] for p in self.open_positions]
        for pid in pos_ids:
            closed = self.close_order(pid, exit_reason="MANUAL_CLOSE_ALL")
            if closed:
                closed_list.append(closed)
        self.pending_orders.clear()
        return closed_list

    def _calc_pnl(self, order_type: str, open_price: float, current_price: float, lots: float) -> (float, float):
        """Calculates PnL in USD and Pips accurately across FX, Metals, Indices, and Crypto."""
        sym_info = self.get_symbol_info()
        pip_size = sym_info.get("pip_size", 0.01) or 0.01

        if order_type == "BUY":
            diff = current_price - open_price
        else:
            diff = open_price - current_price

        pips = diff / pip_size
        usd_pnl = diff * self._contract_multiplier(current_price or open_price) * lots
        return usd_pnl, pips

    def _evaluate_pending_orders_on_candle(self, candle: Dict[str, Any]):
        """Evaluates whether pending limit/stop orders are triggered by candle High/Low."""
        high = candle["high"]
        low = candle["low"]
        triggered = []
        
        for i, order in enumerate(self.pending_orders):
            ptype = order["type"]
            t_price = order["target_price"]
            is_triggered = False
            
            if ptype == "BUY_LIMIT" and low <= t_price:
                is_triggered = True
            elif ptype == "BUY_STOP" and high >= t_price:
                is_triggered = True
            elif ptype == "SELL_LIMIT" and high >= t_price:
                is_triggered = True
            elif ptype == "SELL_STOP" and low <= t_price:
                is_triggered = True
                
            if is_triggered:
                triggered.append(i)
                
        for idx in sorted(triggered, reverse=True):
            order = self.pending_orders.pop(idx)
            # Convert to open position
            position = {
                "id": order["id"],
                "symbol": self.symbol,
                "type": "BUY" if "BUY" in order["type"] else "SELL",
                "lots": order["lots"],
                "open_price": order["target_price"],
                "open_time": candle["time"],
                "sl": order.get("sl"),
                "tp": order.get("tp"),
                "pnl": 0.0,
                "pnl_pips": 0.0
            }
            self.open_positions.append(position)

    def _evaluate_positions_on_candle(self, candle: Dict[str, Any]):
        """Evaluates whether open positions hit SL or TP on the new candle's High/Low."""
        high = candle["high"]
        low = candle["low"]
        
        to_close = []
        for pos in self.open_positions:
            is_buy = pos["type"] == "BUY"
            sl = pos.get("sl")
            tp = pos.get("tp")
            
            if is_buy:
                if sl and low <= sl:
                    to_close.append((pos["id"], "SL", sl))
                elif tp and high >= tp:
                    to_close.append((pos["id"], "TP", tp))
            else:
                if sl and high >= sl:
                    to_close.append((pos["id"], "SL", sl))
                elif tp and low <= tp:
                    to_close.append((pos["id"], "TP", tp))
                    
        for pos_id, reason, exit_price in to_close:
            self.close_order(pos_id, exit_reason=reason, close_price=exit_price)


    def _update_account_state(self):
        """Recalculates floating PnL and updates Equity."""
        c_price = self.current_price
        c_time = self.current_time
        floating_pnl = 0.0
        
        for pos in self.open_positions:
            pnl, pips = self._calc_pnl(pos["type"], pos["open_price"], c_price, pos["lots"])
            pos["pnl"] = round(pnl, 2)
            pos["pnl_pips"] = round(pips, 1)
            pos["current_price"] = c_price
            floating_pnl += pnl
            
        self.equity = round(self.balance + floating_pnl, 2)
        
        if not self.equity_curve or self.equity_curve[-1]["time"] != c_time:
            self.equity_curve.append({
                "time": c_time,
                "balance": round(self.balance, 2),
                "equity": self.equity
            })

    def get_statistics(self) -> Dict[str, Any]:
        """Calculates detailed backtesting performance metrics."""
        total_trades = len(self.closed_positions)
        if total_trades == 0:
            return {
                "initial_balance": self.initial_balance,
                "balance": round(self.balance, 2),
                "equity": round(self.equity, 2),
                "net_profit": round(self.equity - self.initial_balance, 2),
                "net_profit_pct": round(((self.equity - self.initial_balance) / self.initial_balance) * 100, 2),
                "total_trades": 0,
                "win_rate": 0.0,
                "won_trades": 0,
                "lost_trades": 0,
                "profit_factor": 0.0,
                "max_drawdown_pct": 0.0,
                "total_pips": 0.0
            }
            
        won_trades = [t for t in self.closed_positions if t["pnl"] > 0]
        lost_trades = [t for t in self.closed_positions if t["pnl"] < 0]
        
        gross_profit = sum(t["pnl"] for t in won_trades)
        gross_loss = abs(sum(t["pnl"] for t in lost_trades))
        
        profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)
        win_rate = round((len(won_trades) / total_trades) * 100, 1)
        
        peak = self.initial_balance
        max_dd_pct = 0.0
        
        for pt in self.equity_curve:
            eq = pt["equity"]
            if eq > peak:
                peak = eq
            dd = peak - eq
            dd_pct = (dd / peak) * 100 if peak > 0 else 0
            if dd_pct > max_dd_pct:
                max_dd_pct = dd_pct
                
        total_pips = sum(t.get("pnl_pips", 0.0) for t in self.closed_positions)
        
        return {
            "initial_balance": self.initial_balance,
            "balance": round(self.balance, 2),
            "equity": round(self.equity, 2),
            "net_profit": round(self.equity - self.initial_balance, 2),
            "net_profit_pct": round(((self.equity - self.initial_balance) / self.initial_balance) * 100, 2),
            "total_trades": total_trades,
            "won_trades": len(won_trades),
            "lost_trades": len(lost_trades),
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "max_drawdown_pct": round(max_dd_pct, 2),
            "total_pips": round(total_pips, 1)
        }
