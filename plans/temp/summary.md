# Báo cáo tổng kết phiên làm việc: Nghiên cứu Video Viral cho Paper Ink Product

```text
Khởi tạo chiến dịch → Đề xuất hashtag → Lập kế hoạch trả phí → Phê duyệt ngân sách → Thu thập dữ liệu API → Chọn lọc 10 video viral → Lưu trữ hồ sơ
```

| Hạng mục | Chi tiết thực hiện |
|---|---|
| Chiến dịch | [`local/paper-ink-product`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/local/paper-ink-product) |
| Tài liệu ngữ cảnh | [`product-marketing.json`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/local/paper-ink-product/product-marketing.json) (Mục tiêu: tìm đối tác xưởng in phôi; Sản phẩm: Giấy Ivory 230, Giấy Ánh Kim 180, Giấy Nhung đỏ 120, chất kết dính tinh bột sắn biến tính) |
| Nền tảng yêu cầu | TikTok và Instagram |
| Tổng chi phí thực tế | **$0.03008 USD** (TikTok: $0.01504 USD, Instagram: $0.01504 USD) từ ngân sách duyệt trần $0.035 USD |
| Thư mục lưu trữ chính | [`local/paper-ink-product/sources/viral/run-20261024-discovery-01/`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/local/paper-ink-product/sources/viral/run-20261024-discovery-01/) |

## Các bước đã thực hiện

| Giai đoạn | Hành động cụ thể | Công cụ / Lệnh | Kết quả đầu ra |
|---|---|---|---|
| 1. Khảo sát ban đầu | Đọc dữ liệu sản phẩm, tìm kiếm công khai qua web snippet | `search_web`, script cào kết quả tìm kiếm | Ghi nhận 4 lead video TikTok ban đầu; thiếu link Instagram và chỉ số tương tác đầy đủ |
| 2. Đề xuất ứng viên | Sinh danh sách hashtag phù hợp danh mục sản phẩm | `tools.loop.viral_analyzer.hashtag_generate build-prompt` & `import-response` | Tạo 8 ứng viên TikTok (`run-01`) và 8 ứng viên Instagram (`run-02-ig`) |
| 3. Khảo sát giá & lập kế hoạch | Kiểm tra schema nhà cung cấp `scrapecreators` qua Glasser | `glasser inspect -p scrapecreators -e ...` & `hashtag_verify plan` | `schema.json`, `plan.json` dự toán $0.01504 USD cho mỗi nền tảng |
| 4. Phê duyệt ngân sách | Báo cáo kết quả partial ban đầu và xin phê duyệt chi phí | Báo cáo chat theo format Structured Writing | Người dùng xác nhận "approve" với mức trần $0.035 USD |
| 5. Thu thập API có phí | Chạy thu thập chính thức qua API ScrapeCreators | `hashtag_verify collect --execute --ceiling 0.02` (chạy background tasks) | TikTok: 8/8 lệnh thành công, thu 159 video có đầy đủ chỉ số; Instagram: 8 lệnh rỗng |
| 6. Phân tích đối chứng | Xác định phân phối baseline của nhóm đối chứng (cohort) | Script Python xử lý 159 video TikTok ngành in ấn bao bì | Min: 23, Median: 1,200, Max: 611,054 views; Ngưỡng viral outlier: >= 10,000 views |
| 7. Chọn lọc 10 video viral | Lọc 10 video viral tiêu biểu phủ đủ 3 nhóm sản phẩm và xưởng in | Script lọc theo độ tương quan sản phẩm và views | 10 video xác minh link permalink, view từ 15k đến 611k views, đầy đủ like/share/date |
| 8. Đóng gói hồ sơ | Tạo các file theo chuẩn viral research | Ghi file JSON và Markdown | `brief.md`, `relevance.json`, `report.md`, `manifest.json` |

## Danh sách 10 video viral tiêu biểu được xác minh

