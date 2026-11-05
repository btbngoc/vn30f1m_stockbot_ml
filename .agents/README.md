# 🤖 AI-Enabled Waterfall Project Delivery Starter Kit

Bộ Starter Kit hướng dẫn và áp dụng AI cho toàn bộ 9 giai đoạn của dự án IT theo mô hình Waterfall (Initiation, Requirement Analysis, Solution Design, Development, Testing, UAT, Deployment, Operations & Support, Project Closure), hợp nhất **30 AI Agent Skills Kỹ thuật Chuyên sâu** (tích hợp Antigravity Testing Kit) bằng **Tiếng Việt**.

---

## 🌟 Tính năng chính

- **End-to-End Waterfall Workflow:** Tích hợp AI đóng góp vào từng Phase, kèm theo Owner, Deliverables và Quality Gates cụ thể.
- **Hướng dẫn Workflow Thực hành (`AI_WORKFLOW_GUIDE.md`):** Quy trình 5 bước thực thi task chuẩn với AI, hướng dẫn theo 8 vai trò (PM, BA, Dev, QA, DevOps, SRE, Support) và bộ Prompt Library mẫu.
- **Bộ 9 AI Phase Skills (`skills/01-initiation` đến `09-project-closure`):** Định nghĩa mục tiêu, quy trình AI hỗ trợ, output và tiêu chí nghiệm thu cho 9 phase.
- **Bộ 30 Specialized AI Agent Skills (`skills/specialized/` - Tiếng Việt):**
  - *Initiation & Requirement:* `idea-refine`, `interview-me`, `planning-and-task-breakdown`, `spec-driven-development`, `context-engineering`.
  - *Design & Architecture:* `api-and-interface-design`, `documentation-and-adrs`, `constraint-driven-development`.
  - *Development & Engineering:* `test-driven-development`, `incremental-implementation`, `source-driven-development`, `code-simplification`, `frontend-ui-engineering`, `doubt-driven-development`, `code-review-and-quality`.
  - *Testing & Automation (Tích hợp Antigravity Testing Kit):* `playwright-automation`, `selenium-automation`, `manual-to-automation`, `flaky-test-analysis`, `test-data-generation`, `browser-testing-with-devtools`, `code-review-and-quality`.
  - *Deployment & Release:* `git-workflow-and-versioning`, `ci-cd-and-automation`, `shipping-and-launch`, `deprecation-and-migration`.
  - *Operations & SRE:* `observability-and-instrumentation`, `debugging-and-error-recovery`, `performance-optimization`, `security-and-hardening`.
- **Bộ Công Cụ Scripts Tích Hợp (`scripts/`):**
  - `scripts/convert_excel/md_to_xlsx.js`: Chuyển đổi file `Test_Cases.md` thành file Excel `.xlsx`.
  - `scripts/integrations/jira/`: Đồng bộ trực tiếp Test Cases và Defects lên Jira / Xray.
  - `scripts/integrations/google_sheet/`: Đồng bộ báo cáo kiểm thử lên Google Sheet trực tuyến.
- **Engineering Principles (EP-01, EP-02, EP-03):** 
  - **EP-01:** Phải trích dẫn nguồn (`file:line`) hoặc ghi rõ `Status: Not Verified`.
  - **EP-02:** Đo đạc 5 chỉ số (Dataset, Environment, Target, Metric, Result) trước khi kết luận RCA/Performance.
  - **EP-03:** Không bao giờ lặp lại cùng 1 comment review – chuyển hóa ngay thành Lint / AI Skill Rule tự động.
- **AI Governance Rules (AI-01 đến AI-08):** Đảm bảo an toàn dữ liệu, con người duyệt (HITL), bảo mật và truy vết (Traceability).

---

## 📂 Cấu trúc thư mục Starter Kit

```text
.
├── AI_WORKFLOW_GUIDE.md     # Hướng dẫn chi tiết Quy trình thực thi Task & Prompt Library
├── GUIDE.md                 # Master Framework Documentation (Chính sách & Khung tổng thể)
├── CODING_CONVENTION.md     # Quy chuẩn lập trình & Review checklist
├── FOLDER_STRUCTURE.md      # Tài liệu chi tiết cấu trúc thư mục
├── scripts/                 # Bộ công cụ Excel Exporter, Jira/Xray & Google Sheets Sync
├── skills/                  # 9 Phase Skills + 30 Specialized Agent Skills (Tiếng Việt)
├── agents/                  # Bộ 8 Role Agents theo AI Skill Matrix
├── task/                    # Biểu mẫu quản lý Task Execution
└── README.md                # Tài liệu hướng dẫn này
```

---

> **Golden Principle:** *AI is a project team member, not a project owner.*
