---
name: doubt-driven-development
description: "Phương pháp phát triển dựa trên tư duy phản biện và hoài nghi giả định."
---

# Doubt-Driven Development (Phát triển Hoài nghi & Rà soát Rủi ro)

## Tổng quan
Tư duy lập trình và thiết kế dựa trên sự hoài nghi lành mạnh đối với mọi giả định, dữ liệu đầu vào và dịch vụ bên ngoài. Đặt ra câu hỏi *"Điều gì sẽ xảy ra nếu phần này thất bại?"* trước khi viết code.

## Khi nào sử dụng
- Khi tích hợp với các API bên thứ ba (Third-party integrations).
- Khi xử lý giao dịch tài chính, thanh toán hoặc dữ liệu quan trọng.
- Thiết kế cơ chế phòng vệ lỗi (Fault Tolerance & Resilience).

## Các câu hỏi phản biện cốt lõi
1. **Dữ liệu này có thực sự hợp lệ không?** $\rightarrow$ Thêm Input Validation khắt khe.
2. **Nếu API này timeout hoặc sập thì sao?** $\rightarrow$ Thêm Circuit Breaker, Timeout & Fallback strategy.
3. **Nếu có 10,000 requests đồng thời thì sao?** $\rightarrow$ Thêm Concurrency Lock & Rate Limiting.

## Checklist
- [ ] Mọi giả định kỹ thuật đều có nhãn xác minh (EP-01).
- [ ] Đã chuẩn bị kịch bản xử lý sự cố cho các điểm nhạy cảm.
