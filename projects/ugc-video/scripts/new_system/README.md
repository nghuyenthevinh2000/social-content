# Multi-Scene Declarative UGC Video Engine (`new_system`)

```text
[configs/<post_slug>.json]  (Khai báo N scenes: actions + clauses, không cần viết code mới)
             |
             v
python3 scripts/new_system/engine.py scripts/new_system/configs/<post_slug>.json
             |
   +---------+------------------------------------------------------------------+
   | 1. Scene 1: face.jpg + clothes.jpg -> scene1_raw.mp4 (10s)                 |
   | 2. Scene k (k>=2): Trích scene{k-1}_end.jpg + task="image_to_video"        |
   |    -> scene{k}_raw.mp4 (10s, khóa cứng Frame 0 với MAE < 4.0)              |
   | 3. Voice: Gọi thẳng REST API eleven_v3 with-timestamps (FXJGVNPXC71BGT9PjlMX)|
   | 4. Auto-Sync: Tự dò khoảng lặng (silencedetect) + chia tỷ lệ TTS duration  |
   | 5. Stitch & Normalize: Nối N cảnh + atempo + loudnorm -16 LUFS + BT.709    |
   +----------------------------------------------------------------------------+
```

| Tệp trong `scripts/new_system/` | Vai trò trong hệ thống | Cách sử dụng |
|---|---|---|
| [`engine.py`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/projects/ugc-video/scripts/new_system/engine.py) | **Engine tổng duy nhất** xử lý từ $1 \dots N$ phân cảnh, tự động khóa `<FIRST_FRAME>` (`image_to_video`), gọi ElevenLabs `eleven_v3` `with-timestamps`, tự động dò cửa sổ khẩu hình bằng `silencedetect`, áp dụng Seam Editor (`lutrgb` + `1-frame xfade`) và chuẩn hóa BT.709. | `python3 projects/ugc-video/scripts/new_system/engine.py <path_to_config.json>` |
| [`normalize_video.py`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/projects/ugc-video/scripts/new_system/normalize_video.py) | **Module chuẩn hóa mạng xã hội** (BT.709, 44.1kHz Stereo AAC, GOP 48, FastStart + `ffprobe` assert check), được `engine.py` import trực tiếp hoặc chạy độc lập qua CLI. | `python3 projects/ugc-video/scripts/new_system/normalize_video.py <in.mp4> <out.mp4>` |
| [`configs/post_4_wedding_paper.json`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/projects/ugc-video/scripts/new_system/configs/post_4_wedding_paper.json) | Cấu hình 2 phân cảnh (`20.0s`) cho **Post 4 — Giấy Ánh Kim 180 In Thiệp Cưới** (hoàn toàn dùng chế độ tự động dò khẩu hình `auto`, không cần điền tay mốc giây). | `python3 projects/ugc-video/scripts/new_system/engine.py projects/ugc-video/scripts/new_system/configs/post_4_wedding_paper.json` |
| [`configs/post_5_red_velvet_envelope.json`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/projects/ugc-video/scripts/new_system/configs/post_5_red_velvet_envelope.json) | Cấu hình mẫu 2 phân cảnh (`20.0s`) cho **Giấy Đỏ Nhung & Bao Lì Xì Ép Kim** minh họa cách tạo video nhiều cảnh mới chỉ bằng 1 file JSON. | `python3 projects/ugc-video/scripts/new_system/engine.py projects/ugc-video/scripts/new_system/configs/post_5_red_velvet_envelope.json` |

| Trường trong `config.json` | Kiểu dữ liệu | Cơ chế xử lý của `engine.py` |
|---|---|---|
| `slug`, `work_dir`, `output_path` | `string` | Định danh thư mục làm việc (`renders/<slug>`) và đường dẫn file MP4 đầu ra. Nếu `scene{k}_raw.mp4` hoặc `tts_v3_raw.mp3` đã tồn tại trong `work_dir`, engine tự động tái sử dụng cache. |
| `voice_id` | `string` | Mặc định `FXJGVNPXC71BGT9PjlMX` (*Vietnamese Actual Women Voice*, `vi-northern`). Engine ghép toàn bộ `clauses` của cả $N$ cảnh để gọi `eleven_v3` **1 lần duy nhất**, đảm bảo giọng đọc đồng nhất 100% xuyên suốt video. |
| `scenes[k].actions` | `string[]` | Mô tả hành động theo nhịp `00:00 - 00:03`, `00:03 - 00:07`, `00:07 - 00:10`. Ở cảnh $k \ge 2$, luôn chỉ đạo nhân vật tương tác với đạo cụ đã đặt sẵn trên bàn từ cảnh 1. |
| `scenes[k].clauses` | `string[]` hoặc `{text, window}[]` | Danh sách câu thoại của cảnh $k$. Khi chỉ truyền chuỗi văn bản (`string`), engine tự chạy `silencedetect` trên `scene{k}_raw.mp4` (tự ngắt `0.6s` cuối các cảnh đầu để tránh nói vấp ở điểm nối) và chia khung thời gian khớp tự động. |
