---
name: test-data-generation
description: "Sinh bộ dữ liệu kiểm thử giả lập (Mock Test Data) chuẩn hóa và an toàn bảo mật."
---

# Test Data Generation (Sinh Dữ liệu Kiểm thử)

## Tổng quan
Kỹ thuật sinh dữ liệu giả lập (Mock Data / Fixtures) có cấu trúc, đa dạng và thực tế phục vụ cho kịch bản kiểm thử đơn vị, kiểm thử tích hợp và kiểm thử tự động.

## Nguyên tắc Bảo mật AI-03
> **No Production Data Leak:** Tuyệt đối KHÔNG sử dụng dữ liệu Production thật chứa thông tin cá nhân khách hàng (PII), mật khẩu hay số tài khoản để làm Test Data.

## Loại Dữ liệu Cần Sinh
1. **Valid Data (Happy Path):** Dữ liệu chuẩn đúng định dạng.
2. **Invalid Data (Negative Path):** Dữ liệu sai type, thiếu trường bắt buộc, vượt độ dài.
3. **Boundary Data (Edge Case):** Giá trị cực biên (null, empty string, 0, MAX_INT, ký tự đặc biệt SQL/XSS).

## Checklist
- [ ] Dữ liệu test độc lập và tái lập được (Reproducible).
- [ ] Dùng thư viện Faker / Factory-bot thay vì hardcode chuỗi cố định.
