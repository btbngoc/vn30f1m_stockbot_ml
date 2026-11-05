---
name: 07-deployment
description: "AI-Enabled Skill cho Phase 7: Deployment - Chuẩn bị Runbook, Rollback Plan, Release Notes và Smoke Test Checklist cho Go-Live."
---

# Phase 7: Deployment Skill

## 1. Mục tiêu & Scope
Triển khai hệ thống lên môi trường Production an toàn, đúng quy trình, có phương án sao lưu, khôi phục rủi ro (Rollback Plan) và xác nhận hệ thống vận hành mượt mà sau triển khai (Smoke Test).

- **Owners:** DevOps, Release Manager
- **Vị trí lưu sản phẩm:** `07_Deployment/Runbook`, `07_Deployment/Release_Note`, `07_Deployment/Rollback_Plan`

---

## 2. Input Cần Có
- Biên bản UAT Sign-off từ Phase 6.
- Release Candidate Package & Database Migration Scripts.
- Cấu hình môi trường Production & Infrastructure Architecture.

---

## 3. Quy trình AI Hỗ trợ (AI Contribution)
1. **Runbook Creation:** Tự động tạo kịch bản triển khai theo mốc thời gian từng bước (Step-by-step Execution Plan: DB migration, Config update, Service restart, Cache clear).
2. **Rollback Plan Generation:** Xây dựng kịch bản khôi phục trạng thái cũ nếu xảy ra sự cố nghiêm trọng trong quá trình Go-Live.
3. **Release Note Generation:** Tổng hợp danh sách tính năng mới, lỗi đã fix, thay đổi cấu hình từ các commit log và User Stories.
4. **Smoke Test Checklist Generation:** Sinh danh mục kiểm tra nhanh các chức năng cốt lõi (Health checks, API Ping, Core login/checkout flow) ngay sau khi Go-Live.

---

## 4. Deliverables Output
- `Deployment_Package`: Gói mã nguồn/Container image đã đóng gói và dán nhãn Version.
- `Runbook.md`: Kịch bản chi tiết từng bước triển khai Production.
- `Release_Note.md`: Tài liệu ghi nhận các nội dung thay đổi của phiên bản phát hành.
- `Rollback_Plan.md`: Kịch bản khôi phục dữ liệu và mã nguồn khi Go-Live thất bại.
- `Smoke_Test_Checklist.md`: Danh mục các bước kiểm thử nhanh sau triển khai.

---

## 5. Quality Gate / Exit Criteria
- [ ] Infrastructure Ready: Hạ tầng Production đã sẵn sàng, được kiểm tra kết nối & tài nguyên.
- [ ] Backup completed: Đã hoàn tất sao lưu Database và cấu hình hiện tại trước khi triển khai.
- [ ] DB Migration tested: Kịch bản migrate dữ liệu đã được chạy thử thành công trên môi trường Staging/Pre-prod.
- [ ] Rollback tested: Kịch bản Rollback đã được diễn tập hoặc kiểm tra tính khả thi.
- [ ] Monitoring enabled: Hệ thống giám sát (Logging, APM, Alerting) đã bật và nhận dữ liệu.
- [ ] Smoke Test passed: 100% các ca trong Smoke Test Checklist pass sau khi Go-Live.
- [ ] Go-Live approved: Release Manager và các bên liên quan duyệt hoàn thành triển khai.

---

## 6. Enforced Governance & Engineering Principles
- **AI-07 (Test Before Production):** Mọi script triển khai, SQL migration, cấu hình hạ tầng do AI sinh ra phải được diễn tập và kiểm thử thành công trên môi trường Staging trước khi chạy ở Production.
- **AI-03 (Data Protection):** Tuyệt đối không lưu trữ credential, token, password hoặc private key Production trong các script hay prompt AI.