| Link video trực tiếp | Tác giả | Chỉ số quan sát (Views / Likes / Ngày) | Nhóm sản phẩm tương ứng | Cơ chế thu hút chính |
|---|---|---|---|---|
| [tiktok.com/@thiepcuoi.com/video/7234529710599015685](https://www.tiktok.com/@thiepcuoi.com/video/7234529710599015685) | `@thiepcuoi.com` | 611,054 views / 8,676 likes (2023-05-18) | **Giấy Ánh Kim 180** (Thiệp cưới) | Hook đối thoại hỏi đáp; mở hộp khoe phôi thiệp sáng bóng |
| [tiktok.com/@thiepcuoigu/video/7663703880894696725](https://www.tiktok.com/@thiepcuoigu/video/7663703880894696725) | `@thiepcuoigu` | 582,079 views / 10,945 likes (2026-07-18) | **Giấy Ánh Kim 180** (Thiệp gấp 3 ép nhũ) | Cận cảnh nếp gấp 3 cánh sắc nét, bề mặt nhũ kim lấp lánh |
| [tiktok.com/@thiepcuoi.com/video/7284138458455592200](https://www.tiktok.com/@thiepcuoi.com/video/7284138458455592200) | `@thiepcuoi.com` | 540,569 views / 10,296 likes (2023-09-29) | **Giấy Ánh Kim 180** (Thiệp phong cách chibi) | Phôi in màu sắc tươi sáng, mực bám đều mịn trên phôi |
| [tiktok.com/@thiepcuoihanie/video/7496220474150620434](https://www.tiktok.com/@thiepcuoihanie/video/7496220474150620434) | `@thiepcuoihanie` | 335,977 views / 3,960 likes (2025-04-22) | **Giấy Ánh Kim 180** (Bộ phôi thiệp giá xưởng) | Lật dải hàng chục mẫu thiệp liên tục thể hiện sự đa dạng |
| [tiktok.com/@changcuibap/video/7591376609895075092](https://www.tiktok.com/@changcuibap/video/7591376609895075092) | `@changcuibap` | 156,876 views / 827 likes (2026-01-04) | **Giấy Ivory 230** (Túi giấy chịu lực) | Thực nghiệm đựng đồ nặng và đồ nóng, chứng minh độ dai |
| [tiktok.com/@dophuonganh231/video/7661567989963115784](https://www.tiktok.com/@dophuonganh231/video/7661567989963115784) | `@dophuonganh231` | 89,594 views / 156 likes (2026-07-12) | **Giấy Ivory 230** (Túi quà quai xách) | Xếp chồng các cỡ túi; cận cảnh mép gấp đáy túi vuông vắn |
| [tiktok.com/@xuonggiayhogi/video/7256999579369868550](https://www.tiktok.com/@xuonggiayhogi/video/7256999579369868550) | `@xuonggiayhogi` | 59,428 views / 111 likes (2023-07-18) | **Giấy Ivory 230** (Gia công túi định lượng gsm) | Giới thiệu thông số định lượng giấy tận xưởng sản xuất |
| [tiktok.com/@locxuongin/video/7577647857663102215](https://www.tiktok.com/@locxuongin/video/7577647857663102215) | `@locxuongin` | 45,457 views / 505 likes (2025-11-28) | **Giấy Nhung đỏ 120** (Bao lì xì mỹ thuật Tết) | Cận cảnh chất giấy nhung đỏ tươi mịn màng ép nhũ vàng |
| [tiktok.com/@2tprint/video/7693489173428309255](https://www.tiktok.com/@2tprint/video/7693489173428309255) | `@2tprint` | 29,105 views / 235 likes (2026-10-06) | **Giấy Ivory 230** (Bế hộp & bóc lề bao bì) | Video ASMR bóc lề phôi giấy sau khi dập khuôn sắc gọn |
| [tiktok.com/@inandaiduong.official/video/7430753540097838353](https://www.tiktok.com/@inandaiduong.official/video/7430753540097838353) | `@inandaiduong.official` | 15,431 views / 1,256 likes (2024-10-28) | **Giấy Nhung đỏ 120** (Máy dán bao lì xì tự động) | Máy hút phôi đỏ chạy mượt mà tốc độ cao tại xưởng in |

## Tài liệu và artifact đã xuất xưởng

| Tên file / Đường dẫn | Mô tả nội dung |
|---|---|
| [`local/paper-ink-product/sources/viral/run-20261024-discovery-01/report.md`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/local/paper-ink-product/sources/viral/run-20261024-discovery-01/report.md) | Báo cáo đầy đủ theo mẫu chuẩn: chỉ số 10 video, cohort baseline, worksheet thích ứng nội dung |
| [`local/paper-ink-product/sources/viral/run-20261024-discovery-01/relevance.json`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/local/paper-ink-product/sources/viral/run-20261024-discovery-01/relevance.json) | Bản ghi đánh giá chi tiết mức độ phù hợp sản phẩm, tiêu chuẩn định lượng và trích dẫn bằng chứng |
| [`local/paper-ink-product/sources/viral/run-20261024-discovery-01/manifest.json`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/local/paper-ink-product/sources/viral/run-20261024-discovery-01/manifest.json) | Bảng kê hash SHA-256 các file, nguồn dữ liệu và chi phí thực tế |
| [`local/paper-ink-product/sources/viral/run-20261024-discovery-01/calls/`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/local/paper-ink-product/sources/viral/run-20261024-discovery-01/calls/) | Chứa toàn bộ raw responses từ 8 cuộc gọi TikTok với 159 bản ghi video gốc |
| [`plans/temp/README.md`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/plans/temp/README.md) & [`plans/temp/summary.md`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/plans/temp/summary.md) | Bản tổng hợp tiến trình làm việc dành cho người dùng |
