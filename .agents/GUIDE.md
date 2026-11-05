# 🚀 AI-Enabled Waterfall Project Delivery Framework

> **Guiding Principle:** *AI is a project team member, not a project owner.*
> AI hỗ trợ nâng cao năng suất và chất lượng, nhưng mọi quyết định cuối cùng về nghiệp vụ, kiến trúc, bảo mật và triển khai phải được thực hiện bởi con người.

---

## 1. Mục tiêu Framework

Framework này hướng dẫn cách sử dụng AI trong toàn bộ vòng đời dự án IT theo mô hình Waterfall nhằm:
- **Tăng năng suất làm việc:** Tự động hóa các công việc lặp lại, sinh mã nguồn, sinh test case và tạo tài liệu.
- **Chuẩn hóa quy trình delivery:** Thống nhất các bước thực hiện, biểu mẫu và tiêu chuẩn đánh giá giữa các dự án.
- **Nâng cao chất lượng tài liệu:** Đảm bảo tài liệu dự án đầy đủ, nhất quán, có cấu trúc rõ ràng.
- **Giảm lỗi thiết kế và phát triển:** Phát hiện sớm các rủi ro kiến trúc, lỗ hổng bảo mật và bug mã nguồn thông qua AI Code Review.
- **Tăng khả năng traceability:** Đảm bảo mọi yêu cầu, thiết kế, mã nguồn và kịch bản test đều có mối liên kết truy vết 1-1 hoặc 1-N.
- **Xây dựng Knowledge Base cho tổ chức:** Tích lũy tri thức từ các lỗi, sự cố (RCA) và quy tắc dự án thành tài sản chung.
- **Đảm bảo AI được sử dụng có kiểm soát:** Áp dụng nghiêm ngặt bộ quy tắc Governance Rules và Engineering Principles.

---

## 2. End-to-End Project Workflow

| Phase | Mục tiêu | AI Đóng Góp | Deliverables | Checklist / Quality Gate | Owner |
|-------|----------|-------------|--------------|--------------------------|-------|
| **1. Initiation** | Xác định phạm vi và mục tiêu dự án | Scope Analysis, Stakeholder Analysis, Risk Assessment | Project Charter, Scope Definition, Stakeholder Matrix, Risk Register | Scope approved; Stakeholder identified; Timeline agreed; Resource allocated; Risk identified | PM, BA |
| **2. Requirement Analysis** | Thu thập và làm rõ yêu cầu | Gap Analysis, Requirement Review, User Story Generation, Acceptance Criteria Generation, Traceability Matrix | BRD, FRD, User Stories, Requirement Matrix, RTM | Requirement clear; Requirement testable; Business Rules defined; NFR identified; Acceptance Criteria completed; Dependency mapped | BA, Product Owner |
| **3. Solution Design** | Thiết kế giải pháp và kiến trúc | Architecture Review, Security Review, Data Flow Analysis, API Review, Risk Assessment | HLD, LLD, Data Model, API Specification, Security Design | Requirements covered; Interfaces identified; Data Flow validated; Security reviewed; Scalability validated; Monitoring designed; Design approved | Architect, Tech Lead |
| **4. Development** | Xây dựng chức năng | Code Generation, Refactoring, Code Review, Unit Test Generation, Security Scan | Source Code, Unit Test, Technical Documentation | Coding Standard followed; Validation completed; Exception Handling implemented; Logging implemented; Security check passed; Unit Test ≥ 80%; Sonar Critical = 0; Peer Review completed | Developer, Tech Lead |
| **5. Testing** | Đảm bảo chất lượng hệ thống | Test Case Generation, Test Data Creation, Automation Script Generation (Playwright/Selenium), Defect Analysis | Test Plan, Test Cases, Test Report, Defect Report | Requirement Coverage > 90%; Positive Test completed; Negative Test completed; Boundary Test completed; Integration Test completed; Regression Test completed; Critical Defect = 0 | QA Lead, QA |
| **6. UAT** | Nghiệm thu nghiệp vụ | UAT Script Generation, User Guide, Demo Script, Training Material | UAT Script, User Guide, Training Material, Sign-Off | End-to-End Scenario passed; User trained; UAT Defects resolved; Known Issues documented; UAT Sign-off completed | BA, Business User |
| **7. Deployment** | Go-Live hệ thống | Runbook Creation, Rollback Plan, Release Note, Smoke Test Checklist | Deployment Package, Runbook, Release Note, Rollback Plan | Infrastructure Ready; Backup completed; DB Migration tested; Rollback tested; Monitoring enabled; Smoke Test passed; Go-Live approved | DevOps, Release Manager |
| **8. Operations & Support** | Đảm bảo hệ thống vận hành ổn định | Log Analysis, RCA Analysis, Incident Summary, Knowledge Article Creation | Incident Report, RCA Report, Operational Runbook, Knowledge Articles | Monitoring active; Alert configured; SLA achieved; RCA completed; Preventive Action implemented; KB updated | SRE, Support Team |
| **9. Project Closure** | Bàn giao và đóng dự án | Lessons Learned Summary, Project Assessment, Documentation Consolidation | Closure Report, Lessons Learned, Final Documentation | Handover completed; Documentation completed; Customer Acceptance received; Lessons Learned documented; Contract Deliverables completed | PM |

