# Kế Hoạch Sản Xuất Post 4: Giấy Ánh Kim 180

```mermaid
flowchart LR
    A["Benchmark rec-01"] --> B["Director Prompt"]
    B --> C["Gemini Video 9:16"]
    C --> D["ElevenLabs STS"]
    D --> E["v3.1 Normalization"]
    E --> F["TikTok Mobile"]
```

| Hạng mục | Chi tiết triển khai | Căn cứ & Quy chuẩn kỹ thuật |
|---|---|---|
| **Mục tiêu sản phẩm** | Video UGC 9:16 (10s) giới thiệu Giấy Ánh Kim 180gsm chuyên thiệp cưới, giấy khen, phong bì. | Mục `anh-kim-180` tại [`product-marketing.json`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/local/paper-ink-product/product-marketing.json). |
| **Đối tượng mục tiêu** | Chủ xưởng in phôi thiệp cưới, xưởng bao bì, đơn vị gia công in ấn. | Hồ sơ khách hàng tại [`product-marketing.json`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/local/paper-ink-product/product-marketing.json). |
| **Nền tảng phân phối** | TikTok Mobile (`com.ss.android.ugc.trill`) kết hợp Facebook Page Reels. | Thiết lập phân phối tại [`project.json`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/projects/ugc-video/project.json). |
| **Trạng thái thực thi** | Lập kế hoạch trước khi tạo video/audio; chưa gọi API phát sinh chi phí. | Yêu cầu phiên làm việc: lập kế hoạch hoàn tất trước khi sinh media. |

