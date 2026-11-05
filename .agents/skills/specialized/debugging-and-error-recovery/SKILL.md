---
name: debugging-and-error-recovery
description: "Chẩn đoán lỗi, truy vết sự cố và khôi phục hệ thống tuân thủ nguyên tắc EP-02."
---

# Debugging and Error Recovery (Chẩn đoán Lỗi & Khôi phục)

## Tổng quan
Quy trình chẩn đoán sự cố mã nguồn và hạ tầng một cách bài bản, tìm nguyên nhân gốc (Root Cause Analysis) và khôi phục hệ thống về trạng thái an toàn.

## Nguyên tắc Bắt buộc EP-02
> **Measure Before Diagnose:** Tuyệt đối KHÔNG đoán nguyên nhân lỗi bằng cách đọc tài liệu suông (`Read Documentation -> Guess Root Cause`). Mọi chẩn đoán phải qua đo đạc và thu thập log thực tế.

## Quy trình 5 bước Chẩn đoán
$$\text{Measure} \longrightarrow \text{Observe} \longrightarrow \text{Hypothesis} \longrightarrow \text{Verify} \longrightarrow \text{Conclusion}$$

### Báo cáo Đo đạc 5 yếu tố bắt buộc:
1. **Dataset:** Tập dữ liệu kích hoạt lỗi.
2. **Environment:** Môi trường xảy ra sự cố (OS, Browser, Service ver).
3. **Target Function/System:** Đối tượng bị lỗi.
4. **Metric:** Phép đo (Stack trace, Error rate, Latency spike).
5. **Result:** Con số/bằng chứng thu được.
*(Nếu thiếu 1 trong 5 mục $\Rightarrow$ `Result = Invalid`)*

## Checklist
- [ ] Đã trích dẫn exact stack trace hoặc log line.
- [ ] Không swallow exception để che giấu lỗi.
- [ ] Phương án sửa đổi có Unit Test tái hiện và khắc phục sự cố.
