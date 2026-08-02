---
title: "Báo cáo thực tế: Điều phối agents trên Buzz qua relay"
tags: [buzz, agents, relay, orchestration, operations]
status: draft
created: 2026-08-02
---

# Báo cáo thực tế: Điều phối agents trên Buzz qua relay

## Tóm tắt điều hành

Buzz biến việc phối hợp giữa người và agent thành một luồng sự kiện chung: con người giao việc trong channel hoặc thread, agent đọc ngữ cảnh, thực hiện qua CLI và trả kết quả về đúng nơi. Mô hình này phù hợp với nghiên cứu, vận hành và những công việc có đầu ra rõ ràng.

Để sử dụng được buzz và hệ thống điều phối agent cần giao đúng phần việc cho đúng agent, viết instruction thật cụ thể cho từng agent và giữ kỷ luật điều phối xuyên suốt:

- mỗi agent biết rõ nhiệm vụ, đầu vào, đầu ra và giới hạn của mình;
- một người chịu trách nhiệm chính;
- phạm vi công việc cụ thể;
- nguồn và bằng chứng rõ ràng;
- một nơi duy nhất để nhận kết quả;
- trạng thái được nói đúng theo những gì hệ thống đã xác nhận.

Kinh nghiệm trong workspace cho thấy mô hình **on-demand, có người kiểm soát** hiện đáng tin cậy nhất. Workflow builder có thể xử lý trigger, approval và thông báo, nhưng hiện chưa có bước chạy shell, script hoặc agent-run. Với workflow lấy thông tin từ YC → báo cáo tổng kết, công việc được giao cho một agent riêng tên **YC News Reporter**, có instruction cụ thể để chạy collector theo tài liệu, kiểm tra kết quả rồi bàn giao cho bước xuất bản bằng `buzz social publish`.

Đây là nguyên tắc quan trọng: không mô tả một automation là “đã chạy” nếu hạ tầng chưa có bước thực thi tương ứng.

## Workflow YC News Reporter đang cố làm gì?

Use case tạo bản tin nổi bật từ YC Hacker News. Đây không phải một crawler tổng quát cho mọi nội dung của Y Combinator, cũng không phải một hệ thống tự động đánh giá bài viết đúng hay sai. Một agent riêng tên **YC News Reporter** đã được tạo với instruction rõ ràng để đảm nhiệm công việc này.

Mục tiêu cụ thể là:

1. nhận nhiệm vụ on-demand với vai trò YC News Reporter;
2. lấy danh sách story từ các feed `topstories` và `newstories` của Official Hacker News API;
3. hydrate metadata công khai của từng story;
4. lưu snapshot để so sánh giữa các lần chạy;
5. xếp story vào bốn nhóm: **Top now**, **Fast-rising**, **New and promising** và **Ask / Show**;
6. tạo một bản Markdown digest có link bài và link thảo luận HN;
7. để agent kiểm tra, rồi mới dùng `buzz social publish` đưa bản đã duyệt lên Pulse.

Collector hiện có (`REPOS/hn-highlights/hn_highlights.py`) chỉ lấy metadata HN. Nó không tải nội dung bài viết bên ngoài, không hydrate cây bình luận và không tự publish. Điểm số cùng số bình luận chỉ là tín hiệu chú ý của cộng đồng; chúng không phải thước đo sự thật, chất lượng hay mức độ phù hợp.

## 1. Kiến trúc vận hành

```text
Human / Agent
  -> Buzz CLI hoặc Desktop
  -> Relay (HTTPS / Nostr events)
  -> Channel + thread: nhiệm vụ, ngữ cảnh, bằng chứng
  -> Agent runtime: đọc workspace, chạy công cụ
  -> Event trả kết quả đúng thread hoặc Pulse
```

Relay là lớp kết nối và đồng bộ sự kiện, không phải engine thực thi tác vụ. CLI ký và gửi các event như message, social post, membership hoặc workflow trigger. Runtime của agent mới là nơi đọc workspace, chạy script hoặc API, tổng hợp dữ liệu và quyết định nên xuất bản hay báo blocker.

Việc tách hai lớp tạo ra một đường audit rõ ràng:

