# Kiểm tra hook adapter trước khi kích hoạt

File spec chưa đăng ký event, chưa chạy scan và chưa chặn hành động. Adapter phải được triển khai theo công cụ thực tế.

| Case | Đầu vào thử | Kỳ vọng |
|---|---|---|
| Cho phép | Nguồn tổng hợp được phép, scope/quyền/evidence đầy đủ | Action phù hợp được phép, lưu decision |
| Secret giả | Chuỗi credential giả định trong nội dung chia sẻ | BLOCK hoặc NEEDS_HUMAN theo policy; action chia sẻ không thực thi |
| Sai scope | Yêu cầu ghi file ngoài thư mục task được phép | BLOCK; file không thay đổi |
| Thiếu evidence | Chuyển ACCEPTED khi kiểm tra bắt buộc chưa chạy | BLOCK; state giữ nguyên; liệt kê prerequisite |
| Sai phiên bản | Evidence build A, candidate build B có thay đổi chưa kiểm tra | BLOCK hoặc NEEDS_HUMAN; không tự cho phép release |
| Lỗi kiểm tra | Scanner/adapter không hoạt động | Báo lỗi, không tự cho phép action bị kiểm soát khi chưa xác minh |
| False positive | Nội dung hợp lệ giống mẫu nhạy cảm | Có đường review có thẩm quyền và ghi căn cứ; không blanket bypass |
| Record failed | Action hoàn tất nhưng lưu state thất bại | Báo record failed; đối chiếu thực tế trước retry để tránh lặp thao tác |

Lưu version adapter, công cụ, case, evidence action thực tế và reviewer. Scan có thể bỏ sót hoặc báo sai; kết hợp phân loại dữ liệu, quyền thực tế và review.
