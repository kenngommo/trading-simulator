# 🚀 HƯỚNG DẪN ĐÓNG GÓI & CHẠY TRADING SIMULATOR TRÊN MÁY TÍNH MỚI

Tài liệu này hướng dẫn cách chuyển toàn bộ thư mục **Trading Simulator** sang bất kỳ máy tính Windows nào khác để chạy ngay lập tức, tự động kết nối và kéo giá chuẩn từ sàn MetaTrader 5 (MT5).

---

## 1. YÊU CẦU TIỀN ĐỀ TRÊN MÁY MỚI (CHỈ CẦN 2 THỨ)

1. **Python 64-bit (Khuyên dùng Python 3.10, 3.11 hoặc 3.12)**:
   - Tải từ trang chủ: [python.org/downloads](https://www.python.org/downloads/)
   - ⚠️ **Lưu ý cực kỳ quan trọng khi cài đặt**: Ở màn hình đầu tiên của bộ cài Python, **bắt buộc tích chọn vào ô:**
     `☑ Add python.exe to PATH` (ở dưới cùng) rồi mới bấm *Install Now*.
2. **Phần mềm MetaTrader 5 (MT5)**:
   - Của bất kỳ sàn nào bạn đang giao dịch (Exness, IC Markets, The5ers, FTMO, XM, FundedNext...).
   - Đăng nhập sẵn tài khoản (Demo hoặc Real).

---

## 2. CÁC BƯỚC TRIỂN KHAI (CHỈ 2 BƯỚC DUY NHẤT)

### 🔹 Bước 1: Clone từ GitHub (hoặc Copy thư mục)
Mở Terminal / PowerShell / Command Prompt trên máy mới và chạy lệnh:
```bash
git clone https://github.com/kenngommo/trading-simulator.git
```
*(Hoặc tải file ZIP trực tiếp tại `https://github.com/kenngommo/trading-simulator` và giải nén ra ổ đĩa bất kỳ như `C:\trading-simulator` hoặc `D:\trading-simulator`).*

### 🔹 Bước 2: Bật MT5 & Khởi động Simulator
1. **Mở sẵn phần mềm MetaTrader 5 (MT5)** trên máy tính.
2. Nhấp đúp chuột vào file:
   👉 **`run_simulator.bat`**

> **Cơ chế tự động thông minh (Zero-Config Bootstrap)**:
> - Nếu là lần đầu chạy trên máy mới, `run_simulator.bat` sẽ tự động khởi tạo môi trường ảo `.venv` và tự tải các thư viện cần thiết (`FastAPI`, `MetaTrader5`, `Pandas`, `NumPy`, `Uvicorn`...) từ file `requirements.txt`.
> - Sau khi cài xong, ứng dụng sẽ tự động mở trình duyệt web tại địa chỉ: **`http://localhost:8080`**.
> - Từ lần thứ 2 trở đi, app sẽ khởi động ngay lập tức chỉ trong **1 giây**.

---

## 3. CÔNG CỤ BÁC SĨ KIỂM TRA KẾT NỐI MT5 (`kiem_tra_ket_noi_mt5.bat`)

Trước hoặc trong khi sử dụng, bạn có thể nhấp đúp chuột vào file:
👉 **`kiem_tra_ket_noi_mt5.bat`**

Hệ thống sẽ chạy chẩn đoán tự động và hiển thị chi tiết:
- Trạng thái kết nối tới MT5 (`Connected: True`).
- Tên sàn, công ty quản lý và tên Server sàn (ví dụ `FivePercentOnline-Real`, `Exness-Real`, `ICMarketsSC-Live`...).
- Số tài khoản MT5, đòn bẩy và số dư khả dụng.
- Tự động quét và khớp tên cặp tiền (`XAUUSD`, `EURUSD`, `GBPUSD`, `USDJPY`, `BTCUSD`...).
- Đo lường Spread thời gian thực và kéo 3 cây nến mẫu để đối chiếu **Giờ Server & Giờ Việt Nam (UTC+7)**.

---

## 4. CƠ CHẾ KÉO GIÁ CHUẨN TỰ ĐỘNG TỪ MT5 VÀO SIMULATOR

1. **Khớp mã thông minh (Auto Symbol Suffix Mapping)**:
   - Các sàn thường đặt tên cặp tiền có phần đuôi (suffix) riêng:
     - Exness: `XAUUSDm`, `EURUSDm`
     - IC Markets: `XAUUSD.raw`, `EURUSD.raw`
     - Sàn có đuôi Pro / Zero / ECN: `XAUUSDpro`, `XAUUSD_i`, `XAUUSD.s`...
   - Hệ thống trong `src/data_fetcher.py` đã được tích hợp bộ lọc nhận diện thông minh, tự động tìm và kéo đúng mã đang hoạt động trên Market Watch của MT5 mà bạn không cần phải sửa code.

2. **Cơ chế hoạt động khi nạp giá**:
   - Khi bạn chọn cặp tiền trên thanh Menu (ví dụ `XAUUSD`), Simulator sẽ ưu tiên gọi API MT5 để lấy dữ liệu nến chính xác của sàn đó.
   - Nếu máy không mở MT5, hệ thống sẽ tự động dùng dữ liệu nến mẫu trong thư mục `data/` để bạn vẫn luyện tập backtest được bình thường.

3. **Nhập dữ liệu lịch sử cực lớn từ MT5 (Tùy chọn)**:
   - Nếu bạn muốn nạp 50.000 nến M15 từ năm 2020 trở lại đây từ sàn của bạn:
     - Trên MT5: Bấm `F2` (Symbols) $\rightarrow$ Chọn cặp tiền $\rightarrow$ Chọn khung M15 $\rightarrow$ Bấm `Export` lưu thành file `.csv`.
     - Trên giao diện Simulator: Bấm nút **`📁 Import MT5 CSV`** trên thanh công cụ và chọn file vừa xuất. Simulator sẽ tự động chuyển đổi và sinh ra cả 3 khung thời gian đồng bộ ngay lập tức!

---

## 5. DANH MỤC CÁC TỆP QUAN TRỌNG

| Tên Tệp / Thư Mục | Ý Nghĩa Chức Năng |
| :--- | :--- |
| **`run_simulator.bat`** | **Tệp chính khởi động toàn bộ Simulator (tự cài đặt nếu máy mới & mở trình duyệt)**. |
| **`setup_env.bat`** | Tệp cài đặt thủ công môi trường Python `.venv` và thư viện. |
| **`kiem_tra_ket_noi_mt5.bat`** | Tệp kiểm tra và chẩn đoán kết nối tới phần mềm MT5. |
| **`requirements.txt`** | Danh sách các thư viện Python chuẩn mực. |
| **`src/`** | Toàn bộ mã nguồn backend, chỉ báo, thuật toán nến đa khung và Quân Sư Chiến Lược. |
| **`static/`** | Giao diện đồ họa TradingView 3 biểu đồ (HTML, CSS, JavaScript). |
| **`templates/`** | Các mẫu lưu cấu hình chỉ báo (`Divergence.tpl`...). |
| **`data/`** | Thư mục lưu trữ nến đệm dự phòng khi không mở MT5. |

---
*Chúc bạn luyện tập và backtest thành công trên bất kỳ cỗ máy nào!*
