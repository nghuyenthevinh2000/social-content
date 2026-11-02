# Chiến lược Sao chép Viral 24h theo Thuật toán tại Việt Nam

```text
Quét KOL Tier-1 & Outlier -> Bóc tách Hook/OCR/Sound ID -> Ghép B-Roll (15p) -> Vượt Traffic Pool -> Chuyển đổi Follow
```

## 1. Bể lưu lượng & Thuật toán 24h

| Bể lưu lượng (Traffic Pool) | Quy mô lượt xem | Ngưỡng chỉ số thuật toán | Cơ chế định tuyến vùng miền tại Việt Nam |
|---|---|---|---|
| Pool 1: Cold Sandbox | 200 – 500 views | Giữ chân 3s đầu (3s Hold) >= 65%; Lướt bỏ < 35% | Quét chữ trên màn hình (OCR), giọng nói tiếng Việt (ASR) và IP/SIM để phân luồng nội địa |
| Pool 2: Validation | 1,000 – 5,000 views | Xem hết (Completion) >= 35%; Xem lặp (Loop) >= 1.15x | So khớp hành vi dừng xem với tệp vừa tương tác chủ đề hoặc âm thanh tương tự trong 24h |
| Pool 3: Breakout | 10,000 – 50,000 views | Share/Save >= 1.5%; Comment >= 1.0%; Click hồ sơ >= 2.0% | Đẩy vào cụm khán giả tiểu vùng (Hà Nội/Miền Bắc hoặc TP.HCM/Miền Nam) theo mật độ từ lóng |
| Pool 4: Semi-Viral | 100,000 – 500,000 views | Thời gian xem trung bình > 120% nhờ đọc bình luận | Mở rộng phân phối chéo sang tệp lân cận; ưu tiên video có tranh luận sôi nổi dưới bình luận |
| Pool 5: Mega FYP | > 1,000,000 views | Duy trì gia tốc Share + Profile Follow qua 3 khung giờ vàng | Phủ sóng toàn quốc trên For You Page / Reels; định hình mẫu cấu trúc cho thị trường |

## 2. Sao chép KOL Đầu bảng & Kênh Bứt phá

| Nhóm mục tiêu theo dõi | Đặc quyền phân phối trong thuật toán | Công thức phát hiện tín hiệu viral 24h | Chiến thuật sao chép cấu trúc (Fast-Follow) |
|---|---|---|---|
| Tier-1 Alpha KOLs (20 kênh đầu ngành/MCN) | Điểm tín nhiệm (Account Authority) cao; bỏ qua Pool 1–2, vào thẳng Pool 3–4 trong 30 phút đầu | Video đạt `Views_3h >= 3x Median_7d` của kênh, hoặc >= 3 KOL cùng dùng 1 cấu trúc/nhạc trong 12h | Sao chép ngay bố cục Hook thị giác 3s đầu, nhịp cắt cảnh và gắn chung Sound ID trong 4 giờ |
| Tier-2 Breakout Outliers (30 kênh nhỏ 5k–30k sub) | Không có đặc quyền thương hiệu; thắng thuật toán hoàn toàn nhờ điểm giữ chân và tương tác thực | Kênh nhỏ đạt `Views_24h >= 10x Followers` (ví dụ: kênh 10k follow đạt 150k view sau 1 đêm) | Rút trích nguyên mẫu kịch bản (Script Skeleton) và cú pháp tiêu đề OCR vì cấu trúc tự thắng thuật toán |
| Ký sinh cụm chủ đề (Topic Graph Hijacking) | Thuật toán gom các video chung từ khóa OCR, âm thanh và lời thoại vào một luồng đề xuất | Video gốc của KOL tăng nóng (> 10,000 views/giờ) và bình luận xuất hiện nhiều câu hỏi bỏ ngỏ | Làm video Stitch/Duet hoặc dùng chính xác cụm từ khóa tiêu đề của KOL ở 3s đầu để đón đề xuất |
| Bẫy bình luận lặp vòng (Comment-Drawer Loop) | Khi người xem mở bình luận đọc/tranh cãi, video phía sau tự phát lặp lại (Watch Time > 200%) | Video viral tại Việt Nam đạt tỷ lệ `Comment / Like >= 0.15` nhờ chi tiết gây tò mò hoặc khẩu vị vùng miền | Cài cắm 1 chi tiết lạ ở hậu cảnh, phát âm vùng miền hoặc nhận định sắc bén để giữ chân đọc bình luận |

