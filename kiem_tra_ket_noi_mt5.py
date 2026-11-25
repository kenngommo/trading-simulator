"""
MetaTrader 5 (MT5) Connection & Data Health Doctor.
Run this script or double click 'kiem_tra_ket_noi_mt5.bat' to verify MT5 connectivity.
"""

import sys
import os
from datetime import datetime, timezone, timedelta

def main():
    print("=" * 65)
    print("  KIEM TRA KET NOI METATRADER 5 (MT5 HEALTH DOCTOR)")
    print("=" * 65)
    print()

    # 1. Check Python environment
    print(f"[*] Python Runtime: {sys.executable}")
    print(f"[*] Python Version: {sys.version.split()[0]} ({'64-bit' if sys.maxsize > 2**32 else '32-bit'})")

    if sys.maxsize <= 2**32:
        print("[!] CANH BAO: Ban dang dung Python 32-bit. Thu vien MetaTrader5 yeu cau Python 64-bit!")
        print("    Vui long cai dat Python 64-bit tu python.org.")
        return

    # 2. Check MetaTrader5 package
    try:
        import MetaTrader5 as mt5
        print(f"[*] Thu vien MetaTrader5: v{mt5.__version__} [OK]")
    except ImportError:
        print("[X] LOI: Chua cai dat thu vien 'MetaTrader5'.")
        print("    Hay chay: pip install MetaTrader5 (hoac chay file setup_env.bat)")
        return

    # 3. Check MT5 connection
    print("\n[*] Dang tim kiem va ket noi toi phan mem MetaTrader 5...")
    
    # Try default initialize
    connected = mt5.initialize()
    if not connected:
        # Try common paths
        common_paths = [
            r"C:\Program Files\MetaTrader 5\terminal64.exe",
            r"C:\Program Files\MetaTrader 5 IC Markets (SC)\terminal64.exe",
            r"C:\Program Files\Exness MetaTrader 5\terminal64.exe",
            r"C:\Program Files\Five Percent Online MetaTrader 5\terminal64.exe",
            r"C:\Program Files\The5ers MT5\terminal64.exe",
            r"C:\Program Files\FTMO MetaTrader 5\terminal64.exe",
            r"C:\Program Files\XM Global MT5\terminal64.exe",
            r"C:\Program Files (x86)\MetaTrader 5\terminal64.exe"
        ]
        custom_path = os.environ.get("MT5_PATH")
        if custom_path and os.path.exists(custom_path):
            common_paths.insert(0, custom_path)
            
        for path in common_paths:
            if os.path.exists(path):
                print(f"[*] Thu khoi dong MT5 tai: {path}")
                if mt5.initialize(path=path):
                    connected = True
                    break

    if not connected:
        print(f"[X] KHONG THE KET NOI MT5. Ma loi: {mt5.last_error()}")
        print("\n--> HUONG DAN KHAC PHUC:")
        print("  1. Hay mo phan mem MetaTrader 5 (MT5) tren may tinh cua ban.")
        print("  2. Dang nhap vao tai khoan san giao dich (Demo hoac Real).")
        print("  3. Sau do chay lai file nay de kiem tra.")
        return

    # 4. Account & Broker Info
    acc_info = mt5.account_info()
    term_info = mt5.terminal_info()

    print("\n[OK] KET NOI METATRADER 5 THANH CONG!")
    print("-" * 50)
    if term_info:
        print(f"  - Ten phan mem : {term_info.name} (Build {term_info.build})")
        print(f"  - Cong ty san  : {term_info.company}")
        print(f"  - Thu muc MT5  : {term_info.path}")
        print(f"  - Connected    : {term_info.connected}")
    if acc_info:
        print(f"  - So tai khoan : {acc_info.login}")
        print(f"  - Server San   : {acc_info.server}")
        print(f"  - Tien te      : {acc_info.currency}")
        print(f"  - So du Ban dau: ${acc_info.balance:,.2f}")
        print(f"  - Don bay (Lev): 1:{acc_info.leverage}")
    print("-" * 50)

    # 5. Check Core Symbols & Fetch Test Candles
    test_symbols = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "BTCUSD"]
    print("\n[*] Kiem tra do phu song cac cap tien va gia theo thoi gian thuc:")

    all_symbols = [s.name for s in (mt5.symbols_get() or [])]

    from src.data_fetcher import _get_mt5_symbol_name, fetch_mt5_history

    for sym in test_symbols:
        matched = _get_mt5_symbol_name(sym)
        if matched:
            mt5.symbol_select(matched, True)
            tick = mt5.symbol_info_tick(matched)
            candles = fetch_mt5_history(sym, "M15", count=3)
            
            bid = tick.bid if tick else "N/A"
            ask = tick.ask if tick else "N/A"
            spread = round((tick.ask - tick.bid), 2) if (tick and isinstance(tick.ask, float)) else "N/A"
            
            time_str = ""
            if candles and len(candles) > 0:
                last_c = candles[-1]
                t_utc = datetime.fromtimestamp(last_c["time"], tz=timezone.utc)
                # MT5 server time is roughly UTC+2 (winter) or UTC+3 (summer)
                t_server_str = t_utc.strftime("%H:%M")
                t_vn = t_utc + timedelta(hours=7)
                t_vn_str = t_vn.strftime("%H:%M")
                time_str = f"| Nen cuoi: Close {last_c['close']} luc {t_server_str} Server ({t_vn_str} VN)"

            print(f"  ✓ {sym:<7} -> Matched: '{matched:<10}' | Bid: {bid} / Ask: {ask} (Spread: {spread}) {time_str}")
        else:
            print(f"  ! {sym:<7} -> Khong tim thay cap tuong ung tren san nay.")

    print("\n" + "=" * 65)
    print("  [KET LUAN] HE THONG DA SAN SANG DE CHAY SIMULATOR!")
    print("  Ban co the khoi dong app bang cach chay file 'run_simulator.bat'")
    print("=" * 65)

    mt5.shutdown()

if __name__ == "__main__":
    main()
