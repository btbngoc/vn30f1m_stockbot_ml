# Predict & Visualize Walkthrough

Mình đã hoàn tất việc cập nhật và viết code cho 2 module quan trọng. Dưới đây là cách sử dụng.

## 1. Kết quả chạy thử
Hệ thống vừa chạy xong script visualization. Một trình duyệt web sẽ tự động bật lên hiển thị file `chart.html` (chứa 1000 nến gần nhất).
Bạn hãy thử:
- **Di chuột** vào các điểm tam giác Xanh/Đỏ để xem bảng Hover cực kỳ chi tiết (Confidence, TP/SL points, Volume Spike, EMA20 Dist).
- **Xem góc trên cùng bên trái** để thấy Dashboard Thống Kê (Mini-Backtest) với thông số Trades, Winrate, Profit Factor, Net Profit của số nến đang hiển thị.
- **Cuộn chuột** để Zoom In/Out, kéo sang trái phải để xem lịch sử.

## 2. Cách tuỳ biến Chart (CLI)
Bạn có thể tự do sinh ra các chart khác nhau ngay trên Terminal với các lệnh linh hoạt sau:

### Lọc theo Nến (Bars)
Xem 5000 nến gần nhất (khoảng 3 tuần):
```bash
python -m trading_engine.visualize.chart --bars 5000
```

### Lọc theo Ngày (Days)
Xem biến động trong 10 ngày giao dịch gần nhất:
```bash
python -m trading_engine.visualize.chart --days 10
```

### Lọc theo một phiên cụ thể (Session)
Cực kỳ hữu ích để soi lại 1 ngày giao dịch:
```bash
python -m trading_engine.visualize.chart --session 2026-07-23
```

### 💎 Bộ lọc "Chất Lượng" (--min-conf)
Loại bỏ các lệnh nhiễu, chỉ hiện các tín hiệu có sự tự tin từ 80% trở lên. Giúp chart cực kỳ sạch sẽ:
```bash
python -m trading_engine.visualize.chart --bars 5000 --min-conf 0.8
```

## 3. Những thay đổi chính

#### `trading_engine/ml/predict.py`
- Lấy toàn bộ `VN30F1M_features.parquet` để tính toán.
- Chạy qua mô hình XGBoost để sinh ra cột `Confidence` (xác suất thành công).
- Kết hợp với dữ liệu Take Profit, Stop Loss từ Triple Barrier.
- Lưu xuống `ml_predictions.csv` ở dạng bảng dữ liệu hoàn chỉnh.

#### `trading_engine/visualize/chart.py`
- Đọc data OHLC và data dự đoán.
- Cắt gọt data theo Time / Session do bạn chỉ định (tránh treo trình duyệt).
- Tính toán nhanh Mini-Backtest dựa trên kết quả exit đã có.
- Trình bày trực quan với thư viện `plotly`, chia theo nhiều layers để dễ quan sát. Mức độ đậm nhạt của màu sắc thể hiện trực quan độ tự tin (Confidence) của mô hình.

> [!TIP]
> Bạn có thể kết hợp nhiều cờ. Ví dụ: `python -m trading_engine.visualize.chart --days 5 --min-conf 0.75` để xem 5 ngày qua mô hình có tín hiệu nào chắc ăn không.