## 3. Khai thác Âm thanh Thịnh hành 24h

| Kỹ thuật khai thác Audio | Cơ chế thuật toán đứng sau | Cách săn âm thanh bứt phá 24h tại Việt Nam | Quy tắc thực thi chuẩn xác |
|---|---|---|---|
| Ký sinh âm thanh ẩn (Hidden Audio 2%–5%) | Sound ID là kênh phân phối độc lập; video gắn nhạc đang lên được đẩy tới người vừa xem nhạc đó | Quét bảng "Breakout" 24h trên TikTok Creative Center (VN) hoặc lưu nhạc xuất hiện >= 3 lần/20 phút lướt FYP | Giữ giọng gốc (Voiceover 100%) và chèn nhạc viral ở mức âm lượng 2%–5% làm nền để vào bể lưu lượng nhạc |
| Đồng bộ điểm rơi nhịp nhạc (Beat-Drop Sync) | Tỷ lệ xem hết tăng vọt khi chuyển cảnh hoặc tung kết quả khớp nhịp bass nhạc Remix/Vinahouse | Kiểm tra tab "Mới nhất" trong trang âm thanh: nếu kênh nhỏ vừa đăng 2–6h trước đều vọt view thì nhạc đang được trợ giá | Đặt điểm cắt hình ảnh (Visual Cut) và dòng chữ kết luận ngay tại giây beat-drop để khóa mắt người xem |
| Chiếm quyền âm thanh gốc (Original Sound Seeding) | Khi kênh khác lấy âm thanh gốc của bạn làm video, kênh gốc được cộng điểm uy tín và kéo truy cập hồ sơ | Săn đoạn thoại đời thường hài hước, câu nói viral trên Threads/Facebook chưa có bản thu chuẩn trên TikTok/Reels | Tách âm câu thoại sắc nét, ghép nhịp nhạc nền bắt tai và đặt tên âm thanh chứa từ khóa dễ tìm |

## 4. Ngân hàng B-Roll & Lắp ghép 15 Phút

| Phân loại B-Roll dự trữ | Bối cảnh thị giác bản địa hóa Việt Nam | Cấu trúc kỹ thuật quay & lưu trữ | Công thức lắp ghép tăng lặp vòng (Replay Hack) |
|---|---|---|---|
| Hành động tập trung (Hustle / Deep Work) | Làm việc tại quán cà phê, gõ phím, đóng gói hàng tại xưởng, di chuyển ngoài đường phố Hà Nội/Sài Gòn | Quay dọc 9:16 (4K 60fps), dài 5–7s/clip, chừa trống 1/3 khung giữa để chèn chữ tiếng Việt rõ nét | Ghép clip B-Roll dài 6s với khối văn bản (Wall of Text) mất 12–15s đọc -> Ép video tự lặp >= 2 lần (Completion 200%) |
| Phản ứng ngắt nhịp (Pattern Interrupts) | Cầm ly cà phê sữa đá, ngước nhìn máy quay bất ngờ, chỉ tay lên tiêu đề, lắc đầu hoặc gật đầu đồng tình | Quay sẵn 20–30 biến thể biểu cảm trong 1 buổi (thay 3–4 áo), cắt sát điểm đầu không có giây chết | Dùng làm 2s mở đầu (0–2s Hook) kèm hiệu ứng âm thanh chuyển cảnh và chữ vàng/trắng viền đen cỡ lớn để chặn vuốt |
| Cận cảnh thỏa mãn (Tactile / Chữa lành) | Pha đồ uống, lật sổ tay, bóc kiện hàng, góc phố mưa, ánh đèn đêm, thao tác tay nhanh gọn | Ánh sáng tương phản cao, tốc độ 0.8x hoặc 1.2x, gắn thẻ theo cảm xúc và bối cảnh trong thư mục | Làm nền cho kịch bản kể chuyện, bài học nghề nghiệp hoặc trích dẫn chủ đề đang gây bão trên Threads 24h |

