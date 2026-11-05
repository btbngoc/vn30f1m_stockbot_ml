---
name: using-agent-skills
description: "Hướng dẫn vận hành, phối hợp và quản lý bộ kỹ năng Agent Skills trong tổ chức."
---

# Using Agent Skills (Hướng dẫn Vận hành & Phối hợp Agent Skills)

## Tổng quan
Tài liệu hướng dẫn tổng thể cách khám phá, nạp, phối hợp và kích hoạt bộ kỹ năng AI Agent Skills trong suốt vòng đời dự án IT theo mô hình Waterfall.

## Cách thức Khám phá & Kích hoạt Skill
1. **Theo Phase của Dự án:** Mỗi Phase trong Waterfall (từ Phase 1 đến Phase 9) tích hợp các specialized skills tương ứng.
2. **Theo Vai trò Agent:** Mỗi vai trò (PM, BA, Architect, Dev, QA, DevOps, SRE, Support) có danh mục AI Skills được phép sử dụng.
3. **Nạp Bối cảnh (Context Loading):** Đọc nội dung file `SKILL.md` trước khi giao việc cho AI để đảm bảo AI tuân thủ đúng quy trình.

## Phối hợp giữa các Agent Skills
- Các Agent Skills có thể phối hợp chuỗi (Chaining): vd: `spec-driven-development` $\rightarrow$ `test-driven-development` $\rightarrow$ `code-simplification` $\rightarrow$ `code-review-and-quality`.

## Checklist
- [ ] AI Agent nạp đầy đủ `SKILL.md` trước khi thực thi task.
- [ ] Tuân thủ nghiêm ngặt bộ 8 AI Governance Rules và 3 Engineering Principles.