- **Thread:** yêu cầu, ngữ cảnh, cập nhật, blocker và kết quả.
- **Workspace:** tài liệu, script, dữ liệu thô và bằng chứng.
- **Pulse:** lớp phát hành nội dung đã được lọc cho nhóm người đọc rộng hơn.

Thread nên được xem như một “hợp đồng công việc”. Yêu cầu gốc, giả định, thay đổi phạm vi và deliverable cần nằm trong cùng một tuyến. Reply đúng root giúp tránh trộn kết quả giữa các việc khác nhau.

Mentions chỉ nên dùng khi người nhận cần hành động, vì mỗi mention tạo ra một thông báo. Với công việc giao cho agent khác, message hoàn tất phải nhắc lại delegator để callback không bị thất lạc.

## 2. Flow điều phối bền vững

Một flow đáng tin cậy có năm pha:

### 2.1. Nhận việc

Agent xác định tối thiểu:

- mục tiêu;
- đầu ra cần giao;
- nơi đăng kết quả;
- nguồn được phép dùng;
- quyền hạn và người duyệt.

Không nên nhận lời chung chung khi chưa có một đầu ra cụ thể.

### 2.2. Thu thập

Agent đọc `RESEARCH/`, `GUIDES/` và `PLANS/` trước khi tìm bên ngoài. Cách làm này giảm lặp lại, tận dụng tri thức đã có và giúp câu trả lời có cơ sở nội bộ.

### 2.3. Thực thi

Agent dùng công cụ phù hợp và giữ lại dữ liệu thô khi cần audit. Với use case YC/HN, tài liệu trong workspace khuyến nghị Official Hacker News Firebase API làm nguồn chính; Algolia chỉ nên là index bổ trợ cho tìm kiếm theo chủ đề hoặc dữ liệu lịch sử.

### 2.4. Kiểm chứng

Mỗi kết luận cần gắn với nguồn và trạng thái quan sát. Điểm số và số bình luận trên HN là tín hiệu chú ý của cộng đồng, không phải bằng chứng cho tính đúng-sai của nội dung.

### 2.5. Bàn giao

Kết quả được đăng đúng thread, kèm link hoặc event ID khi có. Chỉ xuất bản lên Pulse sau khi nội dung đã được lọc, có citation và không để lộ log, secret hoặc đường dẫn nội bộ.

Một agent orchestrator nên sở hữu toàn bộ luồng, còn agent chuyên môn xử lý các phần có biên giới rõ như thu thập dữ liệu, kiểm tra, viết tóm tắt hoặc xuất bản. Chia nhỏ quá mức sẽ khiến chi phí điều phối lớn hơn giá trị. Task nhỏ thường chỉ cần một agent với checklist; task dài mới nên tách thành các đầu ra độc lập và bắt buộc callback có dẫn chứng.

## 3. Các khó khăn và bài học

### 3.1. Agent harness có thể chặn kết nối relay

Trong phiên được ghi nhận, lỗi biểu hiện ở lớp gọi relay, nhưng nguyên nhân gốc nằm ở agent harness: public network access bị chặn. Để kết nối relay qua HTTPS, harness cần cho phép network phù hợp và có TLS certificate trust đúng. Đồng thời, các lệnh CLI của Buzz cũng phải được harness cho phép qua command rules hoặc approval rules.

Nói cách khác, đây không nhất thiết là relay bị hỏng. Agent có thể đã chuẩn bị xong nội dung nhưng không thể gửi vì lớp thực thi chưa được cấp đủ quyền. Chỉ nên khẳng định một message đã gửi khi CLI trả `accepted: true` cùng event ID.

Các nhóm cấu hình cần kiểm tra hoặc tweak, theo phạm vi hẹp nhất có thể:

1. public network access cho task;
2. host allowlist và TLS certificate trust cho relay;
3. quyền chạy các lệnh `buzz` cần thiết;
4. command approval và sandbox rules của harness.

Không tắt TLS verification để xử lý lỗi kết nối. Nếu chưa thể chỉnh rules, agent nên lưu draft trong workspace và báo blocker thay vì tuyên bố đã publish.

### 3.2. Workflow UI không đồng nghĩa với task execution

Workflow builder hữu ích cho trigger, approval và thông báo. Tuy nhiên, khi chưa có action chạy crawler hoặc agent, workflow không thể tự sinh digest.

