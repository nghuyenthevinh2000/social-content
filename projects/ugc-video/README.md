# UGC Video Project Workspace (`projects/ugc-video`)

```text
Reference Reel URL ──> engine.py --analyze-reel ──> configs/<slug>.json ──> engine.py <config> ──> renders/<slug>/*.mp4
```

| Thành phần | Đường dẫn chuẩn (Relative to repo root) | Vai trò & Cách chạy |
|---|---|---|
| **Engine tạo video tổng** | [`projects/ugc-video/scripts/new_system/engine.py`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/projects/ugc-video/scripts/new_system/engine.py) | Phân tích reel mẫu (`--analyze-reel`), sinh video đa cảnh `gemini-omni-1.1-flash-preview`, ghép nối `<FIRST_FRAME>`, đồng bộ giọng `eleven_v3` và chuẩn hóa BT.709. |
| **Engine hậu kỳ hiệu ứng** | [`projects/ugc-video/scripts/new_system/effect_editor.py`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/projects/ugc-video/scripts/new_system/effect_editor.py) | Đóng phụ đề karaoke từng từ, hook banner, punch zoom và nhạc nền/SFX. |
| **Thư mục cấu hình JSON** | [`projects/ugc-video/scripts/new_system/configs/`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/projects/ugc-video/scripts/new_system/configs) | Chứa các file cấu hình kịch bản (`ngat_ngoai_tinh_psychology.json`, `post_4_wedding_paper.json`, `post_5_red_velvet_envelope.json`). |
| **Creator `"ngat"`** | `assets/images/ngat/{face,clothes}.jpg` + [`voice_meta.json`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/projects/ugc-video/assets/audio/ngat/voice_meta.json) | Bùi Thị Ngát — Voice ID `a95xm5oG7Gvnxoyv5jeJ` (tự động nạp khi khai báo `"creator": "ngat"`). |
| **Creator `"diep"`** | `assets/images/diep/{face,clothes}.jpg` + [`voice_meta.json`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/projects/ugc-video/assets/audio/diep/voice_meta.json) | Diệp (Xưởng in) — Voice ID `FXJGVNPXC71BGT9PjlMX` (tự động nạp khi khai báo `"creator": "diep"`). |

```bash
# 1. Phân tích & chép lời Reel mẫu để lấy kịch bản 2 cảnh (18-24 từ/cảnh)
python3 projects/ugc-video/scripts/new_system/engine.py --analyze-reel "<REEL_URL>"

# 2. Sinh video hoàn chỉnh từ file cấu hình JSON (bắt buộc chạy ngay trong Turn 1)
python3 projects/ugc-video/scripts/new_system/engine.py projects/ugc-video/scripts/new_system/configs/<slug>.json
```
