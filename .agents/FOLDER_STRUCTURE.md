# 📂 Cấu trúc Thư mục AI-Enabled Waterfall Project Starter Kit

Tài liệu này mô tả hai cây thư mục:
1. **Cấu trúc Thư mục AI Starter Kit:** Bộ 9 Phase Skills + 30 Specialized Agent Skills, Agent Roles, Task Templates, Scripts tự động hóa và AI Workflow Guide.
2. **Cấu trúc Thư mục Deliverables Repository:** Thư mục tiêu chuẩn chứa sản phẩm đầu ra (Deliverables) của dự án.

---

## 1. Cấu trúc Thư mục AI Starter Kit (`AI_Workflow_Starter_Kit/`)

```text
AI_Workflow_Starter_Kit/
├── AI_WORKFLOW_GUIDE.md               # Hướng dẫn chi tiết Quy trình làm việc với AI & Prompt Library
├── GUIDE.md                           # Master Guidebook của Framework
├── CODING_CONVENTION.md               # Quy chuẩn lập trình & Review checklist
├── FOLDER_STRUCTURE.md                # Tài liệu cấu trúc thư mục này
├── README.md                          # Hướng dẫn bắt đầu nhanh
│
├── scripts/                            # Các công cụ Scripts tự động hóa
│   ├── convert_excel/                 # Xuất file Markdown Test Cases -> Excel (.xlsx)
│   │   └── md_to_xlsx.js
│   └── integrations/                  # Công cụ đồng bộ Jira, Xray, Google Sheets
│       ├── jira/
│       └── google_sheet/
│
├── skills/                            # Bộ Skills đầy đủ
│   ├── 01-initiation/                 # Phase 1: Initiation Skill
│   ├── 02-requirement-analysis/       # Phase 2: Requirement Analysis Skill
│   ├── 03-solution-design/            # Phase 3: Solution Design Skill
│   ├── 04-development/                # Phase 4: Development Skill
│   ├── 05-testing/                    # Phase 5: Testing Skill (Playwright/Selenium/Jira/Excel)
│   ├── 06-uat/                        # Phase 6: UAT Skill
│   ├── 07-deployment/                 # Phase 7: Deployment Skill
│   ├── 08-operations-support/         # Phase 8: Operations Skill
│   ├── 09-project-closure/            # Phase 9: Project Closure Skill
│   │
│   └── specialized/                   # 30 Kỹ năng AI Kỹ thuật Chuyên sâu (Tiếng Việt)
│       ├── api-and-interface-design/
│       ├── browser-testing-with-devtools/
│       ├── ci-cd-and-automation/
│       ├── code-review-and-quality/
│       ├── code-simplification/
│       ├── constraint-driven-development/
│       ├── context-engineering/
│       ├── debugging-and-error-recovery/
│       ├── deprecation-and-migration/
│       ├── documentation-and-adrs/
│       ├── doubt-driven-development/
│       ├── flaky-test-analysis/         <--- MỚI (Testing Kit)
│       ├── frontend-ui-engineering/
│       ├── git-workflow-and-versioning/
│       ├── idea-refine/
│       ├── incremental-implementation/
│       ├── interview-me/
│       ├── manual-to-automation/        <--- MỚI (Testing Kit)
│       ├── observability-and-instrumentation/
│       ├── performance-optimization/
│       ├── planning-and-task-breakdown/
│       ├── playwright-automation/       <--- MỚI (Testing Kit)
│       ├── security-and-hardening/
│       ├── selenium-automation/         <--- MỚI (Testing Kit)
│       ├── shipping-and-launch/
│       ├── source-driven-development/
│       ├── spec-driven-development/
│       ├── test-data-generation/        <--- MỚI (Testing Kit)
│       ├── test-driven-development/
│       └── using-agent-skills/
│
├── agents/                            # Bộ 8 AI Agent Roles chuẩn
│   ├── pm.md
│   ├── ba.md
│   ├── architect.md
│   ├── developer.md
│   ├── qa.md                          # (Tích hợp Playwright/Selenium/Jira/Excel)
│   ├── devops.md
│   ├── sre.md
│   └── support.md
│
└── task/                              # Biểu mẫu quản lý Task Execution
    ├── task_brief.md
    ├── plan.md
    ├── context.md
    ├── step_result.md                 # (EP-02 5 Metrics)
    ├── verification.md
    ├── review.md                      # (EP-03 Pattern check)
    └── handoff.md
```

---

## 2. Cấu trúc Thư mục Deliverables Repository (`Project/`)

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
