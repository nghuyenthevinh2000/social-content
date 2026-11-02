# Kiến trúc Công cụ Mã nguồn Mở Nhúng Giám sát Viral 24h

```text
Thu thập (yt-dlp/CDP/pytrends) -> Xử lý NLP tiếng Việt (underthesea) -> Thuật toán Burst 24h -> Lưu trữ nhúng (SQLite)
```

## So sánh YouNet và giải pháp nhúng

| Tiêu chí | YouNet Media / Nền tảng đóng | Giải pháp mã nguồn mở nhúng (Embedded Open Source) |
|---|---|---|
| Khả năng tích hợp mã | Dashboard SaaS giao diện web, không cấp REST API công khai hay webhook cho hệ thống nhúng | Thư viện Python chạy trực tiếp trong tiến trình (in-process), nhúng thẳng vào agent loop |
| Bản quyền & Chi phí | Hợp đồng doanh nghiệp $5,000 - $25,000/năm, phụ thuộc quy trình phê duyệt thủ công | Hoàn toàn miễn phí bản quyền (MIT/Apache 2.0), kiểm soát 100% dữ liệu và hạ tầng cục bộ |
| Dữ liệu và Permalinks | Báo cáo số liệu tổng hợp theo cụm, trễ nhịp và thiếu liên kết video permalink trực tiếp | Thu thập raw metadata, URL video gốc, mã âm thanh và bình luận chính xác theo từng phút |
| Tùy biến phân tích | Cố định danh mục tổng quát, không thể can thiệp mô hình phân loại sắc thái văn hóa địa phương | Tự huấn luyện hoặc gắn nhãn theo các mô thức văn hóa Việt: Hóng biến, Cà khịa, Check VAR |

## Các thành phần mã nguồn mở tối giản

| Tầng chức năng | Thư viện mã nguồn mở | Vai trò kỹ thuật | Cơ chế hoạt động |
|---|---|---|---|
| Thu thập xu hướng tìm kiếm | `pytrends` / `trendspy` | Lấy dữ liệu Google Trends 24h tại Việt Nam | Gọi endpoint thời gian thực `trending_searches(pn='vietnam')` trả về DataFrame |
| Thu thập video đa nền tảng | `yt-dlp` | Trích xuất video, lượt xem, ngày đăng, sound ID | Trích xuất JSON metadata không tải video: `yt-dlp --dump-json <URL>` |
| Điều khiển thiết bị thật | `tools/taktik-bot` | Thu thập For You Page tự nhiên từ ứng dụng TikTok | Kết nối ADB tới Android lắp SIM Viettel/Vinaphone, cuộn trang và cào video thật |
| Trình duyệt không đầu (CDP) | `tools/common` + Playwright | Quét bài đăng từ Fanpage Facebook và Threads | Tái sử dụng session browser đã đăng nhập sẵn trong profile cục bộ |
| Xử lý tiếng Việt (NLP) | `underthesea` & `pyvi` | Tách từ (Word Segmentation), gán nhãn từ loại, lọc stopword | Thư viện xử lý ngôn ngữ tự nhiên tối ưu riêng cho cấu trúc ngữ pháp tiếng Việt |
| Mô hình nhúng ngữ nghĩa | `bkai-foundation-models/vietnamese-bi-encoder` | Biến đổi văn bản thành vector để gom cụm chủ đề | Tương thích `sentence-transformers`, chạy mượt mà trên CPU bằng ONNX runtime |
| Phát hiện bứt phá (Burst) | Thuật toán Kleinberg / Z-Score | Tính gia tốc xuất hiện của từ khóa/video trong 24h | Đếm tần suất trượt, so sánh độ lệch chuẩn với baseline 7 ngày trước đó |
| Cơ sở dữ liệu nhúng | `sqlite3` + `sqlite-vec` (hoặc DuckDB) | Lưu trữ bản ghi video, chỉ số tương tác và vector | Tích hợp sẵn trong Python standard library, không cần cài đặt database daemon |