---

## 3. Engineering Principles & AI Governance Rules

Vi phạm các nguyên tắc này đồng nghĩa với việc kết quả phân tích, thiết kế hoặc triển khai **không được xem là đáng tin cậy**.

### 3.1. EP-01: Cite the Source or State the Assumption
- **Mục tiêu:** Mọi nhận định phải có bằng chứng. Nếu chưa có bằng chứng, phải nói rõ đó là giả định và chưa được xác minh.
- **Nguồn được chấp nhận:** `file:line`, `file:line-line`, `commit`, `log`, `measurement`, `benchmark`, `test result`, `design document`, `official documentation`.
- **Trạng thái xác minh:** Mọi báo cáo phải đánh dấu rõ: `Status: Verified` | `Status: Partially Verified` | `Status: Not Verified`.

### 3.2. EP-02: Measure Before Diagnose
- **Mục tiêu:** Đo trước khi kết luận. Áp dụng cho: Performance, Memory, Concurrency, Capacity, RCA.
- **Quy trình chuẩn:** $\text{Measure} \longrightarrow \text{Observe} \longrightarrow \text{Hypothesis} \longrightarrow \text{Verify} \longrightarrow \text{Conclusion}$
- **Chuẩn ghi nhận 5 số liệu:** Dataset, Environment, Target Function/System, Metric, Result. (Thiếu 1 trong 5 $\Rightarrow$ `Result = Invalid`).

### 3.3. EP-03: Reviewer Comment Must Never Repeat
- **Mục tiêu:** Một review comment chỉ nên xuất hiện đúng một lần. Nếu cùng một lỗi xuất hiện lặp lại, phải chuyển hóa thành Automation/Rule.
- **Workflow:** $\text{Review Comment} \longrightarrow \text{Identify Pattern} \longrightarrow \text{Create Rule} \longrightarrow \text{Create Lint / AI Skill} \longrightarrow \text{Run Against PR} \longrightarrow \text{Must Detect Same Issue}$

### 3.4. AI Governance Rules (AI-01 đến AI-08)
- **AI-01: Human Approval Required:** Quyết định cuối cùng thuộc về con người (`AI Recommend -> Human Review -> Approval`).
- **AI-02: Mandatory Review:** Mọi output AI phải được review trước khi sử dụng chính thức.
- **AI-03: Data Protection:** Bảo vệ dữ liệu nhạy cảm (`Treat as Sensitive`).
- **AI-04: Traceability:** Lưu giữ bằng chứng truy vết.
- **AI-05: Knowledge Management:** Biến kinh nghiệm sự cố thành bài viết KB.
- **AI-06: Source-Based Analysis:** Ưu tiên bằng chứng mã nguồn: $\text{Source Code} > \text{Logs} > \text{Execution Result} > \text{Documentation} > \text{Assumption}$.
- **AI-07: Test Before Production:** Thử nghiệm trước khi deploy.
- **AI-08: Security First:** Bảo mật hàng đầu (OWASP, SAST).

