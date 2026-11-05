---
name: source-driven-development
description: "Phát triển phần mềm dựa trên bằng chứng trích dẫn mã nguồn thực tế tuân thủ EP-01."
---

# Source-Driven Development (Phát triển Dựa trên Bằng chứng Mã nguồn)

## Tổng quan
Phương pháp luận yêu cầu mọi quyết định phát triển, phân tích lỗi hoặc thiết kế đều phải bắt nguồn từ việc đọc và trích dẫn trực tiếp mã nguồn thực tế trong repository, tránh suy đoán cảm tính.

## Nguyên tắc Bắt buộc EP-01
> **Cite the Source or State the Assumption:** Mọi nhận định kỹ thuật phải có bằng chứng từ mã nguồn (`file:line`). Nếu chưa có bằng chứng, phải ghi rõ `Status: Not Verified`.

## Thứ tự Ưu tiên Bằng chứng (AI-06)
$$\text{Source Code} > \text{Logs} > \text{Execution Result} > \text{Documentation} > \text{Assumption}$$

## Quy tắc Thực thi
1. **Không đoán code:** Không suy luận hành vi khi chưa đọc trực tiếp file mã nguồn.
2. **Không cậy vào kiến thức framework chung:** Kiểm tra xem repository cụ thể đang cài đặt như thế nào.
3. **Trích dẫn minh bạch:** Trong mọi task brief, review comment hay pull request, trích dẫn chính xác `path/to/file.ts#L45-L60`.

## Checklist
- [ ] Mọi báo cáo bug hoặc đề xuất sửa code đều kèm đường dẫn file:line.
- [ ] Giả định chưa xác minh đều có nhãn `Status: Not Verified`.
