# book-translation-toolkit

Bộ công cụ chuyển đổi EPUB → text/markdown và dịch sách (song ngữ), cùng các bản sách đã xử lý.

## Công cụ
- `epub_to_code.py` — trích xuất nội dung EPUB thành dạng text/markdown có cấu trúc.

## Sách đã xử lý
- **Kinh Thánh** (bản dịch Thế Giới Mới): `Kinh Thanh - Chua xac dinh.epub` (nguồn) + `ban_dich_the_gioi_moi_nwt_vt.py` (kết quả xử lý).
- **Thép Đã Tôi Thế Đấy**: `ThepDaToiTheDay_d017c8a84b.epub` (nguồn) + `thep_da_toi_the_day.py` (kết quả xử lý) + `ThepDaToiTheDay.md` (bản markdown).
- **Project Management, 2nd Edition** (Abdullah Oguz): `project_management_2nd_edition.md` (nguồn). Bản dịch song ngữ Anh–Việt được xử lý trong repo riêng `pm-bilingual` (không nằm trong repo này).

## Ghi chú
Các thư mục `pm-build/`, `pm-quarantine/`, `pm-salvage/` là artifact tạm khi gỡ lỗi pipeline dịch qua AgentHub, không thuộc nội dung repo này (đã đưa vào `.gitignore`).
