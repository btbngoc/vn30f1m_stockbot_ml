---
name: constraint-driven-development
description: "Phát triển phần mềm dựa trên các ràng buộc hệ thống (Constraints & NFRs)."
---

# Constraint-Driven Development (Phát triển Dựa trên Ràng buộc)

## Tổng quan
Quy trình thiết kế và lập trình phần mềm tập trung vào việc tuân thủ nghiêm ngặt các ràng buộc về tài nguyên (Memory, CPU, Network bandwidth), an ninh bảo mật và tiêu chuẩn tuân thủ (Compliance).

## Khi nào sử dụng
- Phát triển hệ thống có tài nguyên hạn chế (Embedded, Mobile, Edge).
- Hệ thống yêu cầu độ trễ cực thấp (Low Latency) hoặc băng thông cao (High Throughput).
- Dự án có các quy định khắt khe về bảo mật (HIPAA, PCI-DSS, GDPR).

## Quy trình thực hiện
1. **Xác định Ràng buộc (Constraint Elicitation):** Liệt kê toàn bộ các ngưỡng giới hạn (Latencies < 100ms, Memory Peak < 512MB, No PII Leak).
2. **Thiết kế theo Ràng buộc:** Lựa chọn giải thuật và cấu trúc dữ liệu tối ưu không vượt ngưỡng.
3. **Đo đạc và Xác minh (EP-02):** Liên tục đo đạc số liệu thực tế trong môi trường thử nghiệm.

## Checklist
- [ ] Mọi ràng buộc phi chức năng (NFR) đều có tiêu chí đo lường định lượng.
- [ ] Không vi phạm giới hạn tài nguyên dưới tải cao.
