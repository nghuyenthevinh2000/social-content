# Product Canvas: Chụp hàng thật → dựng 3D → sinh video quảng cáo

**Ngày:** 18/10/2026 · **Trạng thái:** Đề xuất để kiểm chứng, chưa phải năng lực sản phẩm đã triển khai.  
**Tên làm việc:** Physical Product-to-Video — chưa chốt thương hiệu.  
**Khách hàng:** Người bán hàng vật lý mới làm nội dung/quảng cáo, không phải chuyên gia 3D hoặc media buyer.

> **Chụp sản phẩm thật bằng điện thoại một lần, tạo nhiều video bán hàng từ cùng một bản 3D đã duyệt — không cần biết dựng phim.**

**Quy ước số liệu:** **[Nguồn]** = thông tin công khai của nhà cung cấp, không phải kiểm thử độc lập; **[Mục tiêu]** = ngưỡng đề xuất; **[Giả định]** = đầu vào tính toán cần đo lại. Không dùng số liệu của đối thủ làm lời hứa cho sản phẩm mình.

## 1. Canvas tổng quan

| Thành phần | Quyết định đề xuất |
| :--- | :--- |
| Vấn đề | Chủ shop có hàng thật nhưng thiếu video mới; không biết quay, dựng, viết nội dung; ảnh/video AI có thể làm sai nhãn, hình dáng, màu và chi tiết hàng |
| Khách hàng đầu tiên | Shop nhỏ bán phụ kiện bàn làm việc/đồ gia dụng nhỏ, có sẵn hàng để chụp; chủ shop trực tiếp làm nội dung; cần video lặp lại cho cùng SKU |
| Phạm vi thử nghiệm ICP | **[Giả định]** Shop có 5–50 SKU đang bán, muốn 4–12 video/tháng; không xem đây là số liệu thị trường |
| Job-to-be-done | “Tôi muốn biến món hàng trước mặt thành video có thể đăng bán hôm nay, mà không phải học quay dựng hoặc lo AI đổi sản phẩm.” |
| Kết quả khách hàng mua | Video đã duyệt để đăng bán/quảng cáo, không phải một file 3D để tự xử lý |
| Cơ chế | Chụp đa góc → kiểm tra chất lượng → tái dựng 3D → duyệt sản phẩm → render chuyển động → ghép thông điệp/giá/CTA → xuất video |
| Lợi ích cốt lõi | Tái sử dụng cùng một SKU qua nhiều góc quay, thông điệp và chiến dịch, giảm nhu cầu chụp lại |
| Khác biệt cần chứng minh | Giữ đúng sản phẩm + thao tác ít + bộ video bán hàng hoàn chỉnh + chi phí minh bạch, không chỉ video xoay 360° |
| Đầu ra MVP | **[Mục tiêu]** Một SKU đã duyệt → 3 video khác thông điệp, mỗi video 10–15 giây, MP4 1080×1920, có bản không nhạc |
| North Star | Số **SKU thật** tạo được ít nhất một video **được chủ shop duyệt và thực sự đăng** trong tuần |
| Không làm ở MVP | Tự chạy tiền quảng cáo, tự tăng ngân sách, dashboard ROAS, avatar, AR/try-on, chỉnh mesh thủ công, mô hình 3D nền tảng tự phát triển |
| Vai trò của loop cũ | Sau khi chứng minh sản xuất video có giá trị: gắn video/SKU với kết quả để gợi ý vòng nội dung tiếp theo; không đưa toàn bộ Ads Manager vào MVP |

## 2. Chọn loại hàng: bắt đầu hẹp để đạt chất lượng

