Một cô gái hỏi AI: "Tối nay em nên mặc váy nào: đỏ hay đen?"

Người bạn bình thường chỉ mất 2 giây để chốt. Nhưng AI agent truyền thống thì mất tới… 30 giây xoay vòng:

- Bật radar xem độ ẩm không khí.
- Quét 150 tin nhắn phân tích gu bạn trai.
- Gọi API ngân hàng kiểm tra số dư thẻ phòng khi đổ rượu vang.
Đốt 2$ GPU chỉ để nhả ra câu trả lời: *"Nên mặc cả hai chiếc váy cùng lúc."*

---

Đây là căn bệnh kinh điển: **Nhồi 50 công cụ vào cùng một prompt**.  
Hậu quả là **ô nhiễm ngữ cảnh** (context pollution) và **ảo giác công cụ** (tool hallucination) — vừa chậm, vừa đắt, vừa ngáo.

Giải pháp chuẩn kỹ thuật là tách hệ thống thành **2 tầng kiến trúc**:

1. **Tầng Quyết Định (Decision Layer - Bản năng):**  
   Nhìn yêu cầu và chốt *cần công cụ nào* trong vài mili-giây.

2. **Tầng Thực Thi (Execution Layer - Đôi bàn tay):**  
   Chỉ nhận duy nhất công cụ đó, giải quyết bài toán với ngữ cảnh sạch tinh, rồi dừng lại.

---

Và "người gác cổng" hoàn hảo cho Tầng Quyết Định chính là **Jev** (từ TypeSafe AI).

Khác với LLM thông thường, Jev là mô hình **System One (tư duy phản xạ)** — giống như thấy đèn đỏ là đạp phanh, tức thì và dứt khoát.

Được đặt làm **Skill-Selection Hook**:

- Khi câu hỏi đến, Jev trả về các quyết định với độ tự tin cao nhất, bỏ qua 49 công cụ thừa (thời tiết, ngân hàng, SQL...).
- Trong đúng **180ms**, Jev chốt quyết định chuẩn xác: `Cần dùng skill: Phối đồ thời trang`.

LLM dựa vào đó để gọi chính xác kỹ năng và công cụ, trả lời trong 1 giây. Vừa nhanh, vừa cắt giảm 90% chi phí token, lại không bao giờ lo AI gọi nhầm công cụ nhạy cảm.

1. Jev: <https://typesafe.ai/manifesto>
2. Skill selection hooks: <https://github.com/nghuyenthevinh2000/social-content#skill-selection-router-jev-hook>
