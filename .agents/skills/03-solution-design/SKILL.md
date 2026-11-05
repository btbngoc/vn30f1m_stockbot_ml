---
name: 03-solution-design
description: "AI-Enabled Skill cho Phase 3: Solution Design - Thiết kế kiến trúc HLD, LLD, Data Model, API Specification và Security Design."
---

# Phase 3: Solution Design Skill

## 1. Mục tiêu & Scope
Chuyển đổi yêu cầu chức năng và phi chức năng thành thiết kế kỹ thuật toàn diện bao gồm Kiến trúc tổng thể (HLD), Thiết kế chi tiết (LLD), Mô hình dữ liệu (Data Model), Đặc tả API (API Spec) và Thiết kế bảo mật (Security Design).

- **Owners:** Architect, Tech Lead
- **Vị trí lưu sản phẩm:** `03_Design/HLD`, `03_Design/LLD`, `03_Design/API_Spec`, `03_Design/Data_Model`

---

## 2. Input Cần Có
- BRD, FRD, User Stories và RTM từ Phase 2.
- Tiêu chuẩn công nghệ, Coding Standards & Architecture Guidelines của tổ chức.
- Yêu cầu phi chức năng (NFRs: Throughput, Latency, SLA, Retention, Security).

---

## 3. Quy trình AI Hỗ trợ (AI Contribution)
1. **Architecture Review:** AI phân tích kiến trúc đề xuất, đánh giá tính mở rộng (Scalability), điểm nghẽn (Bottlenecks) và SPOF (Single Point of Failure).
2. **Security Review:** AI đối chiếu thiết kế với OWASP Top 10 và các nguyên tắc AuthN/AuthZ, Data Encryption (at rest / in transit).
3. **Data Flow Analysis:** AI hỗ trợ vẽ luồng dữ liệu (Data Flow Diagrams), Sequence Diagrams (Mermaid format).
4. **API & Data Model Generation:** AI sinh nháp OpenAPI/Swagger specs, JSON Schemas, ERD diagrams và SQL DDL scripts.

---

## 4. Deliverables Output
- `HLD.md` (High-Level Design): Architecture diagram, Component diagram, Tech stack decision.
- `LLD.md` (Low-Level Design): Detailed class diagrams, sequence diagrams, package structure.
- `Data_Model.md` (hoặc `.sql`): ERD, Relational schema, DDL scripts, Indexing strategy.
- `API_Specification.md` (hoặc `openapi.yaml`): API Endpoints, Request/Response payloads, Status Codes, Error Schemas.
- `Security_Design.md`: Authentication, Authorization, Token handling, Encryption specs.

---

## 5. Quality Gate / Exit Criteria
- [ ] Requirements covered: 100% các FRD/User Stories được đáp ứng trong HLD/LLD.
- [ ] Interfaces identified: Các API và tích hợp hệ thống bên ngoài được xác định rõ contract.
- [ ] Data Flow validated: Luồng dữ liệu và trạng thái dữ liệu được kiểm tra hợp lệ.
- [ ] Security reviewed: Thiết kế bảo mật đạt chuẩn OWASP và chính sách bảo mật dữ liệu.
- [ ] Scalability validated: Đáp ứng các chỉ số NFR về tải và hiệu năng.
- [ ] Monitoring designed: Có phương án Logging, Metrics và Tracing (Observability).
- [ ] Design approved: Architect và Tech Lead ký duyệt thiết kế.

---

## 6. Enforced Governance & Engineering Principles
- **EP-01 (Cite the Source or State the Assumption):** Mọi quyết định kiến trúc phải dẫn nguồn từ NFR/FRD gốc. Các quyết định chưa có bằng chứng benchmark phải ghi `Status: Not Verified`.
- **EP-02 (Measure Before Diagnose):** Khi đề xuất thay đổi kiến trúc vì lý do hiệu năng, phải có số liệu đo đạc baseline hoặc benchmark dự kiến (Dataset, Environment, Target, Metric, Result).
- **AI-08 (Security First):** Không chấp nhận bất kỳ thiết kế API/Database nào hardcode secret, thiếu mã hóa hoặc không có xác thực/phân quyền.