| Nhóm hàng | Quyết định | Lý do / rủi ro |
| :--- | :--- | :--- |
| Phụ kiện bàn làm việc, hộp đựng, đồ decor nhỏ có bề mặt mờ và chi tiết nhìn thấy rõ | **Ưu tiên pilot** | Vật thể cứng, dễ đặt cố định, dễ tạo cảnh trưng bày; vẫn cần đủ texture để tái dựng |
| Bao bì/hộp giấy, chai nhựa đục có nhãn | **Nhóm thử thách fidelity riêng** | Phù hợp video bán hàng nhưng nhãn, chữ nhỏ và bề mặt phẳng dễ lộ lỗi; phải kiểm tra trước khi nhận đại trà |
| Giày, túi | **Mở rộng sau** | Có đối thủ chuyên sâu như Fibbl; vật liệu, quai, đế và hình dạng mềm cần kiểm soát |
| Thủy tinh, nhựa trong, trang sức, kim loại bóng gương | **Tạm loại khỏi MVP** | Phản xạ/truyền sáng làm capture và tái dựng khó; không hứa “chụp gì cũng được” |
| Quần áo mềm, tóc/lông, vật thể chuyển động | **Tạm loại** | Hình dạng thay đổi giữa các góc; cần pipeline và bộ dữ liệu đánh giá khác |
| Sản phẩm cần minh họa công dụng bằng tương tác người thật | **Dùng footage thật bổ sung** | Bản 3D tĩnh không chứng minh độ bền, công dụng, độ vừa vặn hoặc trải nghiệm sử dụng |

**Chưa chốt địa lý:** Đề xuất pilot với nhóm shop nói tiếng Việt mà đội có thể tiếp cận trực tiếp. Không suy ra quy mô thị trường hay giá chấp nhận trả từ lựa chọn ngôn ngữ này.

## 3. Trải nghiệm người mới: 5 bước nhìn thấy, không lộ công cụ 3D

| Bước | Người bán làm gì | Hệ thống làm gì | Số đo đề xuất |
| :--- | :--- | :--- | :--- |
| 1. Chọn món hàng | Nhập tên, giá, tối đa 3 điểm bán hàng có thật | Kiểm tra loại hàng được hỗ trợ; giải thích điều kiện chụp | **[Mục tiêu]** ≤2 phút nhập liệu |
| 2. Chụp ngay trong app | Đi theo hướng dẫn quanh sản phẩm | Chỉ vùng còn thiếu; cảnh báo rung, mờ, thiếu sáng, vật thể dịch chuyển | **[Giả định thử nghiệm]** 30–80 ảnh hoặc chuỗi ảnh trích từ video; **[Mục tiêu]** ≤5 phút thao tác capture |
| 3. Duyệt hàng số | Xoay xem preview, so với ảnh gốc; xác nhận hình/nhãn/màu/chi tiết | Tái dựng; kiểm tra vùng thiếu; chỉ cho dùng góc đã đủ dữ liệu | **[Mục tiêu]** ≥80% capture đạt sau tối đa 1 lần chụp lại |
| 4. Chọn mục đích | Chọn “giới thiệu”, “nêu điểm nổi bật”, hoặc “ưu đãi”; duyệt chữ | Đề xuất 3 kịch bản, cảnh quay, overlay, CTA; render preview rẻ trước | **[Mục tiêu]** Không cần viết prompt hoặc dùng timeline |
| 5. Nhận và đăng video | Duyệt, tải, chia sẻ; xác nhận đã đăng | Render final, lưu preset và asset theo SKU để làm vòng sau | **[Mục tiêu]** ≥70% người bắt đầu hoàn tất được một bộ video không cần người vận hành can thiệp |

**Thời gian không nhập nhằng:** Tách **thời gian người dùng thao tác**, **thời gian máy xử lý** và **tổng thời gian từ capture đến video**. Mục tiêu ban đầu: thao tác ≤10 phút; P50 tổng thời gian ≤30 phút và P90 ≤60 phút trên loại hàng được hỗ trợ. Đây là mục tiêu pilot, chưa phải cam kết bán hàng.

