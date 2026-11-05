---
name: api-and-interface-design
description: "Hướng dẫn thiết kế API và giao diện hợp đồng (Interface Contract) ổn định, dễ sử dụng và bảo mật."
---

# API & Interface Design (Thiết kế API và Giao diện Hợp đồng)

## Tổng quan
Thiết kế giao diện API, GraphQL schema, ranh giới module hoặc component props ổn định, nhất quán và khó dùng sai. Giao diện tốt giúp việc làm đúng trở nên dễ dàng và làm sai trở nên khó khăn.

## Khi nào sử dụng
- Thiết kế các API endpoints mới (REST / GraphQL / gRPC).
- Định nghĩa ranh giới giữa các module hoặc giao ước contract giữa các team.
- Tạo interface DTOs và component props.
- Định nghĩa schema DB ảnh hưởng trực tiếp tới cấu trúc API.

## Nguyên tắc cốt lõi
1. **Contract-First (Đặc tả trước, Cài đặt sau):** Định nghĩa contract rõ ràng trước khi viết mã nguồn thực thi.
2. **Hyrum's Law:** Mọi hành vi có thể quan sát (kể cả error message, timing, ordering) sẽ trở thành cam kết thực tế. Tránh lộ chi tiết cài đặt (leak implementation details).
3. **One-Version Rule:** Hạn chế duy trì nhiều phiên bản API song song, ưu tiên mở rộng (extend) thay vì tách nhánh (fork).

## Quy trình thực hiện
1. **Xác định Use Case:** Liệt kê đầy đủ kịch bản request/response, validation rules và error cases.
2. **Thiết kế Schema:** Định nghĩa types, DTOs, HTTP status codes chuẩn (200, 201, 400, 401, 403, 404, 422, 500).
3. **Tuân thủ OWASP & Security (AI-08):** Xác thực AuthN/AuthZ, rate limiting, validate dữ liệu đầu vào khắt khe.
4. **Viết Đặc tả (OpenAPI / Swagger):** Soạn thảo tài liệu đặc tả API chuẩn xác.

## Checklist Kiểm tra
- [ ] Tên endpoint rõ nghĩa, dùng danh từ số nhiều (vd: `/v1/orders`).
- [ ] Validate dữ liệu đầu vào ở mọi trường.
- [ ] Cấu trúc Error Response thống nhất (`statusCode`, `errorCode`, `message`).
- [ ] Không rò rỉ thông tin nhạy cảm trong response.
