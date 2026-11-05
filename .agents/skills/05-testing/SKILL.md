---
name: 05-testing
description: "AI-Enabled Skill cho Phase 5: Testing - Thiết kế test cases, sinh dữ liệu test, tạo script tự động hóa (Playwright/Selenium) và xuất báo cáo Excel/Jira."
---

# Phase 5: Testing Skill

## 1. Mục tiêu & Scope
Đảm bảo chất lượng toàn diện của phần mềm thông qua Functional Testing và Technical Testing, đảm bảo Requirement Coverage > 90%, 0 lỗi Critical/High tồn đọng trước khi nghiệm thu, hỗ trợ tự động hóa Playwright/Selenium và đồng bộ Excel/Jira.

- **Owners:** QA Lead, QA Engineer
- **Vị trí lưu sản phẩm:** `05_Testing/Test_Cases`, `05_Testing/Test_Report`, `05_Testing/Defects`

---

## 2. Input Cần Có
- FRD, User Stories, Acceptance Criteria & RTM từ Phase 2.
- API Specs, Data Model & Architecture Diagrams từ Phase 3.
- Source Code & Deployable Package từ Phase 4.

---

## 3. Quy trình AI Hỗ trợ (AI Contribution)
1. **Functional & Technical Test Design:**
   - *Positive, Negative, Boundary & Business Rule Validation.*
   - *API & Integration Testing.*
   - *Security & Performance Testing.*
2. **Automation Script Generation (Specialized Skills):**
   - Sử dụng `playwright-automation` hoặc `selenium-automation` sinh script tự động hóa UI/API.
   - Sử dụng `manual-to-automation` chuyển đổi kịch bản manual sang script tự động.
   - Sử dụng `flaky-test-analysis` chẩn đoán và khắc phục test chập chờn.
3. **Test Data Generation:** Sử dụng `test-data-generation` sinh mock test data an toàn (AI-03).
4. **Tool Integration & Export Scripts:**
   - Dùng script `scripts/convert_excel/md_to_xlsx.js` xuất file Markdown test cases ra file Excel `.xlsx`.
   - Dùng script `scripts/integrations/jira/` để đẩy tự động Test Cases và Defects lên Jira / Xray.
   - Dùng script `scripts/integrations/google_sheet/` đẩy báo cáo kiểm thử lên Google Sheet.

---

## 4. Deliverables Output
- `Test_Plan.md`: Kế hoạch kiểm thử.
- `Test_Cases.md` (hoặc `.xlsx`): Danh sách chi tiết các test case.
- `Test_Report.md`: Báo cáo kết quả kiểm thử.
- `Defect_Report.md`: Danh sách lỗi.

---

## 5. Quality Gate / Exit Criteria
- [ ] Requirement Coverage > 90%.
- [ ] Positive, Negative, Boundary, Integration, Regression Test completed.
- [ ] Critical Defect = 0; High Defect Resolved.

---

## 6. Enforced Governance & Engineering Principles
- **EP-01:** Báo cáo defect trích dẫn rõ log/evidence (`Status: Verified`).
- **EP-02:** Đo đạc 5 chỉ số cho lỗi hiệu năng.
- **AI-04:** Test case có liên kết 1-1 hoặc 1-N với User Story ID trong RTM.