**Nhánh thất bại:** Nếu scan không đủ dữ liệu, yêu cầu chụp lại vùng thiếu hoặc cho dùng ảnh thật để làm video 2D. Gắn nhãn rõ “video từ ảnh”; không gọi đó là model 3D thành công. Báo riêng tỷ lệ thành công 3D và tỷ lệ hoàn thành nhờ fallback.

## 4. Từ model 3D đến video bán hàng — không chỉ xoay sản phẩm

| Lớp | Nội dung MVP | Ranh giới chất lượng |
| :--- | :--- | :--- |
| Capture | Ảnh đa góc của **chính SKU**, thêm ảnh nhãn chính diện và kích thước nếu có | Một ảnh không cung cấp mặt sau; không tự nhận là bản sao chính xác khi phải đoán |
| Asset 3D | Ưu tiên mesh có texture khi cần camera/light điều khiển ổn định; đánh giá Gaussian splat như nhánh khác | Splat không mặc định có khả năng relight, sửa hình học hoặc hoạt động như mesh; benchmark riêng |
| Kiểm duyệt | Preview đối chiếu ảnh gốc; xác nhận logo, chữ, màu, hình và số chi tiết | Không hứa “100% giống thật”; khóa xuất nếu có lỗi nghiêm trọng |
| Render sản phẩm | Góc hero, quay một phần/xoay, zoom chi tiết, cắt cận | Ưu tiên render từ asset đã duyệt; không cho generative video tự vẽ lại foreground ở MVP |
| Bối cảnh | Preset studio/lifestyle đơn giản; ánh sáng, bóng và bố cục phù hợp | Kiểm tra mép ghép, che khuất, tỷ lệ; không đặt cảnh làm hiểu sai kích thước/công dụng |
| Kịch bản | 3 hướng: thông tin sản phẩm, chi tiết nổi bật, ưu đãi đã được người bán xác nhận | Không tự bịa chứng nhận, hiệu quả sức khỏe, đánh giá, giảm giá hoặc khan hiếm |
| Hậu kỳ | Hook chữ → bằng chứng thị giác → CTA; caption, giá, logo; voice là tùy chọn | Giữ nhãn không bị overlay che; nhạc/font/voice có quyền dùng thương mại |
| Gói xuất | 3 creative khác nhau × 1 tỷ lệ chính 9:16; thêm 1:1/16:9 sau | Resize cùng một video không được tính là 3 creative khác nhau |

**MVP tự động và pilot concierge phải phân biệt:** Có thể dùng người hỗ trợ kiểm duyệt/cleanup để học, nhưng ghi phút can thiệp và chi phí thực; không báo kết quả concierge là bằng chứng “tự động hoàn toàn”.

## 5. Đối thủ và số liệu tham chiếu

Thông tin công khai kiểm tra trong nghiên cứu ngày 18/10/2026. “Chưa xác nhận” không có nghĩa đối thủ không có tính năng.

