# 📐 Coding Standards & Code Review Guide

Tài liệu này quy định các tiêu chuẩn lập trình bắt buộc khi phát triển dự án IT theo mô hình AI-Enabled Waterfall. Mọi Pull Request (PR) không tuân thủ sẽ bị từ chối (reject).

---

## 1. General Coding Rules

| Category | Rule | Mô tả chi tiết |
|----------|------|----------------|
| **Naming Convention** | Camel Case / Pascal Case | Thư mục & file: `kebab-case`. Class/Interface/Type: `PascalCase`. Biến/Hàm: `camelCase`. Constant: `UPPER_SNAKE_CASE`. DB Table/Column: `snake_case`. |
| **Logging** | Mandatory Logging | Bắt buộc log đầy đủ `Error`, `Warning` và các `Business Events` quan trọng kèm Correlation ID. Không log dữ liệu nhạy cảm (PII, password, secrets). |
| **Exception Handling** | Custom Error Handling | Không swallow exception (không try/catch rỗng). Dùng Custom Error Class chứa `statusCode`, `message`, `errorCode`. Chuyển toàn bộ lỗi không xử lý được về Global Error Handler. |
| **Validation** | Input & Output Validation | Validate toàn bộ input/output ở ranh giới hệ thống (API Request payloads, Query params, DTOs, External Responses). |
| **Security** | OWASP Top 10 | Tuân thủ tuyệt đối OWASP Top 10: Chống SQL Injection, XSS, SSRF, Broken Access Control, CSRF. Mã hóa dữ liệu nhạy cảm (At Rest & In Transit). |
| **Unit Test** | Coverage ≥ 80% | Độ bao phủ mã nguồn (Unit Test Coverage) tối thiểu 80%. Áp dụng pattern **AAA (Arrange - Act - Assert)**. Test cả happy path, edge cases và exception paths. |
| **Documentation** | Public API & Service Doc | Public API và Business Service phức tạp bắt buộc phải có tài liệu JSDoc/Swagger/OpenAPI kèm chú thích rõ ràng. |
| **Dependency** | Approved Libraries Only | Chỉ sử dụng các thư viện và package đã được duyệt trong danh mục cấp phép của dự án. Đánh giá rủi ro an ninh cho mọi thư viện mới. |
| **Configuration** | Config Externalization | Cấu hình ứng dụng phải được tách hoàn toàn khỏi mã nguồn (dùng biến môi trường `.env` hoặc Config Server). |
| **Secrets** | No Hardcoded Secrets | Tuyệt đối không hardcode secret, token, password, API key hay private key trong mã nguồn hoặc file cấu hình commit lên Git. |

---

## 2. Pre-Commit Checklist

Trước khi commit mã nguồn hoặc tạo Pull Request, Lập trình viên phải hoàn thành toàn bộ checklist sau:

- [ ] Business logic hoàn thành đúng yêu cầu và AC.
- [ ] Input validation đầy đủ cho tất cả các đầu vào.
- [ ] Exception handling đầy đủ, không swallow catch block.
- [ ] Logging đầy đủ ở các điểm ranh giới và xử lý lỗi.
- [ ] Unit test completed (Coverage ≥ 80%, tất cả test cases PASS).
- [ ] Security scan completed (không lộ secret, không vi phạm OWASP).
- [ ] No critical issue (Sonar Critical/Blocker = 0).
- [ ] Technical documentation updated (API Spec / Code comments).

---

## 3. AI Code Review Checklist

Dành cho AI Agent Reviewer và Peer Reviewer khi đánh giá Pull Request:

- [ ] **SOLID Principle:** Tuân thủ 5 nguyên tắc SOLID (Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation, Dependency Inversion).
- [ ] **Clean Code:** Mã nguồn dễ đọc, hàm ngắn gọn, tên biến tự giải thích, không nếp lặp `if-else` lồng nhau quá sâu (dùng Early Return).
- [ ] **Duplicate Code Detection:** Không trùng lặp mã nguồn (áp dụng nguyên tắc DRY).
- [ ] **Security Vulnerabilities:** Không chứa lỗ hổng an ninh (SQL Injection, XSS, Hardcoded secrets, Broken Authentication).
- [ ] **Performance Issues:** Không có giải thuật hiệu năng kém O(N^2) không cần thiết, N+1 query pattern, hay truy vấn cơ sở dữ liệu thiếu Index.
- [ ] **Memory Leak Risk:** Giải phóng tài nguyên đầy đủ (mở stream, DB connection, event listener phải được close/unsubscribe).
- [ ] **Error Handling Coverage:** Xử lý đầy đủ các ngoại lệ có thể xảy ra từ hệ thống bên ngoài hoặc cơ sở dữ liệu.
- [ ] **Dependency Risk Review:** Thư viện mới thêm vào có an toàn và đúng phiên bản được phép không.
