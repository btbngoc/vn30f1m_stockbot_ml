---
name: flaky-test-analysis
description: "Phân tích nguyên nhân và khắc phục các kịch bản kiểm thử chập chờn (Flaky Tests)."
---

# Flaky Test Analysis (Phân tích & Khắc phục Flaky Tests)

## Tổng quan
Quy trình phát hiện, chẩn đoán nguyên nhân gốc và sửa chữa các test case chập chờn (lúc Pass lúc Fail mà không có sự thay đổi mã nguồn), đảm bảo độ tin cậy của bộ kiểm thử tự động.

## Nguyên nhân Cốt lõi của Flaky Tests
1. **Async / Timing Issues:** Quên chờ bất đồng bộ (Missing auto-wait / Hardcoded sleep).
2. **Shared State / Side Effects:** Test case này làm ảnh hưởng dữ liệu của test case khác (Thiếu cleanup/isolation).
3. **Network Instability:** Gọi API thật bị trễ hoặc ngắt kết nối.
4. **Order Dependency:** Test case phụ thuộc vào thứ tự chạy.

## Nguyên tắc Khắc phục EP-02
Sử dụng quy trình 5 bước đo đạc để xác định Flaky Test: `Measure -> Observe -> Hypothesis -> Verify -> Conclusion`.

## Checklist
- [ ] Loại bỏ 100% `sleep()` cứng.
- [ ] Mock các dịch vụ bên ngoài (External Services) khi chạy E2E/Integration test.
- [ ] Mỗi test case tự khởi tạo và dọn dẹp dữ liệu riêng.
