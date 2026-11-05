---
name: test-driven-development
description: "Phát triển hướng kiểm thử TDD (Red - Green - Refactor) đảm bảo độ bao phủ ≥ 80%."
---

# Test-Driven Development (Phát triển Hướng Kiểm thử TDD)

## Tổng quan
Kỹ thuật phát triển phần mềm theo chu trình Red-Green-Refactor: Viết test case tự động trước khi viết code thực thi, đảm bảo code sinh ra luôn được kiểm thử và đáp ứng thiết kế.

## Vòng lặp Red-Green-Refactor
1. **RED:** Viết một Unit Test cho yêu cầu mới. Chạy test và xác nhận test **FAIL** (do chưa có code thực thi).
2. **GREEN:** Viết mã nguồn tối thiểu đủ để Unit Test **PASS**.
3. **REFACTOR:** Tối ưu hóa mã nguồn (áp dụng `code-simplification`), đảm bảo Unit Test vẫn **PASS**.

## Pattern Viết Unit Test: AAA (Arrange - Act - Assert)
- **Arrange:** Chuẩn bị dữ liệu đầu vào và các đối tượng giả lập (Mocks/Stubs).
- **Act:** Thực thi hàm/chức năng cần kiểm tra.
- **Assert:** Xác nhận kết quả trả về đúng kỳ vọng.

## Tiêu chuẩn nghiệm thu
- Unit Test Coverage tối thiểu 80%.
- Bao phủ Happy paths, Edge cases và Exception scenarios.

## Checklist
- [ ] Mọi hàm xử lý logic phức tạp đều có Unit Test đi kèm.
- [ ] Không swallow exception trong code hoặc trong test case.
