---
name: frontend-ui-engineering
description: "Kỹ thuật phát triển giao diện người dùng (Frontend UI/UX) chuẩn hóa và thẩm mỹ cao."
---

# Frontend UI Engineering (Kỹ thuật Phát triển Giao diện UI/UX)

## Tổng quan
Quy trình xây dựng giao diện ứng dụng web hiện đại, đạt tiêu chuẩn thẩm mỹ cao (Rich Aesthetics), đáp ứng trải nghiệm người dùng mượt mà, hỗ trợ Responsive và chuẩn Accessibility (a11y).

## Tiêu chuẩn Thiết kế (Design Principles)
1. **Modern Aesthetics:** Sử dụng gam màu harmonious, dark mode sleek, glassmorphism, hiệu ứng chuyển cảnh mượt mà. Tránh màu plain cơ bản.
2. **Typography & Layout:** Dùng Google Fonts (Inter, Roboto, Outfit). Bố cục linh hoạt (Flexbox, CSS Grid).
3. **State Management:** Xử lý đầy đủ 4 trạng thái giao diện:
   - `Normal State`
   - `Loading State` (Skeleton Loaders)
   - `Empty State` (No Data Illustration)
   - `Error State` (User-friendly error messages)

## Checklist
- [ ] Không hardcode kích thước static pixel không phù hợp.
- [ ] Mọi thành phần tương tác đều có hover/focus states.
- [ ] Không rò rỉ dữ liệu hoặc lỗi uncaught trên giao diện người dùng.