| Đối thủ / thay thế | Capture → 3D | Video / quảng cáo | Số liệu công khai | Hàm ý cho mình |
| :--- | :--- | :--- | :--- | :--- |
| **Solaya + Play** | Chụp bằng điện thoại → tái dựng; hỗ trợ Gaussian splat và xuất mesh theo mô tả nền tảng [S1] | Play xuất ảnh raw/studio/ecommerce và MP4 turntable [S2] | **[Nguồn]** Play công bố dùng miễn phí; nhận .ply/.sly đến **2 GB**, có **4 kiểu đầu ra**. Không suy ra toàn bộ scan/commercial workflow miễn phí | Đối thủ gần nhất về phone-first. “Chụp một lần → nhiều ảnh/video” không độc quyền; cần hơn turntable và ít quyết định hơn |
| **Fibbl** | Gửi hàng vào pipeline scan chuyên nghiệp [S3] | Ảnh, lifestyle, video tự render, feed tương thích Meta; **6 preset video** [S4] | **[Nguồn]** Starter **€499/tháng**; Excel **€1.399/tháng**, có AI/video; dựng model **€50–€240/model**; trial 1 model/30 ngày [S5] | Đối thủ trực tiếp scan-to-ad, mạnh giày/túi. Có thể thử phân khúc tự chụp, ít SKU, trả theo bộ; chưa chứng minh mình rẻ hơn ở chất lượng tương đương |
| **Photoroom** | Không cần bước tái dựng 3D trong workflow được mô tả | Ảnh sản phẩm → template/prompt → MP4 [S6] | **[Nguồn]** Nhận **1–4 ảnh**, **300+ template**, tỷ lệ **9:16, 1:1, 16:9** [S6] | Đối thủ thay thế quan trọng nhất: ít thao tác hơn. 3D phải chứng minh tính nhất quán/tái sử dụng đáng công capture, không chỉ “có công nghệ 3D” |
| **Polycam + công cụ render/edit** | Capture vật thể bằng smartphone → xuất sang phần mềm 3D [S7] | Cần ghép pipeline render, kịch bản, editor riêng | **[Nguồn]** Mô tả xuất **15+ định dạng**, gồm OBJ/FBX/GLTF [S7] | Có thể là building block; phải kiểm tra API, quyền thương mại, tự động hóa và điều khoản, không giả định mọi export có API |
| **ALLSIDES** | Scanner tự động hoặc đối tác nhận hàng scan [S8] | Digital twin relightable, contextual video; không xác nhận loop ads cho beginner | **[Nguồn]** Công bố **>30.000 model/scanner/năm** — tuyên bố công suất của hãng [S8] | Chuẩn tham chiếu chất lượng/công nghiệp, không phải đối thủ cùng UX nhỏ lẻ; không so trực tiếp công suất này với điện thoại |
| **Creatify** | Chưa xác nhận scan sản phẩm thật trong workflow đã nghiên cứu | Video/image ads, launch, phân tích và feedback creative [S9] | Không dùng lại giá cũ **$299** làm neo cạnh tranh; entitlements thay đổi | Đối thủ downstream khi mở rộng sang phân phối/learning; không nên đua toàn bộ tính năng |
| **Ảnh thật + CapCut/Canva hoặc freelancer** | Không bắt buộc 3D | Quay/dựng thủ công, hiểu ngữ cảnh sản phẩm | Chưa khảo sát giá/giờ thực tế của ICP; **không gán mức tiết kiệm giả** | Baseline phải đo cùng chất lượng, cùng bộ 3 video; có thể thắng mình nếu shop chỉ cần 1 video |

**Không dùng làm luận cứ:** “Chưa ai làm scan-to-video”, “3D chắc chắn tăng ROAS”, “giá rẻ nhất”, “AI giữ nguyên sản phẩm tuyệt đối”. Nghiên cứu hiện tại không chứng minh các câu này.

## 6. Unique strengths đề xuất và cách chứng minh

Đây là **lợi thế muốn xây**, không phải tài sản đã sở hữu hoặc tính năng chắc chắn độc nhất.

