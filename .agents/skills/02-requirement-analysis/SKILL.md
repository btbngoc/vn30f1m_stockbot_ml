---
name: 02-requirement-analysis
description: "AI-Enabled Skill cho Phase 2: Requirement Analysis - Phân tích khoảng trống, làm rõ yêu cầu, tạo User Stories, Acceptance Criteria và RTM."
---

# Phase 2: Requirement Analysis Skill

## 1. Mục tiêu & Scope
Thu thập, phân tích và chuẩn hóa toàn bộ yêu cầu nghiệp vụ (Business Requirements) và yêu cầu chức năng (Functional Requirements) cho hệ thống, đảm bảo tính đầy đủ, có thể kiểm thử (testable) và truy vết được (traceable).

- **Owners:** BA (Business Analyst), Product Owner (PO)
- **Vị trí lưu sản phẩm:** `02_Requirement/BRD`, `02_Requirement/FRD`, `02_Requirement/User_Stories`, `02_Requirement/RTM`

---

## 2. Input Cần Có
- Scope Definition & Project Charter từ Phase 1.
- Biển biên làm việc (Meeting Minutes), phỏng vấn người dùng, quy trình nghiệp vụ hiện tại (AS-IS).
- Tài liệu quy định nghiệp vụ (Business Rules), tiêu chuẩn phi chức năng (NFR).

---

## 3. Quy trình AI Hỗ trợ (AI Contribution)
1. **Gap Analysis:** Đối chiếu yêu cầu mới với hệ thống hiện tại hoặc chuẩn ngành để phát hiện điểm thiếu hụt / mâu thuẫn.
2. **Requirement Review:** AI rà soát tài liệu yêu cầu, phát hiện câu từ mơ hồ, không đo lường được.
3. **User Story & Acceptance Criteria Generation:** Tự động sinh danh sách User Stories theo chuẩn `As a... I want to... So that...` cùng bộ Acceptance Criteria (Given... When... Then...).
4. **Traceability Matrix (RTM):** Tự động lập bảng ánh xạ giữa Requirement ID ↔ Business Rule ↔ User Story ID ↔ Module.

---

## 4. Deliverables Output
- `BRD.md` (Business Requirement Document): Chi tiết yêu cầu nghiệp vụ và mục tiêu kinh doanh.
- `FRD.md` (Functional Requirement Document): Mô tả chi tiết các chức năng, màn hình, luồng xử lý.
- `User_Stories.md`: Danh sách User Stories hoàn chỉnh kèm Acceptance Criteria.
- `Requirement_Matrix.md` & `RTM.md` (Requirements Traceability Matrix): Ma trận truy vết yêu cầu.

---

## 5. Quality Gate / Exit Criteria
- [ ] Requirement clear: Không còn yêu cầu mơ hồ hoặc đa nghĩa.
- [ ] Requirement testable: Mọi User Story đều có Acceptance Criteria đo lường được.
- [ ] Business Rules defined: Đã định nghĩa đầy đủ tất cả quy tắc nghiệp vụ.
- [ ] NFR identified: Đã xác định rõ các yêu cầu phi chức năng (Performance, Security, Availability).
- [ ] Acceptance Criteria completed: 100% User Stories có AC được chốt.
- [ ] Dependency mapped: Các phụ thuộc giữa các chức năng đã được làm rõ.

---

## 6. Enforced Governance & Engineering Principles
- **EP-01 (Cite the Source or State the Assumption):** Mọi User Story / Requirement đều phải trích dẫn nguồn gốc (file:line hoặc số biên bản họp). Nếu AI đề xuất thêm chi tiết chưa được BA/PO chốt, bắt buộc ghi `Status: Not Verified`.
- **AI-02 (Mandatory Review):** BA và Product Owner bắt buộc review toàn bộ BRD/FRD do AI sinh ra trước khi gửi khách hàng nghiệm thu requirement.
- **AI-06 (Source-Based Analysis):** Ưu tiên thông tin trong tài liệu chính thức hơn suy luận tự do của AI.
