---
name: context-engineering
description: "Kỹ thuật tối ưu hóa ngữ cảnh và nạp dữ liệu cho AI Agent hoạt động chính xác."
---

# Context Engineering (Kỹ thuật Quản lý Bối cảnh AI)

## Tổng quan
Nghệ thuật và phương pháp xây dựng, quản lý và nạp bối cảnh (Context Window) cho AI Agent nhằm đảm bảo AI hiểu đúng yêu cầu, không bị nhiễu thông tin và không sinh ra thông tin sai lệch (Hallucinations).

## Khi nào sử dụng
- Khởi tạo task mới hoặc chuẩn bị nạp tài liệu cho AI phân tích.
- Khi AI bắt đầu trả lời sai lệch hoặc quên quy tắc dự án.
- Thiết lập hệ thống Knowledge Base & Project Index.

## Nguyên tắc Cốt lõi
1. **Right-Sizing Context:** Chỉ cung cấp những file và đoạn mã trực tiếp liên quan tới task. Tránh nạp toàn bộ codebase.
2. **Explicit References (EP-01):** Cung cấp chính xác vị trí file:line và phiên bản tài liệu.
3. **Structured Prompts:** Định nghĩa rõ Mục tiêu, Nguồn, Phạm vi, Quy tắc, Output và Tiêu chuẩn kiểm tra.

## Checklist
- [ ] Bối cảnh chứa thông tin phiên bản tài liệu chuẩn.
- [ ] Loại bỏ các dữ liệu nhạy cảm trước khi gửi vào AI (AI-03).
