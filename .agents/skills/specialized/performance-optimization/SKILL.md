---
name: performance-optimization
description: "Tối ưu hóa hiệu năng hệ thống dựa trên số liệu đo đạc thực tế tuân thủ EP-02."
---

# Performance Optimization (Tối ưu hóa Hiệu năng Hệ thống)

## Tổng quan
Quy trình phân tích, phát hiện điểm nghẽn (Bottlenecks) và tối ưu hóa tốc độ xử lý, mức tiêu thụ tài nguyên của ứng dụng dựa trên bằng chứng đo đạc thực tế.

## Nguyên tắc Bắt buộc EP-02
> **Measure Before Diagnose:** Không tối ưu hóa sớm (Premature Optimization) khi chưa có số liệu đo đạc chứng minh điểm nghẽn.

### Báo cáo Benchmark 5 thông số bắt buộc:
1. **Dataset:** Kích thước mẫu thử nghiệm (vd: 100,000 requests).
2. **Environment:** Thông số hạ tầng thử nghiệm (CPU, RAM, OS, DB ver).
3. **Target Function/System:** Endpoint/Hàm được tối ưu.
4. **Metric:** Phép đo (Latency p95, Throughput RPS, CPU Saturation).
5. **Result:** Kết quả Trước và Sau khi tối ưu.
*(Thiếu 1 trong 5 mục $\Rightarrow$ Kết quả bị coi là `Invalid`)*

## Kỹ thuật Tối ưu Phổ biến
- Indexing cơ sở dữ liệu & Tối ưu câu lệnh SQL.
- Áp dụng Caching strategy (Redis/Memcached).
- Bất đồng bộ hóa (Async Queue / Event-Driven Architecture).

## Checklist
- [ ] Có kết quả đo đạc trước và sau tối ưu.
- [ ] 100% Unit Tests & Functional Tests vẫn PASS.
