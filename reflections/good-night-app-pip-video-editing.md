# Reflection: Trải Nghiệm Biên Tập Video-in-Video Bằng Code (Programmatic PiP Pipeline)

> **Dự án**: Good Night App Demo (`topics/good-night-app/`)  
> **Tài nguyên đầu vào**: `app.mov` (bản quay màn hình ứng dụng) + `talk.MOV` (video người nói quay từ iPhone)  
> **Sản phẩm đầu ra**: `output.mp4` (video composite hoàn chỉnh) + `make_pip.py` (công cụ tự động hóa)  
> **Thời điểm thực hiện**: 2026-09-08  

---

## 1. Bối cảnh & Mục tiêu

Mục tiêu của bài toán là tạo ra một video demo sản phẩm phong cách presenter (tương tự Loom / TikTok / Reels tech demo) hoàn toàn bằng code, không cần mở các phần mềm dựng video thủ công (CapCut, Premiere, DaVinci):

* **Video nền (`app.mov`)**: Màn hình dọc (880 $\times$ 1754, 60 fps, ~14.5s) quay giao diện app đếm cừu ngủ tối giản (Good Night).
* **Video thuyết minh (`talk.MOV`)**: Video selfie từ iPhone 16e (HEVC 10-bit, 30 fps), ghi hình khuôn mặt người sáng lập đang chia sẻ.
* **Yêu cầu kỹ thuật**:
  1. Cắt khuôn mặt người nói thành hình tròn (circular crop).
  2. Viền trắng sắc nét (crisp stroke border) để tách biệt với nền tối của ứng dụng.
  3. Đặt ở góc dưới bên phải (Bottom Right), không che các chi tiết UI cốt lõi.
  4. Hòa trộn âm thanh: giọng nói rõ ràng nổi bật trên nền nhạc kalimba êm dịu của app.
  5. Xử lý linh hoạt khi người dùng thay đổi độ dài video thuyết minh.

---

## 2. Các Thử Thách Kỹ Thuật & Giải Pháp Thực Chiến

### 2.1. Thử Thách 1: Metadata xoay của iPhone (`Display Matrix`) & Không gian màu HEVC 10-bit

* **Hiện tượng**: File `talk.MOV` xuất ra từ iPhone báo kích thước gốc trong stream là `1920x1080` (ngang) kèm side data `Display Matrix: rotation of -90.00 degrees` và định dạng màu `yuv420p10le` (HDR/Dolby Vision).
* **Bài học**: Nếu chỉ đọc width/height thuần qua regex hoặc parser ngây thơ, code sẽ tính toán tọa độ sai lệch 90 độ. 
* **Cách xử lý**: Dựa trên cơ chế `autorotate` mặc định của FFmpeg để giải mã đúng tỉ lệ khung hình thực tế là `1080x1920` (dọc), từ đó thực hiện các bước crop chuẩn xác.

---

### 2.2. Thử Thách 2: Cắt Mặt Chính Xác Tránh "Cắt Mất Cằm" (Visual Inspection Loop)

* **Hiện tượng**: Nếu crop hình vuông tâm tuyệt đối `(in_w-900)/2` và `(in_h-900)/2`, khuôn mặt sẽ bị lệch hoặc bị đứt ngang trán/cằm.
* **Quy trình giải quyết**: 
  Thay vì đoán mò pixel, hệ thống đã thực hiện vòng lặp **trích xuất khung hình mẫu $\rightarrow$ kiểm tra thị giác (Visual Inspection)**:
  * Thử nghiệm 1: `Y=220` $\rightarrow$ Quá cao, mất miệng và cằm.
  * Thử nghiệm 2: `Y=480` $\rightarrow$ Đã thấy cằm nhưng đường cong tròn phía dưới vẫn cấn râu.
  * Thử nghiệm 3 (Chuẩn): `crop=1000:1000:40:455` $\rightarrow$ Đầu, tóc, kính mắt và cổ áo nằm cân đối tuyệt đối ở trung tâm hình vuông trước khi bo tròn.

---

### 2.3. Thử Thách 3: Kiến Trúc 3 Lớp (Sandwich Architecture) — Tại Sao Cần Cả `mask.png` và `ring.png`?

Một câu hỏi rất hay gặp khi làm video composite: *Tại sao không gộp chung vào 1 file ảnh duy nhất?*

Thực tế, quá trình compositing video đòi hỏi tách rời **tính trong suốt (transparency)** và **vẽ viền (decorating)** theo thứ tự 3 tầng:

```
[Layer 3 - Top]       ring.png            (Vẽ viền trắng sắc nét)
                            ▲
[Layer 2 - Middle]    talk.MOV + mask.png (Đục lỗ video vuông thành hình tròn)
                            ▲
[Layer 1 - Bottom]    app.mov             (Bản quay màn hình app)
```

1. **`mask.png` (Grayscale Alpha Mask)**:
   * Bản chất là ảnh đen-trắng (trắng = giữ lại pixel video, đen = loại bỏ 100%).
   * Dùng bộ lọc `alphamerge` của FFmpeg để biến video chữ nhật thành video có kênh alpha hình tròn.
   * **Mask chỉ kiểm soát độ đục/trong suốt, không thể "tô màu" viền trắng**.
