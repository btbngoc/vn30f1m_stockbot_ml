---
name: planning-and-task-breakdown
description: "Lập kế hoạch dự án và phân rã công việc (Work Breakdown Structure - WBS)."
---

# Planning and Task Breakdown (Lập Kế hoạch & Phân rã Task WBS)

## Tổng quan
Kỹ năng lập kế hoạch dự án IT theo mô hình Waterfall, phân rã các Deliverables lớn thành cấu trúc công việc chi tiết (WBS), ước lượng effort và xác định các phụ thuộc (Dependencies).

## Khi nào sử dụng
- Đầu Phase 1 (Initiation) hoặc khi bắt đầu một Sprint/Giai đoạn phát triển mới.
- Soạn thảo `Project_Plan.xlsx` và `plan.md`.

## Quy trình Phân rã WBS
1. **Phân rã theo Phase:** Initiation $\rightarrow$ Requirement $\rightarrow$ Design $\rightarrow$ Dev $\rightarrow$ Test $\rightarrow$ UAT $\rightarrow$ Deploy $\rightarrow$ Ops $\rightarrow$ Closure.
2. **Xác định Task chi tiết:** Mỗi task phải có Scope rõ ràng, Thời gian thực hiện (0.5 - 2 ngày), Người chịu trách nhiệm (Owner) và Tiêu chí hoàn thành (Quality Gate).
3. **Ước lượng Effort:** Cần tính cả thời gian review, sửa lỗi (rework) và kiểm thử.
4. **Gắn nguồn trích dẫn (EP-01):** Trích dẫn căn cứ ước lượng hoặc ghi nhãn `Status: Not Verified`.

## Checklist
- [ ] Task đủ nhỏ để đo lường tiến độ hàng ngày.
- [ ] Mọi task đều có owner và reviewer rõ ràng.
