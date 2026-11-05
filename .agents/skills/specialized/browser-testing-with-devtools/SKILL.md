---
name: browser-testing-with-devtools
description: "Kỹ thuật kiểm thử trình duyệt giao diện UI/UX sử dụng DevTools và tự động hóa."
---

# Browser Testing with DevTools (Kiểm thử Trình duyệt qua DevTools)

## Tổng quan
Kỹ năng kiểm thử, chẩn đoán sự cố giao diện người dùng (Frontend UI/UX) và luồng tương tác trên trình duyệt web thông qua Chrome DevTools hoặc các công cụ browser automation.

## Khi nào sử dụng
- Kiểm thử các kịch bản UI/UX phức tạp, responsive layout và CSS.
- Chẩn đoán lỗi JavaScript runtime trên trình duyệt hoặc API request thất bại (Network tab).
- Đánh giá hiệu năng tải trang (Performance tab, Lighthouse).
- Kiểm tra tính truy cập (Accessibility - a11y) và Responsive breakpoints.

## Quy trình thực hiện
1. **Rà soát Console & Network:** Kiểm tra các lỗi Console errors, failed network requests (4xx, 5xx) và CORS issues.
2. **Kiểm thử Luồng Nghiệp vụ (End-to-End):** Thực thi kịch bản kiểm thử luồng người dùng (User Journeys) từ trang đăng nhập đến hoàn tất giao dịch.
3. **Đo đạc Hiệu năng (EP-02):** Đo đạc các chỉ số Core Web Vitals (LCP, FID, CLS, TTFB) kèm theo bằng chứng cụ thể:
   - **Dataset:** Kích thước tài nguyên (images, bundles).
   - **Environment:** Trình duyệt & thiết bị kiểm thử.
   - **Target:** Trang/Component cần đo.
   - **Metric:** LCP / Execution Time.
   - **Result:** Con số thực tế.

## Checklist Kiểm tra
- [ ] Không có lỗi Uncaught Exception trong Console.
- [ ] Đạt chuẩn hiển thị trên Mobile, Tablet và Desktop.
- [ ] Form validation hoạt động đúng với cả input hợp lệ và không hợp lệ.
