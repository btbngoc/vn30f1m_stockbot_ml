# Task Review Checklist

- **Reviewer:** [Tên Peer Reviewer / Tech Lead]
- **Review Date:** [Ngày thực hiện review]

## 1. AI Code Review Checklist
- [ ] **SOLID Principles:** Mã nguồn tuân thủ Single Responsibility, Open-Closed, Liskov Substitution, Interface Segregation, Dependency Inversion.
- [ ] **Clean Code:** Tên biến/hàm rõ nghĩa, không nested loops/if-else quá sâu, no magic numbers.
- [ ] **Duplicate Code Detection:** Không có đoạn mã trùng lặp (DRY).
- [ ] **Security Vulnerabilities:** Đã rà soát chống OWASP Top 10 (SQL Injection, XSS, SSRF, Broken Auth, Hardcoded Secrets).
- [ ] **Performance Issues:** Không có O(N^2) không cần thiết, memory leaks, N+1 query patterns.
- [ ] **Memory Leak Risk:** Đã đóng các tài liệu/stream/connection sau khi sử dụng.
- [ ] **Error Handling Coverage:** Validate toàn bộ input/output, không swallow exception.
- [ ] **Dependency Risk Review:** Chỉ sử dụng các thư viện đã được phê duyệt.

## 2. Reviewer Comment Pattern Check (EP-03)
- [ ] Lỗi phát hiện có từng xuất hiện ở PR/Task trước đó không?
  - Nếu **CÓ**: Đã cập nhật Lint Rule / AI Review Skill để bắt lỗi tự động chưa?
  - Rule mới / Lint mới được tạo: `[Điền tên Lint/Skill Rule mới]`

## 3. Review Approval Status
- [ ] **APPROVED:** Đạt toàn bộ tiêu chuẩn và sẵn sàng merge/bàn giao.
- [ ] **REJECTED:** Cần sửa chữa các điểm liệt kê ở trên.
