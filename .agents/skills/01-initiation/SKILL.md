---
name: 01-initiation
description: "AI-Enabled Skill cho Phase 1: Initiation - Xác định phạm vi, mục tiêu dự án, phân tích bên liên quan và đánh giá rủi ro."
---

# Phase 1: Initiation Skill

## 1. Mục tiêu & Scope
Xác định phạm vi, mục tiêu dự án IT theo mô hình Waterfall, lập Project Charter, Scope Definition, Stakeholder Matrix và Risk Register ban đầu.

- **Owners:** PM (Project Manager), BA (Business Analyst)
- **Vị trí lưu sản phẩm:** `01_Initiation/Charter`, `01_Initiation/Scope`, `01_Initiation/Risk_Register`

---

## 2. Input Cần Có
- Yêu cầu ban đầu từ khách hàng / SOW / Hợp đồng / Presale Handover.
- Thông tin về ngân sách, mốc thời gian (milestones) và nguồn lực dự kiến.
- Các quy định an toàn thông tin & bảo mật dữ liệu tổ chức (AI-03).

---

## 3. Quy trình AI Hỗ trợ (AI Contribution)
1. **Scope Analysis:** AI đọc dữ liệu đầu vào, phân tích phạm vi cam kết, phân tách In-Scope / Out-of-Scope và nêu các rủi ro mơ hồ.
2. **Stakeholder Analysis:** AI lập danh sách bên liên quan, vai trò, mức độ ảnh hưởng và kênh giao tiếp.
3. **Risk Assessment:** AI gợi ý danh mục rủi ro kỹ thuật, vận hành, nhân sự và đề xuất phương án giảm thiểu (Mitigation Plan).

---

## 4. Deliverables Output
- `Project_Charter.md` (hoặc `.docx`): Tóm tắt mục tiêu, phạm vi, cột mốc chính và ngân sách.
- `Scope_Definition.md`: Phân tích phạm vi chi tiết, các tiêu chí nghiệm thu cấp cao (High-level Acceptance Criteria).
- `Stakeholder_Matrix.md`: Bảng phân tích các bên liên quan và RACI cấp cao.
- `Risk_Register.md`: Danh mục rủi ro, mức độ ưu tiên và hành động phòng ngừa.

---

## 5. Quality Gate / Exit Criteria
- [ ] Scope được khách hàng / Sponsor phê duyệt.
- [ ] Stakeholders được xác định đầy đủ và có phương án giao tiếp.
- [ ] Timeline và Milestones chính được các bên thống nhất.
- [ ] Resource allocation ban đầu được xác nhận.
- [ ] Risk Register được tạo và gắn owner xử lý.

---

## 6. Enforced Governance & Engineering Principles
- **EP-01 (Cite the Source or State the Assumption):** Mọi phạm vi, mốc thời gian hay giả định chưa có hợp đồng/SOW xác nhận phải được đánh dấu rõ `Status: Not Verified` hoặc `Chưa verify`.
- **AI-01 (Human Approval Required):** AI đề xuất Charter và Risk Register, PM và BA phải review và chốt chính thức.
- **AI-03 (Data Protection):** Không đưa thông tin nhạy cảm, hợp đồng thương mại chứa thông tin tài chính cá nhân lên AI public.