| Lợi thế đề xuất | Cơ chế cụ thể | Khác biệt tương đối | Bằng chứng cần có |
| :--- | :--- | :--- | :--- |
| **Product-locked video** | Render foreground từ cùng asset đã duyệt; giữ ảnh nhãn/logo gốc; kiểm tra trước khi xuất | So với sinh video thuần ảnh/prompt; Fibbl và Solaya cũng nhấn mạnh fidelity nên bản thân “giữ đúng hàng” không độc quyền | Tỷ lệ lỗi nghiêm trọng thấp hơn baseline photo-to-video trong cùng bài test |
| **Tự chụp, không cần gửi hàng** | Hướng dẫn capture trong app, phát hiện thiếu góc và sửa tại chỗ | So với quy trình studio/mail-in; **không** khác biệt độc quyền với Solaya/Polycam | Người mới tự làm được; phút hỗ trợ/scan thấp; thất bại không bị giấu bằng fallback |
| **Một SKU → nhiều video bán hàng** | Dùng lại asset; đổi hook, camera, ưu đãi, CTA thay vì chỉ đổi nền | So với chỉ xuất turntable hoặc bắt đầu lại từng clip; Fibbl/Photoroom vẫn có khả năng tạo nhiều asset | Người bán quay lại dùng asset cho chiến dịch thứ hai và chấp nhận trả tiền |
| **Đúng ngôn ngữ người bán** | Chọn mục đích bằng tiếng Việt; 3 preset rõ; không prompt, mesh, credit puzzle hay timeline | Phù hợp nhóm pilot cụ thể; đối thủ hoàn toàn có thể sao chép UX | ≥70% hoàn thành không can thiệp; hiểu tổng tiền trước khi render |
| **Giá theo kết quả hữu dụng** | Bộ video có quota rõ, preview trước; chính sách rerender/lỗi minh bạch | So với phí nền tảng lớn hoặc credit khó hiểu; Solaya Play miễn phí là đối trọng thực | Khách trả tiền ở giá bảo đảm contribution margin sau retries/support |
| **Bộ nhớ theo SKU, rồi mới learning** | Lưu version asset, hook, video và outcome; gợi ý lần sau từ dữ liệu thật | Liên kết asset chính xác với sáng tạo/hiệu quả; không gọi tương quan là nguyên nhân | Tái sử dụng tốt hơn; trace được variant → ad ID; kết quả có trạng thái “chưa đủ dữ liệu” |

**Moat có thể hình thành:** tập lỗi capture/fidelity được gán nhãn theo loại hàng, capture UX đã tối ưu, bộ asset khách đã duyệt và lịch sử tái sử dụng có quyền xử lý dữ liệu rõ. API gọi model, prompt template, hoặc hỗ trợ nhiều AI model **không tự tạo moat**.

## 7. Giá và unit economics — giả định có thể bác bỏ

### 7.1 Gói giá để thử, không phải bảng giá đã chốt

| Gói pilot | Giá giả định | Phạm vi | Mục đích |
| :--- | :--- | :--- | :--- |
| Preview | $0 | Upload/capture và xem preview chất lượng thấp; quota 1 SKU | Giảm rủi ro trước khi trả tiền, giới hạn chi phí abuse |
| First Product Pack | **$29 trả một lần** | 1 capture/model được duyệt, 3 video 10–15s, 1 format, tối đa 2 lượt rerender hợp lệ/bộ | Kiểm tra mua kết quả thay vì mua subscription |
| Refresh Pack | **$15 trả một lần** | Dùng lại đúng asset, 3 video mới, không dựng lại model; tối đa 2 rerender/bộ | Kiểm tra lợi ích kinh tế từ tái sử dụng 3D |
| Subscription | Chưa mở | Chỉ thiết kế khi có bằng chứng mua lại | Tránh thuê bao cho khách chỉ có nhu cầu một lần |

USD chỉ là đơn vị mô hình hóa; test giá địa phương riêng nếu pilot tại Việt Nam. Không quy đổi theo tỷ giá tự giả định. Quota, thế nào là lỗi hệ thống, thay đổi yêu cầu, cách hoàn tiền và quyền xuất asset cần ghi rõ trước thu tiền.

### 7.2 Chi phí biến đổi cho một First Product Pack $29