## Tái sử dụng công cụ nội bộ repository

| Công cụ sẵn có | Vị trí file trong codebase | Cách thức tái sử dụng nhúng | Lợi ích theo chuẩn Ponytail |
|---|---|---|---|
| Trình tải video `yt-dlp` | Môi trường ảo dự án (`uv run yt-dlp`) | Gọi qua module `subprocess` hoặc import trực tiếp để lấy metadata | Tận dụng công cụ sẵn có, không cài thêm wrapper dư thừa |
| Quản lý profile trình duyệt | [`tools/common/local/profiles.json`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/tools/common/local/profiles.json) | Kết nối CDP tới port trình duyệt đang mở để đọc Facebook/Threads | Tránh bị chặn captcha, không cần mua tài khoản proxy đắt đỏ |
| Tự động hóa thiết bị di động | [`tools/taktik-bot/`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/tools/taktik-bot/) | Điều khiển ứng dụng TikTok trên điện thoại thật có định vị VN | Bỏ qua cơ chế chặn bot web, lấy nguồn cấp For You chuẩn xác 100% |
| Kiểm định dữ liệu viral | `tools/loop/viral_analyzer` | Tái cấu trúc schema báo cáo manifest, relevance và receipts | Kế thừa định dạng báo cáo kiểm toán có sẵn trong repository |

## Mẫu mã nguồn nhúng tối giản

| Khối mã nguồn | Cú pháp triển khai tối giản (Python) | Giải thích chức năng |
|---|---|---|
| Khởi tạo Google Trends | `from pytrends.request import TrendReq; pt = TrendReq(hl='vi-VN', tz=420); df = pt.trending_searches(pn='vietnam')` | Lấy danh sách 20 thực thể bùng nổ nhất trong 24h tại Việt Nam |
| Trích xuất metadata video | `cmd = ['yt-dlp', '--dump-json', '--flat-playlist', f'https://www.tiktok.com/tag/{tag}']; res = json.loads(run(cmd))` | Lấy trực tiếp danh sách video, lượt xem, tác giả mà không tải tệp video |
| Tính điểm bứt phá 24h | `def get_velocity(views_24h, median_views): return views_24h / max(median_views, 1)` | Lọc các video có tỷ lệ bứt phá >= 5.0 so với trung bình kênh |
| Lọc từ khóa tiếng Việt | `from underthesea import word_tokenize; words = word_tokenize(text, format="text").split()` | Tách từ ghép tiếng Việt chuẩn xác (ví dụ: "chữa_lành", "bóc_phốt") |
| Lưu trữ SQLite cục bộ | `import sqlite3; conn = sqlite3.connect('viral_24h.db'); conn.execute('CREATE TABLE IF NOT EXISTS trends (...)')` | Lưu vết thời gian thực, phục vụ truy vấn và cập nhật cuốn chiếu |

## Đánh giá đánh đổi và vận hành

| Khía cạnh | Ưu thế giải pháp nhúng nội bộ | Nhược điểm & Biện pháp khắc phục |
|---|---|---|
| Tốc độ phản hồi | Cập nhật theo chu kỳ 15 phút, phản ứng tức thì với trend 24h | Cần máy chủ nhỏ hoặc máy cục bộ duy trì tiến trình định kỳ cron |
| Bảo mật thông tin | Dữ liệu thương hiệu và lịch sử phân tích không bị gửi ra ngoài | Tự quản lý sao lưu dữ liệu SQLite và vòng đời lưu trữ metadata |
| Giới hạn tần suất gọi | Không phụ thuộc vào gói đăng ký số lượng API call của bên thứ ba | Phải thiết lập khoảng giãn cách (rate limit) 2-3s và xoay vòng profile |
| Khả năng mở rộng | Dễ dàng bổ sung nguồn dữ liệu mới (Telegram, Zalo, diễn đàn) | Cần cập nhật bộ bóc tách khi giao diện web mạng xã hội thay đổi |
