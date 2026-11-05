# 📖 Hướng Dẫn Quy Trình Làm Việc Với AI (AI Workflow Guide)

> **Khẩu hiệu cốt lõi (Golden Rule):** *AI is a project team member, not a project owner.*
> AI đóng vai trò là trợ lý năng suất cao, hỗ trợ phân tích, viết mã, sinh test case và soạn tài liệu. Con người (Human-in-the-Loop - HITL) chịu trách nhiệm phê duyệt cuối cùng và sở hữu kết quả.

---

## 🎯 1. Tổng Quan Quy Trình Làm Việc AI

Khung làm việc AI Workflow được thiết kế nhằm đảm bảo tính **Chuẩn hóa - Truy vết được - Kiểm soát an toàn - Không lặp lại sai lầm**. 

```text
    [Ý Tưởng / Task]
           │
           ▼
┌─────────────────────────┐
│ 1. Context & Task Brief │  <--- Nạp file:line, Gán Status: Not Verified (EP-01)
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│ 2. Kế hoạch & Quality   │  <--- Phân rã WBS, Nạp SKILL.md & Agent Role
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│ 3. Co-Working với AI    │  <--- Lập trình TDD, Clean Code, Refactor cuốn chiếu
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│ 4. Kiểm thử & Đo đạc    │  <--- 5 Chỉ số EP-02 (Dataset, Env, Target, Metric, Result)
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│ 5. Review & Bàn giao    │  <--- Kiểm tra lặp lỗi EP-03 -> Tạo Lint/Rule tự động
└─────────────────────────┘
```

---

## 🔄 2. Quy Trình 5 Bước Thực Thi Một Task Chuẩn Với AI

### 📌 Bước 1: Khởi Tạo Task Brief & Quản Lý Bối Cảnh (Context Engineering)

1. **Tạo file `task/task_brief.md`:**
   - Điền đầy đủ mục tiêu, phạm vi (In-Scope / Out-of-Scope) và tiêu chí nghiệm thu (Acceptance Criteria).
   - **Tuân thủ EP-01:** Trích dẫn chính xác nguồn dữ liệu (`path/to/file.ts#L20-L45` hoặc Ticket ID).
   - Nếu thông tin chưa có chứng minh, đánh dấu rõ `Status: Not Verified`.

2. **Cấu hình Bối Cảnh trong `task/context.md`:**
   - Chỉ nạp các tài liệu và đoạn mã nguồn trực tiếp liên quan (Right-sizing context).
   - Nạp file `SKILL.md` tương ứng với Phase (ví dụ: `skills/04-development/SKILL.md`) và Specialized Skill liên quan (ví dụ: `skills/specialized/test-driven-development/SKILL.md`).
   - Tuân thủ **AI-03 (Data Protection):** Tuyệt đối loại bỏ passwords, API secrets, PII hoặc dữ liệu khách hàng nhạy cảm.

---

### 📋 Bước 2: Lập Kế Hoạch Thực Thi (Execution Planning)

1. **Soạn thảo `task/plan.md`:**
   - Phân rã task lớn thành các bước thực thi siêu nhỏ (sử dụng skill `incremental-implementation`).
   - Mỗi bước thực thi phải có: **Đầu vào $\rightarrow$ Hành động $\rightarrow$ Đầu ra $\rightarrow$ Tiêu chí Verify**.
2. **Gán Agent Role phù hợp:**
   - Đọc vai trò tương ứng trong `agents/` (ví dụ: `developer.md` cho Dev, `qa.md` cho Tester, `sre.md` cho SRE).
   - Định nghĩa rõ người review và người chịu trách nhiệm nghiệm thu (RACI).

---

### 💻 Bước 3: Phối Hợp Thực Thi Cùng AI (AI Co-Working)

1. **Quy tắc làm việc với AI:**
   - **Luôn yêu cầu AI trích dẫn nguồn (EP-01):** "Hãy chỉ ra chính xác dòng code nào trong file `src/user.service.ts` gây ra bug này."
   - **Không chấp nhận suy đoán:** Nếu AI đưa ra giả thuyết chưa verify, yêu cầu AI ghi nhãn `Status: Not Verified`.
   - **Áp dụng TDD (Test-Driven Development):**
     1. Yêu cầu AI sinh Unit Test trước (`RED`).
     2. Yêu cầu AI sinh mã thực thi tối thiểu để PASS test (`GREEN`).
     3. Tối ưu mã nguồn với `code-simplification` (`REFACTOR`).
