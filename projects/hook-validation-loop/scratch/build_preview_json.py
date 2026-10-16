import json

data = {
  "project": "Lạc Hồng / Kiến trúc Wireframe · Vòng lặp Video: 01. AI analysis → 02. Hook suggestion → 03. Video creation → 04. Metrics",
  "directions": [
    {
      "id": "onboarding",
      "name": "Onboarding · Full-screen chat & Project Tree",
      "notes": "Màn hình bắt đầu toàn cảnh (Full-screen chat). Thanh điều hướng bên trái có thể mở rộng thành Cây thư mục (File Tree) hiển thị các dự án và tài nguyên thương hiệu (Brand Assets). Người dùng có thể kéo thả tài sản thương hiệu vào chat hoặc bấm '+ Thêm tài sản thương hiệu'. Khung chat tiếp tục thu gọn ở cột 30% khi vào dashboard.",
      "design": {
        "layout": "centered",
        "visual": "interface",
        "font": "modern",
        "colors": {
          "background": "#f5f4f0",
          "surface": "#ffffff",
          "ink": "#242823",
          "muted": "#6b7168",
          "accent": "#346149",
          "line": "#dedfd7"
        },
        "containerWidth": "1120px",
        "cornerRadius": "10px"
      },
      "hero": {
        "eyebrow": "BẮT ĐẦU MỘT Ý TƯỞNG MỚI",
        "topLabel": "lạc hồng.",
        "navigation": ["File Tree: Sắc Ngọc Khang ▾", "01 AI analysis", "02 Hook suggestion", "03 Video creation", "04 Metrics"],
        "footerLeft": "Bản mẫu tương tác",
        "footerRight": "Full-screen chat"
      },
      "visual": {
        "imageUrl": "",
        "imageAlt": "",
        "caption": "Cuộc trò chuyện khởi đầu & Nạp tài sản thương hiệu",
        "index": "01 / 06",
        "interface": {
          "label": "Lạc Hồng",
          "title": "Bạn đang làm video cho sản phẩm nào?",
          "description": "Gửi liên kết, ảnh sản phẩm hoặc tài liệu thương hiệu nhé.",
          "metric": "",
          "metricLabel": "Gửi"
        }
      },
      "wireframe": {
        "title": "Screen 1 / Onboarding Chat & Cây tài nguyên (first-onboarding-screen-redesigned.html)",
        "rows": [
          {
            "label": "Header with file tree toggle",
            "cells": [
              {"type": "link", "text": "≡ Cây thư mục", "href": "#file-tree", "pixels": 120},
              {"type": "brand", "text": "lạc hồng.", "pixels": 160},
              {"type": "text", "text": "Không gian sáng tạo video & Quản lý tài nguyên thương hiệu", "pixels": 580},
              {"type": "link", "text": "Mở Dashboard workspace →", "href": "four-stage-loop-dashboard-redesigned.html", "pixels": 260}
            ]
          },
          {
            "label": "Collapsible file tree drawer preview",
            "id": "file-tree",
            "cells": [
              {"type": "space", "pixels": 200},
              {"type": "text", "text": "CÂY THƯ MỤC DỰ ÁN & TÀI NGUYÊN (FILE TREE):\n▼ 📂 Sắc Ngọc Khang (Serum rau má · Đang mở)\n  ▼ 📁 Brand Assets (Tài nguyên thương hiệu)\n    ├── 🎬 raw-footage-serum-01.mp4 [Preview / Adjust]\n    ├── 🖼 chai-serum-rau-ma.png [Preview / Adjust]\n    ├── 📄 huong-dan-giong-dieu-brand.pdf [Preview / Adjust]\n    └── ➕ [Thêm tài sản thương hiệu mới…]\n  ► 📁 Hook Variants (Vòng 01)\n  ► 📁 Telemetry Data\n► 📂 Mỹ phẩm Cocoon\n► 📂 Thời trang Yame\n+ Tạo dự án mới…", "pixels": 720},
              {"type": "space", "pixels": 200}
            ]
          },
          {
            "label": "Welcome inside scrollable chat",
            "cells": [
              {"type": "space", "pixels": 200},
              {"type": "text", "text": "Bắt đầu một ý tưởng mới\nAI tự động quét winning hooks và thử nghiệm video.\nGiới thiệu sản phẩm hoặc đính kèm tài nguyên thương hiệu. Hệ thống sẽ đối chiếu số liệu với các winning hooks trên mạng xã hội.", "pixels": 720},
              {"type": "space", "pixels": 200}
            ]
          },
          {
            "label": "Assistant opening",
            "id": "conversation",
            "cells": [
              {"type": "space", "pixels": 200},
              {"type": "text", "text": "Lạc Hồng\nBạn đang làm video cho sản phẩm nào? Gửi liên kết, mô tả hoặc kéo thả tài liệu thương hiệu vào đây nhé.", "pixels": 720},
              {"type": "space", "pixels": 200}
            ]
          },
          {
            "label": "Optional sample prompt & asset upload",
            "cells": [
              {"type": "space", "pixels": 200},
              {"type": "text", "text": "Ví dụ mẫu sẵn có:\nSerum rau má Sắc Ngọc Khang (Đã đính kèm 2 video b-roll + 1 ảnh sản phẩm trong Brand Assets)", "pixels": 720},
              {"type": "space", "pixels": 200}
            ]
          },
          {
            "label": "Conversation after sending sample",
            "cells": [
              {"type": "space", "pixels": 200},
              {"type": "text", "text": "Bạn\nMình bán serum rau má Sắc Ngọc Khang cho người có da nhạy cảm.\nLạc Hồng\nMình đã lưu thông tin và kết nối với Brand Assets trong cây thư mục. Chuyển sang 01. AI analysis để xem đối chiếu chỉ số nhé.", "pixels": 720},
              {"type": "space", "pixels": 200}
            ]
          },
          {
            "label": "Inline transition to workspace",
            "cells": [
              {"type": "space", "pixels": 200},
              {"type": "link", "text": "Chuyển sang Dashboard (01. AI analysis: Đối chiếu metrics & xem video) →", "href": "four-stage-loop-dashboard-redesigned.html", "pixels": 720},
              {"type": "space", "pixels": 200}
            ]
          },
          {
            "label": "Persistent bottom composer",
            "id": "composer",
            "cells": [
              {"type": "space", "pixels": 200},
              {"type": "text", "text": "Kể về sản phẩm hoặc đính kèm tệp tài sản thương hiệu…\nEnter để gửi · Shift + Enter để xuống dòng\n[Đính kèm tệp 📎] [Gửi ↑]", "pixels": 720},
              {"type": "space", "pixels": 200}
            ]
          },
          {
            "label": "Footer",
            "cells": [
              {"type": "text", "text": "Bản mẫu tương tác · Cây thư mục và tài nguyên thương hiệu được đồng bộ xuyên suốt các màn hình.", "pixels": 1120}
            ]
          }
        ]
      },
      "spec": {
        "goal": {
          "what": "Conversational onboarding tích hợp Cây thư mục dự án (File Tree) và nạp tài sản thương hiệu (Brand Assets).",
          "audience": "Nhà bán hàng và người sáng tạo nội dung quản lý tài nguyên video/hình ảnh.",
          "successCriteria": "Người dùng nắm rõ các tệp tài nguyên sẵn có, thêm được tài sản mới và chuyển sang Dashboard liền mạch."
        },
        "format": {
          "canvas": "Toàn màn hình 1120px; cây thư mục có thể mở dạng drawer bên trái; khung chat thoáng ở giữa.",
          "safeMargins": "Đệm 24px bên trong chat; thanh composer ghim đáy hỗ trợ nút đính kèm tài sản."
        },
        "layout": {
          "grid": "Thanh điều hướng cây thư mục trái, khung đối thoại giữa, composer đáy.",
          "placement": "Nút mở Cây thư mục ở góc trái; luồng chat ở trung tâm.",
          "hierarchy": "Trò chuyện và nạp tài nguyên thương hiệu được tích hợp tự nhiên."
        },
        "typeSystem": {
          "display": "Be Vietnam Pro 50px desktop / 37px mobile.",
          "metadata": "10–12px nhãn tệp và định dạng MIME.",
          "contrast": "Tương phản đạt chuẩn WCAG AA."
        },
        "colorMaterial": {
          "foundation": "Nền ấm #f5f4f0 và chữ than chì #242823.",
          "surfaces": "Thẻ thư mục màu trắng, icon tệp tinh giản.",
          "borders": "1px #dedfd7; bo góc 10px.",
          "signal": "Xanh lá #346149 cho hành động đính kèm và gửi."
        },
        "copy": {
          "headline": "AI tự động thử nghiệm hooks.",
          "subtitle": "Giới thiệu sản phẩm hoặc đính kèm tài nguyên thương hiệu. Sau đó, thử các cách mở đầu khác nhau trên cùng một video.",
          "actions": [{"label": "Gửi", "href": "#composer"}]
        },
        "constraints": {
          "font": "Be Vietnam Pro tiếng Việt chuẩn.",
          "accent": "Một màu xanh lá chủ đạo.",
          "container": "Hỗ trợ duyệt cây thư mục và nạp tệp tài sản thương hiệu (video, ảnh, pdf)."
        },
        "negativePrompt": [
          "Không biến chat thành trang tải tệp phức tạp.",
          "Không làm đứt gãy luồng trao đổi khi xem cây thư mục.",
          "Không ẩn nút thêm tài sản thương hiệu."
        ]
      }
    },
    {
      "id": "ai-loop-analysis",
      "name": "AI Analysis · 01 AI analysis & Pure Metrics Comparison",
      "notes": "Giai đoạn 01: AI analysis. Trong mỗi vòng lặp (Loop), AI quét thị trường để tìm nhiều winning hooks khác nhau (không chỉ 1 video dẫn đầu). Màn hình đối chiếu side-by-side là THUẦN SỐ LIỆU (purely metrics) với 2 nút clickable ở trên cùng: khi người dùng bấm vào 'Winning Hooks', hệ thống mở danh sách các video thắng lớn khác nhau trên mạng xã hội; khi người dùng bấm vào 'Our Performance', hệ thống mở danh sách các video quảng cáo của chính thương hiệu. Bên dưới là bảng đối chiếu metrics chi tiết (giữ chân 3s, drop-off 1s, nhịp cắt cảnh, điểm giác quan) và giả thuyết chuyển tiếp sang 02. Hook suggestion.",
      "design": {
        "layout": "split",
        "visual": "interface",
        "font": "modern",
        "colors": {
          "background": "#f5f4f0",
          "surface": "#ffffff",
          "ink": "#242823",
          "muted": "#6b7168",
          "accent": "#346149",
          "line": "#dedfd7"
        },
        "containerWidth": "1440px",
        "cornerRadius": "10px"
      },
      "hero": {
        "eyebrow": "DASHBOARD / 01. AI ANALYSIS · PURE METRICS & VIDEO LISTS",
        "topLabel": "lạc hồng.",
        "navigation": ["File Tree: Sắc Ngọc Khang ▾", "01 AI analysis (Đang mở)", "02 Hook suggestion →", "Về trò chuyện"],
        "footerLeft": "File Tree + Chat 30% / Dashboard 70%",
        "footerRight": "Giai đoạn 01 / 04"
      },
      "visual": {
        "imageUrl": "",
        "imageAlt": "",
        "caption": "Đối chiếu thuần số liệu (Pure Metrics) với 2 nút bấm mở danh sách video phía trên",
        "index": "02 / 06",
        "interface": {
          "label": "01. AI ANALYSIS · PURE METRICS COMPARISON",
          "title": "Winning Hooks 82,3% vs Our Ads 58,5%",
          "description": "Bấm vào 'Winning Hooks' để xem danh sách video mẫu; bấm 'Our Performance' để xem quảng cáo của bạn. So sánh side-by-side hoàn toàn là số liệu.",
          "metric": "+23.8%",
          "metricLabel": "Khoảng cách giữ chân 3s"
        }
      },
      "wireframe": {
        "title": "Dashboard Wireframe / 01. AI analysis · Pure Metrics Side-by-Side with Clickable Video List Triggers",
        "rows": [
          {
            "label": "Header with file tree status",
            "cells": [
              {"type": "link", "text": "≡ Cây thư mục (Thu gọn)", "href": "#file-tree", "pixels": 260},
              {"type": "brand", "text": "lạc hồng.", "pixels": 180},
              {"type": "text", "text": "Sắc Ngọc Khang / Vòng 01 · Quét thị trường TikTok & Meta Ads (Đa dạng winning hooks)", "pixels": 600},
              {"type": "link", "text": "Về trò chuyện", "href": "first-onboarding-screen-redesigned.html", "pixels": 200},
              {"type": "link", "text": "02 Hook suggestion →", "href": "#hooks", "pixels": 200}
            ]
          },
          {
            "label": "Workspace layout / File Tree 260px + Chat 350px + Dashboard 830px",
            "cells": [
              {"type": "visual", "text": "📂 CÂY THƯ MỤC DỰ ÁN\n\n▼ Sắc Ngọc Khang (Đang mở)\n  ▼ 📁 Brand Assets\n    ├── 🎬 broll-rau-ma.mp4\n    ├── 🖼 chai-serum.png\n    ├── 📄 brand-voice.pdf\n    └── ➕ [Thêm tài sản]\n  ► 📁 Hook Variants\n  ▼ 📁 Market Telemetry\n    ├── 📹 winning-hooks-gallery.json\n    └── 📊 our-performance-ads.json\n► 📂 Mỹ phẩm Cocoon\n\n[+ Tạo dự án mới]", "pixels": 260},
              {"type": "text", "text": "Lạc Hồng\nTrợ lý chẩn đoán hình ảnh & số liệu AI\nMình đã quét 1.280 video và gom được 4 winning hooks xuất sắc (80.8% - 84.1% giữ chân 3s), không chỉ một mẫu duy nhất.\nBên phải là bảng đối chiếu THUẦN SỐ LIỆU (Pure Metrics).\nBạn có thể bấm vào nút 'Winning Hooks' để mở danh sách video thị trường, hoặc bấm 'Our Performance' để xem lại các quảng cáo của bạn.\nNhắn cho Lạc Hồng…\n[Đính kèm 📎] [Gửi ↑]", "pixels": 350},
              {"type": "text", "text": "DASHBOARD / 01. AI ANALYSIS\nĐối chiếu thuần số liệu (Purely Metrics) & 2 Danh sách video mở rộng\nKhu vực so sánh song song hiển thị các chỉ số đo lường chuẩn hóa. Hai nút bấm trên cùng cho phép mở danh sách video thực tế của thị trường hoặc của thương hiệu.", "pixels": 830}
            ]
          },
          {
            "label": "Four stage progress tabs (01 -> 02 -> 03 -> 04)",
            "cells": [
              {"type": "space", "pixels": 260},
              {"type": "space", "pixels": 350},
              {"type": "link", "text": "01 · AI analysis (Đang mở)", "href": "#analysis", "pixels": 207},
              {"type": "link", "text": "02 · Hook suggestion →", "href": "#hooks", "pixels": 207},
              {"type": "link", "text": "03 · Video creation", "href": "#video", "pixels": 208},
              {"type": "link", "text": "04 · Metrics", "href": "#metrics", "pixels": 208}
            ]
          },
          {
            "label": "Market scan status banner",
            "cells": [
              {"type": "space", "pixels": 260},
              {"type": "space", "pixels": 350},
              {"type": "text", "text": "🔍 DỮ LIỆU QUÉT TỰ ĐỘNG THỊ TRƯỜNG (LOOP 01 SCAN):\n• 1.280 video & ads đã quét từ TikTok Creative Center, Meta Ad Library, Reels, Shorts.\n• Đã phân loại 4 nhóm Winning Hooks tiêu biểu (Sensory Snap, Myth Busting, Minimal Routine, Micro-Proof).\n• Điểm so sánh: Benchmark thị trường đạt 82,3% giữ chân 3s vs Video của thương hiệu đạt 58,5%.", "pixels": 830}
            ]
          },
          {
            "label": "TWO CLICKABLE TRIGGERS ON-TOP (Click to view video lists)",
            "id": "triggers",
            "cells": [
              {"type": "space", "pixels": 260},
              {"type": "space", "pixels": 350},
              {"type": "link", "text": "🏆 [BẤM ĐỂ MỞ] WINNING HOOKS (Xem danh sách 4 video thắng lớn ▾)", "href": "#winning-hooks-list", "pixels": 415},
              {"type": "link", "text": "🎬 [BẤM ĐỂ MỞ] OUR PERFORMANCE (Xem danh sách 4 video ads của bạn ▾)", "href": "#our-ads-list", "pixels": 415}
            ]
          },
          {
            "label": "EXPANDABLE LIST 1: Winning Hooks Videos (Shown when clicking Winning Hooks)",
            "id": "winning-hooks-list",
            "cells": [
              {"type": "space", "pixels": 260},
              {"type": "space", "pixels": 350},
              {"type": "visual", "text": "🏆 DANH SÁCH CÁC WINNING HOOKS THẮNG LỚN TRÊN MẠNG XÃ HỘI (BẤM VÀO ĐỂ XEM FOOTAGE):\n\n1. [▶ Phát video] W01 · Sensory Crackle (TikTok Ad · 1.8M views · 83,4% 3s · CTR 7,1%)\n   Footage: 0s-0.8s Cận cảnh Macro bẻ đôi lá rau má tươi văng bọt tuyết đá giòn tan $\\rightarrow$ Đưa vết mẩn đỏ $\\rightarrow$ Tan vào da.\n\n2. [▶ Phát video] W02 · Myth Busting / Problem Hook (Reels · 1.2M views · 81,2% 3s · CTR 6,5%)\n   Footage: 0s-0.8s Tay giơ bảng cảnh báo đỏ: 'Đừng vội mua serum nếu da chưa gặp 3 điều này' $\\rightarrow$ Zoom lỗ chân lông.\n\n3. [▶ Phát video] W03 · Minimal 2-Step Routine (Shorts · 960K views · 80,8% 3s · CTR 6,9%)\n   Footage: 0s-0.8s Đếm ngón tay 1-2 trên mặt mộc: 'Routine cứu da mẩn đỏ của một đứa siêu nhạy cảm'.\n\n4. [▶ Phát video] W04 · Before/After Micro-Proof (TikTok Spark · 1.5M views · 83,9% 3s · CTR 7,8%)\n   Footage: 0s-0.8s Màn hình chia đôi nửa mặt kích ứng vs làm dịu sau 1 đêm $\\rightarrow$ Nhỏ 3 giọt serum lên biểu bì.", "pixels": 830}
            ]
          },
          {
            "label": "EXPANDABLE LIST 2: Our Performance Ads (Shown when clicking Our Performance)",
            "id": "our-ads-list",
            "cells": [
              {"type": "space", "pixels": 260},
              {"type": "space", "pixels": 350},
              {"type": "visual", "text": "🎬 DANH SÁCH QUẢNG CÁO & VIDEO CỦA THƯƠNG HIỆU (OUR PERFORMANCE ADS):\n\n1. [▶ Xem video] Ad V01 · Bản nói chuyện mở đầu (Talking Head Baseline · 40.000 views · 58,5% 3s)\n   Footage: Người đứng im cầm chai serum trước máy quay $\\rightarrow$ Gãy tương tác (Drop-off 36%) tại giây 1.1s.\n\n2. [▶ Xem video] Ad V02 · Bản đặt câu hỏi chung chung (Generic Question · 27.500 views · 53,1% 3s)\n   Footage: Text tĩnh 'Bạn chọn serum rau má vì điều gì?' $\\rightarrow$ Gãy tương tác tại giây 0.9s do chữ chạy chậm.\n\n3. [▶ Xem video] Ad V03 · Bản giải thích thành phần (Ingredient Explainer · 22.400 views · 45,8% 3s)\n   Footage: Bảng infographic liệt kê hoạt chất chiết xuất rau má $\\rightarrow$ Gãy tương tác tại giây 0.7s vì quá học thuật.\n\n4. [▶ Xem video] Ad V04 · Bản trải nghiệm buổi tối (Evening Routine · 32.000 views · 60,4% 3s)\n   Footage: Mở nắp chai thoa serum trong phòng ngủ $\\rightarrow$ Gãy tương tác tại giây 1.8s do mở đầu thiếu kịch tính.", "pixels": 830}
            ]
          },
          {
            "label": "SIDE-BY-SIDE COMPARISON: PURELY METRICS",
            "id": "pure-metrics",
            "cells": [
              {"type": "space", "pixels": 260},
              {"type": "space", "pixels": 350},
              {"type": "text", "text": "📊 METRICS CHUẨN: WINNING HOOKS\n(Bình quân 4 mẫu winning ads hàng đầu thị trường)\n\n• Tỷ lệ giữ chân 3s: 82,3% (Top 1% viral niche)\n• Tỷ lệ rớt giây đầu (1s Drop-off): 10,8% (Rất thấp)\n• Thời lượng xem trung bình: 14,2 giây / 25 giây (56,8%)\n• Nhịp chuyển cảnh 3s đầu: 2,4 nhịp cắt (0,7s - 1,2s/cảnh)\n• Điểm kích thích giác quan (Sensory AI Score): 9,2 / 10\n• Tỷ lệ tương tác & nhấp chuột (CTR): 7,1%\n• Tỷ lệ xem hết video: 28,4%\n\n✓ Đặc trưng số liệu: 1s Drop-off dưới 12% nhờ kích thích thị giác mạnh (nước/lá/zoom) và âm thanh giòn trong 0,5s đầu.", "pixels": 415},
              {"type": "text", "text": "📉 METRICS CỦA BẠN: OUR PERFORMANCE\n(Bình quân 4 video ads của thương hiệu vòng trước)\n\n• Tỷ lệ giữ chân 3s: 58,5% (Thấp hơn benchmark 23,8%)\n• Tỷ lệ rớt giây đầu (1s Drop-off): 36,0% (Gãy phễu sớm)\n• Thời lượng xem trung bình: 9,8 giây / 25 giây (39,2%)\n• Nhịp chuyển cảnh 3s đầu: 0,8 nhịp cắt (Khung hình tĩnh)\n• Điểm kích thích giác quan (Sensory AI Score): 4,1 / 10\n• Tỷ lệ tương tác & nhấp chuột (CTR): 3,2%\n• Tỷ lệ xem hết video: 14,1%\n\n⚠ Vấn đề số liệu: 36% người xem thoát ngay ở giây 1.1s vì mở đầu bằng khung hình tĩnh và nói về sản phẩm quá sớm.", "pixels": 415}
            ]
          },
          {
            "label": "Second-by-second retention delta curve",
            "cells": [
              {"type": "space", "pixels": 260},
              {"type": "space", "pixels": 350},
              {"type": "text", "text": "📈 ĐỐI CHIẾU CHỈ SỐ GIỮ CHÂN TỪNG GIÂY (RETENTION CURVE DELTA):\n• Giây 0.0s: Winning Hooks 100% vs Our Ads 100% (Khởi đầu ngang nhau)\n• Giây 1.0s: Winning Hooks 89,2% vs Our Ads 64,0% $\\rightarrow$ Chênh lệch giữ chân: +25,2% (Khoảng cách lớn nhất hình thành tại đây!)\n• Giây 2.0s: Winning Hooks 85,1% vs Our Ads 60,2% $\\rightarrow$ Chênh lệch giữ chân: +24,9%\n• Giây 3.0s: Winning Hooks 82,3% vs Our Ads 58,5% $\\rightarrow$ Chênh lệch giữ chân: +23,8%\n• Đúc kết số liệu: 72% khoảng cách giữ chân bị tạo ra ngay trong 1,2 giây đầu tiên do thiếu kích thích giác quan lập tức.", "pixels": 830}
            ]
          },
          {
            "label": "AI metric diagnosis & hypothesis bridge",
            "cells": [
              {"type": "space", "pixels": 260},
              {"type": "space", "pixels": 350},
              {"type": "text", "text": "⚡ KẾT LUẬN TỪ ĐỐI CHIẾU CHỈ SỐ (METRIC DIAGNOSIS):\n1. Khoảng cách 23,8% giữ chân xuất phát chủ yếu từ tỷ lệ thoát giây đầu (36,0% vs 10,8%).\n2. Nhịp cắt cảnh 3s đầu của video nội bộ (0,8 nhịp) quá chậm so với chuẩn thị trường (2,4 nhịp).\n3. 4 mẫu winning hooks cho thấy người xem chỉ dừng lại khi có yếu tố giác quan (Sensory) hoặc nỗi đau da ngứa rát.", "pixels": 415},
              {"type": "text", "text": "🎯 GIẢ THUYẾT VÒNG MỚI (ROUND HYPOTHESIS):\nỨng dụng 4 công thức winning hooks vào Brand Assets: Cắt cảnh 0.8s lấy hình ảnh giọt nước bắn trên lá rau má tươi để kéo tỷ lệ rớt 1s xuống dưới 15%.\n[Chấp thuận giả thuyết & Sang chọn hook]", "pixels": 415}
            ]
          },
          {
            "label": "Action transition to stage 02",
            "cells": [
              {"type": "space", "pixels": 260},
              {"type": "space", "pixels": 350},
              {"type": "text", "text": "Đã hoàn tất đối chiếu chỉ số và phân loại các winning hooks. Sẵn sàng tạo các biến thể hook riêng cho sản phẩm.", "pixels": 430},
              {"type": "link", "text": "Chuyển sang 02. Hook suggestion để chọn biến thể mới →", "href": "#hooks", "pixels": 400}
            ]
          },
          {
            "label": "Footer",
            "cells": [
              {"type": "space", "pixels": 260},
              {"type": "space", "pixels": 350},
              {"type": "text", "text": "Lạc Hồng / 01. AI analysis: Đối chiếu thuần số liệu song song, bấm 2 nút trên cùng để xem chi tiết danh sách video thị trường và quảng cáo nội bộ.", "pixels": 830}
            ]
          }
        ]
      },
      "spec": {
        "goal": {
          "what": "Đối chiếu thuần số liệu (Purely Metrics) side-by-side giữa Winning Hooks trên thị trường và Our Performance của thương hiệu, với 2 nút clickable trên cùng mở danh sách các video thắng lớn khác nhau hoặc danh sách quảng cáo của bạn.",
          "audience": "Người sáng tạo nội dung và nhà tiếp thị muốn nắm bắt khoảng cách số liệu chuẩn xác và duyệt qua nhiều mẫu video thực tế.",
          "successCriteria": "Khu vực side-by-side hiển thị thuần số liệu rõ ràng; 2 nút clickable phía trên kích hoạt danh sách video thắng lớn (đầy đủ các hook khác nhau) và danh sách quảng cáo nội bộ."
        },
        "format": {
          "canvas": "Độ rộng 1440px: File Tree (260px) + Chat 30% (350px) + Dashboard 70% (830px).",
          "safeMargins": "Đệm 20–24px mỗi cột; bảng metrics phân bổ 415px mỗi cột cân xứng tuyệt đối."
        },
        "layout": {
          "grid": "Thanh cây thư mục trái ngoài cùng, cột chat hỗ trợ, khu vực 2 clickable triggers trên cùng, 2 danh sách video mở rộng, bảng side-by-side thuần số liệu và thanh hành động.",
          "placement": "2 nút clickable ghim ngay trên đầu bảng so sánh -> Danh sách video mở rộng tương ứng -> Bảng đối chiếu thuần số liệu (Pure Metrics) -> Đường cong giữ chân từng giây -> Chẩn đoán & Giả thuyết -> Chuyển sang 02. Hook suggestion.",
          "hierarchy": "2 nút clickable mở danh sách video -> Bảng thuần số liệu side-by-side -> Bóc tách từng giây -> Đúc kết giả thuyết."
        },
        "typeSystem": {
          "display": "Be Vietnam Pro 32px tiêu đề, 22px chỉ số nổi bật.",
          "metadata": "10–12px nhãn chỉ số (3s retention, 1s drop-off, CTR, pacing cuts) và ID video.",
          "contrast": "Chữ và số liệu tương phản cao, định dạng rõ ràng giữa benchmark (xanh lá #346149) và chỉ số nội bộ (than chì/hổ phách)."
        },
        "colorMaterial": {
          "foundation": "Nền ấm #f5f4f0 và chữ than chì #242823.",
          "surfaces": "Thẻ bảng metrics trắng tinh #ffffff viền 1px #dedfd7; nút clickable trên cùng có màu xanh sage dịu viền đậm nổi bật.",
          "borders": "1px #dedfd7; bo góc 10px.",
          "signal": "Xanh lá #346149 cho nút kích hoạt và chỉ số benchmark; hổ phách cho tỷ lệ thoát cần cải thiện."
        },
        "copy": {
          "headline": "01. AI analysis · Pure Metrics Side-by-Side & Video Lists",
          "subtitle": "Khu vực so sánh thuần số liệu với 2 nút clickable trên cùng mở danh sách nhiều winning hooks thị trường và quảng cáo của thương hiệu.",
          "actions": [
            {"label": "Winning Hooks (Xem danh sách video)", "href": "#winning-hooks-list"},
            {"label": "Our Performance (Xem quảng cáo của bạn)", "href": "#our-ads-list"},
            {"label": "Chuyển sang 02. Hook suggestion", "href": "#hooks"}
          ]
        },
        "constraints": {
          "font": "Be Vietnam Pro tiếng Việt chuẩn.",
          "accent": "Một màu xanh lá chủ đạo.",
          "container": "Phần side-by-side phải là thuần số liệu (purely metrics); có 2 nút clickable ở trên cùng để mở danh sách video thắng lớn (nhiều video khác nhau) và danh sách quảng cáo của bạn."
        },
        "negativePrompt": [
          "Không nhồi nhét video player trực tiếp vào giữa các dòng số liệu gây rối mắt.",
          "Không chỉ hiển thị duy nhất 1 video top 1 mà phải trình bày danh sách nhiều winning hooks khác nhau.",
          "Không làm mất tính năng mở danh sách quảng cáo của chính thương hiệu khi bấm nút Our Performance."
        ]
      }
    },
    {
      "id": "human-curation-hooks",
      "name": "Human Curation · 02 Hook suggestion & File Tree",
      "notes": "Giai đoạn 02: Hook suggestion (Human Curation). Kế thừa phân tích metrics và danh sách video từ 01. AI analysis cùng tài nguyên từ Cây thư mục (Brand Assets), AI chia thành hai phần riêng biệt: (1) Relevant winning hooks (các công thức thu hút cao đã chứng minh trên mạng xã hội) và (2) Hook for your product (lưới 4 video mock 3s được may đo riêng cho sản phẩm của thương hiệu). Người dùng lựa chọn các hook tối ưu để chuyển sang dựng video.",
      "design": {
        "layout": "split",
        "visual": "interface",
        "font": "modern",
        "colors": {
          "background": "#f5f4f0",
          "surface": "#ffffff",
          "ink": "#242823",
          "muted": "#6b7168",
          "accent": "#346149",
          "line": "#dedfd7"
        },
        "containerWidth": "1440px",
        "cornerRadius": "10px"
      },
      "hero": {
        "eyebrow": "DASHBOARD / 02. HOOK SUGGESTION · HUMAN CURATION",
        "topLabel": "lạc hồng.",
        "navigation": ["File Tree: Sắc Ngọc Khang ▾", "← 01 AI analysis", "02 Hook suggestion (Đang mở)", "03 Video creation →"],
        "footerLeft": "File Tree + Chat 30% / Dashboard 70%",
        "footerRight": "Giai đoạn 02 / 04"
      },
      "visual": {
        "imageUrl": "",
        "imageAlt": "",
        "caption": "Tuyển chọn hook dựa trên Brand Assets & Kết quả phân tích AI",
        "index": "03 / 06",
        "interface": {
          "label": "HUMAN CURATION · GIAI ĐOẠN 02",
          "title": "Người dùng chọn hook & quản lý Brand Assets",
          "description": "Hai phần riêng biệt: Winning hooks từ mạng xã hội & Hook may đo cho sản phẩm.",
          "metric": "4",
          "metricLabel": "Hook đề xuất"
        }
      },
      "wireframe": {
        "title": "Dashboard Wireframe / Human Curation · 02 Hook suggestion & File Tree",
        "rows": [
          {
            "label": "Header with file tree status",
            "cells": [
              {"type": "link", "text": "≡ Cây thư mục (Thu gọn)", "href": "#file-tree", "pixels": 260},
              {"type": "brand", "text": "lạc hồng.", "pixels": 180},
              {"type": "text", "text": "Sắc Ngọc Khang / Vòng 01 · Đã ứng dụng bài học từ 01. AI analysis", "pixels": 600},
              {"type": "link", "text": "← 01 AI analysis", "href": "#analysis", "pixels": 200},
              {"type": "link", "text": "03 Video creation →", "href": "#video", "pixels": 200}
            ]
          },
          {
            "label": "Workspace layout / File Tree 260px + Chat 350px + Dashboard 830px",
            "cells": [
              {"type": "visual", "text": "📂 CÂY THƯ MỤC DỰ ÁN\n\n▼ Sắc Ngọc Khang (Đang mở)\n  ▼ 📁 Brand Assets\n    ├── 🎬 broll-rau-ma.mp4 [Click để xem]\n    ├── 🖼 chai-serum.png [Click để xem]\n    ├── 📄 brand-voice.pdf [Click để xem]\n    └── ➕ [Thêm tài sản thương hiệu]\n  ▼ 📁 Hook Variants\n    ├── 🎥 hook-H01.mp4\n    ├── 🎥 hook-H02.mp4\n    └── 🎥 hook-H04.mp4\n  ► 📁 Market Telemetry\n► 📂 Mỹ phẩm Cocoon\n\n[+ Tạo dự án mới]", "pixels": 260},
              {"type": "text", "text": "Lạc Hồng\nCùng bạn làm nội dung\nDựa trên phát hiện từ 01. AI analysis (Winning footage dùng Sensory Hook văng nước đá và nhịp cắt 2.4 nhịp/3s), mình đã kết nối broll-rau-ma.mp4 và ảnh chai serum trong Brand Assets.\nAI đề xuất 4 góc mở đầu bên phải chia thành 2 phần: Winning hooks xã hội & Hook may đo riêng cho sản phẩm của bạn.\nNhắn cho Lạc Hồng hoặc đính kèm tệp…\n[Đính kèm 📎] [Gửi ↑]", "pixels": 350},
              {"type": "text", "text": "DASHBOARD / 02. HOOK SUGGESTION\nHook suggestion · Gợi ý & Tuyển chọn hook\nAI sử dụng Brand Assets và bài học số liệu từ 01. AI analysis để tạo 4 video hook mẫu 3s. Bạn chọn các hook phù hợp để đưa sang bước dựng video.", "pixels": 830}
            ]
          },
          {
            "label": "Four stage progress tabs (01 -> 02 -> 03 -> 04)",
            "cells": [
              {"type": "space", "pixels": 260},
              {"type": "space", "pixels": 350},
              {"type": "link", "text": "← 01 · AI analysis", "href": "#analysis", "pixels": 207},
              {"type": "link", "text": "02 · Hook suggestion (Đang mở)", "href": "#hooks", "pixels": 207},
              {"type": "link", "text": "03 · Video creation →", "href": "#video", "pixels": 208},
              {"type": "link", "text": "04 · Metrics", "href": "#metrics", "pixels": 208}
            ]
          },
          {
            "label": "Phần 2A: Relevant winning hooks (Social proven from online scan)",
            "cells": [
              {"type": "space", "pixels": 260},
              {"type": "space", "pixels": 350},
              {"type": "text", "text": "🔥 RELEVANT WINNING HOOKS (THAM KHẢO SOCIAL TỪ 01. AI ANALYSIS SCAN):\n• TikTok (W01 · 1.8M views · 83,4% 3s): “Đừng vội mua serum rau má nếu da chưa gặp 1 trong 3 tình trạng này…” [Áp dụng công thức]\n• Reels (W02 · 1.2M views · 81,2% 3s): “Routine làm dịu mẩn đỏ đúng 2 bước của một đứa da siêu nhạy cảm.” [Áp dụng công thức]\n• Shorts (W03 · 960K views · 80,8% 3s): “Tại sao bác sĩ da liễu luôn khuyên dùng chiết xuất rau má thay vì kem đặc khi kích ứng?” [Áp dụng công thức]\n• TikTok Spark (W04 · 1.5M views · 83,9% 3s): “Thử nghiệm bôi serum lên nửa mặt kích ứng và cái kết sau 1 đêm.” [Áp dụng công thức]", "pixels": 830}
            ]
          },
          {
            "label": "AI Adaptation Bridge",
            "cells": [
              {"type": "space", "pixels": 260},
              {"type": "space", "pixels": 350},
              {"type": "text", "text": "⚡ AI tích hợp 4 công thức winning hooks vào Brand Assets của thương hiệu để sinh ra 4 hook riêng bên dưới ↓", "pixels": 830}
            ]
          },
          {
            "label": "Phần 2B: Hook for your product (Lưới 4 video mock 3s)",
            "id": "hooks",
            "cells": [
              {"type": "space", "pixels": 260},
              {"type": "space", "pixels": 350},
              {"type": "visual", "text": "H01 · Nhu cầu & Giác quan (Áp dụng W01)\nDa nhạy cảm bôi gì cũng rát? Xem ngay cách lá rau má làm dịu tức thì.\nNguồn: broll-rau-ma.mp4 (Sensory splash)\nMock video · 03 giây\n[x] Đã chọn", "pixels": 415},
              {"type": "visual", "text": "H02 · Câu hỏi trúng đích (Áp dụng W02)\nBạn chọn serum rau má vì quảng cáo hay vì thành phần làm dịu thực sự?\nNguồn: broll-rau-ma.mp4\nMock video · 03 giây\n[x] Đã chọn", "pixels": 415}
            ]
          },
          {
            "label": "Hook grid / row 2",
            "cells": [
              {"type": "space", "pixels": 260},
              {"type": "space", "pixels": 350},
              {"type": "visual", "text": "H03 · Góc nhìn ngược (Áp dụng W03)\nThêm kem dưỡng chưa chắc là điều làn da kích ứng đang cầu cứu.\nNguồn: broll-rau-ma.mp4\nMock video · 03 giây\n[ ] Chưa chọn", "pixels": 415},
              {"type": "visual", "text": "H04 · Trải nghiệm thực tế (Áp dụng W04)\nCách mình dứt điểm cơn mẩn đỏ sau 1 đêm nhờ 3 giọt serum này.\nNguồn: chai-serum.png\nMock video · 03 giây\n[x] Đã chọn", "pixels": 415}
            ]
          },
          {
            "label": "Selection bar & Transition to stage 03",
            "cells": [
              {"type": "space", "pixels": 260},
              {"type": "space", "pixels": 350},
              {"type": "text", "text": "Đã chọn 3 hook (H01, H02, H04) · Tự động chuẩn bị ghép vào Brand Assets để dựng video.", "pixels": 490},
              {"type": "link", "text": "Tiếp tục: 03 Video creation →", "href": "#video", "pixels": 340}
            ]
          },
          {
            "label": "Footer",
            "cells": [
              {"type": "space", "pixels": 260},
              {"type": "space", "pixels": 350},
              {"type": "text", "text": "Lạc Hồng / Cây thư mục hỗ trợ thêm và điều chỉnh tài sản thương hiệu. Bấm vào tệp để mở Asset Inspector.", "pixels": 830}
            ]
          }
        ]
      },
      "spec": {
        "goal": {
          "what": "Màn hình Human Curation cho phép tuyển chọn hook dựa trên Cây thư mục (File Tree) và dữ liệu bóc tách từ 01. AI analysis.",
          "audience": "Creators và chủ shop muốn kiểm soát nội dung mở đầu trước khi xuất bản.",
          "successCriteria": "Phân tách rõ ràng giữa winning hooks xã hội và hook may đo sản phẩm; người dùng dễ dàng chọn 3 hook phù hợp."
        },
        "format": {
          "canvas": "Độ rộng 1440px: File Tree (260px) + Chat 30% (350px) + Dashboard 70% (830px).",
          "safeMargins": "Đệm 20–24px mỗi cột; cây thư mục có thể thu gọn linh hoạt."
        },
        "layout": {
          "grid": "Thanh cây thư mục trái, cột chat trao đổi, bảng điều khiển hiển thị 2 phần hook và thanh hành động.",
          "placement": "Phần 2A (Winning hooks tham khảo) ở trên -> Phần 2B (Hook may đo sản phẩm dạng lưới 2x2) ở dưới.",
          "hierarchy": "Bài học từ AI analysis -> Mẫu tham khảo xã hội -> Hook sản phẩm tùy biến."
        },
        "typeSystem": {
          "display": "Be Vietnam Pro 32px tiêu đề, 18px nội dung hook.",
          "metadata": "10–12px tên tệp nguồn và độ dài video 3s.",
          "contrast": "Chữ rõ nét, tương phản WCAG AA."
        },
        "colorMaterial": {
          "foundation": "Nền ấm #f5f4f0 và chữ than chì #242823.",
          "surfaces": "Thẻ hook trắng, cây thư mục phân cách bởi đường kẻ #dedfd7.",
          "borders": "1px #dedfd7; bo góc 10px.",
          "signal": "Xanh lá #346149 cho hook đã chọn và nút chuyển tiếp."
        },
        "copy": {
          "headline": "02. Hook suggestion & File Tree",
          "subtitle": "AI ứng dụng bài học từ 01. AI analysis và Brand Assets để tạo 4 video hook mẫu 3s.",
          "actions": [
            {"label": "Thêm tài sản thương hiệu", "href": "#file-tree"},
            {"label": "Tiếp tục: 03 Video creation", "href": "#video"}
          ]
        },
        "constraints": {
          "font": "Be Vietnam Pro tiếng Việt chuẩn.",
          "accent": "Một màu xanh lá chủ đạo.",
          "container": "Phải có 2 phần riêng biệt: Relevant winning hooks và Hook for your product."
        },
        "negativePrompt": [
          "Không gộp chung winning hooks xã hội với hook của sản phẩm gây lẫn lộn.",
          "Không làm đứt liên kết từ 01. AI analysis.",
          "Không ẩn khung chat và thanh cây thư mục."
        ]
      }
    },
    {
      "id": "asset-inspector",
      "name": "Asset Inspector · Right Hover Panel on Top of Dashboard",
      "notes": "Màn hình tương tác Tài sản (Asset Inspector). Khi người dùng nhấp vào bất kỳ tệp nào trong Cây thư mục (ví dụ: chai-serum.png hoặc broll-rau-ma.mp4), một thanh điều khiển và xem trước (Asset Inspector Hover Panel) sẽ trượt ra từ bên phải, hiển thị đè lên trên Dashboard. Người dùng có thể xem trước video/ảnh chất lượng cao, điều chỉnh tệp (đổi tên, thay thế tệp mới, chỉnh thẻ tag) và đóng panel khi hoàn tất.",
      "design": {
        "layout": "split",
        "visual": "interface",
        "font": "modern",
        "colors": {
          "background": "#f5f4f0",
          "surface": "#ffffff",
          "ink": "#242823",
          "muted": "#6b7168",
          "accent": "#346149",
          "line": "#dedfd7"
        },
        "containerWidth": "1440px",
        "cornerRadius": "10px"
      },
      "hero": {
        "eyebrow": "ASSET INSPECTOR / XEM TRƯỚC & ĐIỀU CHỈNH TỆP",
        "topLabel": "lạc hồng.",
        "navigation": ["Đang xem: chai-serum.png ▾", "Đóng panel [✕]", "Về trò chuyện"],
        "footerLeft": "File Tree + Chat 30% / Dashboard + Asset Flyout",
        "footerRight": "Inspector Active"
      },
      "visual": {
        "imageUrl": "",
        "imageAlt": "",
        "caption": "Asset Flyout trượt từ bên phải đè lên Dashboard",
        "index": "04 / 06",
        "interface": {
          "label": "BRAND ASSET · IMAGE PREVIEW",
          "title": "chai-serum.png · 1080x1920 PNG",
          "description": "Ảnh sản phẩm có nền trong suốt. Đang dùng làm layer trung tâm trong Hook H01 & H04.",
          "metric": "2.4 MB",
          "metricLabel": "Dung lượng tệp"
        }
      },
      "wireframe": {
        "title": "Interactive Wireframe / Right Hover Asset Inspector on top of Dashboard",
        "rows": [
          {
            "label": "Header with active asset context",
            "cells": [
              {"type": "link", "text": "≡ Cây thư mục", "href": "#file-tree", "pixels": 260},
              {"type": "brand", "text": "lạc hồng.", "pixels": 180},
              {"type": "text", "text": "Sắc Ngọc Khang / Đang xem tệp: chai-serum.png trong Brand Assets", "pixels": 560},
              {"type": "link", "text": "Đóng Asset Flyout [✕]", "href": "#close-inspector", "pixels": 220},
              {"type": "link", "text": "Về trò chuyện", "href": "first-onboarding-screen-redesigned.html", "pixels": 220}
            ]
          },
          {
            "label": "Workspace with File Tree, Chat, Dashboard & Right Asset Flyout Overlay",
            "id": "file-tree",
            "cells": [
              {"type": "visual", "text": "📂 CÂY THƯ MỤC\n\n▼ Sắc Ngọc Khang\n  ▼ 📁 Brand Assets\n    ├── 🎬 broll-rau-ma.mp4\n    ├── 🖼 chai-serum.png ◄ [ĐANG CHỌN]\n    ├── 📄 brand-voice.pdf\n    └── ➕ [Thêm tài sản]\n  ► 📁 Hook Variants\n  ► 📁 Market Telemetry", "pixels": 260},
              {"type": "text", "text": "Lạc Hồng\nTrợ lý sáng tạo\nBạn đang kiểm tra tệp 'chai-serum.png'.\nTệp này có độ phân giải cao, phù hợp để tạo hiệu ứng zoom 3 giây đầu.\nBạn có muốn đổi tên hoặc nạp ảnh phiên bản mới không?", "pixels": 340},
              {"type": "text", "text": "DASHBOARD (LỚP NỀN PHÍA DƯỚI FLYOUT)\n02. Hook suggestion\n(Các thẻ hook H01, H02, H03, H04 nằm phía dưới lớp phủ mờ khi Asset Inspector trượt ra từ bên phải).", "pixels": 500},
              {"type": "visual", "text": "ASSET INSPECTOR (FLYOUT TỪ PHẢI) [✕]\n\n🖼 XEM TRƯỚC TÀI SẢN:\n[ Khung hình 9:16 - Chai serum rau má ]\nĐộ phân giải: 1080 x 1920 px (PNG)\nDung lượng: 2.4 MB · Nền trong suốt\n\n⚙️ ĐIỀU CHỈNH TỆP (ADJUST FILE):\n• [ Đổi tên tệp: chai-serum-v2.png ]\n• [ Thay thế tệp mới (Upload replacement) ]\n• [ Gán vào kịch bản: H01, H04 ]\n• [ Xóa tài sản này khỏi dự án ]\n\n✓ Tệp đang hoạt động tốt trong 2 video mẫu.", "pixels": 340}
            ]
          },
          {
            "label": "Asset management action row",
            "cells": [
              {"type": "space", "pixels": 260},
              {"type": "space", "pixels": 340},
              {"type": "text", "text": "Dashboard vẫn giữ nguyên tiến trình tuyển chọn hook.", "pixels": 500},
              {"type": "link", "text": "Lưu thay đổi tệp & Đóng inspector →", "href": "#close-inspector", "pixels": 340}
            ]
          },
          {
            "label": "Footer",
            "cells": [
              {"type": "space", "pixels": 260},
              {"type": "space", "pixels": 340},
              {"type": "text", "text": "Lạc Hồng / Asset Inspector cho phép xem trước và điều chỉnh tài sản mà không làm gián đoạn luồng làm việc chính.", "pixels": 840}
            ]
          }
        ]
      },
      "spec": {
        "goal": {
          "what": "Panel trượt từ bên phải (Right Hover Flyout) để render xem trước và cho phép điều chỉnh tệp khi nhấp vào cây thư mục.",
          "audience": "Người dùng muốn xem chi tiết video footage, ảnh sản phẩm hoặc tài liệu và điều chỉnh tệp.",
          "successCriteria": "Render trực quan tệp trên dashboard, cung cấp đủ công cụ chỉnh sửa (đổi tên, thay thế, xóa) và đóng mở mượt mà."
        },
        "format": {
          "canvas": "Độ rộng 1440px: File Tree (260px) + Chat 30% (340px) + Dashboard nền (500px) + Asset Flyout (340px).",
          "safeMargins": "Đệm 16–20px trong flyout; có nút đóng ✕ rõ ràng ở góc trên bên phải."
        },
        "layout": {
          "grid": "Thanh cây thư mục trái, cột chat, khu vực dashboard phía dưới và Asset Flyout overlay bên phải.",
          "placement": "Asset Flyout ghim cạnh phải, trượt ra khi bấm vào tệp trong cây thư mục.",
          "hierarchy": "Tệp được chọn nổi bật -> Xem trước trực quan -> Công cụ điều chỉnh tệp."
        },
        "typeSystem": {
          "display": "Be Vietnam Pro 20px tiêu đề flyout, 14px tên tệp.",
          "metadata": "10–12px dung lượng, kích thước pixel, codec định dạng.",
          "contrast": "Chữ rõ ràng, nút điều chỉnh phân biệt giữa hành động chỉnh sửa và xóa."
        },
        "colorMaterial": {
          "foundation": "Nền ấm #f5f4f0 và than chì #242823.",
          "surfaces": "Thanh Asset Flyout trắng tinh #ffffff, viền bóng đổ box-shadow 4px 0 24px rgba(0,0,0,0.12).",
          "borders": "1px #dedfd7; bo góc 10px.",
          "signal": "Xanh lá #346149 cho lưu thay đổi; đỏ trầm cho xóa tệp."
        },
        "copy": {
          "headline": "Asset Inspector · Xem trước & Điều chỉnh tệp",
          "subtitle": "Xem trước video/ảnh chất lượng cao và tinh chỉnh tài sản thương hiệu trực tiếp từ cây thư mục.",
          "actions": [
            {"label": "Thay thế tệp mới", "href": "#file-tree"},
            {"label": "Đóng panel", "href": "#close-inspector"}
          ]
        },
        "constraints": {
          "font": "Be Vietnam Pro tiếng Việt chuẩn.",
          "accent": "Một màu xanh lá chủ đạo.",
          "container": "Hỗ trợ phát video/audio hoặc xem ảnh trong flyout; không gây giật lag cho dashboard nền."
        },
        "negativePrompt": [
          "Không điều hướng người dùng sang trang mới chỉ để xem một bức ảnh hay clip ngắn.",
          "Không làm mất ngữ cảnh công việc đang dở trên Dashboard.",
          "Không khóa cứng giao diện khi flyout đang mở."
        ]
      }
    },
    {
      "id": "human-curation-video",
      "name": "Human Curation · 03 Video creation & Duyệt kịch bản",
      "notes": "Giai đoạn 03: Video creation (Human Curation). 3 hook đã chọn được ghép cùng Brand Assets (b-roll footage + ảnh sản phẩm) thành 3 video hoàn chỉnh 9:16. Người dùng kiểm duyệt kịch bản, chỉnh sửa qua chat 30% và duyệt đăng bài. Sau khi duyệt xong, hệ thống thông báo video bắt đầu phân phối và mời người dùng chuyển sang 04. Metrics để theo dõi chu kỳ số liệu.",
      "design": {
        "layout": "split",
        "visual": "interface",
        "font": "modern",
        "colors": {
          "background": "#f5f4f0",
          "surface": "#ffffff",
          "ink": "#242823",
          "muted": "#6b7168",
          "accent": "#346149",
          "line": "#dedfd7"
        },
        "containerWidth": "1440px",
        "cornerRadius": "10px"
      },
      "hero": {
        "eyebrow": "DASHBOARD / 03. VIDEO CREATION · HUMAN REVIEW",
        "topLabel": "lạc hồng.",
        "navigation": ["File Tree: Sắc Ngọc Khang ▾", "← 02 Hook suggestion", "03 Video creation (Đang mở)", "04 Metrics →"],
        "footerLeft": "File Tree + Chat 30% / Dashboard 70%",
        "footerRight": "Giai đoạn 03 / 04"
      },
      "visual": {
        "imageUrl": "",
        "imageAlt": "",
        "caption": "Duyệt kịch bản & Xuất bản bởi người dùng",
        "index": "05 / 06",
        "interface": {
          "label": "HUMAN CURATION · GIAI ĐOẠN 03",
          "title": "Người dùng duyệt & xuất bản 3 phiên bản",
          "description": "Tài sản Brand Assets đã ghép vào video 9:16. Sau khi duyệt, chuyển sang 04. Metrics.",
          "metric": "3/3",
          "metricLabel": "Đã duyệt"
        }
      },
      "wireframe": {
        "title": "Dashboard Wireframe / Human Curation · 03 Video creation & Duyệt đăng",
        "rows": [
          {
            "label": "Header with file tree status",
            "cells": [
              {"type": "link", "text": "≡ Cây thư mục", "href": "#file-tree", "pixels": 260},
              {"type": "brand", "text": "lạc hồng.", "pixels": 180},
              {"type": "text", "text": "Sắc Ngọc Khang / Vòng 01 · 3 phiên bản video đang chuẩn bị", "pixels": 600},
              {"type": "link", "text": "← 02 Hook suggestion", "href": "#hooks", "pixels": 200},
              {"type": "link", "text": "04 Metrics →", "href": "#metrics", "pixels": 200}
            ]
          },
          {
            "label": "Workspace layout / File Tree 260px + Chat 350px + Dashboard 830px",
            "cells": [
              {"type": "visual", "text": "📂 CÂY THƯ MỤC\n\n▼ Sắc Ngọc Khang\n  ► 📁 Brand Assets (3 tệp)\n  ▼ 📁 Hook Variants\n    ├── 🎥 V01-H01.mp4 [Đã duyệt]\n    ├── 🎥 V02-H02.mp4 [Đã duyệt]\n    └── 🎥 V04-H04.mp4 [Đã duyệt]\n  ► 📁 Telemetry Data", "pixels": 260},
              {"type": "text", "text": "Lạc Hồng\nCuộc trò chuyện của bạn\nĐang chỉnh V02 · H02\nGửi câu mở đầu mới bạn muốn dùng nếu cần điều chỉnh lại từ ngữ.\nNhắn cho Lạc Hồng…\n[Đính kèm 📎] [Gửi ↑]", "pixels": 350},
              {"type": "text", "text": "DASHBOARD / 03. VIDEO CREATION\nVideo creation & Duyệt đăng\nXem từng phiên bản ghép với Brand Assets, chỉnh sửa trong chat hoặc bấm duyệt để đưa video lên kênh.", "pixels": 830}
            ]
          },
          {
            "label": "Four stage progress tabs (01 -> 02 -> 03 -> 04)",
            "cells": [
              {"type": "space", "pixels": 260},
              {"type": "space", "pixels": 350},
              {"type": "link", "text": "01 · AI analysis", "href": "#analysis", "pixels": 207},
              {"type": "link", "text": "← 02 · Hook suggestion", "href": "#hooks", "pixels": 207},
              {"type": "link", "text": "03 · Video creation (Đang mở)", "href": "#video", "pixels": 208},
              {"type": "link", "text": "04 · Metrics →", "href": "#metrics", "pixels": 208}
            ]
          },
          {
            "label": "Three hook + video cards for human review",
            "id": "video",
            "cells": [
              {"type": "space", "pixels": 260},
              {"type": "space", "pixels": 350},
              {"type": "visual", "text": "V01 · H01 · Nhu cầu & Giác quan\nDa nhạy cảm bôi gì cũng rát? Xem lá rau má làm dịu tức thì.\nKhung 9:16 · Ghép broll-rau-ma.mp4\n✓ Người dùng đã duyệt", "pixels": 276},
              {"type": "visual", "text": "V02 · H02 · Câu hỏi\nBạn chọn serum rau má dựa trên điều gì?\nKhung 9:16 · Ghép broll-rau-ma.mp4\n✓ Người dùng đã duyệt", "pixels": 277},
              {"type": "visual", "text": "V04 · H04 · Trải nghiệm\nCách mình đưa serum vào thói quen hàng ngày.\nKhung 9:16 · Ghép chai-serum.png\n✓ Người dùng đã duyệt", "pixels": 277}
            ]
          },
          {
            "label": "Human actions on cards",
            "cells": [
              {"type": "space", "pixels": 260},
              {"type": "space", "pixels": 350},
              {"type": "text", "text": "Edit in chat\n✓ Đã duyệt\nTải file .mp4", "pixels": 276},
              {"type": "text", "text": "Edit in chat\n✓ Đã duyệt\nTải file .mp4", "pixels": 277},
              {"type": "text", "text": "Edit in chat\n✓ Đã duyệt\nTải file .mp4", "pixels": 277}
            ]
          },
          {
            "label": "Handoff to Stage 04 Metrics notice",
            "cells": [
              {"type": "space", "pixels": 260},
              {"type": "space", "pixels": 350},
              {"type": "text", "text": "HOÀN TẤT BƯỚC DỰNG & DUYỆT VIDEO:\n3 video đã được duyệt và chuyển sang hàng đợi xuất bản tự động.\nDo số liệu tương tác cần thời gian phân phối thực tế (sau 2h, 6h, 24h, 48h, 72h), bạn có thể quay lại sau và chuyển sang '04. Metrics' để theo dõi dữ liệu đo lường tự động.", "pixels": 830}
            ]
          },
          {
            "label": "Navigation to Metrics",
            "cells": [
              {"type": "space", "pixels": 260},
              {"type": "space", "pixels": 350},
              {"type": "link", "text": "← Quay lại sửa chọn hook (Giai đoạn 02)", "href": "#hooks", "pixels": 415},
              {"type": "link", "text": "Chuyển sang [04. Metrics (Đo lường tự động)] →", "href": "#metrics", "pixels": 415}
            ]
          },
          {
            "label": "Footer",
            "cells": [
              {"type": "space", "pixels": 260},
              {"type": "space", "pixels": 350},
              {"type": "text", "text": "Lạc Hồng / Đã hoàn tất phần duyệt video. 04. Metrics sẽ tự động đo lường số liệu khi video lên sóng.", "pixels": 830}
            ]
          }
        ]
      },
      "spec": {
        "goal": {
          "what": "Xem kịch bản ghép với Brand Assets, chỉnh sửa qua chat và duyệt đăng tải.",
          "audience": "Người sáng tạo nội dung kiểm duyệt chất lượng trước khi phân phối.",
          "successCriteria": "Duyệt từng phiên bản độc lập và chuyển giao sang giai đoạn 04. Metrics."
        },
        "format": {
          "canvas": "Độ rộng 1440px: File Tree (260px) + Chat 30% (350px) + Dashboard 70% (830px).",
          "safeMargins": "Đệm 20–24px mỗi cột; trên mobile các thẻ video xếp chồng dọc."
        },
        "layout": {
          "grid": "Thanh cây thư mục trái ngoài cùng, cột chat hỗ trợ, bảng làm việc 3 thẻ video kèm thông báo bàn giao.",
          "placement": "Header chứa link chuyển chế độ; nút chuyển chế độ ở cuối trang.",
          "hierarchy": "Xem video -> Duyệt -> Thông báo bàn giao sang 04. Metrics."
        },
        "typeSystem": {
          "display": "Be Vietnam Pro 32px tiêu đề.",
          "metadata": "10–12px ID video và trạng thái duyệt.",
          "contrast": "Chữ rõ ràng, dễ phân biệt giữa video đã duyệt và chưa duyệt."
        },
        "colorMaterial": {
          "foundation": "Nền ấm #f5f4f0 và than chì #242823.",
          "surfaces": "Thẻ video trắng, hộp thông báo chuyển đổi màu be dịu viền hổ phách.",
          "borders": "1px #dedfd7; bo góc 10px.",
          "signal": "Xanh lá #346149 cho trạng thái đã duyệt thành công."
        },
        "copy": {
          "headline": "03. Video creation & Duyệt đăng",
          "subtitle": "Xem từng phiên bản ghép với Brand Assets, chỉnh sửa trong chat hoặc bấm duyệt để đưa video lên kênh.",
          "actions": [
            {"label": "Edit in chat", "href": "#video"},
            {"label": "Chuyển sang 04. Metrics", "href": "#metrics"}
          ]
        },
        "constraints": {
          "font": "Be Vietnam Pro tiếng Việt.",
          "accent": "Một màu xanh lá chủ đạo.",
          "container": "Hiển thị rõ ràng thông báo số liệu không có ngay lập tức; chuyển sang 04. Metrics khi có dữ liệu."
        },
        "negativePrompt": [
          "Không tự động xuất bản khi chưa có sự xác nhận của người dùng.",
          "Không làm mất liên kết chuyển đổi giữa các giai đoạn.",
          "Không ẩn khung chat khi duyệt video."
        ]
      }
    },
    {
      "id": "ai-loop-metrics",
      "name": "AI Loop · 04 Metrics & Telemetry (Đo lường tự động)",
      "notes": "Giai đoạn 04: Metrics. Người dùng quay lại phân hệ này sau khi video đã lên sóng (T+2h, 6h, 24h, 48h, 72h). Cây thư mục bên trái tự động bổ sung thư mục 'Telemetry Data' chứa các tệp JSON số liệu. Khung chat 30% giữ vai trò trợ lý dữ liệu AI. Dashboard hiển thị bộ lọc mốc thời gian tự động, bảng so sánh hiệu quả giữa các hook, và khi chạm mốc 72h, toàn bộ dữ liệu hiệu suất và video thực tế sẽ được tổng kết để chuyển tiếp làm đầu vào cho 01. AI analysis của Vòng lặp tiếp theo (Loop 02).",
      "design": {
        "layout": "split",
        "visual": "interface",
        "font": "modern",
        "colors": {
          "background": "#f5f4f0",
          "surface": "#ffffff",
          "ink": "#242823",
          "muted": "#6b7168",
          "accent": "#346149",
          "line": "#dedfd7"
        },
        "containerWidth": "1440px",
        "cornerRadius": "10px"
      },
      "hero": {
        "eyebrow": "DASHBOARD / 04. METRICS · AUTOMATED TELEMETRY",
        "topLabel": "lạc hồng.",
        "navigation": ["File Tree: Sắc Ngọc Khang ▾", "← 03 Video creation", "04 Metrics (Đang mở)", "01 AI analysis (Vòng 02) ↻"],
        "footerLeft": "File Tree + Chat 30% / Dashboard 70%",
        "footerRight": "Giai đoạn 04 / 04"
      },
      "visual": {
        "imageUrl": "",
        "imageAlt": "",
        "caption": "AI thu thập chỉ số giữ chân & chuẩn bị dữ liệu cho vòng tiếp theo",
        "index": "06 / 06",
        "interface": {
          "label": "AI LOOP · GIAI ĐOẠN 04 (METRICS & LOOP HANDOFF)",
          "title": "H01 dẫn đầu với 67,8% xem qua 3 giây",
          "description": "Dữ liệu mốc 72h hoàn tất; sẵn sàng đưa dữ liệu vào 01. AI analysis cho Vòng 02.",
          "metric": "121.900",
          "metricLabel": "Lượt xem tự động"
        }
      },
      "wireframe": {
        "title": "Dashboard Wireframe / 04. Metrics & Telemetry (Đo lường tự động & Chuyển giao vòng mới)",
        "rows": [
          {
            "label": "Header with file tree status",
            "cells": [
              {"type": "link", "text": "≡ Cây thư mục", "href": "#file-tree", "pixels": 260},
              {"type": "brand", "text": "lạc hồng.", "pixels": 180},
              {"type": "text", "text": "Sắc Ngọc Khang / Vòng 01 · Dữ liệu mốc 24h/72h đã đồng bộ tự động", "pixels": 600},
              {"type": "link", "text": "Về trò chuyện", "href": "first-onboarding-screen-redesigned.html", "pixels": 200},
              {"type": "link", "text": "Vòng mới: 01 AI analysis ↻", "href": "#analysis", "pixels": 200}
            ]
          },
          {
            "label": "Workspace layout / File Tree 260px + Chat 350px + Dashboard 830px",
            "cells": [
              {"type": "visual", "text": "📂 CÂY THƯ MỤC\n\n▼ Sắc Ngọc Khang\n  ► 📁 Brand Assets (3 tệp)\n  ► 📁 Hook Variants (3 tệp)\n  ▼ 📁 Telemetry Data\n    ├── 📊 round-01-24h.json [Click xem]\n    ├── 📊 round-01-72h-final.json\n    └── 📝 round-01-learning.md\n► 📂 Mỹ phẩm Cocoon", "pixels": 260},
              {"type": "text", "text": "Lạc Hồng\nTrợ lý phân tích số liệu AI\nĐang xem mốc: 24 giờ sau đăng.\nHook H01 đang có tỷ lệ giữ chân 3s tốt nhất (67,8%), cao hơn trung bình (58,5%).\nH03 bị drop-off nhiều ở giây thứ 2 do nhịp chuyển cảnh chậm.\nKhi kết thúc 72h, số liệu này cùng video H01 sẽ trở thành tệp đầu vào để đưa lên 01. AI analysis của Vòng 02 đối chiếu tiếp với các winning ads mới nhất trên thị trường!\nNhắn cho Lạc Hồng…\n[Đính kèm 📎] [Gửi ↑]", "pixels": 350},
              {"type": "text", "text": "DASHBOARD / 04. METRICS\nMetrics & Telemetry · Đo lường tự động & Đóng vòng lặp\nAI tự động kéo dữ liệu từ TikTok, Reels, Shorts theo lịch trình. Sau 72h, kết quả chuyển tiếp trực tiếp vào 01. AI analysis của vòng tiếp theo.", "pixels": 830}
            ]
          },
          {
            "label": "Four stage progress tabs (01 -> 02 -> 03 -> 04)",
            "cells": [
              {"type": "space", "pixels": 260},
              {"type": "space", "pixels": 350},
              {"type": "link", "text": "01 · AI analysis", "href": "#analysis", "pixels": 207},
              {"type": "link", "text": "02 · Hook suggestion", "href": "#hooks", "pixels": 207},
              {"type": "link", "text": "03 · Video creation", "href": "#video", "pixels": 208},
              {"type": "link", "text": "04 · Metrics (Đang mở)", "href": "#metrics", "pixels": 208}
            ]
          },
          {
            "label": "AI loop automated telemetry banner",
            "cells": [
              {"type": "space", "pixels": 260},
              {"type": "space", "pixels": 350},
              {"type": "text", "text": "TRẠNG THÁI VÒNG LẶP AI TỰ ĐỘNG (SCHEDULED INGESTION):\n✓ Mốc 2h: Hoàn tất · ✓ Mốc 6h: Hoàn tất · ✓ Mốc 24h: Đang hiển thị.\n⏳ Mốc 48h: Đang đếm ngược (còn 23h 40m) · ⏳ Mốc 72h: Chốt vòng lặp & Đưa số liệu vào 01. AI analysis (Vòng 02).\nDữ liệu được đồng bộ tự động qua API, không cần thao tác thủ công.", "pixels": 830}
            ]
          },
          {
            "label": "Measurement filters",
            "id": "metrics",
            "cells": [
              {"type": "space", "pixels": 260},
              {"type": "space", "pixels": 350},
              {"type": "text", "text": "Nền tảng đăng tải:\nTất cả nền tảng / TikTok / YouTube Shorts / Facebook Reels", "pixels": 415},
              {"type": "text", "text": "Mốc thời gian phân phối:\n2 giờ / 6 giờ / [24 giờ - Đang chọn] / 48 giờ / 72 giờ", "pixels": 415}
            ]
          },
          {
            "label": "Metric summary cards at 24 hours",
            "cells": [
              {"type": "space", "pixels": 260},
              {"type": "space", "pixels": 350},
              {"type": "text", "text": "Tổng lượt xem\n121.900\nTổng 3 nền tảng", "pixels": 276},
              {"type": "text", "text": "Xem qua 3 giây\n58,5%\nTrọng số lượt xem", "pixels": 277},
              {"type": "text", "text": "Thời gian xem TB\n11,7 giây\nBình quân theo view", "pixels": 277}
            ]
          },
          {
            "label": "Comparison table across variants at 24 hours",
            "cells": [
              {"type": "space", "pixels": 260},
              {"type": "space", "pixels": 350},
              {"type": "text", "text": "Bảng so sánh hiệu quả các phiên bản hook sau 24h\nPhiên bản · Hook · Lượt xem · Xem qua 3 giây · Chi tiết nền tảng\nV01 · H01 Nhu cầu & Giác quan · 40.000 · 67,8% (Dẫn đầu) · Xem chi tiết\nV02 · H02 Câu hỏi trúng đích · 27.500 · 53,1% · Xem chi tiết\nV03 · H03 Góc nhìn ngược · 22.400 · 45,8% · Xem chi tiết\nV04 · H04 Trải nghiệm thực tế · 32.000 · 60,4% · Xem chi tiết\nLưu ý: Tỷ lệ giữ chân 3s được chuẩn hóa theo cỡ mẫu phân phối của từng nền tảng.", "pixels": 830}
            ]
          },
          {
            "label": "Continuous loop closure banner",
            "cells": [
              {"type": "space", "pixels": 260},
              {"type": "space", "pixels": 350},
              {"type": "text", "text": "TỔNG KẾT MỐC 72H & BÀN GIAO VÒNG LẶP KẾ TIẾP:\nPhiên bản V01 (H01) chiến thắng với 67,8% giữ chân 3s (72.000 lượt xem).\nDữ liệu và video thực tế này sẽ được đóng gói tự động thành hồ sơ 'round-01-performance' để chuyển giao sang 01. AI analysis của Vòng 02 đối chiếu với các mẫu quảng cáo viral mới nhất.", "pixels": 830}
            ]
          },
          {
            "label": "Next action: loop back to stage 01 for round 2",
            "cells": [
              {"type": "space", "pixels": 260},
              {"type": "space", "pixels": 350},
              {"type": "text", "text": "Vòng 01 hoàn tất mốc đo lường. Sẵn sàng cho chu kỳ cải tiến mới.", "pixels": 430},
              {"type": "link", "text": "Đưa dữ liệu vào 01. AI analysis (Vòng 02) để đối chiếu footage mới →", "href": "#analysis", "pixels": 400}
            ]
          },
          {
            "label": "Footer",
            "cells": [
              {"type": "space", "pixels": 260},
              {"type": "space", "pixels": 350},
              {"type": "text", "text": "Lạc Hồng / 04. Metrics khép kín vòng lặp học hỏi liên tục. Dữ liệu thực chiến là nền tảng khởi đầu cho vòng lặp kế tiếp.", "pixels": 830}
            ]
          }
        ]
      },
      "spec": {
        "goal": {
          "what": "Hệ thống tự động thu thập và chuẩn hóa dữ liệu giữ chân người xem theo mốc thời gian, sau đó khép vòng lặp đưa dữ liệu sang 01. AI analysis của vòng tiếp theo.",
          "audience": "Người làm nội dung theo dõi tiến trình thử nghiệm sau khi video đã xuất bản và chuẩn bị vòng mới.",
          "successCriteria": "Xem được tiến trình thu thập số liệu tự động, lọc theo nền tảng/thời gian, đối chiếu tỷ lệ giữ chân 3s và kích hoạt vòng 2 dễ dàng."
        },
        "format": {
          "canvas": "Độ rộng 1440px: File Tree (260px) + Chat 30% (350px) + Dashboard 70% (830px).",
          "safeMargins": "Đệm 20–24px mỗi cột; bảng số liệu cuộn ngang mượt mà."
        },
        "layout": {
          "grid": "Thanh cây thư mục trái ngoài cùng, cột chat phân tích số liệu, bảng điều khiển số liệu tự động.",
          "placement": "Bộ lọc thời gian và 3 thẻ tóm tắt đặt trước bảng so sánh; banner bàn giao vòng lặp ở cuối bảng.",
          "hierarchy": "Mốc thời gian -> Tổng quan số liệu -> Bảng so sánh hook chi tiết -> Khép vòng lặp chuyển sang 01. AI analysis."
        },
        "typeSystem": {
          "display": "Be Vietnam Pro 32px tiêu đề.",
          "metadata": "10–12px nhãn bộ lọc và bảng dữ liệu.",
          "contrast": "Chữ rõ nét, số liệu nổi bật theo chuẩn hiển thị bảng biểu."
        },
        "colorMaterial": {
          "foundation": "Nền ấm #f5f4f0 và than chì #242823.",
          "surfaces": "Thẻ số liệu trắng, thanh trạng thái vòng lặp tự động màu sage dịu.",
          "borders": "1px #dedfd7; bo góc 10px.",
          "signal": "Xanh lá #346149 cho hook chiến thắng và nút khởi động vòng mới."
        },
        "copy": {
          "headline": "04. Metrics & Telemetry (Đo lường tự động)",
          "subtitle": "AI tự động kéo dữ liệu từ các nền tảng theo lịch trình và đóng gói dữ liệu cho Vòng 02.",
          "actions": [
            {"label": "Xem chi tiết", "href": "#metrics"},
            {"label": "Khởi động Vòng 02 trong 01. AI analysis", "href": "#analysis"}
          ]
        },
        "constraints": {
          "font": "Be Vietnam Pro chuẩn tiếng Việt.",
          "accent": "Một màu xanh lá chủ đạo.",
          "container": "Hiển thị rõ các mốc lịch trình (2h, 6h, 24h, 48h, 72h) và chuyển giao vòng lặp trơn tru."
        },
        "negativePrompt": [
          "Không trình bày dữ liệu như thể có ngay sau khi duyệt video.",
          "Không làm đứt liên kết khép vòng lặp quay về 01. AI analysis.",
          "Không che mất cây thư mục dự án."
        ]
      }
    }
  ]
}

with open('screens/wireframe_preview.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print('Successfully updated screens/wireframe_preview.json with pure metrics and clickable video lists')
