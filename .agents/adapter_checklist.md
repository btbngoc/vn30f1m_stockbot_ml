# Checklist chuyển template vào công cụ AI

- [ ] Xác định công cụ, phiên bản, môi trường, tài khoản được phép và owner.
- [ ] Tra tài liệu chính thức: cơ chế project instructions, skill discovery/invocation, agent và hook có được hỗ trợ không.
- [ ] Ánh xạ tên/vị trí/schema; không giả định `.md` hoặc `.spec.json` tự nạp.
- [ ] Điền đường dẫn, rule, scope và cách kiểm tra thực tế; loại trường template chưa điền.
- [ ] Cấu hình quyền ở công cụ/môi trường; prompt không thay permission control.
- [ ] Thử task nhỏ: xác minh AI đã đọc đúng instructions/skill và đúng version nguồn.
- [ ] Nếu có agent: xác minh quyền và output của từng role; không cần nhiều agent nếu làm tuần tự đủ.
- [ ] Nếu có hook: triển khai adapter/event mapping và chạy các ca trong hook_test_cases.md.
- [ ] Kiểm tra action thực sự được phép/bị chặn, lỗi kiểm tra và log không lộ dữ liệu.
- [ ] Ghi status NOT_CONFIGURED / TESTED / ACTIVATED / UNSUPPORTED, version và evidence.
- [ ] Nếu UNSUPPORTED: chọn kiểm tra thủ công, không tuyên bố enforcement tự động.
- [ ] Chấp nhận baseline cấu hình theo quyền của dự án; quy định cách sửa và kiểm tra lại.
