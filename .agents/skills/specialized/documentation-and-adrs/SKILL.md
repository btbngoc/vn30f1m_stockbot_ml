---
name: documentation-and-adrs
description: "Soạn thảo tài liệu dự án và ghi nhận các quyết định kiến trúc (Architecture Decision Records - ADR)."
---

# Documentation and ADRs (Tài liệu hóa & Ghi nhận Quyết định Kiến trúc)

## Tổng quan
Quy trình viết và duy trì tài liệu kỹ thuật chất lượng cao, bao gồm việc ghi nhận các Quyết định Kiến trúc Trọng yếu (ADR - Architecture Decision Record) giúp lưu giữ bối cảnh và lý do đằng sau các lựa chọn công nghệ.

## Cấu trúc chuẩn của một ADR
1. **Title:** Tên quyết định (vd: *ADR-005: Sử dụng PostgreSQL thay cho MongoDB cho Module Đơn hàng*).
2. **Status:** `Proposed` | `Accepted` | `Deprecated` | `Superseded`.
3. **Context:** Bối cảnh và bài toán kỹ thuật cần giải quyết.
4. **Decision:** Quyết định lựa chọn giải pháp nào và lý do.
5. **Consequences:** Hệ quả tích cực và đánh đổi (trade-offs) tiêu cực.

## Quy tắc Trích dẫn EP-01
- Mọi tài liệu phải liên kết chính xác tới mã nguồn hoặc thiết kế gốc.
- Nếu tài liệu chứa các ước lượng chưa kiểm chứng $\Rightarrow$ Bắt buộc ghi `Status: Not Verified`.

## Checklist
- [ ] ADR được lưu trữ trong thư mục `03_Design/HLD` hoặc repo dự án.
- [ ] Tài liệu được cập nhật đồng thời khi có thay đổi mã nguồn.