2. **Tuân thủ `CODING_CONVENTION.md`:**
   - Validate đầy đủ Input/Output.
   - Không swallow exception (try/catch rỗng).
   - Log đầy đủ Error, Warning và Business Events kèm `correlationId`.

---

### 🧪 Bước 4: Kiểm Thử & Thu Tập Bằng Chứng (Verification & Evidence)

1. **Ghi nhận Kết quả Đo đạc (Bắt buộc tuân thủ EP-02 khi Debug/RCA/Performance):**
   - Lưu kết quả vào `task/step_result.md` với đầy đủ **5 chỉ số**:
     ```text
     1. Dataset: 500,000 records / 10,000 req/min
     2. Environment: Production K8s Node-02, Node.js v20.10, PostgreSQL 16
     3. Target Function/System: loadCustomerData() / API /v1/orders
     4. Metric: Execution Time / CPU Saturation / Memory Peak
     5. Result: 3.4 seconds / 98% CPU saturation
     ```
   - *Lưu ý: Thiếu 1 trong 5 mục $\Rightarrow$ `Result = Invalid`.*

2. **Chạy Kiểm thử Tự động & Điền `task/verification.md`:**
   - Unit Test Coverage $\ge 80\%$.
   - Sonar Static Scan: `Sonar Critical = 0`.
   - OWASP Security Scan: PASS.
   - Đính kèm log chạy test thực tế.

---

### 🔍 Bước 5: Review & Bàn Giao (Review & Handoff Gate)

1. **Thực hiện AI & Peer Code Review (`task/review.md`):**
   - Đánh giá theo AI Code Review Checklist: SOLID, Clean Code, DRY, OWASP Top 10, Performance, Memory Leak.
2. **Kiểm tra Lặp Lỗi (Bắt buộc tuân thủ EP-03):**
   - Đặt câu hỏi: *"Lỗi này từng xuất hiện ở PR hoặc Task trước chưa?"*
   - Nếu **CÓ**: Bắt buộc tạo hoặc cập nhật **Lint Rule** hoặc **AI Skill Rule** mới để tự động bắt lỗi từ các lần sau.
3. **Bàn giao Deliverables (`task/handoff.md`):**
   - Chuyển file sản phẩm vào đúng thư mục trong **Deliverables Repository Structure**:
     - Phase 1 $\rightarrow$ `01_Initiation/`
     - Phase 2 $\rightarrow$ `02_Requirement/`
     - Phase 3 $\rightarrow$ `03_Design/`
     - Phase 4 $\rightarrow$ `04_Development/`
     - Phase 5 $\rightarrow$ `05_Testing/`
     - Phase 6 $\rightarrow$ `06_UAT/`
     - Phase 7 $\rightarrow$ `07_Deployment/`
     - Phase 8 $\rightarrow$ `08_Operations/`
     - Phase 9 $\rightarrow$ `09_Closure/`

---

## 👥 3. Hướng Dẫn Workflow Chi Tiết Theo Vai Trò (Role-Based AI Workflows)

### 📊 3.1. Workflow Cho PM (Project Manager)
- **Phase chính:** Phase 1 (Initiation) & Phase 9 (Closure).
- **Skills sử dụng:** `skills/01-initiation`, `skills/09-project-closure`, `planning-and-task-breakdown`, `idea-refine`.
- **Các bước thực hiện:**
  1. Sử dụng `idea-refine` để làm rõ phạm vi và mục tiêu từ SOW/Presale.
  2. Sử dụng `planning-and-task-breakdown` để phân rã WBS, ước lượng effort (tính cả công review/rework/test).
  3. Tạo `Project_Charter.md` và `Risk_Register.md` gửi Stakeholders duyệt (AI-01).
  4. Đóng dự án: Dùng `skills/09-project-closure` tổng kết `Closure_Report.md` và bài học `Lessons_Learned.md`.

---

### 📝 3.2. Workflow Cho BA (Business Analyst)
- **Phase chính:** Phase 2 (Requirement Analysis) & Phase 6 (UAT).
- **Skills sử dụng:** `skills/02-requirement-analysis`, `skills/06-uat`, `spec-driven-development`, `interview-me`.
- **Các bước thực hiện:**
  1. Dùng `interview-me` phỏng vấn khách hàng/PO để làm rõ các điểm mơ hồ.
  2. Dùng `spec-driven-development` chuẩn hóa User Stories (As a... I want to... So that...) và Acceptance Criteria (Given... When... Then...).
  3. Tạo ma trận truy vết `RTM.md` nối từ Requirement $\rightarrow$ User Story $\rightarrow$ Test Case.
  4. Soạn tài liệu `User_Guide.md` và `UAT_Script.md` cho người dùng nghiệm thu.

