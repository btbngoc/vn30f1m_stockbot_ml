---
name: security-and-hardening
description: "Gia cố an ninh bảo mật hệ thống và tuân thủ OWASP Top 10."
---

# Security and Hardening (Gia cố An ninh & Bảo mật Hệ thống)

## Tổng quan
Kỹ thuật rà soát, phát hiện và khắc phục các lỗ hổng an toàn thông tin trên mã nguồn, ứng dụng, API và hạ tầng triển khai theo tiêu chuẩn OWASP Top 10 và chính sách bảo mật doanh nghiệp (AI-08).

## Các nguy cơ an ninh hàng đầu (OWASP Top 10 Focus)
1. **Injection (SQL, NoSQL, Command Injection):** Dùng Parameterized Queries / ORM.
2. **Broken Authentication:** Dùng strong JWT, bcrypt/argon2 hashing, MFA.
3. **Sensitive Data Exposure (AI-03):** Mã hóa AES-256 at rest, TLS 1.3 in transit. Tránh log PII.
4. **Broken Access Control:** Kiểm tra quyền RBAC/ABAC ở mức server side cho từng API endpoint.
5. **Security Misconfiguration:** Tắt debug mode, xóa bớt các header lộ thông tin server.

## Quy trình Hardening
1. **SAST Scan:** Chạy static security analysis trên mã nguồn.
2. **Dependency Audit:** Rà soát lỗ hổng bảo mật trong các thư viện bên thứ ba (`npm audit`, `trivy`).
3. **Secret Scan:** Đảm bảo không lộ API Keys, Token hay Passwords (Gitleaks).

## Checklist
- [ ] 0 lỗ hổng Critical/High tồn đọng.
- [ ] 100% API endpoints đều kiểm tra xác thực và phân quyền.
