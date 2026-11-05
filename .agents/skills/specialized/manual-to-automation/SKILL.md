---
name: manual-to-automation
description: "Chuyển đổi kịch bản kiểm thử thủ công (Manual Test Cases) sang Script kiểm thử tự động."
---

# Manual to Automation (Chuyển đổi Kiểm thử Thủ công sang Tự động)

## Tổng quan
Quy trình phân tích bộ kịch bản kiểm thử thủ công (`Test_Cases.md`), xác định các kịch bản phù hợp cho tự động hóa và chuyển đổi chúng thành mã nguồn kiểm thử tự động (Playwright/Selenium).

## Tiêu chí Chọn Kịch bản Tự động hóa (Automation Eligibility)
- [x] Luồng nghiệp vụ cốt lõi (Core Happy Paths).
- [x] Kịch bản kiểm thử hồi quy (Regression Suite) lặp lại nhiều lần.
- [x] Kịch bản kiểm thử API và dữ liệu khối lượng lớn.
- [ ] *Tránh tự động hóa:* Kịch bản UI thay đổi liên tục hoặc test 1 lần (Ad-hoc testing).

## Quy trình Thực hiện
1. **Rà soát Test Cases Thủ công:** Đọc danh sách kịch bản trong `05_Testing/Test_Cases`.
2. **Trích xuất Test Steps & Assertions:** Xác định preconditions, action steps và expected results.
3. **Sinh mã Automation:** Dùng Playwright/Selenium tạo script tự động tương ứng.
4. **Xác minh Độ tin cậy:** Chạy thử nghiệm script 5 lần liên tiếp để đảm bảo không bị Flaky.

## Checklist
- [ ] Mọi kịch bản automation đều có assertions rõ ràng.
- [ ] Mã nguồn script được lưu vào thư mục `05_Testing/Source_Code` hoặc `tests/`.