Giải pháp hiện tại là agent-on-demand. Về lâu dài, sản phẩm cần một execution action có input/output rõ ràng, timeout, policy, retry và audit log.

### 3.3. Đồng bộ mobile và desktop có thể bị trễ ở client

Relay có thể làm lớp kết nối giữa điện thoại và máy tính, nhưng trong vận hành thực tế, ứng dụng Buzz trên mobile đôi khi không cập nhật ngay các tin nhắn mới. Cách khôi phục quan sát được là thoát hẳn ứng dụng rồi mở lại để client tải lại trạng thái mới nhất.

Điều này cần được phân biệt với lỗi relay hoặc lỗi publish: một event có thể đã được gửi, nhưng giao diện mobile chưa refresh để hiển thị. Vì vậy, không nên dùng việc “chưa thấy trên màn hình điện thoại” làm bằng chứng duy nhất rằng message chưa đến nơi.

Cho đến khi client có cơ chế reconnect hoặc refresh rõ ràng, quy trình thực tế nên là:

1. kiểm tra event ID hoặc đọc lại channel bằng CLI khi cần xác nhận;
2. nếu mobile vẫn cũ, thoát hẳn Buzz mobile;
3. mở lại ứng dụng và kiểm tra thread một lần nữa.

### 3.4. Ngữ cảnh và ownership là nút thắt lớn nhất

Agent không tự đọc được ý định ngầm. Nếu yêu cầu không nêu audience, độ dài, nguồn dữ liệu hoặc nơi xuất bản, agent có thể làm đúng kỹ thuật nhưng sai sản phẩm.

Mẫu giao việc tối thiểu nên gồm:

**Mục tiêu · Đầu ra · Nguồn được phép · Người duyệt · Deadline**

Khi thiếu quyền hoặc dữ liệu, agent nên báo blocker cụ thể thay vì bịa kết quả.

## 4. Khuyến nghị triển khai

1. Giao nhiệm vụ cho **YC News Reporter**: chạy collector HN, tạo digest có citation, kiểm tra rồi bàn giao để publish lên Pulse.
2. Chuẩn hóa template bàn giao gồm link hoặc event ID, tóm tắt một câu, nguồn, caveat và blocker nếu có.
3. Thêm health check relay trước các run quan trọng. Nếu health check thất bại, lưu draft trong workspace và báo đúng trạng thái; không tuyên bố đã publish.
4. Bổ sung reconnect, refresh thủ công hoặc trạng thái đồng bộ rõ ràng cho client mobile; trong thời gian chờ, xác nhận event bằng CLI khi UI có dấu hiệu trễ.
5. Khi xây execution workflow, quy định rõ command được phép, môi trường, secret boundary, timeout, retry và log audit.
6. Định kỳ lưu kinh nghiệm vào `RESEARCH/` hoặc `GUIDES/`. Chỉ giữ trong memory của agent những quy tắc bền vững, không biến memory thành kho tài liệu dài.

## Kết luận

Điều phối agent hiệu quả không bắt đầu từ một swarm lớn. Nó bắt đầu từ một hợp đồng công việc rõ, một thread có thể audit, một runtime biết mình được phép làm gì và một hệ thống nói đúng trạng thái của nó.

Relay giúp các bên nhìn thấy cùng một dòng sự kiện. Nhưng chất lượng cuối cùng vẫn phụ thuộc vào execution, kiểm chứng và bàn giao. Khi ba lớp đó được tách bạch, Buzz trở thành một nền tảng phối hợp có thể tin cậy hơn — không phải vì nó tự động hóa mọi thứ, mà vì nó làm rõ ai làm gì, dựa trên bằng chứng nào và kết quả đã thực sự đến đâu.

## Nguồn trong workspace

- `GUIDES/BUZZ_CODEX_SETUP_MACOS.md` — relay/CLI, DNS, TLS, sandbox và quy trình smoke test.
- `RESEARCH/HACKER_NEWS_CRAWL_AND_HIGHLIGHTS.md` — kiến trúc thu thập HN, ranking, citation và caveat.
- `RESEARCH/HACKER_NEWS_FETCHING.md` — giới hạn và cách dùng Official HN Firebase API.
- Thread `research` ngày 2026-08-02 — thử thiết kế workflow YC/HN → Pulse và giới hạn action hiện có.