2. **`ring.png` (RGBA Outline)**:
   * Bản chất là ảnh rỗng trong suốt, chỉ có vòng tròn trắng dày 6px được vẽ khử răng cưa (supersampling 4x bằng PIL Lanczos).
   * Phủ lên trên cùng để che các mép pixel khử răng cưa còn sót lại của video nén, tạo cảm giác tinh tế như một UI widget cao cấp.
3. **Hiệu năng**:
   * Việc dùng 2 ảnh PNG tĩnh tạo sẵn bằng Python PIL giúp FFmpeg tận dụng bộ giải mã phần cứng và thuật toán Blit Alpha nhanh gấp **4 lần thời gian thực (render 15s chỉ mất ~3.8s)**, thay vì bắt FFmpeg tính công thức toán `geq` từng pixel trên từng frame.

---

### 2.4. Thử Thách 4: Bất Đồng Bộ Thời Lượng (Async Lifecycles & Dynamic Fade-Out)

Khi người dùng ghi âm lại lời thoại mới (`talk.MOV` rút gọn từ 14.5s xuống còn **8.17s**), trong khi `app.mov` dài **14.48s**:

* **Nguy cơ**: 
  * Nếu dùng `shortest=1` thuần túy: Video bị ngắt cụt ở giây thứ 8, làm mất đoạn demo đổi sang tiền đô và đếm tiền phía sau.
  * Nếu để mặc định: Khuôn mặt người nói sẽ **bị đông cứng (freeze frame)** từ giây 8.2 đến giây 14.5 như một cuộc gọi video bị lag.
* **Giải pháp đột phá**:
  * Tự động đo thời lượng qua `ffprobe` trong code script.
  * Khi phát hiện `talk_dur < main_dur`: Kích hoạt bộ lọc `fade=t=out:st=7.66:d=0.5:alpha=1` cho cả vòng tròn khuôn mặt lẫn viền trắng.
  * Kèm điều kiện `enable='between(t,0,8.17)'`: Đến đúng giây thứ 8.2, vòng tròn biến mất hoàn toàn một cách mượt mà, nhường toàn bộ không gian cho phần demo ứng dụng tiếp diễn trọn vẹn.

---

### 2.5. Thử Thách 5: Hòa Âm Thông Minh (Intelligent Audio Blending)

* Đo mức âm lượng (`volumedetect`):
  * `talk.MOV`: Âm lượng trung bình -20.8 dB (tiếng nói rõ ràng).
  * `app.mov`: Âm lượng trung bình -38.2 dB (tiếng hiệu ứng chuông ngân nhẹ).
* Chiến lược mix qua `amix`:
  * Tăng nhẹ giọng nói (`volume=1.2`) để người nghe tập trung vào thông điệp.
  * Giữ tiếng chuông nhẹ nhàng ở mức vừa phải (`volume=0.5`), tự động duy trì xuyên suốt kể cả sau khi phần thuyết minh kết thúc.

---

## 3. Tổng Hợp Pipeline Tự Động Hóa (`make_pip.py`)

Toàn bộ quy trình trên đã được đúc kết thành CLI script độc lập:

```bash
# Lệnh chạy mặc định
python3 make_pip.py

# Tùy biến vị trí và kích thước
python3 make_pip.py --position bottom_right --size 360
python3 make_pip.py --position top_right --size 320
```

Các tọa độ được tính toán tự động:
* `bottom_right`: `x=W-w-margin`, `y=H-h-margin`
* `bottom_center`: `x=(W-w)/2`, `y=H-h-(margin*3)` (tránh chạm bottom bar)
* `top_right`: `x=W-w-margin`, `y=margin*2`
* `top_left`: `x=margin`, `y=margin*2`
* `middle_right`: `x=W-w-margin`, `y=(H-h)/2`

---

## 4. Bài Học Rút Ra Cho Việc Ứng Dụng AI Biên Tập Video (Key Takeaways)

1. **AI biên tập video cần "đôi mắt" kiểm chứng (Visual Feedback Loop)**:
   * Nếu AI chỉ viết code mà không tự trích xuất ảnh frame để xem lại kết quả (`view_file`), tỉ lệ sai sót về bố cục (lệch mặt, che nút bấm quan trọng) là cực kỳ cao.
   * Việc trích xuất frame tại $t = 1.5s$, $4.0s$, $9.5s$ giúp kiểm định được cả lúc overlay hiển thị, lúc chuyển động, và lúc fade-out.
2. **Đừng để code phụ thuộc vào thời lượng cố định**:
   * Người sáng tạo nội dung liên tục quay lại thoại (retake). Pipeline tự động phải luôn dùng probe động để tự co giãn thời lượng và hiệu ứng fade thay vì gán cứng con số giây.
3. **Phối hợp công cụ đúng thế mạnh**:
   * **Python PIL**: Tạo đồ họa tĩnh (mask, ring, icon) với độ phân giải siêu nét (antialiased supersampling).
   * **FFmpeg**: Đảm nhận nhiệm vụ nén, encode H.264/AAC, stream blending và căn chỉnh phần cứng với tốc độ tối đa.
   * **CLI Wrapper**: Giúp AI hoặc con người chỉ cần 1 lệnh duy nhất là hoàn thành toàn bộ công đoạn sản xuất.