| Chỉ số tham chiếu | Giá trị quan sát (TikTok Benchmark) | Phân tích cơ chế thu hút |
|---|---|---|
| **ID & URL** | `rec-01` — [tiktok.com/@thiepcuoi.com/video/7234529710599015685](https://www.tiktok.com/@thiepcuoi.com/video/7234529710599015685) | Top 1 lượt xem trong 159 video khảo sát ngành in ấn. |
| **Kênh & Ngày đăng** | `@thiepcuoi.com` (TikTok) — Ngày ghi nhận: `2023-05-18` | Kênh chuyên xưởng in phôi thiệp cưới thực tế. |
| **Số liệu tương tác** | `611,054 views`, `8,676 likes`, `36 comments`, `55 shares` | Vượt ngưỡng viral outlier (>=10,000 views) gấp 61 lần. |
| **Báo cáo nguồn** | [`run-20261024-discovery-01/report.md`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/local/paper-ink-product/sources/viral/run-20261024-discovery-01/report.md) | Lưu tại `local/paper-ink-product/sources/viral/run-20261024-discovery-01/`. |
| **Hook gốc** | “Shop ơi tư vấn cho em mẫu nào đơn giản và đẹp...” (Mở hộp khoe phôi thiệp). | Question Hook (`HK-02`), đánh trúng nhu cầu phôi thiệp sang trọng, tối giản. |
| **Điểm chạm thị giác** | Cận cảnh mở hộp khoe phôi thiệp nhũ lấp lánh phản chiếu ánh sáng. | Kích thích xúc giác trong 2 giây đầu, giữ chân người xem tức thì. |

| Bước | Nguyên tắc chuyển đổi | Nội dung áp dụng vào Post 4 (Giấy Ánh Kim 180) |
|---|---|---|
| **1. Hook phỏng vấn** | Giữ mẫu câu hỏi: `[Chủ thể] ơi tư vấn cho em [nhu cầu cốt lõi]?` | "Xưởng ơi, có mẫu giấy in thiệp cưới nào vừa sang vừa kinh tế không?" |
| **2. Hành động mở đầu** | Chuyển mở hộp khách mua thành thợ xưởng mở kiện phôi Ánh Kim 79×109cm. | Nữ thợ xưởng cười tươi, mở nhanh kiện phôi giấy trên bàn thao tác. |
| **3. Trình diễn vật lý** | Cận cảnh bề mặt giấy bắt sáng và thử độ dai nếp gấp. | Nghiêng mặt giấy dưới đèn xưởng lộ ánh nhũ mịn, vuốt nếp gấp không nứt gãy. |
| **4. Lời kêu gọi (CTA)** | Chuyển thành lời mời xưởng in nhận tập mẫu giấy và test máy thực tế. | "Xưởng in thiệp cưới nhắn bên em nhận mẫu phôi Giấy Ánh Kim test máy miễn phí nhé!" |

| Phân đoạn | Thời lượng | Khung hình, Hành động & Đạo cụ | Lời thoại tiếng Việt | Chữ hiển thị (Safe Zone) |
|---|---|---|---|---|
| **Hook** | 0.0s – 3.0s | POV góc cao 35° bàn xưởng. Nữ thợ (khớp [`face.jpg`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/projects/ugc-video/assets/images/face.jpg) và [`clothes.jpg`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/projects/ugc-video/assets/images/clothes.jpg)) cười tươi, hai tay mở kiện phôi Giấy Ánh Kim 180 lấp lánh trên bàn. | “Xưởng ơi, có mẫu giấy in thiệp cưới nào vừa sang vừa kinh tế không?” | **TÌM PHÔI THIỆP SANG & KINH TẾ?** |
| **Proof** | 3.0s – 7.0s | Nữ thợ nhấc 1 tờ phôi, nghiêng dưới ánh đèn xưởng khoe lớp nhũ xà cừ óng ánh, vuốt nếp cấn chứng minh giấy dai, không nứt sườn. | “Giấy Ánh Kim 180 bên em bề mặt nhũ xà cừ cực mịn, ăn mực sắc nét, lên máy bế hay gấp nếp không lo nứt gãy.” | **GIẤY ÁNH KIM 180GSM**<br>• Nhũ xà cừ mịn đẹp<br>• Gấp nếp không nứt |
| **CTA** | 7.0s – 10.0s | Đặt phôi ngay ngắn cạnh thùng thành phẩm, nhìn thẳng ống kính camera cười thân thiện và ra hiệu kết nối. | “Khổ 79×109 có sẵn tận xưởng, nhận đơn từ 2 gam. Nhắn tin xưởng em gửi mẫu test máy liền nha!” | **KHỔ 79×109cm • TỪ 2 GAM**<br>📞 Hotline/Zalo: 0904642276<br>👉 **Nhắn nhận mẫu test máy** |

| Cấu hình | Thiết lập | Mục đích kỹ thuật |
|---|---|---|
| **Engine tạo hình** | Vertex AI `gemini-omni-flash-preview` (`location="global"`) | Tái tạo cử chỉ cầm giấy tự nhiên, phản xạ nhũ kim và khẩu hình tiếng Việt. |
| **Kích thước & Tỷ lệ** | `720 × 1280` px (Chuẩn dọc 9:16 mobile) | Định dạng chuẩn dọc cho TikTok và Facebook Reels. |
| **Khung hình & Độ dài** | 24.0 fps — Thời lượng: `10s` (~10.03s) | Nhịp chuẩn UGC ngắn tối ưu tỷ lệ xem hết (completion rate). |
| **Neo diện mạo (Ref 0)** | [`assets/images/face.jpg`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/projects/ugc-video/assets/images/face.jpg) | Giữ diện mạo nữ thợ xưởng đặc trưng qua các tập video. |
| **Neo trang phục (Ref 1)** | [`assets/images/clothes.jpg`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/projects/ugc-video/assets/images/clothes.jpg) | Áo loungewear hoa cà cộc tay có hoa thêu ngực. |
| **Bối cảnh xưởng** | Xưởng in giấy mỹ thuật với máy xén công nghiệp phía sau. | Tạo độ tin cậy thực tế của xưởng sản xuất, bỏ bối cảnh studio nhân tạo. |

| Khối Prompt | Cấu hình cho Vertex AI Gemini Omni Flash API |
|---|---|
| **`[CAMERA]`** | `Vertical 9:16 mobile POV. High-angle perspective (35-degree downward tilt) filmed beside workshop workbench, looking down across the table. Natural handheld camera breathing and motion tracking presenter's hands, raw BTS workshop documentary style. Pristine clean video, no watermarks, no logos, no text overlays, no usernames.` |
| **`[ENVIRONMENT]`** | `Active paper workshop. Background: guillotine cutting machine, stacked paper pallets under overhead lighting. On workbench: gleaming sheets of specialty metallic pearlescent paper (giấy ánh kim 180gsm) shimmering under light, with sample wedding cards.` |
| **`[SUBJECT]`** | `Young East Asian female artisan matching <IMAGE_REF_0> wearing pale lavender loungewear top with tonal floral embroidery in <IMAGE_REF_1>. Leaning forward over pearlescent paper sheets, smiling warmly and engaging directly with camera.` |
| **`[ACTION]`** | `00:00-00:03: She uncovers and fans out large sheets of metallic pearlescent paper (giấy ánh kim) on table, tilting under light to catch pearlescent shimmer.<br>00:03-00:07: She lifts one sheet, gently curling it to demonstrate flexibility and smooth texture, showing fold edge without cracking.<br>00:07-00:10: She places paper down alongside reams, smiling warmly, nodding and making a welcoming gesture toward camera.` |
| **`[AUDIO]`** | `'Lively spoken Vietnamese dialogue delivered with enthusiastic artisan cadence matching her recorded voice: "Xưởng ơi, có mẫu giấy in thiệp cưới nào vừa sang vừa kinh tế không? Dòng Giấy Ánh Kim 180 bên em bề mặt nhũ xà cừ cực mịn, ăn mực sắc nét, lên máy bế hay gấp nếp không lo nứt gãy. Khổ tiêu chuẩn 79×109 có sẵn tận xưởng, nhận đơn từ 2 gam. Nhắn tin xưởng em gửi mẫu test máy liền nha!". Ambient print shop background.'` |

| Bước xử lý âm | Công cụ & Tài nguyên | Kỹ thuật đồng bộ khẩu hình |
|---|---|---|
| **1. Đo cửa sổ khẩu hình** | `silencedetect` / kiểm tra biên độ âm thanh dẫn từ video | Lấy mốc bắt đầu và kết thúc từng mệnh đề trên video. |
| **2. Tái tạo giọng thợ** | ElevenLabs Client — Voice ID: `FXJGVNPXC71BGT9PjlMX` | Dùng trực tiếp giọng chuẩn miền Bắc (*Vietnamese Actual Women Voice*) trên ElevenLabs. |
| **3. Khóa nhịp `eleven_v3`** | `textToSpeech.convertWithTimestamps("FXJGVNPXC71BGT9PjlMX", { modelId: "eleven_v3" })` | Ánh xạ từng mệnh đề vào đúng cửa sổ khẩu hình bằng `atempo` + `loudnorm=-16 LUFS`. |
| **4. Ghép muxing** | `ffmpeg -i post_4.mp4 -i tts_v3_20s_aligned.wav -c:v copy -c:a aac` | Xuất deliverable đồng bộ [`renders/omni-1.1-flash/post_4_omni11_20s_web_optimized.mp4`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/projects/ugc-video/renders/omni-1.1-flash/post_4_omni11_20s_web_optimized.mp4). |

| Tham số v3.1 | Giá trị thiết lập | Phòng ngừa lỗi thực tế |
|---|---|---|
| **Ma trận màu** | `colorspace=all=bt709:trc=bt709:primaries=bt709` | Khắc phục lỗi pixel vỡ hồng/tím trên di động ([`feedback_29_10_2026.jpg`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/projects/ugc-video/plans/feedback_29_10_2026.jpg)). |
| **Tần số âm thanh** | `44,100 Hz Stereo AAC` (`-ar 44100 -ac 2 -b:a 192k`) | Ngăn ngừa mobile decoder bị drop packet hoặc mất tiếng. |
| **Chu kỳ GOP** | `-g 48 -keyint_min 48 -sc_threshold 0` (2.0s tại 24fps) | Đảm bảo seek mượt, không sinh macroblock khi mạng chập chờn. |
| **Container MP4** | `-movflags +faststart` | Đẩy header `moov` lên đầu file, phát tức thì khi tải trang. |
| **Script chuẩn hóa** | [`scripts/normalize_video.sh`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/projects/ugc-video/scripts/normalize_video.sh) | Gom toàn bộ cờ transcode vào lệnh: `./scripts/normalize_video.sh`. |

| Bước | Giai đoạn thực thi | Lệnh hoặc script điều hành | Tiêu chí hoàn thành (Stop Condition) |
|---|---|---|---|
| **1** | **Xác nhận kế hoạch** | Duyệt file [`post-4-production-plan.md`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/projects/ugc-video/plans/post-4-production-plan.md) | Người dùng phê duyệt kịch bản và thông số kỹ thuật. |
| **2** | **Tạo video thô (v4)** | `python3 projects/ugc-video/local/generate_post_4_video.py` | Sinh thành công `renders/post_4.mp4` đủ 10 giây, đúng 9:16. |
| **3** | **Tạo âm thanh `eleven_v3`** | `node projects/ugc-video/scripts/sync_eleven_v3_voice.js` | Tạo `tts_v3_20s_aligned.wav` khớp khẩu hình bằng Voice ID `FXJGVNPXC71BGT9PjlMX`. |
| **4** | **Transcode v3.1** | `./projects/ugc-video/scripts/normalize_video.sh post_4_sts_synced.mp4` | Xuất `renders/post_4_web_optimized.mp4` chuẩn BT.709, AAC stereo. |
| **5** | **Preflight & Kiểm tra** | `ffprobe` xác minh tag BT.709 và kiểm tra bằng mắt | Khung hình chuẩn nét, không vỡ hồng, khẩu hình khớp tiếng. |
| **6** | **Xuất bản TikTok** | `tools/taktik-bot` (`tiktok.standalone.upload_post`) | Nhận phản hồi publish thành công từ TikTok mobile bot. |
