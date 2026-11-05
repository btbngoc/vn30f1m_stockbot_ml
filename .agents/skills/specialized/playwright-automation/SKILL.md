---
name: playwright-automation
description: "Xây dựng khung và mã nguồn kiểm thử tự động (E2E / API Testing) với Playwright Framework."
---

# Playwright Automation (Kiểm thử Tự động với Playwright)

## Tổng quan
Kỹ năng xây dựng framework và viết kịch bản kiểm thử tự động (Automation Test Script) cho giao diện Web UI và REST API sử dụng Playwright Framework theo mô hình Page Object Model (POM).

## Khi nào sử dụng
- Xây dựng bộ kiểm thử tự động End-to-End (E2E) cho ứng dụng Web.
- Kiểm thử API tự động với tốc độ cao và tính ổn định tốt.
- Kiểm thử đa trình duyệt (Chromium, Firefox, WebKit) và mô phỏng thiết bị di động (Mobile Emulation).

## Kiến trúc & Quy chuẩn Thực thi
1. **Page Object Model (POM):** Tách biệt locator/action trên trang web khỏi test logic.
2. **Auto-Waiting:** Tận dụng cơ chế tự động chờ của Playwright, tránh dùng hardcode `sleep()`.
3. **Parallel Execution:** Cấu hình chạy test song song để tối ưu thời gian chạy CI/CD Pipeline.

## Quy trình Thực hiện
1. **Khởi tạo Framework:** Cấu hình `playwright.config.ts` (baseURL, trace, video, screenshot khi fail).
2. **Định nghĩa Page Objects:** Tạo các class định vị phần tử (Locators) và phương thức thao tác.
3. **Viết Test Specs:** Viết kịch bản test sạch sẽ, dễ đọc với các câu lệnh `expect()`.
4. **Tích hợp CI/CD (EP-03):** Kết xuất báo cáo HTML và lưu giữ bằng chứng (Trace artifact).

## Checklist
- [ ] 100% locators dùng ưu tiên `getByRole`, `getByText`, `getByTestId`.
- [ ] Không dùng `page.waitForTimeout()` cứng.
- [ ] Test cases chạy độc lập, không phụ thuộc thứ tự execution.
