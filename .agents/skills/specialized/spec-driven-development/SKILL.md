---
name: spec-driven-development
description: "Phương pháp phát triển dựa trên tài liệu đặc tả yêu cầu (Spec-Driven Development)."
---

# Spec-Driven Development (Phát triển Dựa trên Tài liệu Đặc tả)

## Tổng quan
Phương pháp luận phát triển phần mềm trong đó tài liệu đặc tả (BRD, FRD, OpenAPI, User Stories + AC) đóng vai trò là "Nguồn sự thật duy nhất" (Single Source of Truth). Mã nguồn và Test cases được sinh ra và đối chiếu trực tiếp từ Spec.

## Khi nào sử dụng
- Phase 2 (Requirement Analysis) và Phase 3 (Solution Design).
- Giúp đảm bảo 100% tính năng xây dựng đều đáp ứng yêu cầu nghiệp vụ.

## Quy trình thực hiện
1. **Hoàn thiện Spec:** Chuẩn hóa tài liệu đặc tả với bộ Acceptance Criteria có thể kiểm thử (Given-When-Then).
2. **Sinh Code & Test từ Spec:** Sử dụng AI để sinh nháp DTOs, API Interfaces và Test Cases trực tiếp từ Spec.
3. **Lập RTM Matrix (Traceability):** Ánh xạ Spec ID ↔ Code Component ↔ Test Case ID.

## Checklist
- [ ] 100% User Stories có Acceptance Criteria rõ ràng.
- [ ] Không có tính năng nào được code mà không có trong Spec.