| Khoản mục | Kịch bản base **[Giả định]** | Cách đo khi pilot |
| :--- | :--- | :--- |
| Capture processing / dựng 3D | $2,00 | Tổng compute/provider, gồm lần thất bại chia cho số bộ giao được |
| Render + encode | 3 × $0,50 = $1,50 | Chi phí actual cho 3 video final |
| Script / voice / scene assets | $0,50 | Meter provider + license phân bổ |
| Retry reserve | 2 × $0,50 = $1,00 | Đo chi phí rerender và scan lại riêng; mức reserve này có thể không đủ |
| Storage / delivery | $0,30 | Lưu source/model/output và tải xuống theo retention thực |
| Hỗ trợ / cleanup | 5 phút × $12/giờ = $1,00 | Ghi đủ phút can thiệp; đây là giả định lương, không phải benchmark |
| Thanh toán | 3% × $29 + $0,30 = $1,17 | Thay bằng phí PSP thực tế, gồm chi phí refund nếu có |
| **Tổng biến phí / bộ giao thành công** | **$7,47** | Không loại chi phí thất bại khỏi mẫu số |
| **Contribution / bộ** | **$29 − $7,47 = $21,53 (~74,2%)** | Trước CAC, lương cố định, R&D, thuế, overhead và dự phòng refund |

**Stress test:** Nếu cleanup tăng từ 5 lên **30 phút**, chi phí hỗ trợ tăng từ $1 lên $6; tổng thành **$12,47**, contribution còn **$16,53 (~57,0%)**. Nếu pipeline provider đắt hơn hoặc khách sửa nhiều, mô hình có thể không phù hợp giá $29.

**[Mục tiêu]** Contribution margin sau compute/retries/support/phí thanh toán **≥65%**. Chưa có báo giá/provider benchmark để khẳng định đạt. Giá vốn cần đo trên bộ giao được, không chỉ giá một lần render đẹp.

### 7.3 Vì sao khách nên chịu công dựng 3D?

So sánh cùng định nghĩa “video được duyệt”:

`C_3D(N) = S + N × R` và `C_photo(N) = N × G`.

Với **[Giả định minh họa]** setup 3D `S=$4`, render mỗi video `R=$0,50`, photo-to-video có expected cost sau retries `G=$2`, thì 3D rẻ hơn ở `N > 4/(2−0,5) ≈ 2,67`, tức từ **3 video**. Nếu `G=$0,75`, ngưỡng thành **17 video**. Chưa tính thời gian capture/chỉnh sửa của khách. Đây là sensitivity analysis, **không phải giá API hay bằng chứng 3D luôn rẻ hơn**.

## 8. Kế hoạch kiểm chứng có số đo

| Thử nghiệm | Thiết kế đề xuất | Điều kiện tiếp tục **[Mục tiêu]** |
| :--- | :--- | :--- |
| Problem interviews | 15 chủ shop đúng nhóm; xem nội dung gần nhất và quy trình thật | ≥10/15 mô tả nhu cầu tạo video lặp lại; ghi bằng chứng, không chỉ hỏi “có thích không” |
| Paid demand | Mời cả 15 shop mua pack $29 với điều kiện giao/hoàn tiền rõ | ≥5/15 mua thật; mẫu nhỏ chỉ là tín hiệu định hướng |
| Capture usability | 10 người mới, 2 SKU/người = 20 lượt; không người vận hành chụp hộ | ≥14/20 lượt hoàn thành end-to-end không can thiệp; ≥16/20 đạt capture sau tối đa 1 lần chụp lại |
| Fidelity & baseline | 20 SKU × 3 video × 2 pipeline = **120 video**; so 3D-render với photo-to-video bằng cùng brief | ≥54/60 video 3D được seller duyệt; 0 lỗi nghiêm trọng được phép đi ra bản final; báo cả lỗi draft/retry |
| Chi phí | Đo cùng 120 video; gồm capture thất bại, render lỗi, phút sửa và support | ≥65% contribution ở giá thực thu; biết nhóm vật liệu làm chi phí tăng |
| Publish | Theo dõi 10 shop pilot, xác nhận link/bằng chứng đăng trong 7 ngày | ≥6/10 đăng ít nhất 1 video; download không tính là publish |
| Reuse / repeat | Theo dõi cùng cohort trong 30 ngày | ≥4/10 dùng lại asset cho bộ thứ hai; ≥3/10 mua pack tiếp theo |

