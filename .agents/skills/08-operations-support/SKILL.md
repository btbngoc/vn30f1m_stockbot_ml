---
name: 08-operations-support
description: "AI-Enabled Skill cho Phase 8: Operations & Support - Phân tích log, phân tích nguyên nhân gốc (RCA), tổng hợp sự cố và xây dựng Knowledge Base."
---

# Phase 8: Operations & Support Skill

## 1. Mục tiêu & Scope
Đảm bảo hệ thống vận hành ổn định, xử lý và phân tích các sự cố Production (Incidents), phân tích nguyên nhân gốc (Root Cause Analysis - RCA), xây dựng tài liệu vận hành và Knowledge Base cho tổ chức.

- **Owners:** SRE (Site Reliability Engineer), Support Team
- **Vị trí lưu sản phẩm:** `08_Operations/RCA`, `08_Operations/Incident_Report`, `08_Operations/Knowledge_Base`

---

## 2. Input Cần Có
- System Logs, Application Logs, Error Stack Traces, Metrics (CPU, RAM, Latency, Throughput).
- Incident Ticket / Mô tả sự cố từ người dùng hoặc hệ thống giám sát.
- Operational Runbook & Architecture Design hiện tại.

---

## 3. Quy trình AI Hỗ trợ (AI Contribution)
1. **Log Analysis:** AI lọc và phân tích dữ liệu log dung lượng lớn, phát hiện các chuỗi lỗi bất thường (Exception cascades, timeouts, deadlocks).
2. **RCA Analysis (Bắt buộc tuân thủ EP-02):** Hỗ trợ lập báo cáo phân tích nguyên nhân gốc theo quy trình chuẩn: `Measure -> Observe -> Hypothesis -> Verify -> Conclusion`.
3. **Incident Summary:** Tóm tắt diễn biến sự cố, mốc thời gian (Timeline), ảnh hưởng kinh doanh và hành động khắc phục tạm thời (Workaround).
4. **Knowledge Article Creation:** Tự động chuyển đổi các bài học từ RCA thành bài viết hướng dẫn xử lý sự cố (Troubleshooting Guide / KB Article) để tái sử dụng.

---

## 4. Deliverables Output
- `Incident_Report.md`: Báo cáo sự cố Production (Severity, Impact, Timeline, Resolution).
- `RCA_Report.md`: Báo cáo phân tích nguyên nhân gốc sâu sắc kèm hành động phòng ngừa (Preventive Actions).
- `Operational_Runbook.md`: Hướng dẫn xử lý các tình huống vận hành và bảo trì định kỳ.
- `Knowledge_Articles/`: Bộ tài liệu tri thức xử lý sự cố trong Knowledge Base.

---

## 5. Quality Gate / Exit Criteria
- [ ] Monitoring active: Hệ thống giám sát hoạt động liên tục 24/7.
- [ ] Alert configured: Các ngưỡng cảnh báo (Alert thresholds) được thiết lập chính xác.
- [ ] SLA achieved: Cam kết mức độ dịch vụ (SLA / SLO) đạt mục tiêu.
- [ ] RCA completed: Hoàn thành RCA cho 100% sự cố mức Critical/High trong vòng 24-48h.
- [ ] Preventive Action implemented: Các hành động khắc phục triệt để đã được phân công và đưa vào backlog.
- [ ] KB updated: Bài viết tri thức tương ứng được đưa vào Knowledge Base tổ chức.

---

## 6. Enforced Governance & Engineering Principles
- **EP-02 (Measure Before Diagnose):** Tuyệt đối KHÔNG được đoán nguyên nhân gốc sự cố dựa trên đọc tài liệu suông (`Read Documentation -> Guess Root Cause`). Mọi kết luận RCA bắt buộc phải qua đo đạc và có số liệu thực tế với đầy đủ 5 thành tố:
  1. **Dataset:** (ví dụ: 500,000 records / 10,000 req/min)
  2. **Environment:** (ví dụ: Production K8s Cluster Node-02, Windows/Linux kernel ver)
  3. **Target Function/System:** (ví dụ: `loadCustomerData()`, API `/v1/orders`)
  4. **Metric:** (ví dụ: Execution Time, Memory Usage, GC Pause time)
  5. **Result:** (ví dụ: 3.4 seconds, 98% CPU saturation)
  *Nếu thiếu bất kỳ thành tố nào trong 5 mục trên, kết quả phân tích bị coi là Invalid (`Result = Invalid`).*
- **EP-03 (Reviewer Comment Must Never Repeat):** Sự cố do lỗi lặp lại phải được chuyển hóa thành Lint Rule / Static Check / Health Check rule mới trong hệ thống.
- **AI-05 (Knowledge Management):** Biến mọi kinh nghiệm sự cố thành tài sản tri thức lưu trữ vào Knowledge Base.
