---
name: deprecation-and-migration
description: "Quy trình loại bỏ chức năng cũ (Deprecation) và nâng cấp hệ thống (Migration) an toàn."
---

# Deprecation and Migration (Bảo trì & Chuyển đổi Hệ thống)

## Tổng quan
Quy trình lập kế hoạch và thực thi đánh dấu không còn hỗ trợ (Deprecate) các API, thư viện hoặc schema cũ, đồng thời thực hiện chuyển đổi (Migration) sang phiên bản mới mà không làm gián đoạn người dùng.

## Khi nào sử dụng
- Thay đổi phá vỡ tương thích (Breaking changes) trên API public.
- Cập nhật database schema (Thêm/xóa bảng, đổi tên cột).
- Nâng cấp phiên bản framework chính (vd: Node 18 -> Node 20).

## Chiến lược Chuyển đổi An toàn
1. **Expand and Contract Pattern:** 
   - *Bước 1 (Expand):* Thêm field/API mới, hỗ trợ song song cả cũ và mới.
   - *Bước 2 (Migrate):* Chuyển toàn bộ traffic người dùng sang API mới.
   - *Bước 3 (Contract):* Gắn nhãn `@deprecated`, gửi cảnh báo và xóa API cũ sau thời gian cam kết.
2. **Zero-Downtime DB Migration:** Chạy migration script không khóa bảng (non-blocking).

## Checklist
- [ ] Có cảnh báo Deprecation trong API response header hoặc log.
- [ ] Có kịch bản Rollback chi tiết nếu Migration thất bại trên Production.