## 5. Phễu Chuyển đổi Lượt xem sang Follower

| Điểm chạm trong phễu | Nguyên nhân có View nhưng không ra Follow | Cơ chế tối ưu hóa chuyển đổi (View -> Profile -> Follow) | Chỉ số mục tiêu |
|---|---|---|---|
| Định vị Bản sắc ở Giây thứ 2 (Tribe Signaling) | Nội dung đại trà khiến người xem giải trí xong rồi lướt đi mà không quan tâm tác giả | Gắn xu hướng 24h với danh xưng/tệp cụ thể: *"Góc nhìn dân [Ngành] tại Sài Gòn/Hà Nội"*, *"Ngày thứ X xây [Mục tiêu]"* | Nhận diện đúng ngách trong 3s đầu |
| Cắt ngang Mở vòng lặp (Open-Loop Cliffhanger) | Giải quyết hết thông tin trong video khiến người xem không có động lực bấm vào hồ sơ | Ngắt video ngay trước bước quan trọng nhất -> CTA: *"Bản đầy đủ/Phần 2 đã ghim ở đầu kênh, bấm vào hồ sơ xem ngay"* | Click Hồ sơ (Profile Visit) >= 2.5% – 4.0% |
| Cửa hàng 3 Video Ghim (Pinned Storefront) | Khách vào trang cá nhân thấy video lộn xộn, không hiểu kênh mang lại lợi ích dài hạn gì | **Ghim 1:** Câu chuyện định danh/Bảo chứng kết quả; **Ghim 2:** Hướng dẫn/Tài nguyên giá trị cao; **Ghim 3:** Chuỗi đang viral | Ghé thăm sang Follow (Profile-to-Follow) >= 15% – 25% |
| Khóa Tài nguyên ở Bình luận Ghim (Comment Gate) | Người xem chỉ mở bình luận đọc rồi thoát ra mà không bấm theo dõi | Tự đăng và ghim bình luận ngay khi xuất bản: *"Bấm Follow kênh + bình luận từ khóa [X] để nhận quy trình/tài liệu"* | Tăng mật độ bình luận (lên Pool 4–5) và follower |

## 6. Lịch trình Tác chiến 24h

| Khung giờ (VN) | Giai đoạn tác chiến | Thao tác kỹ thuật cụ thể | Đầu ra bắt buộc |
|---|---|---|---|
| 08:00 – 09:00 | Săn mồi thuật toán | Quét 20 KOL Tier-1 và 30 kênh Outlier; lọc 3 video có vận tốc view/giờ cao nhất 12h qua; lưu 3 Sound ID đang lên | 3 khung kịch bản (Hook OCR + Nhịp cắt + Sound ID) được thuật toán xác nhận |
| 09:00 – 10:00 | Ghép B-Roll (15p) | Viết lại Hook tiếng Việt theo ngách; kéo 3 clip từ Ngân hàng B-Roll; chèn chữ, gắn nhạc trending ở mức 3% âm lượng | 2–3 video hoàn chỉnh (7–15s hoặc 30–45s) có bẫy bình luận và CTA về hồ sơ |
| 11:15 & 19:15 | Xuất bản đón sóng | Đăng trước giờ cao điểm trưa và tối 15 phút; tự thả bình luận mồi (Seed Comment) định hướng tranh luận | Video vượt Pool 1–2 trong 60 phút đầu với giữ chân 3s >= 70% |
| 22:00 – 23:00 | Kiểm toán Pool | Đo `3s Hold`, `Completion`, `Profile Visit -> Follow`; nếu chạm Pool 3 (>10k views), làm ngay Phần 2 trả lời bình luận | Video phản hồi bình luận (Video Reply) đăng sáng hôm sau để thu hoạch tiếp lưu lượng |