**Fidelity rubric:** chấm hình dáng, nhãn/chữ/logo, màu/vật liệu, chi tiết cấu tạo và độ ổn định theo thời gian. Lỗi nghiêm trọng gồm nhãn sai, mất/thêm bộ phận hoặc hình ảnh gây hiểu sai sản phẩm. Người bán phải duyệt; checker tự động chỉ hỗ trợ, không được coi là kiểm chứng tuyệt đối. “0 lỗi final” là chính sách chặn xuất trong pilot, không phải tuyên bố hệ thống không bao giờ sinh lỗi.

Không suy ra statistical significance hoặc ROAS uplift từ cohort 10–20 mẫu. Thử quảng cáo trả phí sau khi production workflow đạt, với thiết kế/budget theo baseline thật; không hứa một số tiền cố định sẽ tìm được winner.

## 9. MVP roadmap và điều kiện dừng

| Giai đoạn | Phạm vi | Điều kiện qua cổng |
| :--- | :--- | :--- |
| Tuần 1 — demand & input | Phỏng vấn 15 shop, thu SKU thật với sự đồng ý, báo giá pilot | Có ≥5 khách mua/cam kết trả theo điều kiện giao; không dùng model tải mạng thay cho hàng khách để chứng minh fidelity |
| Tuần 2 — concierge benchmark | Chạy 2 pipeline, làm video có hỗ trợ, ghi thao tác và chi phí | Biết loại hàng phù hợp, lỗi phổ biến, cost per approved video; không gọi đây là automation |
| Tuần 3–4 — guided capture → preview | Tích hợp reconstruction có sẵn nếu điều khoản cho phép; crop/quality guidance; màn hình duyệt | Đạt gate capture/usability; không đầu tư custom reconstruction trước |
| Tuần 5–6 — self-serve pack | 3 template nội dung, render từ asset, export, quota, payment, revision/refund | Đạt fidelity, publish, contribution; nếu chưa đạt thì sửa phạm vi thay vì mở thêm tính năng |
| Sau pilot | Preset bổ sung, tái sử dụng SKU, integration shop tùy nhu cầu | Có repeat purchase; campaign launch và learning chỉ triển khai sau bằng chứng nhu cầu |

**Lịch là giả định năng lực đội, không phải deadline được xác nhận.**

**Dừng hoặc đổi hướng nếu:** dưới 5/15 chịu trả; capture 3D gây bỏ cuộc dù đã thu hẹp loại hàng; photo-to-video đạt chất lượng tương đương với ít công hơn; không có nhu cầu tái sử dụng; cleanup làm contribution không đạt. Khi đó có thể giữ lời hứa “hàng thật → video” nhưng cho 3D là tùy chọn/backend có chọn lọc, không ép mọi SKU qua 3D.

## 10. Go-to-market và quy mô minh họa

| Thành phần | Phương án |
| :--- | :--- |
| Thu hút ban đầu | Founder-led outreach tới shop cùng một ngành; demo bằng **sản phẩm của shop**, không video AI chung chung |
| Thông điệp | “Chụp hàng ngay trên điện thoại. Duyệt đúng sản phẩm. Nhận 3 video để đăng bán.” Chỉ quảng cáo con số sau khi pilot xác nhận quota/chất lượng |
| Kênh tiếp theo | Cộng đồng chủ shop, đối tác chụp ảnh sản phẩm, đơn vị hỗ trợ mở shop; Shopify app chỉ khi nhóm khách thực sự dùng Shopify |
| Cách bán | Preview trước; gói trả một lần; giải thích rõ loại hàng hỗ trợ, thời gian xử lý và sửa/hoàn tiền |
| Kịch bản doanh thu nhỏ | **[Giả định]** 100 shop mua 1 pack $29 = **$2.900**; 30 shop mua thêm 1 refresh $15 = **$450**; tổng **$3.350/tháng** |
| Giới hạn con số | Đây là doanh thu theo lượt giả định, **không phải MRR cam kết, TAM/SAM/SOM hay dự báo**; chưa trừ cost/CAC/refunds/thuế; chưa có dữ liệu số shop có thể tiếp cận |
| CAC | Chưa biết. Đo tiền và giờ founder bỏ ra riêng; không suy LTV khi chưa có repeat/retention |

