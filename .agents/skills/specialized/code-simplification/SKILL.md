---
name: code-simplification
description: "Tối giản mã nguồn, loại bỏ độ phức tạp không cần thiết và tái cấu trúc Clean Code."
---

# Code Simplification (Tối giản & Clean Code)

## Tổng quan
Kỹ thuật rút gọn và đơn giản hóa mã nguồn phức tạp mà không làm thay đổi hành vi chuẩn của phần mềm (Refactoring). Giảm độ phức tạp Cyclomatic Complexity và giúp code dễ bảo trì.

## Khi nào sử dụng
- Sau khi viết xong chức năng và Unit Test đã PASS.
- Khi gặp các hàm quá dài, nhiều nếp lồng `if-else` hoặc vòng lặp lồng nhau.
- Chuẩn bị tạo Pull Request cho Peer Review.

## Quy tắc Refactoring
1. **Early Return / Guard Clauses:** Loại bỏ lồng `if-else` bằng cách throw error hoặc return sớm ở đầu hàm.
2. **KISS (Keep It Simple, Stupid):** Ưu tiên giải pháp đơn giản nhất hoạt động đúng.
3. **DRY (Don't Repeat Yourself):** Trích xuất logic lặp lại thành helper function hoặc utility class.

## Checklist Kiểm tra
- [ ] 100% Unit Tests vẫn PASS sau khi refactor.
- [ ] Hàm không dài quá 30-40 dòng lệnh.
- [ ] Tên biến và tham số tự giải thích ý nghĩa.
