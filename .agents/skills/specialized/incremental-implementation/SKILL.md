---
name: incremental-implementation
description: "Phát triển phần mềm theo phương pháp cuốn chiếu từng bước nhỏ (Small Incremental Steps)."
---

# Incremental Implementation (Triển khai Cuốn chiếu theo Bước nhỏ)

## Tổng quan
Chiến lược chia nhỏ task phát triển lớn thành các bước thực thi siêu nhỏ (Small Atomic Increments). Mỗi bước đều chạy được, kiểm thử được và không làm hỏng mã nguồn hiện tại.

## Khi nào sử dụng
- Khi triển khai tính năng phức tạp hoặc tái cấu trúc mã nguồn lớn.
- Giúp dễ dàng debug, rà soát code và rollback khi có sự cố.

## Quy trình thực hiện
1. **Phân rã Task:** Chia task chính thành 3-5 bước nhỏ có thứ tự phụ thuộc rõ ràng.
2. **Thực thi từng bước:**
   - Viết code cho bước 1.
   - Chạy Unit Test xác nhận thành công.
   - Commit mã nguồn bước 1.
3. **Lặp lại cho đến khi hoàn thành.**

## Checklist
- [ ] Không commit những đoạn code đang dở dang không thể build.
- [ ] Mỗi increment đều có Unit Test hoặc bài kiểm tra đi kèm.
