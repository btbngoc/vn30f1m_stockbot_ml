---
name: 06-uat
description: "AI-Enabled Skill cho Phase 6: UAT - Chuẩn bị kịch bản nghiệm thu nghiệp vụ, tài liệu hướng dẫn sử dụng và tài liệu đào tạo."
---

# Phase 6: UAT (User Acceptance Testing) Skill

## 1. Mục tiêu & Scope
Hỗ trợ người dùng nghiệp vụ (Business Users/PO) tiến hành nghiệm thu hệ thống theo kịch bản End-to-End, cung cấp tài liệu hướng dẫn sử dụng (User Guide) và tài liệu đào tạo (Training Material), đảm bảo sẵn sàng cho Go-Live.

- **Owners:** BA (Business Analyst), Business User
- **Vị trí lưu sản phẩm:** `06_UAT/UAT_Script`, `06_UAT/User_Guide`, `06_UAT/Sign_Off`

---

## 2. Input Cần Có
- BRD, User Stories & Acceptance Criteria từ Phase 2.
- Test Report & Defect Resolution Status từ Phase 5.
- Giao diện ứng dụng hoàn chỉnh trên môi trường UAT.

---

## 3. Quy trình AI Hỗ trợ (AI Contribution)
1. **UAT Script Generation:** Chuyển đổi các User Stories và AC thành kịch bản nghiệm thu góc nhìn người dùng cuối (Business Process Scenarios).
2. **User Guide Authoring:** Tự động soạn thảo tài liệu hướng dẫn sử dụng theo từng phân quyền/vai trò người dùng, kèm mô tả các bước thao tác chi tiết.
3. **Demo Script & Training Material Creation:** Sinh kịch bản Demo cho buổi bàn giao nghiệm thu và tài liệu tập huấn (Presentation/FAQ).

---

## 4. Deliverables Output
- `UAT_Script.md` (hoặc `.xlsx`): Kịch bản kiểm thử nghiệm thu nghiệp vụ End-to-End.
- `User_Guide.md`: Sổ tay hướng dẫn sử dụng hệ thống cho người dùng cuối.
- `Training_Material.md`: Tài liệu đào tạo, kịch bản Demo, bộ câu hỏi thường gặp (FAQ).
- `UAT_Sign_Off.md`: Biên bản xác nhận nghiệm thu UAT của khách hàng / Business User.

---

## 5. Quality Gate / Exit Criteria
- [ ] End-to-End Scenario passed: Toàn bộ kịch bản nghiệm thu luồng nghiệp vụ chính pass.
- [ ] User trained: Đã hoàn tất đào tạo người dùng cuối / Key Users.
- [ ] UAT Defects resolved: Toàn bộ lỗi phát hiện trong quá trình UAT được xử lý hoặc thống nhất phương án.
- [ ] Known Issues documented: Các vấn đề tồn đọng chưa ảnh hưởng Go-Live được ghi nhận đầy đủ.
- [ ] UAT Sign-off completed: Đại diện phía nghiệp vụ / khách hàng ký duyệt biên bản UAT.

---

## 6. Enforced Governance & Engineering Principles
- **AI-01 (Human Approval Required):** Quyết định Sign-Off UAT hoàn toàn thuộc thẩm quyền của Business User / khách hàng. AI chỉ đóng vai trò soạn tài liệu và kịch bản hỗ trợ.
- **AI-05 (Knowledge Management):** Các thắc mắc nghiệp vụ trong quá trình UAT được AI tổng hợp lại thành bộ FAQ để đưa vào Knowledge Base tổ chức.