## 11. Các quyết định cần founder chốt

1. **Ngành hàng đầu tiên:** đề xuất đồ gia dụng/phụ kiện bàn làm việc nhỏ, không bóng/trong; chỉ một nhóm trong pilot.
2. **3D có bắt buộc không:** core flow có 3D, nhưng giữ fallback được gắn nhãn và quyền chuyển hướng nếu baseline ảnh tốt hơn.
3. **Đích MVP:** xuất video bán hàng, chưa phải tự chạy quảng cáo hay đảm bảo doanh số.
4. **Thị trường/ngôn ngữ/giá:** pilot tiếng Việt là đề xuất; pack $29 chỉ là giả thuyết cần hỏi và bán thật.
5. **Lời hứa:** “Giữ sản phẩm nhất quán bằng asset đã duyệt” là hướng xây; không tuyên bố độc nhất/100% chính xác trước benchmark.

## 12. Nguồn và liên hệ tài liệu

| ID | Nguồn | Dùng cho |
| :--- | :--- | :--- |
| S1 | [Solaya](https://www.solaya.ai/) và [scanner app](https://www.solaya.ai/features) | Phone capture, reconstruction, Gaussian splat/mesh; thông tin do hãng công bố |
| S2 | [Solaya Play](https://www.solaya.ai/play) | File .ply/.sly đến 2 GB, 4 kiểu export, công bố Play miễn phí; không suy toàn bộ pipeline miễn phí |
| S3 | [Fibbl: how it works](https://fibbl.com/how-it-works) | Nhận sản phẩm vật lý để scan và đưa asset lên platform |
| S4 | [Fibbl Dynamic Product Ads](https://fibbl.com/product-content/dynamic-video-feed/) | Auto render, Meta-compatible feed, 6 preset; không dùng lift tự công bố làm forecast của mình |
| S5 | [Fibbl pricing](https://fibbl.com/pricing/) | €499/€1.399 mỗi tháng, €50–€240/model, trial; giá/điều khoản cần xác nhận khi mua |
| S6 | [Photoroom video generation](https://www.photoroom.com/tools/category/video-generation) | 1–4 ảnh, 300+ template, aspect ratios, MP4; vendor claim về accuracy chưa được kiểm thử |
| S7 | [Polycam cho 3D/VFX](https://poly.cam/solutions/3d-vfx) | Capture/export; không phải xác nhận API hợp tác có sẵn |
| S8 | [ALLSIDES](https://allsides.tech/) | Scanner/service, relightable assets, contextual video, công suất >30.000 model/năm do hãng công bố |
| S9 | [Creatify Performance Agent](https://creatify.ai/features/performance-agent) | Đối thủ downstream cho generation/launch/performance loop |
| Nội bộ | [Competitor matrix](ai-performance-marketing-competitor-research-report.md) | Bối cảnh AI performance marketing; không thay thế benchmark 3D |
| Nội bộ | [PRD trước](hook-validation-loop-prd.md) | Bối cảnh hook-validation ban đầu; canvas này là hướng chuyên môn hóa mới, không tự động sửa PRD cũ |

**Kết luận:** Nên bán **video bán hàng cho đúng món hàng của người bán**, không bán “công nghệ scan 3D”. Khả năng thắng nằm ở tổ hợp capture dễ, asset đúng, video dùng được và mua lại có lợi — phải chứng minh được so với cả Solaya/Fibbl lẫn đường tắt photo-to-video của Photoroom.
