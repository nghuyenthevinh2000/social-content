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
  const defaultState = () => ({product: '', messages: [{role: 'assistant', text: opening}], selected: [], edits: {}, interview: [], learning: '', hypothesis: '', nextDraft: false});
  let state = defaultState();
  let storageAvailable = true;
  try {
    const saved = JSON.parse(sessionStorage.getItem(storageKey));
    if (saved && typeof saved === 'object') {
      for (const key of ['product', 'learning', 'hypothesis']) if (typeof saved[key] === 'string') state[key] = saved[key].slice(0, 4000);
      if (Array.isArray(saved.messages)) state.messages = saved.messages.filter(m => m && ['user', 'assistant'].includes(m.role) && typeof m.text === 'string').slice(-100).map(m => ({role: m.role, text: m.text.slice(0, 6000)}));
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

  function renderMessages() {
    const log = $('chat-log');
    log.replaceChildren();
    for (const message of state.messages) {
      const article = make('article', `message ${message.role}`);
      article.append(make('p', 'message-name', message.role === 'user' ? 'Bạn' : 'Lạc Hồng'), make('p', 'message-body', message.text));
      log.append(article);
    }
    $('chat-scroll').scrollTop = $('chat-scroll').scrollHeight;
    if (!isDashboard) {
      $('starter-prompts').hidden = Boolean(state.product);
      $('workspace-entry').hidden = !state.product;
    }
  }

  function addMessage(role, text) { state.messages.push({role, text}); }

  function versionLabel(id) { return `V${String(Number(id.slice(1))).padStart(2, '0')}`; }

  const interviewQuestions = [
    'Khách hàng chính của bạn là ai?',
    'Họ thường băn khoăn điều gì khi chọn sản phẩm?',
    'Bạn muốn giọng kể gần gũi hay tư vấn trực tiếp?'
  ];

  function handleChat(text) {
    if (!text.trim()) return;
    addMessage('user', text);
    if (editingHook) {
      const id = editingHook;
      state.edits[id] = text;
      const asset = videoAssets.get(id);
      if (asset) URL.revokeObjectURL(asset.url);
      videoAssets.delete(id);
      approvals.delete(id);
      setEditContext(null);
      addMessage('assistant', `Đã dùng nguyên văn câu bạn gửi cho ${versionLabel(id)} · ${id}. Đây là chỉnh sửa trực tiếp trong bản mẫu, không phải AI viết lại. Nạp bản dựng mới để xem và duyệt phiên bản này.`);
      renderHooks();
      renderVideos();
    } else if (!state.product) {
      state.product = text;
      addMessage('assistant', isDashboard ? `Mình đã ghi lại thông tin bạn gửi. ${interviewQuestions[0]}` : 'Mình đã ghi lại thông tin bạn gửi. Sang không gian làm việc để chọn hook nhé. Cuộc trò chuyện vẫn ở bên cạnh bạn.');
      if (isDashboard) { updateProject(); renderHooks(); }
    } else if (isDashboard && state.interview.length < interviewQuestions.length) {
      state.interview.push(text);
      const next = interviewQuestions[state.interview.length];
      addMessage('assistant', next || 'Đã ghi lại câu trả lời của bạn. Bốn thẻ bên phải minh họa các hướng: nhu cầu, câu hỏi, góc nhìn khác và trải nghiệm. Chọn các hook muốn thử, rồi tiếp tục sang Video creation. Bản mẫu chưa dùng AI để cá nhân hóa hoặc dự báo hiệu quả.');
    } else {
      addMessage('assistant', isDashboard
        ? 'Mình đã ghi lại yêu cầu này. Bản mẫu chưa kết nối AI để trả lời tự do. Để đổi nội dung một hook, chọn Edit in chat ở phiên bản video tương ứng, rồi gửi chính xác câu mới bạn muốn dùng.'
        : 'Mình đã giữ lại tin nhắn của bạn. Mở không gian làm việc để tiếp tục trao đổi và chọn hook.');
    }
    persist();
    renderMessages();
  }

  $('chat-form').addEventListener('submit', event => {
    event.preventDefault();
    const text = $('chat-input').value.trim();
    if (!text) return;
    $('chat-input').value = '';
    handleChat(text);
  });
  $('chat-input').addEventListener('keydown', event => {
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      $('chat-form').requestSubmit();
    }
  });

  if (!isDashboard) {
    $('sample-product').addEventListener('click', () => handleChat(sampleProduct));
    renderMessages();
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
    $('project-name').textContent = !state.product ? 'Dự án mẫu · Serum rau má' : /sắc ngọc khang/i.test(state.product) ? 'Sắc Ngọc Khang' : 'Dự án của bạn';
    $('project-name').title = state.product || 'Dự án mẫu';
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
    const hooks = getHooks().filter(h => state.selected.includes(h.id));
    $('video-empty').hidden = hooks.length > 0;
    $('video-content').hidden = !hooks.length;
    $('video-count').textContent = `${hooks.length} phiên bản của bạn`;
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
    const count = state.selected.filter(id => approvals.has(id)).length;
    $('approval-count').textContent = `Đã duyệt ${count}/${state.selected.length}`;
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
    hooks: ['Hook suggestion', 'Chọn các hook bạn muốn đưa sang Video creation.'],
    video: ['Một video. Ba cách mở đầu.', 'Xem từng phiên bản, chỉnh trong chat hoặc duyệt để đăng.'],
    metrics: ['Đọc kết quả từng phiên bản.', 'So sánh lượt xem và tỷ lệ xem qua 3 giây trong cùng khoảng thời gian.'],
    results: ['Một vòng thử. Một điều học được.', 'Tổng kết các hook và ghi lại hướng thử tiếp theo.']
  };

  function showStage(stage, focus = false) {
    if (!stageCopy[stage]) stage = 'hooks';
    activeStage = stage;
    document.querySelectorAll('[role=tab]').forEach(tab => { const active = tab.dataset.stage === stage; tab.setAttribute('aria-selected', String(active)); tab.tabIndex = active ? 0 : -1; });
    document.querySelectorAll('[role=tabpanel]').forEach(panel => { panel.hidden = panel.id !== `panel-${stage}`; });
    $('dashboard-title').textContent = stage === 'video' && state.selected.length && state.selected.length !== 3 ? `Một video. ${state.selected.length} cách mở đầu.` : stageCopy[stage][0];
    $('stage-subtitle').textContent = stageCopy[stage][1];
    document.querySelectorAll('video').forEach(video => video.pause());
    if (stage === 'video') renderVideos();
    if (stage === 'metrics') renderMetrics();
    if (stage === 'results') {
      renderResults();
      updateApprovalCount();
    }
    history.replaceState(null, '', `#${stage}`);
    $('dashboard-main').scrollTop = 0;
    if (focus) $('dashboard-title').focus({preventScroll: true});
  }

  document.querySelectorAll('[data-stage]').forEach(tab => {
    tab.addEventListener('click', () => showStage(tab.dataset.stage));
    tab.addEventListener('keydown', event => {
      const tabs = [...document.querySelectorAll('[role=tab]')];
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
  renderMessages();
  renderHooks();
  showStage(location.hash.slice(1) || activeStage);
})();
