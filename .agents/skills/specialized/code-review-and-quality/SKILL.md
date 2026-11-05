---
name: code-review-and-quality
description: "Quy trình Review mã nguồn nâng cao và đảm bảo chất lượng theo nguyên tắc EP-03."
---

# Code Review and Quality (Review Mã nguồn & Đảm bảo Chất lượng)

## Tổng quan
Quy trình rà soát mã nguồn tự động và thủ công nhằm nâng cao chất lượng code, tuân thủ các nguyên tắc SOLID, Clean Code, OWASP và phát hiện sớm các nguy cơ rò rỉ bộ nhớ/hiệu năng.

## Nguyên tắc Vàng EP-03
> **Reviewer Comment Must Never Repeat:** Một nhận xét review chỉ nên xuất hiện đúng một lần. Nếu cùng một lỗi xuất hiện lặp lại ở các PR sau, đó không phải lỗi của Dev mà là hệ thống đang thiếu Automation/Rule.

## Quy trình thực hiện
1. **Chạy AI Code Review Checklist:**
   - SOLID Principles & Clean Code.
   - Trùng lặp code (DRY).
   - Bảo mật (OWASP Top 10, No Hardcoded Secrets).
   - Performance & Memory Leaks.
   - Exception Handling & Logging.
2. **Kiểm tra lặp lỗi (EP-03 Pattern Identification):**
   - Nếu lỗi từng xuất hiện trước đây $\rightarrow$ Tạo ngay Lint Rule hoặc AI Skill Rule mới.
   - Chạy thử Rule mới trên PR hiện tại để đảm bảo bắt lại đúng lỗi.
3. **Cập nhật Governance Rule Base.**

## Checklist Reviewer
- [ ] Code tuân thủ `CODING_CONVENTION.md`.
- [ ] Unit Test Coverage ≥ 80%.
- [ ] Không rò rỉ secret hoặc thông tin nhạy cảm.
- [ ] Mọi comment lặp lại đều được tạo Lint / Rule tự động.
