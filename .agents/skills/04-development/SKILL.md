---
name: 04-development
description: "AI-Enabled Skill cho Phase 4: Development - Xây dựng mã nguồn, Refactoring, Code Review, sinh Unit Test và Security Scan."
---

# Phase 4: Development Skill

## 1. Mục tiêu & Scope
Triển khai xây dựng phần mềm dựa trên tài liệu thiết kế (HLD/LLD/API Spec), tuân thủ tiêu chuẩn lập trình (Coding Standards), đạt phủ Unit Test tối thiểu 80%, không chứa lỗi bảo mật nghiêm trọng và qua bước Peer/AI Code Review.

- **Owners:** Developer, Tech Lead
- **Vị trí lưu sản phẩm:** `04_Development/Source_Code`, `04_Development/Unit_Test`, `04_Development/Code_Review`

---

## 2. Input Cần Có
- HLD, LLD, API Spec, Data Model từ Phase 3.
- `CODING_CONVENTION.md` của dự án.
- Pre-Commit Checklist & AI Code Review Checklist.

---

## 3. Quy trình AI Hỗ trợ (AI Contribution)
1. **Code Generation:** Sinh mã nguồn boilerplate, DTOs, Controllers, Services, Repositories theo thiết kế và convention.
2. **Refactoring:** Cải thiện cấu trúc mã nguồn, tối ưu luồng xử lý, loại bỏ code trùng lặp (DRY), áp dụng nguyên tắc SOLID.
3. **AI Code Review:** Tự động rà soát code theo checklist:
   - SOLID Principles & Clean Code
   - Security Vulnerabilities (OWASP Top 10, SQL Injection, XSS, Hardcoded secrets)
   - Performance Issues & Memory Leak Risk
   - Exception handling coverage & Logging completeness
4. **Unit Test Generation:** Sinh bộ Unit Test tự động (Arrange - Act - Assert) đảm bảo phủ tất cả các nhánh logic (Happy path, Edge cases, Exception cases).
5. **Security Scan Assist:** Đọc kết quả từ SAST/SonarQube và gợi ý sửa chữa.

---

## 4. Deliverables Output
- `Source Code`: Mã nguồn chức năng đã được format và tuân thủ convention.
- `Unit Test`: Mã nguồn các ca kiểm thử đơn vị.
- `Code_Review_Report.md`: Kết quả AI & Peer Code Review, danh sách các issue đã fix.
- `Technical_Documentation.md`: Tài liệu hướng dẫn kỹ thuật / API doc cập nhật.

---

## 5. Quality Gate / Exit Criteria
- [ ] Coding Standard followed: Tuân thủ 100% quy tắc Naming, Style và Structure trong `CODING_CONVENTION.md`.
- [ ] Validation completed: Validate đầy đủ toàn bộ Input/Output.
- [ ] Exception Handling implemented: Không swallow exception, sử dụng Custom Error đúng chuẩn.
- [ ] Logging implemented: Bắt buộc log Error, Warning và Business Events.
- [ ] Security check passed: Không hardcode secret/token/password; qua scan OWASP/SAST.
- [ ] Unit Test Coverage ≥ 80%: Đạt tỷ lệ bao phủ dòng lệnh và nhánh logic theo yêu cầu.
- [ ] Sonar Critical = 0: Không còn lỗi mức Critical/Blocker trên SonarQube hoặc công cụ static analysis.
- [ ] Peer Review completed: Tech Lead / Peer Developer duyệt PR.

---

## 6. Enforced Governance & Engineering Principles
- **EP-01 (Cite the Source or State the Assumption):** Khi giải thích lỗi hoặc sửa code, phải dẫn chứng chính xác `file:line-line`. Không đoán mò khi chưa đọc code.
- **EP-03 (Reviewer Comment Must Never Repeat):** Mọi nhận xét review từ Tech Lead / Peer nếu lặp lại lỗi đã từng xuất hiện phải được chuyển hóa ngay thành Lint Rule hoặc AI Review Skill Rule để tự động hóa chặn ở CI/CD gate.
- **AI-07 (Test Before Production):** Không bao giờ merge mã nguồn do AI sinh ra khi chưa chạy qua suite Unit Test và Build thử nghiệm thành công.