---

## 4. Coding Standards

- Naming Convention (Camel Case / Pascal Case / kebab-case)
- Logging & Exception Handling (Không swallow exception, log correlationId)
- Validation & Security (OWASP Top 10, No Hardcoded secrets)
- Unit Test Coverage ≥ 80% (AAA Pattern)
- Documentation & Configuration separation

---

## 5. Testing Strategy & Tooling

- **Functional Testing:** Positive, Negative, Boundary, Business Rule Validation (Coverage ≥ 90%).
- **Technical Testing:** API, Integration, Regression, Security, Performance, Observability.
- **Automation Testing Skills:** `playwright-automation`, `selenium-automation`, `manual-to-automation`, `flaky-test-analysis`, `test-data-generation`.
- **Export & Integration Scripts:** Xuất Markdown sang Excel (`scripts/convert_excel`), Đồng bộ Jira/Xray (`scripts/integrations/jira`) và Google Sheets (`scripts/integrations/google_sheet`).
- **QA Exit Criteria:** Critical Defect = 0, High Defect Resolved, Regression Passed.

---

## 6. AI Skill Matrix & Specialized Skills Integration

| Role | Core AI Skills | Specialized Agent Skills Tích hợp |
|------|----------------|-----------------------------------|
| **PM** | Planning, Reporting, Risk Analysis, Estimation | `planning-and-task-breakdown`, `idea-refine`, `interview-me`, `using-agent-skills` |
| **BA** | Requirement Analysis, Documentation, Process Modelling, Gap Analysis | `spec-driven-development`, `context-engineering`, `interview-me` |
| **Architect** | Architecture Review, Security Assessment, Scalability Review | `api-and-interface-design`, `documentation-and-adrs`, `constraint-driven-development`, `security-and-hardening` |
| **Developer** | Code Generation, Refactoring, Debugging, Unit Testing | `test-driven-development`, `incremental-implementation`, `source-driven-development`, `code-simplification`, `frontend-ui-engineering`, `doubt-driven-development`, `code-review-and-quality` |
| **QA** | Test Design, Automation Testing, Defect Analysis | `playwright-automation`, `selenium-automation`, `manual-to-automation`, `flaky-test-analysis`, `test-data-generation`, `browser-testing-with-devtools`, `code-review-and-quality`, `spec-driven-development` |
| **DevOps** | CI/CD Review, Infrastructure Validation, Monitoring | `ci-cd-and-automation`, `shipping-and-launch`, `git-workflow-and-versioning`, `deprecation-and-migration` |
| **SRE** | RCA Analysis, Log Investigation, Incident Analysis | `observability-and-instrumentation`, `debugging-and-error-recovery`, `performance-optimization` (EP-02) |
| **Support** | Troubleshooting, KB Authoring, Incident Categorization | `debugging-and-error-recovery`, `documentation-and-adrs` |

---

## 7. Deliverables Repository Structure

```text
Project
├── 01_Initiation        (Charter, Scope, Risk_Register)
├── 02_Requirement       (BRD, FRD, User_Stories, RTM)
├── 03_Design            (HLD, LLD, API_Spec, Data_Model)
├── 04_Development       (Source_Code, Unit_Test, Code_Review)
├── 05_Testing           (Test_Cases, Test_Report, Defects)
├── 06_UAT               (UAT_Script, User_Guide, Sign_Off)
├── 07_Deployment        (Runbook, Release_Note, Rollback_Plan)
├── 08_Operations        (RCA, Incident_Report, Knowledge_Base)
└── 09_Closure           (Lessons_Learned, Closure_Report)
```

---

## 8. KPI Targets

- Requirement Analysis Effort: Reduce 30%
- Documentation Effort: Reduce 50%
- Development Effort: Reduce 20-30%
- Code Review Effort: Reduce 40%
- Test Case Creation Effort: Reduce 50-60%
- RCA Analysis Time: Reduce 70%
- Knowledge Reuse Rate: > 80%
- Production Defect Leakage: Reduce 20-30%
