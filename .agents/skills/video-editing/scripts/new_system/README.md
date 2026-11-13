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
| [`engine.py`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/projects/ugc-video/scripts/new_system/engine.py) | **Engine tổng duy nhất** xử lý từ $1 \dots N$ phân cảnh, phân tích Reel mẫu (`--analyze-reel`), tự động khóa `<FIRST_FRAME>` (`image_to_video`), tự động retry khi Vertex AI chặn safety, gọi [`synthesize_eleven_v3.py`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/projects/ugc-video/scripts/new_system/synthesize_eleven_v3.py), tự phân hoạch từ theo quy hoạch động (`partition_words_to_windows_dp`) khớp vào các khoảng mở miệng (`detect_scene_speech_windows`), áp dụng Seam Editor (`lutrgb` + `1-frame xfade`) và chuẩn hóa BT.709. | `python3 projects/ugc-video/scripts/new_system/engine.py --analyze-reel "<URL>"`<br>`python3 projects/ugc-video/scripts/new_system/engine.py <path_to_config.json>` |
| [`synthesize_eleven_v3.py`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/projects/ugc-video/scripts/new_system/synthesize_eleven_v3.py) | **Module tổng hợp giọng nói ElevenLabs `eleven_v3`** dùng thư viện Python chính thức `elevenlabs` (`client.text_to_speech.convert_with_timestamps`, `mp3_44100_128`), xuất `tts_v3_raw.mp3` và `tts_v3_alignment.json`. | `python3 projects/ugc-video/scripts/new_system/synthesize_eleven_v3.py --voice-id <ID> --text "<TEXT>" --work-dir <DIR>` |
| [`effect_editor.py`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/projects/ugc-video/scripts/new_system/effect_editor.py) | **Engine hậu kỳ hiệu ứng** đóng phụ đề karaoke từng từ từ `tts_v3_alignment.json` và `clause_bounds.json`, thêm banner hook, punch zoom và nhạc nền/SFX. | `python3 projects/ugc-video/scripts/new_system/effect_editor.py <effects_config.json>` |
| [`normalize_video.py`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/projects/ugc-video/scripts/new_system/normalize_video.py) | **Module chuẩn hóa mạng xã hội** (BT.709, 44.1kHz Stereo AAC, GOP 48, FastStart + `ffprobe` assert check), được `engine.py` import trực tiếp hoặc chạy độc lập qua CLI. | `python3 projects/ugc-video/scripts/new_system/normalize_video.py <in.mp4> <out.mp4>` |
| [`configs/ngat_ngoai_tinh_psychology.json`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/projects/ugc-video/scripts/new_system/configs/ngat_ngoai_tinh_psychology.json) | Cấu hình 2 phân cảnh (`20.0s`) cho **Chị Ngát (`"creator": "ngat"`)** với `visual_dialogue` chống chặn safety trên Vertex AI. | `python3 projects/ugc-video/scripts/new_system/engine.py projects/ugc-video/scripts/new_system/configs/ngat_ngoai_tinh_psychology.json` |
| [`configs/post_4_wedding_paper.json`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/projects/ugc-video/scripts/new_system/configs/post_4_wedding_paper.json) | Cấu hình 2 phân cảnh (`20.0s`) cho **Post 4 — Giấy Ánh Kim 180 In Thiệp Cưới** (`"creator": "diep"`). | `python3 projects/ugc-video/scripts/new_system/engine.py projects/ugc-video/scripts/new_system/configs/post_4_wedding_paper.json` |
| [`configs/post_5_red_velvet_envelope.json`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/projects/ugc-video/scripts/new_system/configs/post_5_red_velvet_envelope.json) | Cấu hình mẫu 2 phân cảnh (`20.0s`) cho **Giấy Đỏ Nhung & Bao Lì Xì Ép Kim** (`"creator": "diep"`). | `python3 projects/ugc-video/scripts/new_system/engine.py projects/ugc-video/scripts/new_system/configs/post_5_red_velvet_envelope.json` |

| Trường trong `config.json` | Kiểu dữ liệu | Cơ chế xử lý của `engine.py` |
|---|---|---|
| `slug`, `work_dir`, `output_path` | `string` | Định danh thư mục làm việc (`renders/<slug>`) và đường dẫn file MP4 đầu ra. Nếu `scene{k}_raw.mp4` hoặc `tts_v3_raw.mp3` đã tồn tại trong `work_dir`, engine tự động tái sử dụng cache. |
| `creator` | `string` | `"ngat"` hoặc `"diep"`. Tự động suy diễn `face_image`, `clothes_image` (`assets/images/<creator>/`) và nạp `voice_id` từ `assets/audio/<creator>/voice_meta.json`. |
| `voice_id` | `string` | Tự động nạp theo `creator` (`ngat` -> `a95xm5oG7Gvnxoyv5jeJ`, `diep` -> `FXJGVNPXC71BGT9PjlMX`). Engine ghép toàn bộ `clauses` của cả $N$ cảnh để gọi `eleven_v3` **1 lần duy nhất**. |
| `scenes[k].actions` | `string[]` | Mô tả hành động theo nhịp `00:00 - 00:03`, `00:03 - 00:07`, `00:07 - 00:10`. Ở cảnh $k \ge 2$, luôn chỉ đạo nhân vật tương tác với đạo cụ đã đặt sẵn trên bàn từ cảnh 1. |
| `scenes[k].visual_dialogue` | `string` (optional) | Lời thoại trung tính gửi riêng cho Gemini Omni để tạo khẩu hình mà không kích hoạt bộ lọc an toàn (`safety violations`) với chủ đề nhạy cảm. Nếu bỏ trống và bị chặn safety, `engine.py` tự động fallback. |
| `scenes[k].clauses` | `string[]` hoặc `{text, window}[]` | Danh sách câu thoại thật gửi tới ElevenLabs (`18–24 từ/cảnh` để tốc độ `1.0x–1.2x`). Tự động lưu `clause_bounds.json` trong `work_dir`. |
