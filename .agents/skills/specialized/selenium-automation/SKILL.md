---
name: selenium-automation
description: "Xây dựng kịch bản kiểm thử tự động Web UI với Selenium WebDriver."
---

# Selenium Automation (Kiểm thử Tự động với Selenium)

## Tổng quan
Kỹ năng xây dựng framework và viết script tự động hóa giao diện web với Selenium WebDriver (Java/Python/Node.js), sử dụng mô hình Page Object Model (POM) và Explicit Waits.

## Khi nào sử dụng
- Dự án yêu cầu kiểm thử tự động trên hệ thống Legacy hoặc trình duyệt doanh nghiệp đặc thụ.
- Tích hợp với Selenium Grid để phân tán tải kiểm thử.

## Quy chuẩn Thực thi
1. **Explicit Waits:** Dùng `WebDriverWait` và `ExpectedConditions`, không dùng `Thread.sleep()`.
2. **Page Object Model (POM):** Đóng gói phần tử UI và thao tác theo từng trang.
3. **Cross-Browser Driver Management:** Dùng WebDriverManager để tự động quản lý browser drivers.

## Checklist
- [ ] Xử lý đóng browser session đầy đủ (`driver.quit()`) trong cleanup block.
- [ ] Chụp ảnh màn hình tự động khi test case bị thất bại.
