# Infographic plan (v3) — Nhóm chủ & dân bán hàng trong Nemotron-Personas-Vietnam

**Layout:** `business-plan-summary-report` (thu gọn còn **2 tầng đồ thị chính** + dải chip nhân khẩu, tăng cỡ chữ 35–45% để đọc rõ trên điện thoại).
**Design style:** `multi-hue editorial` (Space Grotesk + Inter, nền kem ấm `#fcf7ec`, bảng 3 màu phân nhóm: Vermilion `#E84A27` · Teal `#0D9488` · Amber `#D97706`, không đổ bóng).
**Canvas / hướng:** 720 × 1280 px (9:16), ảnh xuất 2x = 1440 × 2560 px.
**Ngôn ngữ:** tiếng Việt.
**Output dir:** `projects/emotional-ai/infographic/`

## Nguyên tắc bản v3 (2 hàng đồ thị · chữ lớn · lọc điều cốt lõi)

1. **Bỏ hẳn hàng đồ thị Hồ sơ nhóm (Chart 2 cũ):** Tuổi giữa (`38 / 40 / 40`), tỷ lệ sống ở đô thị (`77% / 40% / 41%`), và tỷ lệ nữ (`40% / 60% / 64%`) đã nằm trọn trong 3 thẻ KPI ở đầu trang. Bỏ hàng đồ thị trùng lặp này giải phóng 312px chiều dọc.
2. **Chỉ giữ 2 hàng đồ thị cốt lõi:**
   - **Đồ thị 1 — Mục tiêu nghề nghiệp (% số người trong nhóm):** Lọc 6 chủ đề tương phản rõ nhất (2 cột × 3 chủ đề):
     - Cột trái (Điểm chung): *Mở rộng quy mô*, *Ổn định & bền vững*, *Học kỹ năng mới*.
     - Cột phải (Độ lệch theo quy mô): *Giữ khách hàng*, *Thu nhập & doanh thu*, *Gia đình & con cái*.
   - **Đồ thị 2 — Kỹ năng đặc trưng theo nhóm (% · trục 0–40%):** Lọc 4 kỹ năng đứng đầu mỗi nhóm (3 cột × 4 kỹ năng) để thấy ngay sự phân hoá giữa *quản trị/chiến lược* (chủ DN) và *giao tiếp/kho hàng/đàm phán* (chủ tiệm & bán hàng).
3. **Tăng mạnh cỡ chữ và độ dày thanh:**
   - Tiêu đề chính `h1`: `38px` · Phụ đề: `13px`
   - Tiêu đề khu vực: `13px` · Chú giải nhóm: `12.5px`
   - Thẻ KPI: tên nhóm `13px`, con số `19px`, nhãn `10.5px`
   - Đồ thị 1: tên chủ đề `14px`, thanh ngang `14px`, số `%` `13px`
   - Đồ thị 2: tên cột `14px`, tên kỹ năng `13px`, thanh ngang `14px`, số `%` `13px`
   - Chân trang: `11px`

## Dữ liệu trong từng phần

### Chip số liệu (3 nhóm)
| Nhóm | Số người | Tuổi | Đô thị | Nữ |
|---|---|---|---|---|
| Chủ doanh nghiệp / Giám đốc | 1.325 | 38 | 77% | 40% |
| Chủ tiệm / Tạp hoá / Quán ăn | 53.052 | 40 | 40% | 60% |
| Bán hàng / Tiểu thương / Thương lái | 135.142 | 40 | 41% | 64% |

### ĐỒ THỊ 1 — Mục tiêu nghề nghiệp (% số người trong nhóm nhắc tới), 2 cột × 3 chủ đề
| Chủ đề | Chủ DN | Chủ tiệm | Bán hàng |
|---|---|---|---|
| Mở rộng quy mô | 82,6 | 80,5 | 72,3 |
| Ổn định & bền vững | 66,7 | 62,4 | 71,8 |
| Học kỹ năng mới | 47,7 | 47,2 | 54,9 |
| Giữ khách hàng | 11,2 | 44,5 | 52,9 |
| Thu nhập & doanh thu | 12,6 | 17,0 | 38,1 |
| Gia đình & con cái | 6,6 | 23,0 | 31,6 |

### ĐỒ THỊ 2 — Kỹ năng đặc trưng (% người trong nhóm có kỹ năng đó, trục chung 0 → 40%), 3 cột × 4 kỹ năng
- **Chủ doanh nghiệp:** Lãnh đạo đội nhóm 33,4 · Quản trị chiến lược 22,2 · Phân tích thị trường 15,2 · Phân tích dữ liệu 13,1
- **Chủ tiệm:** Giao tiếp khách hàng 36,4 · Quản lý kho hàng 27,4 · Chăm sóc khách hàng 20,3 · Vận hành quán ăn 18,2
- **Bán hàng:** Giao tiếp khách hàng 37,8 · Đàm phán giá cả 18,7 · Chăm sóc khách hàng 16,9 · Quản lý tồn kho 15,3

## Wireframe có số đo (khớp chính xác với `index.html`)

```text
720 × 1280 (9:16) — padding: 28px top · 34px sides · 24px bottom → 1228px content height
+-------------------------------------------------------------------+ [Y: 0]
| HEADER (108px)                                                    |
| FPT × NVIDIA · NEMOTRON-PERSONAS-VIETNAM                 [BANNER] |
| Tệp dữ liệu mở mô phỏng 1.000.000 người Việt                      |
| Chủ doanh nghiệp · chủ tiệm · dân bán hàng (189.519 hồ sơ)...     |
+-------------------------------------------------------------------+ [Y: 108]
| KPI CHIPS (124px, margin-top: 14px)                               |
| [Chủ doanh nghiệp]      [Chủ tiệm / Quán ăn]    [Bán hàng]        |
| 1.325 · 38 · 77% · 40%  53.052 · 40 · 40% · 60% 135.142·40·41%·64%|
+-------------------------------------------------------------------+ [Y: 246]
| CHART 1 — MỤC TIÊU NGHỀ NGHIỆP (% số người trong nhóm) (470px,   |
| margin-top: 20px, 2 cột × 3 chủ đề, chữ 14px, thanh 14px)         |
+-------------------------------------------------------------------+ [Y: 736]
| CHART 2 — KỸ NĂNG ĐẶC TRƯNG THEO NHÓM (% · trục 0–40%) (416px,    |
| margin-top: 20px, 3 cột × 4 kỹ năng hàng đầu, chữ 13px)           |
+-------------------------------------------------------------------+ [Y: 1172]
| FOOTER (56px)                                                     |
+-------------------------------------------------------------------+ [Y: 1228]
Tổng vùng nội dung: 108 + (14+124) + (20+470) + (20+416) + 56 = 1228px (+ 52px padding = 1280px)
```
