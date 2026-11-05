---
name: shipping-and-launch
description: "Quy trình đóng gói phát hành, kiểm tra sẵn sàng và Go-Live hệ thống."
---

# Shipping and Launch (Đóng gói Phát hành & Go-Live)

## Tổng quan
Các bước chuẩn bị, đóng gói phần mềm, rà soát điều kiện Go-Live và thực thi triển khai chính thức lên môi trường Production an toàn, không gián đoạn dịch vụ.

## Khi nào sử dụng
- Đánh giá Readiness trước khi phát hành (Go-No-Go Meeting).
- Triển khai Phase 7 (Deployment).

## Checklist Sẵn sàng Go-Live (Go-Live Readiness)
- [ ] **UAT Sign-off:** Đã có chữ ký nghiệm thu UAT chính thức từ khách hàng.
- [ ] **Runbook:** Kịch bản Go-Live từng bước được phê duyệt.
- [ ] **Rollback Plan:** Kịch bản hoàn trả trạng thái cũ được kiểm thử thành công.
- [ ] **Backup:** Đã hoàn thành backup database Production hiện tại.
- [ ] **Smoke Test Checklist:** Đã chuẩn bị bộ kiểm thử nhanh sau khi giải phóng phiên bản.
- [ ] **Human Approval (AI-01):** Release Manager ký duyệt lệnh Go-Live.

## Checklist
- [ ] Đã công bố Release Notes tới các bên liên quan.
- [ ] Hệ thống Monitoring & Alerting đang bật và hoạt động tốt.
