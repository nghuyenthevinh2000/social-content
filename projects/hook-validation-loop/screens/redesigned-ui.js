'use strict';

(() => {
  const $ = id => document.getElementById(id);
  const isDashboard = document.body.dataset.page === 'dashboard';
  const storageKey = 'lac-hong-redesign-v1';
  const sampleProduct = 'Mình bán serum rau má Sắc Ngọc Khang cho người có da nhạy cảm.';
  const opening = 'Bạn đang làm video cho sản phẩm nào? Gửi liên kết hoặc kể ngắn cho mình nghe nhé.';
  const hookDefaults = [
    {id: 'H01', angle: 'Nhu cầu', text: 'Da nhạy cảm? Bắt đầu với một bước chăm sóc đơn giản.', theme: 'sage'},
    {id: 'H02', angle: 'Câu hỏi', text: 'Bạn chọn serum rau má dựa trên điều gì?', theme: 'clay'},
    {id: 'H03', angle: 'Góc nhìn khác', text: 'Thêm sản phẩm chưa chắc là điều làn da bạn cần.', theme: 'olive'},
    {id: 'H04', angle: 'Trải nghiệm', text: 'Đây là cách mình đưa serum rau má vào thói quen hằng ngày.', theme: 'sage'}
  ];
  // Explicit demo fixtures, independent of the user's selected/approved draft videos.
  const mockPlatforms = ['TikTok', 'YouTube Shorts', 'Facebook Reels'];
  const mockMetrics = {
    H01: [[18200, .72, 14.8], [12400, .66, 13.2], [9400, .62, 12.1]],
    H02: [[12600, .56, 11.2], [8500, .52, 10.4], [6400, .49, 9.8]],
    H03: [[10400, .48, 9.6], [7200, .45, 9.1], [4800, .42, 8.7]],
    H04: [[14800, .63, 12.5], [9600, .59, 11.8], [7600, .57, 11.1]]
  };
  const number = value => new Intl.NumberFormat('vi-VN', {maximumFractionDigits: 0}).format(value);
  const decimal = value => new Intl.NumberFormat('vi-VN', {minimumFractionDigits: 1, maximumFractionDigits: 1}).format(value);
  const percentage = value => `${decimal(value * 100)}%`;

  function sampleRows(platform = 'Tất cả nền tảng', window = '24 giờ') {
    const factor = {'2 giờ': .12, '6 giờ': .34, '24 giờ': 1, '48 giờ': 1.5, '72 giờ': 1.8}[window] || 1;
    return hookDefaults.map(hook => {
      const platforms = mockMetrics[hook.id].map(([views, retention, watch], index) => ({
        name: mockPlatforms[index], views: Math.round(views * factor), retention, watch
      })).filter(row => platform === 'Tất cả nền tảng' || row.name === platform);
      const views = platforms.reduce((sum, row) => sum + row.views, 0);
      return {...hook, platforms, views,
        retention: platforms.reduce((sum, row) => sum + row.views * row.retention, 0) / views,
        watch: platforms.reduce((sum, row) => sum + row.views * row.watch, 0) / views};
    });
  }
  const defaultState = () => ({product: '', messages: [{role: 'assistant', text: opening, attachments: []}], selected: [], edits: {}, interview: [], learning: '', hypothesis: '', nextDraft: false});
  let state = defaultState();
  let storageAvailable = true;
  try {
    const saved = JSON.parse(sessionStorage.getItem(storageKey));
    if (saved && typeof saved === 'object') {
      for (const key of ['product', 'learning', 'hypothesis']) if (typeof saved[key] === 'string') state[key] = saved[key].slice(0, 4000);
      if (Array.isArray(saved.messages)) state.messages = saved.messages.filter(m => m && ['user', 'assistant'].includes(m.role) && typeof m.text === 'string').slice(-100).map(m => ({role: m.role, text: m.text.slice(0, 6000), attachments: Array.isArray(m.attachments) ? m.attachments : []}));
      if (Array.isArray(saved.selected)) state.selected = [...new Set(saved.selected.filter(id => hookDefaults.some(h => h.id === id)))];
      if (Array.isArray(saved.interview)) state.interview = saved.interview.filter(s => typeof s === 'string').slice(0, 3);
      if (saved.edits && typeof saved.edits === 'object') for (const hook of hookDefaults) if (typeof saved.edits[hook.id] === 'string') state.edits[hook.id] = saved.edits[hook.id].slice(0, 4000);
      state.nextDraft = saved.nextDraft === true;
    }
  } catch { storageAvailable = false; }

  let toastTimer;
  let editingHook = null;
  let activeStage = 'hooks';
  const videoAssets = new Map();
  const approvals = new Set();

  function toast(text) {
    $('toast').textContent = text;
    $('toast').hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { $('toast').hidden = true; }, 4500);
  }

  function persist() {
    // Keep storage failures visible: cross-page chat persistence is unavailable in this case.
    try { sessionStorage.setItem(storageKey, JSON.stringify(state)); return true; }
    catch { storageAvailable = false; toast('Không lưu được trong trình duyệt. Lịch sử có thể mất khi đổi trang.'); return false; }
  }

  function make(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function getHooks() {
    const generic = [
      'Bạn muốn đơn giản hóa việc lựa chọn? Bắt đầu từ điều mình thực sự cần.',
      'Bạn chọn sản phẩm này dựa trên điều gì?',
      'Thêm lựa chọn chưa chắc đã giúp bạn chọn dễ hơn.',
      'Đây là cách mình dùng sản phẩm này trong một ngày bình thường.'
    ];
    const skincare = !state.product || /serum|rau má/i.test(state.product);
    return hookDefaults.map((h, index) => ({...h, text: state.edits[h.id] || (skincare ? h.text : generic[index])}));
  }

  const brandAssets = [
    {
      id: 'asset-1',
      name: 'raw-footage-serum-01.mp4',
      type: 'video',
      mime: 'video/mp4',
      size: '18.4 MB',
      resolution: '1080 × 1920 (9:16)',
      usage: 'Đang gắn vào Hook 01 · Vòng 01',
      hooks: ['H01'],
      icon: 'MP4',
      url: null
    },
    {
      id: 'asset-2',
      name: 'chai-serum-rau-ma.png',
      type: 'image',
      mime: 'image/png',
      size: '2.4 MB',
      resolution: '1200 × 1200 (1:1)',
      usage: 'Đang gắn vào Hook 01, H02',
      hooks: ['H01', 'H02'],
      icon: 'PNG',
      url: null
    },
    {
      id: 'asset-3',
      name: 'huong-dan-giong-dieu-brand.pdf',
      type: 'doc',
      mime: 'application/pdf',
      size: '450 KB',
      resolution: '12 trang · PDF A4',
      usage: 'Tài liệu hướng dẫn giọng điệu thương hiệu',
      hooks: [],
      icon: 'PDF',
      url: null
    }
  ];

  let currentInspectingAsset = null;
  let stagedChatFiles = [];

  function formatFileSize(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  function renderBrandAssetsTree() {
    const list = $('brand-asset-file-list');
    if (!list) return;
    list.replaceChildren();
    if ($('brand-asset-count')) {
      $('brand-asset-count').textContent = `${brandAssets.length} tệp`;
    }
    brandAssets.forEach(asset => {
      const node = make('div', 'tree-node tree-file');
      node.dataset.assetId = asset.id;
      node.setAttribute('role', 'treeitem');
      const row = make('div', 'tree-node-row file-row');
      const icon = make('span', 'tree-icon');
      if (asset.type === 'video') {
        icon.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18"/><line x1="7" y1="2" x2="7" y2="22"/><line x1="17" y1="2" x2="17" y2="22"/><line x1="2" y1="12" x2="22" y2="12"/></svg>';
      } else if (asset.type === 'image') {
        icon.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>';
      } else {
        icon.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>';
      }
      const label = make('span', 'tree-label', asset.name);
      label.title = asset.name;
      const btn = make('button', 'tree-file-action-btn', 'Xem');
      btn.type = 'button';
      btn.title = `Xem & chỉnh sửa ${asset.name}`;

      row.append(icon, label, btn);
      node.append(row);

      row.addEventListener('click', () => {
        if (window.openAssetInspector) window.openAssetInspector(asset);
      });

      list.append(node);
    });
  }

  function renderStagedChatFiles() {
    const staging = $('chat-attachments-staging');
    if (!staging) return;
    staging.replaceChildren();
    if (!stagedChatFiles.length) {
      staging.hidden = true;
      return;
    }
    staging.hidden = false;
    stagedChatFiles.forEach((file, index) => {
      const chip = make('div', 'staged-chip');
      const icon = make('span', `file-type-badge file-badge-${file.type}`, file.type === 'video' ? 'MP4' : file.type === 'image' ? 'PNG' : 'DOC');
      const name = make('span', 'chip-name', file.name);
      name.title = file.name;
      const size = make('span', 'chip-size', `(${file.size})`);
      const removeBtn = make('button', 'staged-chip-remove', '×');
      removeBtn.type = 'button';
      removeBtn.setAttribute('aria-label', `Bỏ đính kèm ${file.name}`);
      removeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        stagedChatFiles.splice(index, 1);
        renderStagedChatFiles();
      });
      chip.append(icon, name, size, removeBtn);
      staging.append(chip);
    });
  }

  function handleChatFiles(files) {
    if (!files || !files.length) return;
    for (const file of files) {
      const isVideo = file.type.startsWith('video/');
      const isImage = file.type.startsWith('image/');
      const item = {
        id: `asset-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
        name: file.name,
        type: isVideo ? 'video' : isImage ? 'image' : 'doc',
        mime: file.type || 'application/octet-stream',
        size: formatFileSize(file.size),
        resolution: isVideo ? '1080 × 1920 (9:16)' : isImage ? '1200 × 1200' : 'Tài liệu bổ sung',
        usage: 'Nạp qua chat · Brand Assets',
        hooks: [],
        icon: isVideo ? 'MP4' : isImage ? 'PNG' : 'DOC',
        url: URL.createObjectURL(file)
      };
      stagedChatFiles.push(item);
    }
    renderStagedChatFiles();
    toast(`Đã đính kèm ${files.length} tệp. Bấm Gửi để nạp vào cuộc trò chuyện và Brand Assets.`);
  }

  function renderMessages(shouldScroll = true) {
    const log = $('chat-log');
    log.replaceChildren();
    for (const message of state.messages) {
      const article = make('article', `message ${message.role}`);
      article.append(make('p', 'message-name', message.role === 'user' ? 'Bạn' : 'Lạc Hồng'), make('p', 'message-body', message.text));
      if (Array.isArray(message.attachments) && message.attachments.length) {
        const attachList = make('div', 'message-attachments');
        for (const att of message.attachments) {
          const chip = make('button', 'msg-attachment-chip');
          chip.type = 'button';
          chip.title = `Xem tệp ${att.name}`;
          const icon = make('span', `file-type-badge file-badge-${att.type || 'doc'}`, att.type === 'video' ? 'MP4' : att.type === 'image' ? 'PNG' : 'DOC');
          const name = make('span', 'chip-name', att.name);
          const size = make('span', 'small muted', `(${att.size})`);
          const inspect = make('span', 'chip-inspect', 'Xem ↗');
          chip.append(icon, name, size, inspect);
          chip.addEventListener('click', () => {
            const match = brandAssets.find(a => a.id === att.id || a.name === att.name) || att;
            if (window.openAssetInspector) window.openAssetInspector(match);
          });
          attachList.append(chip);
        }
        article.append(attachList);
      }
      log.append(article);
    }
    if (shouldScroll) {
      $('chat-scroll').scrollTop = $('chat-scroll').scrollHeight;
    }
    if (!isDashboard) {
      $('starter-prompts').hidden = Boolean(state.product);
      $('workspace-entry').hidden = !state.product;
    }
  }

  function addMessage(role, text, attachments = []) { state.messages.push({role, text, attachments}); }

  function versionLabel(id) { return `V${String(Number(id.slice(1))).padStart(2, '0')}`; }

  const interviewQuestions = [
    'Khách hàng chính của bạn là ai?',
    'Họ thường băn khoăn điều gì khi chọn sản phẩm?',
    'Bạn muốn giọng kể gần gũi hay tư vấn trực tiếp?'
  ];

  function handleChat(text, attachments = []) {
    const hasText = Boolean(text && text.trim());
    const hasAttachments = Boolean(attachments && attachments.length);
    if (!hasText && !hasAttachments) return;

    if (hasAttachments) {
      for (const att of attachments) {
        if (!brandAssets.some(a => a.name === att.name)) {
          brandAssets.push(att);
        }
      }
      renderBrandAssetsTree();
    }

    const messageText = hasText ? text.trim() : `Đã gửi ${attachments.length} tệp tài nguyên thương hiệu.`;
    addMessage('user', messageText, attachments);

    if (editingHook) {
      const id = editingHook;
      state.edits[id] = text.trim();
      const asset = videoAssets.get(id);
      if (asset) URL.revokeObjectURL(asset.url);
      videoAssets.delete(id);
      approvals.delete(id);
      setEditContext(null);
      addMessage('assistant', `Đã dùng nguyên văn câu bạn gửi cho ${versionLabel(id)} · ${id}. Đây là chỉnh sửa trực tiếp trong bản mẫu, không phải AI viết lại. Nạp bản dựng mới để xem và duyệt phiên bản này.`);
      renderHooks();
      renderVideos();
    } else if (hasAttachments && !hasText) {
      if (!state.product) {
        state.product = attachments[0].name.replace(/\.[^/.]+$/, '');
        addMessage('assistant', `Mình đã nhận ${attachments.length} tệp (${attachments.map(a => a.name).join(', ')}) và tự động lưu vào Brand Assets trong cây thư mục dự án. Mình tạm dùng tên "${state.product}" cho dự án này nhé. ${interviewQuestions[0]}`);
        if (isDashboard) { updateProject(); renderHooks(); }
      } else {
        addMessage('assistant', `Đã nhận ${attachments.length} tệp (${attachments.map(a => a.name).join(', ')}) và tự động lưu vào Brand Assets của dự án. Bạn có thể bấm vào tệp ở cây thư mục hoặc ngay trong tin nhắn để xem trước và gắn vào hook.`);
      }
    } else if (!state.product) {
      state.product = text.trim();
      const attachInfo = hasAttachments ? ` Mình cũng đã lưu ${attachments.length} tệp đính kèm vào Brand Assets.` : '';
      addMessage('assistant', isDashboard ? `Mình đã ghi lại thông tin bạn gửi.${attachInfo} ${interviewQuestions[0]}` : `Mình đã ghi lại thông tin bạn gửi.${attachInfo} Sang không gian làm việc để chọn hook nhé. Cuộc trò chuyện vẫn ở bên cạnh bạn.`);
      if (isDashboard) { updateProject(); renderHooks(); }
    } else if (isDashboard && state.interview.length < interviewQuestions.length) {
      state.interview.push(text.trim());
      const next = interviewQuestions[state.interview.length];
      const attachInfo = hasAttachments ? `(Đã lưu ${attachments.length} tệp đính kèm). ` : '';
      addMessage('assistant', next || `${attachInfo}Đã ghi lại câu trả lời của bạn. Bốn thẻ bên phải minh họa các hướng: nhu cầu, câu hỏi, góc nhìn khác và trải nghiệm. Chọn các hook muốn thử, rồi tiếp tục sang Video creation. Bản mẫu chưa dùng AI để cá nhân hóa hoặc dự báo hiệu quả.`);
    } else {
      const attachInfo = hasAttachments ? ` Đã lưu ${attachments.length} tệp vào Brand Assets.` : '';
      addMessage('assistant', isDashboard
        ? `Mình đã ghi lại yêu cầu này.${attachInfo} Bản mẫu chưa kết nối AI để trả lời tự do. Để đổi nội dung một hook, chọn Edit in chat ở phiên bản video tương ứng, rồi gửi chính xác câu mới bạn muốn dùng.`
        : `Mình đã giữ lại tin nhắn của bạn.${attachInfo} Mở không gian làm việc để tiếp tục trao đổi và chọn hook.`);
    }
    persist();
    renderMessages();
  }

  $('chat-form').addEventListener('submit', event => {
    event.preventDefault();
    const text = $('chat-input').value;
    const attachments = [...stagedChatFiles];
    if (!text.trim() && !attachments.length) return;
    $('chat-input').value = '';
    stagedChatFiles = [];
    renderStagedChatFiles();
    handleChat(text, attachments);
  });
  $('chat-input').addEventListener('keydown', event => {
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      $('chat-form').requestSubmit();
    }
  });

  const chatFileInput = $('chat-file-input');
  if (chatFileInput) {
    chatFileInput.addEventListener('change', e => {
      handleChatFiles(e.target.files);
      chatFileInput.value = '';
    });
  }

  document.querySelectorAll('.composer').forEach(form => {
    ['dragenter', 'dragover'].forEach(eventName => {
      form.addEventListener(eventName, e => {
        e.preventDefault();
        e.stopPropagation();
        form.classList.add('drag-over');
      });
    });
    ['dragleave', 'drop'].forEach(eventName => {
      form.addEventListener(eventName, e => {
        e.preventDefault();
        e.stopPropagation();
        form.classList.remove('drag-over');
      });
    });
    form.addEventListener('drop', e => {
      const dt = e.dataTransfer;
      if (dt && dt.files && dt.files.length) {
        handleChatFiles(dt.files);
      }
    });
  });

  function setupAssetInspector() {
    const flyout = $('asset-inspector-flyout');
    const backdrop = $('asset-inspector-backdrop');
    const closeBtn = $('inspector-close-btn');
    if (!flyout) return;

    function closeInspector() {
      flyout.dataset.open = 'false';
      if (backdrop) backdrop.hidden = true;
      currentInspectingAsset = null;
      if ($('inline-rename-form')) $('inline-rename-form').hidden = true;
      if ($('hook-assign-box')) $('hook-assign-box').hidden = true;
    }

    if (closeBtn) closeBtn.addEventListener('click', closeInspector);
    if (backdrop) backdrop.addEventListener('click', closeInspector);
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && flyout.dataset.open === 'true') {
        closeInspector();
      }
    });

    window.openAssetInspector = function(asset) {
      currentInspectingAsset = asset;
      flyout.dataset.open = 'true';
      if (backdrop) backdrop.hidden = false;

      $('inspector-asset-type').textContent = asset.type === 'video'
        ? 'TÀI NGUYÊN THƯƠNG HIỆU · VIDEO B-ROLL'
        : asset.type === 'image'
        ? 'TÀI NGUYÊN THƯƠNG HIỆU · HÌNH ẢNH SẢN PHẨM'
        : asset.type === 'hook'
        ? 'KỊCH BẢN MỞ ĐẦU · HOOK SCRIPT'
        : 'TÀI NGUYÊN THƯƠNG HIỆU · TÀI LIỆU GUIDELINE';
      $('inspector-asset-title').textContent = asset.name;

      const stage = $('inspector-preview-stage');
      stage.replaceChildren();

      if (asset.type === 'video') {
        const video = document.createElement('video');
        video.controls = true;
        video.playsInline = true;
        if (asset.url) {
          video.src = asset.url;
        } else {
          const canvas = document.createElement('canvas');
          canvas.width = 360;
          canvas.height = 640;
          const ctx = canvas.getContext('2d');
          ctx.fillStyle = '#2d3e34';
          ctx.fillRect(0, 0, 360, 640);
          ctx.fillStyle = '#63784f';
          ctx.fillRect(40, 100, 280, 440);
          ctx.fillStyle = '#ffffff';
          ctx.font = 'bold 20px system-ui';
          ctx.textAlign = 'center';
          ctx.fillText('SERUM RAU MÁ', 180, 300);
          ctx.font = '14px system-ui';
          ctx.fillText('B-roll 1080x1920', 180, 330);
          try {
            const stream = canvas.captureStream(15);
            video.srcObject = stream;
          } catch {
            video.poster = canvas.toDataURL();
          }
        }
        stage.append(video);
      } else if (asset.type === 'image') {
        const img = document.createElement('img');
        if (asset.url) {
          img.src = asset.url;
        } else {
          const canvas = document.createElement('canvas');
          canvas.width = 400;
          canvas.height = 400;
          const ctx = canvas.getContext('2d');
          ctx.fillStyle = '#f5f4ef';
          ctx.fillRect(0, 0, 400, 400);
          ctx.fillStyle = '#346149';
          ctx.beginPath();
          ctx.roundRect(140, 100, 120, 220, 20);
          ctx.fill();
          ctx.fillStyle = '#222222';
          ctx.fillRect(170, 60, 60, 40);
          ctx.fillStyle = '#ffffff';
          ctx.font = 'bold 13px system-ui';
          ctx.textAlign = 'center';
          ctx.fillText('SẮC NGỌC KHANG', 200, 200);
          ctx.font = '11px system-ui';
          ctx.fillText('Serum rau má 30ml', 200, 220);
          img.src = canvas.toDataURL();
        }
        img.alt = asset.name;
        stage.append(img);
      } else if (asset.type === 'hook') {
        const card = make('div', 'doc-preview-card');
        card.append(
          make('h4', '', `${asset.id} · Góc mở đầu: ${asset.angle}`),
          make('p', 'doc-excerpt', `"${asset.text}"`),
          make('p', 'small muted', 'Hook kịch bản được đề xuất dựa trên phân tích từ khóa khách hàng da nhạy cảm.')
        );
        stage.append(card);
      } else {
        const card = make('div', 'doc-preview-card');
        card.append(
          make('h4', '', 'Nguyên tắc giọng điệu (Tone of Voice)'),
          make('p', 'doc-excerpt', '“Chân thành, mộc mạc, không cường điệu công dụng. Tập trung vào cảm giác êm dịu của rau má tươi trên làn da mỏng manh.”'),
          make('p', 'small muted', 'Tài liệu hướng dẫn chuẩn hóa giọng nói cho các video AI & creator.')
        );
        stage.append(card);
      }

      $('meta-format').textContent = asset.mime || 'N/A';
      $('meta-size').textContent = asset.size || 'N/A';
      $('meta-resolution').textContent = asset.resolution || 'N/A';
      $('meta-usage').textContent = asset.usage || 'Chưa gắn vào hook';

      document.querySelectorAll('.hook-chip').forEach(chip => {
        const hid = chip.dataset.hookId;
        const isActive = asset.hooks && asset.hooks.includes(hid);
        chip.classList.toggle('active', isActive);
      });
    };

    if ($('btn-rename-asset')) {
      $('btn-rename-asset').addEventListener('click', () => {
        if (!currentInspectingAsset) return;
        const form = $('inline-rename-form');
        form.hidden = !form.hidden;
        if (!form.hidden) {
          $('rename-input').value = currentInspectingAsset.name;
          $('rename-input').focus();
        }
      });
    }

    if ($('btn-cancel-rename')) {
      $('btn-cancel-rename').addEventListener('click', () => {
        if ($('inline-rename-form')) $('inline-rename-form').hidden = true;
      });
    }

    if ($('inline-rename-form')) {
      $('inline-rename-form').addEventListener('submit', event => {
        event.preventDefault();
        if (!currentInspectingAsset) return;
        const newName = $('rename-input').value.trim();
        if (!newName) return;
        currentInspectingAsset.name = newName;
        $('inspector-asset-title').textContent = newName;
        $('inline-rename-form').hidden = true;
        renderBrandAssetsTree();
        toast(`Đã đổi tên tệp thành: ${newName}`);
      });
    }

    if ($('input-replace-asset')) {
      $('input-replace-asset').addEventListener('change', event => {
        if (!currentInspectingAsset) return;
        const file = event.target.files[0];
        if (!file) return;
        if (currentInspectingAsset.url) URL.revokeObjectURL(currentInspectingAsset.url);
        currentInspectingAsset.url = URL.createObjectURL(file);
        currentInspectingAsset.size = formatFileSize(file.size);
        currentInspectingAsset.mime = file.type || 'application/octet-stream';
        window.openAssetInspector(currentInspectingAsset);
        renderBrandAssetsTree();
        toast(`Đã thay thế tệp: ${file.name}`);
      });
    }

    if ($('btn-assign-asset')) {
      $('btn-assign-asset').addEventListener('click', () => {
        const box = $('hook-assign-box');
        if (box) box.hidden = !box.hidden;
      });
    }

    document.querySelectorAll('.hook-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        if (!currentInspectingAsset) return;
        const hid = chip.dataset.hookId;
        if (!currentInspectingAsset.hooks) currentInspectingAsset.hooks = [];
        const idx = currentInspectingAsset.hooks.indexOf(hid);
        if (idx > -1) {
          currentInspectingAsset.hooks.splice(idx, 1);
          chip.classList.remove('active');
        } else {
          currentInspectingAsset.hooks.push(hid);
          chip.classList.add('active');
        }
        currentInspectingAsset.usage = currentInspectingAsset.hooks.length
          ? `Đã gắn vào ${currentInspectingAsset.hooks.join(', ')} · Vòng 01`
          : 'Chưa gắn vào hook nào';
        $('meta-usage').textContent = currentInspectingAsset.usage;
        toast(`Đã cập nhật liên kết hook cho ${currentInspectingAsset.name}`);
      });
    });

    if ($('btn-delete-asset')) {
      $('btn-delete-asset').addEventListener('click', () => {
        if (!currentInspectingAsset) return;
        const name = currentInspectingAsset.name;
        const idx = brandAssets.findIndex(a => a.id === currentInspectingAsset.id);
        if (idx > -1) {
          brandAssets.splice(idx, 1);
        }
        closeInspector();
        renderBrandAssetsTree();
        toast(`Đã xóa tài sản: ${name}`);
      });
    }
  }

  function setupProjectSidebar() {
    const sidebar = $('project-sidebar');
    const backdrop = $('project-sidebar-backdrop');
    const toggleBtn = $('project-nav-toggle');
    const rearTab = $('left-rear-project-tab');
    const closeBtn = $('sidebar-close-btn');

    function openSidebar() {
      if (!sidebar) return;
      sidebar.dataset.collapsed = 'false';
      if (backdrop) backdrop.hidden = false;
      if (toggleBtn) toggleBtn.setAttribute('aria-expanded', 'true');
    }

    function closeSidebar() {
      if (!sidebar) return;
      sidebar.dataset.collapsed = 'true';
      if (backdrop) backdrop.hidden = true;
      if (toggleBtn) toggleBtn.setAttribute('aria-expanded', 'false');
    }

    if (toggleBtn) toggleBtn.addEventListener('click', () => {
      if (sidebar && sidebar.dataset.collapsed === 'false') closeSidebar();
      else openSidebar();
    });
    if (rearTab) rearTab.addEventListener('click', openSidebar);
    if (closeBtn) closeBtn.addEventListener('click', closeSidebar);
    if (backdrop) backdrop.addEventListener('click', closeSidebar);

    // Project toggle dropdown
    const toggleProjBtn = $('btn-toggle-projects');
    const projDropdown = $('project-dropdown-list');
    if (toggleProjBtn && projDropdown) {
      toggleProjBtn.addEventListener('click', e => {
        e.stopPropagation();
        const open = projDropdown.hidden;
        projDropdown.hidden = !open;
        toggleProjBtn.setAttribute('aria-expanded', String(open));
      });
    }

    // Project selector items
    document.querySelectorAll('.project-item').forEach(item => {
      item.addEventListener('click', () => {
        document.querySelectorAll('.project-item').forEach(p => {
          p.classList.remove('active');
          const badge = p.querySelector('.project-active-badge');
          if (badge) badge.remove();
          const dot = p.querySelector('.project-dot');
          if (dot) { dot.textContent = '○'; dot.classList.add('inactive'); }
        });
        item.classList.add('active');
        const dot = item.querySelector('.project-dot');
        if (dot) { dot.textContent = '●'; dot.classList.remove('inactive'); }
        const activeBadge = make('span', 'project-active-badge', 'Đang mở');
        item.append(activeBadge);

        const name = item.dataset.projectName;
        if (name && $('project-name')) {
          $('project-name').textContent = name;
        }
        if (name && $('sidebar-current-project-name')) {
          $('sidebar-current-project-name').textContent = name;
        }
        if (projDropdown) projDropdown.hidden = true;
        if (toggleProjBtn) toggleProjBtn.setAttribute('aria-expanded', 'false');
        closeSidebar();
        toast(`Đã chuyển sang dự án: ${name || 'Dự án mới'}`);
      });
    });

    // Folder expand/collapse toggling
    document.querySelectorAll('.tree-folder > .folder-row').forEach(row => {
      row.addEventListener('click', () => {
        const folder = row.parentElement;
        const isExpanded = folder.classList.toggle('expanded');
        const chevron = row.querySelector('.tree-chevron');
        if (chevron) chevron.textContent = isExpanded ? '▾' : '▸';
        const children = folder.querySelector('.tree-children');
        if (children) children.hidden = !isExpanded;
      });
    });

    // Hook file items in tree
    document.querySelectorAll('[data-hook-file]').forEach(item => {
      const hid = item.dataset.hookFile;
      const hook = hookDefaults.find(h => h.id === hid) || { id: hid, angle: 'Hook', text: 'Nội dung hook mẫu.' };
      item.addEventListener('click', () => {
        if (window.openAssetInspector) {
          window.openAssetInspector({
            id: hid,
            name: `${hid}-${hook.angle.toLowerCase().replace(/\s+/g, '-')}.txt`,
            type: 'hook',
            mime: 'text/plain; charset=utf-8',
            size: '142 B',
            resolution: '1 câu mở đầu · 3 giây',
            usage: `Kịch bản mở đầu cho ${versionLabel(hid)}`,
            angle: hook.angle,
            text: state.edits[hid] || hook.text,
            hooks: [hid]
          });
        }
      });
    });

    // Add brand asset upload handler
    const addAssetInput = $('input-add-brand-asset');
    if (addAssetInput) {
      addAssetInput.addEventListener('change', e => {
        const file = e.target.files[0];
        if (!file) return;
        const isVideo = file.type.startsWith('video/');
        const isImage = file.type.startsWith('image/');
        const newAsset = {
          id: `asset-${Date.now()}`,
          name: file.name,
          type: isVideo ? 'video' : isImage ? 'image' : 'doc',
          mime: file.type || 'application/octet-stream',
          size: formatFileSize(file.size),
          resolution: isVideo ? '1080 × 1920 (9:16)' : isImage ? '1080 × 1080' : 'Tài liệu bổ sung',
          usage: 'Mới nạp · Chưa gắn hook',
          hooks: [],
          icon: isVideo ? 'MP4' : isImage ? 'PNG' : 'DOC',
          url: URL.createObjectURL(file)
        };
        brandAssets.push(newAsset);
        renderBrandAssetsTree();
        toast(`Đã nạp tài sản mới: ${file.name}`);
        if (window.openAssetInspector) window.openAssetInspector(newAsset);
      });
    }

    const newProjectBtn = $('btn-new-project');
    if (newProjectBtn) {
      newProjectBtn.addEventListener('click', () => {
        closeSidebar();
        toast('Đã tạo không gian dự án mới. Bạn có thể giới thiệu sản phẩm trong chat.');
        if (!isDashboard) {
          $('chat-input').focus();
        } else {
          location.href = 'first-onboarding-screen-redesigned.html';
        }
      });
    }

    renderBrandAssetsTree();
  }

  setupAssetInspector();
  setupProjectSidebar();

  if (!isDashboard) {
    $('sample-product').addEventListener('click', () => handleChat(sampleProduct));
    renderMessages(state.messages.length > 1);
    if (!storageAvailable) toast('Trình duyệt không cho lưu lịch sử. Cuộc trò chuyện có thể không chuyển được sang trang tiếp theo.');
    return;
  }

  if (!state.product && state.messages.length === 1) {
    addMessage('assistant', 'Bạn đang xem dự án mẫu serum rau má. Hook bên phải là nội dung minh họa. Bạn có thể giới thiệu sản phẩm của mình tại đây, hoặc chọn hook để thử giao diện.');
  } else if (state.product && !state.interview.length && !state.messages.some(m => m.role === 'assistant' && m.text.includes(interviewQuestions[0]))) {
    addMessage('assistant', `Mình tiếp tục ở đây nhé. ${interviewQuestions[0]}`);
  }
  persist();

  function updateProject() {
    $('project-name').textContent = !state.product ? 'Sắc Ngọc Khang' : /sắc ngọc khang/i.test(state.product) ? 'Sắc Ngọc Khang' : 'Dự án của bạn';
    $('project-name').title = state.product || 'Sắc Ngọc Khang';
  }

  function renderHooks() {
    $('hook-grid').replaceChildren();
    for (const hook of getHooks()) {
      const selected = state.selected.includes(hook.id);
      const card = make('article', `hook-card${selected ? ' selected' : ''}`);
      const top = make('label', 'hook-card-top');
      top.htmlFor = `select-${hook.id}`;
      const angle = make('span', 'hook-angle');
      angle.append(make('span', '', hook.id), make('span', '', hook.angle));
      const input = document.createElement('input');
      input.type = 'checkbox';
      input.id = `select-${hook.id}`;
      input.value = hook.id;
      input.checked = selected;
      input.setAttribute('aria-label', `Chọn ${hook.id}: ${hook.text}`);
      input.addEventListener('change', () => {
        state.selected = getHooks().filter(h => h.id === hook.id ? input.checked : state.selected.includes(h.id)).map(h => h.id);
        card.classList.toggle('selected', input.checked);
        card.querySelector('.select-label').textContent = input.checked ? 'Đã chọn' : 'Chọn hook';
        persist();
        renderSelection();
      });
      top.append(angle, input);
      const video = document.createElement('video');
      video.className = 'hook-mock-video';
      video.controls = true;
      video.muted = true;
      video.playsInline = true;
      video.preload = 'none';
      video.src = `assets/mock-hook-${hook.id}.mp4`;
      video.poster = `assets/mock-hook-${hook.id}.jpg`;
      video.setAttribute('aria-label', `Video mock 3 giây: ${hook.id} · ${hook.angle}`);
      video.addEventListener('play', () => document.querySelectorAll('video').forEach(other => { if (other !== video) other.pause(); }));
      const bottom = make('label', 'hook-card-bottom');
      bottom.htmlFor = input.id;
      bottom.append(make('span', '', state.edits[hook.id] ? 'Mock video · Hook gốc' : 'Mock video · 03 giây'), make('span', 'select-label', selected ? 'Đã chọn' : 'Chọn hook'));
      card.append(top, make('p', 'hook-copy', hook.text), video, bottom);
      $('hook-grid').append(card);
    }
    renderSelection();
  }

  function renderSelection() {
    const count = state.selected.length;
    $('selection-count').textContent = count ? `Đã chọn ${count} hook` : 'Chưa chọn hook';
    $('selection-summary').textContent = count ? `${state.selected.join(' · ')} — Mỗi hook là một phiên bản video.` : 'Chọn ít nhất 1 hook để tiếp tục.';
    $('continue-video').disabled = !count;
  }

  function setEditContext(id) {
    editingHook = id;
    $('edit-context').hidden = !id;
    $('edit-context-label').textContent = id ? `Đang chỉnh: ${versionLabel(id)} · ${id}` : '';
    $('chat-input').placeholder = id ? 'Nhập chính xác câu hook mới bạn muốn dùng…' : 'Nhắn cho Lạc Hồng…';
  }

  function editInChat(id) {
    const hook = getHooks().find(h => h.id === id);
    setEditContext(id);
    addMessage('assistant', `Đang chỉnh ${versionLabel(id)} · ${id}: “${hook.text}”\nGửi chính xác câu mở đầu mới bạn muốn dùng. Thay đổi sẽ bỏ bản dựng và trạng thái duyệt cũ của phiên bản này.`);
    persist();
    renderMessages();
    setMobileView('chat');
    $('chat-input').focus();
  }

  $('cancel-edit').addEventListener('click', () => { setEditContext(null); toast('Đã hủy chế độ chỉnh hook.'); });

  function renderVideos() {
    const hooks = getHooks();
    $('video-empty').hidden = hooks.length > 0;
    $('video-content').hidden = !hooks.length;
    $('video-count').textContent = `${hooks.length} phiên bản mẫu`;
    $('approval-count').textContent = `Đã duyệt ${hooks.filter(h => approvals.has(h.id)).length}/${hooks.length}`;
    $('video-grid').replaceChildren();
    for (const hook of hooks) {
      const asset = videoAssets.get(hook.id);
      const approved = approvals.has(hook.id);
      const card = make('article', `video-card${approved ? ' approved' : ''}`);
      card.dataset.hook = hook.id;
      const heading = make('div', 'video-card-heading');
      heading.append(make('strong', '', `${versionLabel(hook.id)} · ${hook.id}`), make('span', '', hook.angle));
      const preview = make('div', 'video-preview');
      preview.dataset.theme = hook.theme;
      if (asset) {
        const video = document.createElement('video');
        video.controls = true;
        video.playsInline = true;
        video.preload = 'metadata';
        video.src = asset.url;
        video.setAttribute('aria-label', `Bản dựng ${versionLabel(hook.id)} với hook ${hook.id}`);
        video.addEventListener('loadeddata', () => {
          asset.ready = true;
          approve.disabled = false;
          status.textContent = approved ? 'Approved for posting' : 'Bản dựng của bạn · Chờ duyệt';
        });
        video.addEventListener('error', () => {
          asset.ready = false;
          approvals.delete(hook.id);
          approve.disabled = true;
          card.classList.remove('approved');
          status.textContent = 'Không phát được tệp. Chọn video khác.';
          updateApprovalCount();
        });
        preview.append(video);
      } else {
        const storyboard = make('div', 'storyboard');
        storyboard.append(make('span', 'storyboard-label', 'KHUNG HÌNH MINH HỌA'));
        const art = make('div', 'product-art');
        art.setAttribute('aria-hidden', 'true');
        art.append(make('div', 'product-shadow'), make('div', 'bottle'));
        if (state.product && !/serum|rau má/i.test(state.product)) {
          art.hidden = true;
          storyboard.append(make('span', 'small muted', 'Nạp video của bạn để xem trước'));
        } else storyboard.append(art);
        storyboard.append(make('p', 'storyboard-hook', hook.text));
        preview.append(storyboard);
      }
      const status = make('p', 'video-status', approved ? 'Approved for posting' : asset ? 'Đang kiểm tra video…' : 'Chưa có bản dựng');
      const actions = make('div', 'video-actions');
      const edit = make('button', 'button secondary', 'Edit in chat');
      edit.type = 'button';
      edit.setAttribute('aria-label', `Edit in chat: ${versionLabel(hook.id)}`);
      edit.addEventListener('click', () => editInChat(hook.id));
      const approve = make('button', `button ${approved ? 'secondary' : 'primary'}`, approved ? 'Undo approval' : 'Approve for posting');
      approve.type = 'button';
      approve.disabled = !asset?.ready;
      approve.setAttribute('aria-label', `${approved ? 'Undo approval' : 'Approve for posting'}: ${versionLabel(hook.id)}`);
      approve.title = asset ? 'Duyệt không tự động đăng video.' : 'Nạp bản dựng có thể phát để duyệt.';
      approve.addEventListener('click', () => {
        if (!asset?.ready) return;
        if (approvals.has(hook.id)) approvals.delete(hook.id); else approvals.add(hook.id);
        const nowApproved = approvals.has(hook.id);
        card.classList.toggle('approved', nowApproved);
        status.textContent = nowApproved ? 'Approved for posting' : 'Bản dựng của bạn · Chờ duyệt';
        approve.textContent = nowApproved ? 'Undo approval' : 'Approve for posting';
        approve.setAttribute('aria-label', `${approve.textContent}: ${versionLabel(hook.id)}`);
        approve.className = `button ${nowApproved ? 'secondary' : 'primary'}`;
        updateApprovalCount();
        toast(nowApproved ? `${versionLabel(hook.id)} đã được duyệt trong phiên này. Chưa đăng video.` : `Đã bỏ duyệt ${versionLabel(hook.id)}.`);
      });
      actions.append(edit, approve);
      const fileLabel = make('label', 'file-label', asset ? 'Thay bản dựng' : 'Nạp video bản dựng');
      const file = document.createElement('input');
      file.type = 'file';
      file.accept = 'video/*';
      file.className = 'sr-only';
      file.setAttribute('aria-label', `Nạp bản dựng cho ${versionLabel(hook.id)}`);
      file.addEventListener('change', () => {
        const selected = file.files[0];
        if (!selected) return;
        if (!selected.type.startsWith('video/')) { toast('Hãy chọn một tệp video hợp lệ.'); return; }
        const previous = videoAssets.get(hook.id);
        if (previous) URL.revokeObjectURL(previous.url);
        approvals.delete(hook.id);
        videoAssets.set(hook.id, {url: URL.createObjectURL(selected), ready: false});
        renderVideos();
        toast('Video chỉ được mở trong trình duyệt. Tệp và duyệt không được giữ khi tải lại trang.');
      });
      fileLabel.append(file);
      card.append(heading, preview, make('p', 'video-hook-caption', hook.text), status, actions, fileLabel);
      $('video-grid').append(card);
    }
  }

  function updateApprovalCount() {
    const hooks = getHooks();
    const count = hooks.filter(hook => approvals.has(hook.id)).length;
    $('approval-count').textContent = `Đã duyệt ${count}/${hooks.length}`;
    $('results-approval-count').textContent = `${count} đã duyệt`;
  }

  function renderMetrics() {
    const rows = sampleRows($('platform-filter').value, $('window-filter').value);
    const total = rows.reduce((sum, row) => sum + row.views, 0);
    $('metric-views').textContent = number(total);
    $('metric-retention').textContent = percentage(rows.reduce((sum, row) => sum + row.views * row.retention, 0) / total);
    $('metric-watch').textContent = `${decimal(rows.reduce((sum, row) => sum + row.views * row.watch, 0) / total)} giây`;
    $('metrics-body').replaceChildren();
    for (const hook of rows) {
      const row = document.createElement('tr');
      const title = make('td', '', `${versionLabel(hook.id)} · ${hook.angle}`);
      title.append(make('span', 'muted', hook.id));
      const actionCell = document.createElement('td');
      const button = make('button', 'text-button', 'Xem chi tiết');
      button.type = 'button';
      button.setAttribute('aria-expanded', 'false');
      button.setAttribute('aria-controls', `detail-${hook.id}`);
      actionCell.append(button);
      row.append(title, make('td', 'metric-value', number(hook.views)), make('td', 'metric-value', percentage(hook.retention)), actionCell);
      const detail = make('tr', 'detail-row');
      detail.id = `detail-${hook.id}`;
      detail.hidden = true;
      const detailCell = document.createElement('td');
      detailCell.colSpan = 4;
      const grid = make('div', 'platform-detail-grid');
      for (const platform of hook.platforms) {
        const block = make('div', 'platform-detail');
        block.append(make('strong', '', platform.name),
          make('p', '', `${number(platform.views)} lượt xem`),
          make('p', '', `${percentage(platform.retention)} xem qua 3 giây`),
          make('p', '', `${decimal(platform.watch)} giây xem trung bình`));
        grid.append(block);
      }
      detailCell.append(grid, make('p', 'mock-detail-note', 'Dữ liệu mock · Không lấy từ tài khoản hoặc video của bạn.'));
      detail.append(detailCell);
      button.addEventListener('click', () => { detail.hidden = !detail.hidden; button.setAttribute('aria-expanded', String(!detail.hidden)); button.textContent = detail.hidden ? 'Xem chi tiết' : 'Thu gọn'; });
      $('metrics-body').append(row, detail);
    }
  }

  function renderResults() {
    const rows = sampleRows('Tất cả nền tảng', '72 giờ').sort((a, b) => b.retention - a.retention);
    const winner = rows[0];
    $('mock-winner').textContent = `${winner.id} giữ chân tốt nhất trong vòng mẫu.`;
    $('mock-winner-summary').textContent = `${percentage(winner.retention)} xem qua 3 giây · ${number(winner.views)} lượt xem · Tổng hợp 3 nền tảng sau 72 giờ.`;
    $('mock-total-views').textContent = `${number(rows.reduce((sum, row) => sum + row.views, 0))} lượt xem mẫu`;
    $('mock-ranking').replaceChildren();
    rows.forEach((row, index) => {
      const item = make('div', `ranking-row${index === 0 ? ' leading' : ''}`);
      const title = make('div', 'ranking-title');
      title.append(make('span', 'ranking-index', String(index + 1).padStart(2, '0')),
        make('strong', '', `${row.id} · ${row.angle}`), make('span', '', percentage(row.retention)));
      const track = make('div', 'ranking-track');
      const bar = make('div', 'ranking-fill');
      bar.style.width = `${row.retention * 100}%`;
      track.append(bar);
      item.append(title, track, make('p', 'small muted', `${number(row.views)} lượt xem · ${decimal(row.watch)} giây xem TB`));
      $('mock-ranking').append(item);
    });
  }

  const stageCopy = {
    analysis: ['01. Phân tích', 'Quét và so sánh hook thắng cuộc trên thị trường với video hiệu quả của bạn qua các vòng thử nghiệm.'],
    hooks: ['02. Chọn mở đầu', 'Chọn video tham khảo cùng số liệu ở 2A để tạo gợi ý. Chọn đoạn mở đầu dành cho sản phẩm ở 2B để dựng video.'],
    video: ['03. Dựng video', 'Xem từng phiên bản, chỉnh trong chat hoặc duyệt để đăng.'],
    metrics: ['04. Theo dõi kết quả', 'Số liệu được cập nhật tự động sau 2, 6, 24, 48 và 72 giờ kể từ khi đăng.']
  };

  let activeViewMode = 'curation';

  function setLoopView(mode) {
    activeViewMode = mode;
    const switchCuration = $('switch-curation');
    const switchAiLoop = $('switch-ai-loop');
    if (switchCuration && switchAiLoop) {
      switchCuration.classList.toggle('active', mode === 'curation');
      switchCuration.setAttribute('aria-pressed', String(mode === 'curation'));
      switchAiLoop.classList.toggle('active', mode === 'ai-loop');
      switchAiLoop.setAttribute('aria-pressed', String(mode === 'ai-loop'));
    }
    const stageTabs = document.querySelector('.stage-tabs');
    if (stageTabs) stageTabs.dataset.activePart = mode;
    if ($('stage-eyebrow')) {
      $('stage-eyebrow').textContent = 'THỬ NGHIỆM VIDEO / BỐN GIAI ĐOẠN';
    }
  }

  function initAnalysisStage() {
    const toggle01 = $('btn-toggle-loop-01');
    const header01 = $('loop-01-header');
    const detail01 = $('loop-01-expanded');
    const loop01 = $('loop-01');
    function toggleLoop01() {
      if (!loop01 || !detail01) return;
      const isExpanded = loop01.classList.contains('expanded');
      loop01.classList.toggle('expanded', !isExpanded);
      detail01.hidden = isExpanded;
      if (isExpanded) detail01.querySelectorAll('video').forEach(video => video.pause());
      if (header01) header01.setAttribute('aria-expanded', String(!isExpanded));
      if (toggle01) toggle01.textContent = isExpanded ? 'Mở rộng chi tiết ▾' : 'Thu gọn chi tiết ▴';
    }
    if (toggle01) toggle01.addEventListener('click', (e) => { e.stopPropagation(); toggleLoop01(); });
    if (header01) header01.addEventListener('click', toggleLoop01);
    if (header01) header01.addEventListener('keydown', event => {
      if (event.target !== header01 || !['Enter', ' '].includes(event.key)) return;
      event.preventDefault();
      toggleLoop01();
    });

    const toggle02 = $('btn-toggle-loop-02');
    const header02 = $('loop-02-header');
    const detail02 = $('loop-02-expanded');
    const loop02 = $('loop-02');
    function toggleLoop02() {
      if (!loop02 || !detail02) return;
      const isExpanded = loop02.classList.contains('expanded');
      loop02.classList.toggle('expanded', !isExpanded);
      detail02.hidden = isExpanded;
      if (header02) header02.setAttribute('aria-expanded', String(!isExpanded));
      if (toggle02) toggle02.textContent = isExpanded ? 'Mở rộng chi tiết ▾' : 'Thu gọn chi tiết ▴';
    }
    if (toggle02) toggle02.addEventListener('click', (e) => { e.stopPropagation(); toggleLoop02(); });
    if (header02) header02.addEventListener('click', toggleLoop02);
    if (header02) header02.addEventListener('keydown', event => {
      if (event.target !== header02 || !['Enter', ' '].includes(event.key)) return;
      event.preventDefault();
      toggleLoop02();
    });

    const btnTabWinning = $('btn-tab-winning');
    const btnTabOurs = $('btn-tab-ours');
    const winningList = $('winning-hooks-list');
    const ourAdsList = $('our-ads-list');

    if (btnTabWinning && btnTabOurs) {
      const tabs = [btnTabWinning, btnTabOurs];
      const lists = [winningList, ourAdsList];
      function selectVideoTab(index) {
        tabs.forEach((tab, i) => {
          const active = i === index;
          tab.classList.toggle('active', active);
          tab.setAttribute('aria-selected', String(active));
          tab.tabIndex = active ? 0 : -1;
          if (lists[i]) {
            lists[i].hidden = !active;
            if (!active) lists[i].querySelectorAll('video').forEach(video => video.pause());
          }
        });
      }
      tabs.forEach((tab, index) => {
        tab.addEventListener('click', () => selectVideoTab(index));
        tab.addEventListener('keydown', event => {
          if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
          event.preventDefault();
          const next = event.key === 'Home' ? 0 : event.key === 'End' ? 1 : 1 - index;
          selectVideoTab(next);
          tabs[next].focus();
        });
      });
      selectVideoTab(0);
    }
  }

  function initReferenceHooks() {
    const countLabel = $('ref-selection-count');
    const summaryLabel = $('ref-selection-summary');

    function updateRefSelection() {
      const selected = [...document.querySelectorAll('.ref-hook-card.selected')].map(c => c.dataset.refId);
      if (countLabel) {
        countLabel.textContent = selected.length
          ? `Đã chọn ${selected.length} mẫu tham khảo: ${selected.join(', ')}`
          : 'Chưa chọn mẫu tham khảo nào';
      }
      if (summaryLabel) {
        summaryLabel.textContent = selected.length
          ? 'Các mẫu này dùng để gợi ý nội dung cho sản phẩm, chưa phải lựa chọn để dựng video.'
          : 'Bấm Chọn mẫu trên từng thẻ để dùng làm cơ sở gợi ý mở đầu cho sản phẩm.';
      }
    }

    document.querySelectorAll('[data-ref-toggle]').forEach(btn => {
      btn.setAttribute('aria-pressed', String(btn.closest('.ref-hook-card').classList.contains('selected')));
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const refId = btn.dataset.refToggle;
        const card = document.querySelector(`.ref-hook-card[data-ref-id="${refId}"]`);
        if (!card) return;
        const isSelected = card.classList.contains('selected');
        card.classList.toggle('selected', !isSelected);
        btn.setAttribute('aria-pressed', String(!isSelected));
        btn.textContent = isSelected ? 'Chưa chọn · Chọn mẫu' : 'Đã chọn · Bỏ chọn';
        updateRefSelection();
      });
    });

    const applyRefBtn = $('btn-apply-ref-hooks');
    if (applyRefBtn) {
      applyRefBtn.addEventListener('click', () => {
        const selected = [...document.querySelectorAll('.ref-hook-card.selected')].map(c => c.dataset.refId);
        if (!selected.length) {
          toast('Vui lòng chọn ít nhất 1 mẫu mở đầu tham khảo.');
          return;
        }
        $('chat-input').value = `Gợi ý các câu mở đầu cho serum rau má dựa trên các mẫu tham khảo: ${selected.join(', ')}.`;
        setMobileView('chat');
        $('chat-input').focus();
        toast('Đã nạp yêu cầu gợi ý mở đầu từ mẫu tham khảo vào khung chat.');
      });
    }
  }

  function showStage(stage, focus = false) {
    const openNextLoop = stage === 'analysis-loop-02' || stage === 'results';
    if (openNextLoop) stage = 'analysis';
    if (!stageCopy[stage]) stage = 'hooks';
    activeStage = stage;
    if (stage === 'hooks' || stage === 'video') {
      setLoopView('curation');
    } else if (stage === 'metrics' || stage === 'analysis') {
      setLoopView('ai-loop');
    }
    document.querySelectorAll('.stage-tabs [role=tab]').forEach(tab => { const active = tab.dataset.stage === stage; tab.setAttribute('aria-selected', String(active)); tab.tabIndex = active ? 0 : -1; });
    document.querySelectorAll('.stage-panel').forEach(panel => { panel.hidden = panel.id !== `panel-${stage}`; });
    $('dashboard-title').textContent = stageCopy[stage][0];
    $('stage-subtitle').textContent = stageCopy[stage][1];
    document.querySelectorAll('video').forEach(video => video.pause());
    if (stage === 'video') renderVideos();
    if (stage === 'metrics') renderMetrics();
    if (stage === 'analysis') {
      renderResults();
      updateApprovalCount();
    }
    if (openNextLoop && !$('loop-02').classList.contains('expanded')) $('btn-toggle-loop-02').click();
    history.replaceState(null, '', openNextLoop ? '#analysis-loop-02' : `#${stage}`);
    $('dashboard-main').scrollTop = 0;
    if (openNextLoop) $('loop-02').scrollIntoView({block: 'start'});
    if (focus) $('dashboard-title').focus({preventScroll: true});
  }

  if ($('switch-curation')) {
    $('switch-curation').addEventListener('click', () => {
      setLoopView('curation');
      if (activeStage === 'metrics' || activeStage === 'analysis') {
        showStage('hooks', true);
      }
    });
  }
  if ($('switch-ai-loop')) {
    $('switch-ai-loop').addEventListener('click', () => {
      setLoopView('ai-loop');
      if (activeStage === 'hooks' || activeStage === 'video') {
        showStage('metrics', true);
      }
    });
  }
  document.querySelectorAll('[data-switch-to]').forEach(btn => {
    btn.addEventListener('click', () => {
      const target = btn.dataset.switchTo;
      if (target === 'ai-loop') showStage('metrics', true);
      else if (target === 'curation') showStage('hooks', true);
    });
  });

  document.querySelectorAll('[data-stage]').forEach(tab => {
    tab.addEventListener('click', () => showStage(tab.dataset.stage));
    tab.addEventListener('keydown', event => {
      const tabs = [...document.querySelectorAll('.stage-tabs [role=tab]')];
      let index = tabs.indexOf(tab);
      if (event.key === 'ArrowRight') index = (index + 1) % tabs.length;
      else if (event.key === 'ArrowLeft') index = (index + tabs.length - 1) % tabs.length;
      else if (event.key === 'Home') index = 0;
      else if (event.key === 'End') index = tabs.length - 1;
      else return;
      event.preventDefault();
      showStage(tabs[index].dataset.stage);
      tabs[index].focus();
    });
  });
  document.querySelectorAll('[data-go]').forEach(button => button.addEventListener('click', () => showStage(button.dataset.go, true)));
  $('continue-video').addEventListener('click', () => { if (state.selected.length) showStage('video', true); });

  document.querySelectorAll('.btn-apply-winning-hook').forEach(btn => {
    btn.addEventListener('click', () => {
      const template = btn.dataset.hookTemplate;
      if (!template) return;
      $('chat-input').value = `Áp dụng công thức hook này cho serum rau má: "${template}"`;
      setMobileView('chat');
      $('chat-input').focus();
      toast('Đã đưa mẫu hook vào khung chat để bạn tùy biến cho sản phẩm.');
    });
  });

  function setMobileView(view) {
    document.querySelector('.workspace').dataset.mobileView = view;
    document.querySelectorAll('[data-view]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.view === view)));
  }
  document.querySelectorAll('[data-view]').forEach(button => button.addEventListener('click', () => setMobileView(button.dataset.view)));
  for (const id of ['platform-filter', 'window-filter']) $(id).addEventListener('change', () => {
    $('filter-description').textContent = `${$('platform-filter').value} · ${$('window-filter').value}`;
    renderMetrics();
  });
  $('learning').value = state.learning;
  $('hypothesis').value = state.hypothesis;
  $('draft-note').hidden = !state.nextDraft;
  $('notes-form').addEventListener('submit', event => { event.preventDefault(); state.learning = $('learning').value.trim(); if (persist()) toast('Đã lưu ghi chú trong phiên trình duyệt này.'); });
  $('hypothesis-form').addEventListener('submit', event => {
    event.preventDefault();
    const hypothesis = $('hypothesis').value.trim();
    if (!hypothesis) { $('hypothesis').focus(); toast('Ghi một điều muốn kiểm chứng trước nhé.'); return; }
    state.hypothesis = hypothesis;
    state.learning = $('learning').value.trim();
    state.nextDraft = true;
    if (persist()) { $('draft-note').hidden = false; toast('Đã lưu hướng thử tiếp theo. Vòng 01 được giữ nguyên.'); }
  });
  window.addEventListener('hashchange', () => showStage(location.hash.slice(1)));
  window.addEventListener('pagehide', () => { for (const asset of videoAssets.values()) URL.revokeObjectURL(asset.url); });
  updateProject();
  renderMessages(!(!isDashboard && state.messages.length <= 1));
  renderHooks();
  initAnalysisStage();
  initReferenceHooks();
  document.querySelectorAll('.sample-hook-video').forEach(video => {
    video.addEventListener('play', () => document.querySelectorAll('video').forEach(other => { if (other !== video) other.pause(); }));
  });
  showStage(location.hash.slice(1) || activeStage);
})();
