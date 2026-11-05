---
name: git-workflow-and-versioning
description: "Quy trình quản lý mã nguồn bằng Git, chiến lược phân nhánh và dán nhãn phiên bản Semantic Versioning."
---

# Git Workflow and Versioning (Quy trình Git & Quản lý Phiên bản)

## Tổng quan
Quy chuẩn thao tác mã nguồn trên Git, quy tắc đặt tên nhánh (Branching Strategy), chuẩn viết Commit Message (Conventional Commits) và quản lý phiên bản phần mềm (Semantic Versioning - SemVer).

## Quy tắc Đặt tên Nhánh
- `feature/<ticket-id>-<short-description>`: Tính năng mới.
- `bugfix/<ticket-id>-<short-description>`: Sửa lỗi môi trường Development/Staging.
- `hotfix/<ticket-id>-<short-description>`: Sửa lỗi khẩn cấp trên Production.
- `release/vX.Y.Z`: Chuẩn bị phát hành phiên bản mới.

## Quy tắc Write Commit Message (Conventional Commits)
$$\text{type(scope): description}$$
*Ví dụ:* `feat(auth): implement JWT token refresh mechanism`

## Semantic Versioning (SemVer: MAJOR.MINOR.PATCH)
- **MAJOR:** Thay đổi không tương thích ngược (Breaking changes).
- **MINOR:** Thêm tính năng mới tương thích ngược.
- **PATCH:** Sửa lỗi nhỏ tương thích ngược.

## Checklist
- [ ] commit message rõ nghĩa và chứa Ticket ID.
- [ ] Không commit file rác, `.env` chứa secret hoặc `node_modules`.
