# ⚡ Trading Strategy Simulator & Multi-Timeframe Replay Engine (MT5 Direct Feed)

Ứng dụng mô phỏng giao dịch (**Manual Backtesting & Strategy Tester**) chuẩn giao diện TradingView 3 biểu đồ đồng bộ đa khung thời gian (**Khung Lớn HTF + Cấu Trúc MTF + Thực Thi LTF**), kết nối trực tiếp dữ liệu nến thực tế từ **MetaTrader 5 (MT5)**.

---

## 🌟 Tính Năng Nổi Bật

1. **Bố Cục 3 Khung Thời Gian Đồng Bộ (Tri-View Multi-Timeframe)**:
   - **Khung 1 (HTF - Bên trái)**: Khung lớn xác định xu hướng chủ đạo (H4 / D1).
   - **Khung 2 (MTF - Ở giữa)**: Cấu trúc thị trường & vùng chuyển tiếp (H1 / M15).
   - **Khung 3 (LTF - Bên phải)**: Tìm điểm vào lệnh và tối ưu điểm cắt lỗ (M15 / M5 / M1).
   - Bước nến nhỏ tự động hình thành nến lớn đang chạy theo thời gian thực.

2. **Đồng Bộ Con Trỏ Chuột 2 Chiều (Crosshair Sync)**:
   - Rê chuột trên bất kỳ biểu đồ nào, hệ thống tự động gióng thời gian và mức giá chính xác qua 2 biểu đồ còn lại bằng thuật toán Binary Search $O(\log N)$.

3. **Kết Nối Trực Tiếp MetaTrader 5 (MT5 Broker Real Feed)**:
   - Tự động nhận diện MT5 đang mở trên máy tính (Exness, IC Markets, The5ers, FTMO, XM...).
   - Tự động khớp các hậu tố mã sàn: `XAUUSD`, `XAUUSDm`, `XAUUSD.raw`, `XAUUSDpro`, `XAUUSD_i`...
   - Kéo đúng giá Bid, Ask, Spread và nến lịch sử thực tế của sàn giao dịch.

4. **Tích Hợp Quân Sư Chiến Lược (AI Strategic Radar & Dynamic SL/TP)**:
   - Đánh giá xác suất đa tầng (UP / DN / SW %), Trust Score, và dải sóng ATR tương lai.
   - Nút **`🎯 Dynamic SL/TP`** trên thanh Ribbon cho phép Bật/Tắt đường mục tiêu chốt lời, cắt lỗ linh hoạt.

5. **Bộ Chỉ Báo Chuẩn TradingView (21 Indicators)**:
   - EMA 21, 50, 200, Bollinger Bands, RSI 14, Stochastic (5, 3, 3), Divergence mũi tên xanh/đỏ.
   - Nút **`⚡ Nạp TF1`** nạp nhanh toàn bộ chỉ báo cho khung lớn chỉ với 1 click.

---

## 🚀 Hướng Dẫn Khởi Chạy (Dễ Dàng Đem Sang Máy Khác)

> Chi tiết từng bước vui lòng xem file: [HUONG_DAN_SANG_MAY_KHAC.md](./HUONG_DAN_SANG_MAY_KHAC.md)

1. **Clone về máy mới**:
   ```bash
   git clone https://github.com/kenngommo/trading-simulator.git
   cd trading-simulator
   ```
2. **Yêu cầu máy tính**: Đã cài Python 64-bit (tích chọn `Add python.exe to PATH`) và bật sẵn phần mềm MT5.
3. **Khởi động**: Nhấp đúp chuột vào file:
   👉 **`run_simulator.bat`**
   - Hệ thống tự động tạo `.venv`, cài đặt thư viện cần thiết, kết nối MT5 và mở trình duyệt web tại `http://localhost:8080`.
3. **Kiểm tra kết nối MT5**: Nhấp đúp chuột vào:
   👉 **`kiem_tra_ket_noi_mt5.bat`** để xem tình trạng tài khoản, server sàn và kiểm tra giá các cặp tiền.

---

## ⌨️ Bảng Phím Tắt (Hotkeys)

| Phím | Chức năng |
| :---: | :--- |
| `Space` | Play / Pause Replay |
| `➔` (Mũi tên phải) | Tiến tới 1 nến tiếp theo |
| `Z` | Reset Scale & Fit căn chỉnh tự động cả 3 biểu đồ |
| `P` | Ghim nến cách mép phải ~18% (MT5 Chart Shift) |
| `Ctrl + B` | Ẩn / Hiện thanh quản lý lệnh bên phải (Full Screen Chart) |
| `Chuột phải` | Menu ngữ cảnh: Sao chép giá chuột, Đặt Entry, Đặt SL, Đặt TP |
