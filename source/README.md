# Việt hóa Do Not Feed the Monkeys

- Bản dịch nằm trong `translations/*.json` (section → key → chuỗi tiếng Việt), ghép lên `en.json` gốc.
- `tools/build_vi.py` đọc file gốc từ `..\..\DNFTM_backup_original`, ghi bản vá vào `dnftm_Data`:
  - `resources.assets`: TextAsset `ko` = bản tiếng Việt (chuỗi chưa dịch vẫn là tiếng Anh).
  - `sharedassets2.assets`, `sharedassets3.assets`: 18 font TextMeshPro của slot Hàn được tạo lại có dấu tiếng Việt.
- Trong game: SETTINGS → LANGUAGE, bấm mũi tên tới "TIẾNG VIỆT" (vị trí của tiếng Hàn) → APPLY CHANGES.
- Gỡ bản vá: chép `resources.assets`, `sharedassets2.assets`, `sharedassets3.assets` từ `DNFTM_backup_original` về `dnftm_Data`, hoặc dùng Steam "Verify integrity of game files".
- Credits: `koCredits` được thay bằng credits tiếng Anh có tiêu đề vai trò dịch sang tiếng Việt (giữ đúng 4 trang `*`).
- Phạm vi: đã dịch toàn bộ giao diện, email, tin tức, wiki, cửa hàng, quà, công việc, 19 câu chuyện, kết thúc game và credits (6.749 chuỗi). Giữ nguyên có chủ đích: tên riêng, thương hiệu, địa chỉ, URL, số điện thoại, giờ "0:00…23:55", ngôn ngữ bịa của Peole và các đoạn mật mã.
- Kiểm tra tự động khi build: placeholder/biến/tag/ký tự `|` phải khớp bản gốc; mọi ký tự đều có trong font.
- Nếu Steam cập nhật game và ghi đè file: chạy lại `build_vi.py` (sau khi sao lưu bản gốc mới vào `DNFTM_backup_original`).