---

### 🏗️ 3.3. Workflow Cho Architect / Tech Lead
- **Phase chính:** Phase 3 (Solution Design) & Review Phase 4.
- **Skills sử dụng:** `skills/03-solution-design`, `api-and-interface-design`, `documentation-and-adrs`, `security-and-hardening`.
- **Các bước thực hiện:**
  1. Dùng `api-and-interface-design` thiết kế API Contract (OpenAPI / Swagger) chuẩn Contract-First.
  2. Dùng `documentation-and-adrs` ghi nhận các quyết định kiến trúc quan trọng vào `ADR.md`.
  3. Dùng `security-and-hardening` thiết kế phương án xác thực AuthN/AuthZ và mã hóa dữ liệu.
  4. Review mã nguồn của Dev theo `EP-03` (Chuyển lỗi lặp lại thành Lint Rule).

---

### 💻 3.4. Workflow Cho Developer
- **Phase chính:** Phase 4 (Development).
- **Skills sử dụng:** `skills/04-development`, `test-driven-development`, `incremental-implementation`, `source-driven-development`, `code-simplification`.
- **Các bước thực hiện:**
  1. Đọc kỹ API Spec và `CODING_CONVENTION.md`.
  2. Áp dụng TDD: Sinh Unit Test trước (`RED`), sinh code thực thi (`GREEN`), refactor code (`REFACTOR`).
  3. Sử dụng `source-driven-development` để chứng minh giải thuật dựa trên code thực tế (EP-01).
  4. Kiểm tra Pre-Commit Checklist (Unit test coverage $\ge 80\%$, Sonar Critical = 0) trước khi tạo PR.

---

### 🧪 3.5. Workflow Cho QA Engineer
- **Phase chính:** Phase 5 (Testing).
- **Skills sử dụng:** `skills/05-testing`, `browser-testing-with-devtools`, `code-review-and-quality`.
- **Các bước thực hiện:**
  1. Sinh bộ Test Cases đa dạng (Positive, Negative, Boundary, Business Rules) dựa trên AC trong RTM.
  2. Sử dụng DevTools/Automation script kiểm thử luồng End-to-End và API.
  3. Lập `Defect_Report.md` kèm theo log và các bước tái hiện (EP-01).
  4. Xác nhận QA Exit Criteria (Requirement coverage > 90%, Critical Defect = 0).

---

### 🚀 3.6. Workflow Cho DevOps / Release Manager
- **Phase chính:** Phase 7 (Deployment).
- **Skills sử dụng:** `skills/07-deployment`, `ci-cd-and-automation`, `shipping-and-launch`, `git-workflow-and-versioning`.
- **Các bước thực hiện:**
  1. Xây dựng Pipeline CI/CD tự động hóa kiểm tra Lint, Unit Test, SAST Scan.
  2. Tạo `Runbook.md` (kịch bản Go-Live từng bước) và `Rollback_Plan.md`.
  3. Kiểm thử kịch bản DB Migration và Rollback trên Staging trước khi Go-Live (AI-07).
  4. Thực hiện Smoke Test sau khi deploy Production.

---

### 🚨 3.7. Workflow Cho SRE & Support Team
- **Phase chính:** Phase 8 (Operations & Support).
- **Skills sử dụng:** `skills/08-operations-support`, `debugging-and-error-recovery`, `observability-and-instrumentation`, `performance-optimization`.
- **Các bước thực hiện:**
  1. Khi xảy ra sự cố: Dùng `observability-and-instrumentation` phân tích log và distributed trace.
  2. Thực hiện RCA theo đúng **EP-02 (Measure Before Diagnose)** với đầy đủ 5 chỉ số đo đạc.
  3. Lập báo cáo `RCA_Report.md` và đề xuất hành động phòng ngừa.
  4. Chuyển bài học sự cố thành bài viết tri thức (`Knowledge_Base/`) cho tổ chức (AI-05).

---

## 💬 4. Mẫu Prompt Chuẩn (Prompt Library) Cho AI Co-Working

