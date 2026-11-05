---
name: ci-cd-and-automation
description: "Tự động hóa quy trình tích hợp liên tục (CI) và triển khai liên tục (CD) an toàn."
---

# CI/CD and Automation (Tự động hóa CI/CD & Pipeline)

## Tổng quan
Xây dựng, tối ưu hóa và duy trì các đường ống tự động hóa (CI/CD Pipelines) nhằm kiểm thử, đóng gói và triển khai phần mềm an toàn, tin cậy.

## Khi nào sử dụng
- Cấu hình GitHub Actions, GitLab CI, Jenkins hoặc Azure DevOps pipelines.
- Tự động hóa các bước Linting, Unit Test, Static Code Analysis (SonarQube) và Security Scanning.
- Đóng gói Docker Images và triển khai lên môi trường Staging/Production.

## Nguyên tắc cốt lõi
1. **Fail Fast:** Đẩy các bước kiểm tra nhanh (Lint, Unit Test) lên đầu Pipeline.
2. **Hermetic Builds:** Môi trường build phải hoàn toàn độc lập và tái lập được (Reproducible).
3. **No Hardcoded Secrets (AI-03):** Tuyệt đối không lưu trữ credential/token trong Pipeline YAML file.

## Quy trình thực hiện
1. **CI Stage:** Check out code $\rightarrow$ Run Lint $\rightarrow$ Run Unit Test $\rightarrow$ Run SAST Scan $\rightarrow$ Build Artifact.
2. **CD Stage:** Push Container Image $\rightarrow$ Deploy Staging $\rightarrow$ Run Integration/Smoke Test $\rightarrow$ Deploy Production (với Human Gate Approval - AI-01).

## Checklist Kiểm tra
- [ ] Pipeline fail ngay khi có Unit Test bị hỏng hoặc Lint error.
- [ ] Secret được quản lý qua Vault hoặc Secret Manager.
- [ ] Có bước kiểm tra Rollback tự động hoặc bán tự động.
