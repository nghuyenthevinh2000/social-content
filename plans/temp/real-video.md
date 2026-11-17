# REAL — Vì sao video AI trông giả, và cách làm nó thật

<aside>
🎄

Mình dựng cả video leo núi kéo cây thông Noel bằng AI. Đây là toàn bộ checklist và prompt mình đã dùng. Lưu lại cho lần làm video AI tới.

</aside>

## Phần 1 — 8 dấu hiệu khiến video AI trông giả

Mỗi dấu hiệu đi kèm cách sửa. Câu trong ngoặc kép là câu mình ghi thẳng vào prompt.

| # | Dấu hiệu | Vì sao mắt nhận ra | Cách sửa |
| --- | --- | --- | --- |
| 1 | Da quá mịn, bóng như nhựa | Da thật luôn có lỗ chân lông, mồ hôi, vết nắng | "Real skin: visible pores, fine sweat at the temple, sun-flushed cheeks, dry lips." Ảnh đã ra da nhựa thì edit lại, đừng gen mới. |
| 2 | Ánh sáng không có nguồn | Giữa rừng mà mặt sáng đều như studio | Nói rõ nguồn sáng, hướng và bóng: "hard sun from the upper left, one side lit, the other in deep shadow". |
| 3 | Máy quay quá mượt | Không ai cầm máy mà lướt như drone | Tả hiệu ứng của máy: "handheld, the frame bounces and tilts, focus lands late". Đừng viết "người quay chạy theo", AI sẽ vẽ luôn người quay vào khung. |
| 4 | Không có trọng lượng | Bước chân không lún, gió thổi mà vạt áo đứng yên | Tả vật lý: "foot slips, gravel rolls toward the lens, dust bursts up, weight sinks into the loose stones, coat hem whips in the wind". |
| 5 | Mọi thứ quá sạch, quá cân | Thế giới thật bừa hơn thế nhiều | "mud on the coat hem, hair tangled, grass bent every way, framing off-centre and slightly tilted". |
| 6 | Người to bất thường so với bối cảnh | Model hay tự kéo người lên thành trung cảnh | Ghi người cao bao nhiêu phần khung: "his whole body is about one quarter of the frame height, smaller than the pine". |
| 7 | Nhân vật diễn với máy quay | Nhìn ống kính, cười vào máy là quảng cáo, không phải phim | "He never looks at the camera." Kết bằng hành động và khoảng cách, không bằng một nụ cười cận mặt. |
| 8 | Video câm, hoặc nhạc do AI tự chèn | Tai nhận ra trước cả mắt | Bật âm thanh gốc, chỉ giữ SFX: "natural sound effects only — wind, footsteps, cloth. No music, no voice." Nhạc thêm lúc dựng. |

## Phần 2 — Thứ giả nhất: câu chuyện

Sửa hết 8 điều trên, video vẫn có thể giả. Người xem tin câu chuyện, không tin pixel. Trước khi gen bất cứ thứ gì, trả lời 4 câu:

1. Nhân vật muốn gì?
2. Vì sao phải làm điều đó ngay bây giờ?
3. Điều gì cản đường họ?
4. Cái kết có trả lời được câu "để làm gì?" không?

> Trong video: một người leo núi cả ngày, căng thẳng như đang tìm thứ gì đó. Để làm gì? Để mang cây thông Noel về nhà.
>

## Phần 3 — Quy trình 6 bước mình dùng

1. **Kịch bản và storyboard trước.** Chưa có câu chuyện thì chưa gen.
2. **Character sheet.** 4 ảnh mặt cắt ở cổ, cộng trang phục riêng cho từng video (đã tách nền). Mỗi sheet chỉ có một khuôn mặt.
3. **Bối cảnh trống.** Không có người, góc 3/4, tiền cảnh thoáng, có 2–3 điểm neo cố định (ví dụ: cây thông bên trái, đỉnh tuyết ở giữa).
4. **Frame storyboard** (Seedream 5.0 Pro). Ref theo thứ tự: art ref, bối cảnh, character sheet. Luôn ghi tỉ lệ người trong khung.
5. **Video** (Seedance 2.5 Omni). Ref gồm character sheet, bối cảnh trống và frame đã duyệt. Không đưa ảnh ref có người lạ vào, AI sẽ copy người đó. Gen đúng số giây cần dùng, chạy nháp 480p trước, duyệt xong mới lên 1080p.
6. **Dựng.** Cắt theo giọng đọc. Kiểm điểm cắt bên trong clip AI, dư 1 frame của shot khác cũng thành nháy. Thêm SFX.

## Phần 4 — Prompt mẫu (copy và thay chỗ trong ngoặc)

```
[Ref] image 1 = character sheet (face photos = identity only; right half = clothing). image 2 = empty location. image 3 = approved frame: copy its composition and the man's size in frame.
[Shot] <shot size>, <camera position>. He <action in progress>. He never looks at the camera.
[Scale] His whole body is about <one quarter> of the frame height; the landscape keeps its real size.
[Skin] Real skin: visible pores, a little sweat, sun-flushed cheeks.
[Light] <light source + direction>, one side lit, the other in shadow.
[Camera] Handheld, slight shake, focus breathes. <lens>.
[Physics] <weight, wind, dust, cloth movement>.
[Mess] Mud, tangled hair, grass bent every way, off-centre framing.
[Sound] Natural sound effects only — <wind, steps, cloth>. No music, no voice.
No text, no logos, no subtitles.
```

## Checklist trước khi xuất

- [ ]  Da có texture
- [ ]  Ánh sáng có nguồn, có bóng
- [ ]  Máy quay như có người cầm
- [ ]  Vật lý có trọng lượng
- [ ]  Khung hình có chút bừa
- [ ]  Tỉ lệ người đúng với bối cảnh
- [ ]  Không ai nhìn vào ống kính
- [ ]  Có SFX, không nhạc AI
- [ ]  Câu chuyện trả lời được "để làm gì?"
