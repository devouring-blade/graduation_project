# raw/ – văn bản gốc tải từ vbpl.vn (lớp RAW)

Phạm vi: **4 bộ luật gốc** của lĩnh vực dân sự và hình sự (hai bộ luật nội dung, hai bộ
luật tố tụng), cùng các văn bản sửa đổi và hướng dẫn chúng.

Mỗi văn bản là một file HTML, giữ nguyên như nguồn trả về (không sửa chữ nào). Văn bản
được chia sẵn theo nhóm; code lấy nhóm theo thư mục. Tổng cộng 56 văn bản.

| Thư mục | Số văn bản | Vai trò | Vào corpus? |
| --- | --- | --- | --- |
| `goc/` | 4 | 4 bộ luật gốc | Có |
| `huong_dan/` | 32 | Hướng dẫn áp dụng 4 bộ luật gốc | Có |
| `sua_doi/` | 7 | Chỉ chứa câu lệnh sửa 4 bộ luật gốc hoặc sửa văn bản hướng dẫn | Không – được ghép vào văn bản bị sửa |
| `lien_quan/` | 11 | Luật khác có Điều sửa 4 bộ luật gốc; chỉ lấy các Điều đó | Không – chỉ lấy phần sửa đổi |
| `doi_chieu/` | 2 | Văn bản hợp nhất chính thức, để kiểm tra kết quả ghép sửa đổi | Không |

## Danh sách

**goc/ (4)**
- 91/2015/QH13 – Bộ luật Dân sự
- 92/2015/QH13 – Bộ luật Tố tụng dân sự
- 100/2015/QH13 – Bộ luật Hình sự
- 101/2015/QH13 – Bộ luật Tố tụng hình sự

**sua_doi/ (7)**
- 12/2017/QH14 – Luật sửa đổi Bộ luật Hình sự
- 86/2025/QH15 – Luật sửa đổi Bộ luật Hình sự
- 02/2021/QH15 – Luật sửa đổi Bộ luật Tố tụng hình sự
- 99/2025/QH15 – Luật sửa đổi Bộ luật Tố tụng hình sự
- 85/2025/QH15 – Luật sửa đổi Bộ luật Tố tụng dân sự và một số luật khác
- 01/2022/NQ-HĐTP – Sửa đổi Nghị quyết 02/2018/NQ-HĐTP (án treo)
- 02/2025/NQ-HĐTP – Sửa đổi một số nghị quyết của Hội đồng Thẩm phán

**huong_dan/ (32)**
- Hình sự, tố tụng hình sự (23): Nghị quyết HĐTP 01/2016, 01/2018, 01/2021, 02/2018,
  02/2019, 02/2024, 03/2019, 03/2020, 03/2022, 03/2024, 03/2025, 04/2024, 04/2025,
  05/2018, 05/2019, 06/2019, 07/2019; Thông tư liên tịch 01/2021, 02/2018, 04/2026;
  Nghị quyết 110/2015/QH13; Nghị quyết 08/2021/NQ-UBTVQH15
- Dân sự, tố tụng dân sự (9): Nghị quyết HĐTP 01/2019, 01/2020, 02/2016, 02/2020,
  02/2022, 03/2018, 04/2016, 04/2017; Nghị quyết 103/2015/QH13; Nghị định 21/2021/NĐ-CP

**lien_quan/ (11)**
- 59/2024/QH15 – Luật Tư pháp người chưa thành niên (bãi bỏ Chương XII Bộ luật Hình sự)
- 34/2024/QH15 – Luật Tổ chức Tòa án nhân dân
- 106/2025/QH15 – Luật Thi hành án dân sự
- 128/2025/QH15 – Luật Thi hành tạm giữ, tạm giam và cấm đi khỏi nơi cư trú
- 103/2025/QH15 – Luật Tương trợ tư pháp về hình sự
- 105/2025/QH15 – Luật Giám định tư pháp
- 13/2022/QH15 – Luật Phòng, chống bạo lực gia đình
- 19/2023/QH15 – Luật Bảo vệ quyền lợi người tiêu dùng
- 46/2024/QH15 – Luật Công chứng
- 45/2019/QH14 – Bộ luật Lao động
- 59/2020/QH14 – Luật Doanh nghiệp (chưa chắc có sửa luật gốc, cần kiểm lại)

**doi_chieu/ (2)**
- 105/VBHN-VPQH – Luật Tư pháp người chưa thành niên (hợp nhất)
- 02/VBHN-TANDTC – Nghị quyết 02/2018/NQ-HĐTP về án treo (hợp nhất)

## manifest.jsonl

Mỗi dòng một văn bản: `so_hieu`, `file`, `nhom`, `sha256`, `bytes`, `url`, `vbpl_id`,
`tieu_de_trang`, `fetched_at`, `nguon_noi_dung`, `version`.

## Cập nhật sau này

Chỉ nhận văn bản: (1) sửa 4 bộ luật gốc, (2) hướng dẫn 4 bộ luật gốc, (3) sửa hoặc thay
thế văn bản hướng dẫn đã có. Bỏ file HTML vào đúng thư mục nhóm và thêm một dòng vào
`manifest.jsonl` (`nhom` trùng tên thư mục). Văn bản đã nạp mà không đổi sẽ được bỏ qua.

## Lịch sử

- 15/11/2026: tải về từ vbpl.vn.
- 16/11/2026: chia theo nhóm; bỏ 10 văn bản ngoài phạm vi (đã bị xóa khỏi máy).
- 16/11/2026: chốt phạm vi 4 bộ luật gốc. Xóa 19 văn bản hướng dẫn Đất đai, Nhà ở, Hôn
  nhân và gia đình; xóa 22 văn bản không sửa 4 bộ luật gốc (trong đó có Luật Đất đai,
  Luật Nhà ở, Luật Hôn nhân và gia đình). Còn 56 văn bản.
- Hai văn bản chuyển từ Word bằng pandoc (vbpl không có HTML): 105/2025/QH15,
  04/2025/NQ-HĐTP; HTML là bản gốc duy nhất.
