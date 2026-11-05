---
name: observability-and-instrumentation
description: "Thiết lập khả năng quan sát hệ thống (Observability: Logging, Metrics, Tracing)."
---

# Observability and Instrumentation (Thiết lập Quan sát Hệ thống)

## Tổng quan
Kỹ thuật gắn các điểm đo đạc (Instrumentation) vào mã nguồn để thu thập dữ liệu Log, Metric và Trace, phục vụ công tác giám sát, phát hiện cảnh báo sớm và phân tích nguyên nhân gốc sự cố (RCA).

## 3 Trụ cột Observability (Pillars of Observability)
1. **Structured Logs:** Log dạng JSON có cấu trúc (`timestamp`, `level`, `correlationId`, `service`, `message`).
2. **Metrics:** Thu thập chỉ số hiệu năng (RED metrics: Rate, Errors, Duration; USE metrics: Utilization, Saturation, Errors).
3. **Distributed Tracing:** Truy vết luồng request đi qua nhiều microservices qua Correlation/Trace ID.

## Chuẩn bị cho EP-02 (Measure Before Diagnose)
Thiết lập đầy đủ dữ liệu đo đạc cho 5 thành tố khi có sự cố: `Dataset`, `Environment`, `Target`, `Metric`, `Result`.

## Checklist
- [ ] Mọi API Request đều có `correlationId` duy nhất.
- [ ] Không log password, token, PII (AI-03).
- [ ] Cảnh báo (Alerts) được kích hoạt khi lỗi vượt ngưỡng SLA.