### 📝 Prompt Mẫu 1: Cho BA (Sinh User Story & Acceptance Criteria)
```text
Mục tiêu: Sinh danh sách User Story và Acceptance Criteria cho chức năng [Tên chức năng].
Nguồn: Đọc tài liệu BRD tại `02_Requirement/BRD/BRD_Order.md#L45-L100`.
Phạm vi: Chỉ tạo User Story cho phần Checkout.
Quy tắc: 
- User Story theo chuẩn: As a <role>, I want to <goal>, So that <benefit>.
- Acceptance Criteria theo chuẩn: Given <context>, When <action>, Then <outcome>.
- Nếu có điểm chưa rõ trong BRD, hãy đặt câu hỏi và ghi nhãn Status: Not Verified (EP-01).
Output: Định dạng Markdown cho file User_Stories.md.
```

### 💻 Prompt Mẫu 2: Cho Developer (Viết Code theo TDD)
```text
Mục tiêu: Triển khai hàm `calculateOrderTotal()` theo phương pháp TDD.
Nguồn: API Spec tại `03_Design/API_Spec/order-api.yaml` và `CODING_CONVENTION.md`.
Phạm vi: Xử lý tính tổng tiền, áp mã giảm giá và tính thuế VAT.
Quy tắc:
- Bước 1: Sinh bộ Unit Test (AAA Pattern) phủ Happy Path, Boundary (discount = 100%, 0%), và Exception (invalid input).
- Bước 2: Sinh mã nguồn thực thi tối thiểu để PASS tất cả test cases.
- Tuân thủ Early Return, không swallow catch block, log đầy đủ Error/Warning.
Output: Mã nguồn TypeScript và Jest Unit Tests.
```

### 🔍 Prompt Mẫu 3: Cho Reviewer (Rà soát Code theo EP-03)
```text
Mục tiêu: Review Pull Request #142 cho Module Thanh Toán.
Nguồn: Diff mã nguồn tại PR #142 và `CODING_CONVENTION.md`.
Quy tắc Review:
- Rà soát theo AI Code Review Checklist: SOLID, Clean Code, DRY, OWASP Top 10, Memory Leaks.
- Tuân thủ EP-03: Nếu phát hiện lỗi đã từng xuất hiện ở các PR trước, hãy đề xuất 1 Lint Rule hoặc AI Skill Rule mới để bắt tự động.
Output: Báo cáo Code_Review_Report.md chia thành 2 phần: (1) Review Findings, (2) Suggested Automation Rules.
```

### 🚨 Prompt Mẫu 4: Cho SRE (Lập Báo cáo RCA theo EP-02)
```text
Mục tiêu: Phân tích nguyên nhân gốc (RCA) cho sự cố Timeout API Thanh toán ngày 22/09.
Nguồn: Application log tại `logs/prod-app-20260922.log` và APM Traces.
Quy tắc Bắt buộc (EP-02):
- Không suy đoán nguyên nhân dựa trên đọc tài liệu suông.
- Bắt buộc lập bảng 5 số liệu đo đạc: (1) Dataset, (2) Environment, (3) Target Function/System, (4) Metric, (5) Result.
- Nếu thiếu 1 trong 5 chỉ số, đánh dấu Result = Invalid.
Output: File RCA_Report.md chuẩn bị cho buổi họp Incident Post-Mortem.
```

---

## 🎯 5. KPI Targets & Kiểm Soát Chất Lượng (Quality Governance)

Áp dụng đầy đủ AI Workflow Guide này giúp tổ chức đạt được các mục tiêu KPI sau:

| KPI Metric | Mục tiêu Đạt được | Phương pháp Kiểm soát |
|------------|-------------------|-----------------------|
| **Requirement Analysis Effort** | Giảm 30% | Dùng `spec-driven-development` & `interview-me` |
| **Documentation Effort** | Giảm 50% | Tự động hóa soạn thảo BRD/FRD/API Spec từ bối cảnh |
| **Development Effort** | Giảm 20-30% | Áp dụng TDD, Boilerplate Generation & Refactoring |
| **Code Review Effort** | Giảm 40% | AI Code Review sơ bộ & Tự động hóa Rule theo EP-03 |
| **Test Case Creation Effort** | Giảm 50-60% | Auto-generate Positive/Negative/Boundary Test Cases |
| **RCA Analysis Time** | Giảm 70% | Phân tích Log tự động & Quy trình 5 bước EP-02 |
| **Knowledge Reuse Rate** | > 80% | Chuẩn hóa mọi bài học sự cố vào Knowledge Base (AI-05) |
| **Production Defect Leakage** | Giảm 20-30% | Quality Gates khắt khe ở 9 Phase & EP-01/02/03 |

---

> **Lời kết:** *Quy trình làm việc với AI thành công không nằm ở việc viết prompt dài, mà nằm ở việc nạp bối cảnh đúng, kiểm soát an toàn dữ liệu, đo đạc bằng chứng thực tế và biến mọi lỗi sai thành bài học tự động hóa cho tổ chức.*
