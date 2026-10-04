(() => {
  const PREFIX = 'sv_assist_v2_';
  const frame = document.getElementById('legacyFrame');
  const documentBtn = document.getElementById('documentBtn');
  const documentPanel = document.getElementById('documentPanel');
  const documentList = document.getElementById('documentList');
  const enginePanel = document.getElementById('panel');
  if (!frame || !documentBtn || !documentPanel || !documentList) return;

  async function api(path, options = {}) {
    const res = await fetch(path, {
      ...options,
      headers: {'Content-Type':'application/json', ...(options.headers || {})}
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    return data;
  }

  function readStorage(key, fallback) {
    try {
      const raw = frame.contentWindow.localStorage.getItem(PREFIX + key);
      return raw ? JSON.parse(raw) : fallback;
    } catch (_) { return fallback; }
  }

  function getCurrentCase() {
    const w = frame.contentWindow;
    try {
      const formPage = w.document.getElementById('page-newcase');
      if (formPage?.classList.contains('active') && typeof w.getFormData === 'function') {
        const data = w.getFormData();
        const cases = readStorage('cases', []);
        const stored = cases.find(c => c.id === data.id || (data.caseNo && c.caseNo === data.caseNo));
        if (stored) return {...stored, ...data, _hybrid: stored._hybrid || data._hybrid || {}};
        return data;
      }
    } catch (_) {}
    const cases = readStorage('cases', []);
    return cases.find(c => c.status !== '종결') || cases[0] || null;
  }

  function escapeHtml(v) {
    return String(v ?? '').replace(/[&<>"']/g, s => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[s]));
  }

  function fileToBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result || '').split(',').pop() || '');
      reader.onerror = () => reject(reader.error || new Error('파일을 읽지 못했습니다.'));
      reader.readAsDataURL(file);
    });
  }

  async function renderDocuments() {
    documentList.textContent = '문서 목록을 확인하는 중입니다.';
    try {
      const result = await api('/api/documents');
      const docs = result.documents || [];
      if (!docs.length) {
        documentList.innerHTML = '<div class="small">등록된 문서가 없습니다.</div>';
        return;
      }
      documentList.innerHTML = docs.map(doc => `
        <div class="docItem" data-key="${escapeHtml(doc.key)}">
          <div class="docHead">
            <div class="docName">${escapeHtml(doc.label)}</div>
            <span class="docStatus ${doc.templateReady ? 'ready' : 'missing'}">${doc.templateReady ? '템플릿 준비' : '템플릿 미등록'}</span>
          </div>
          <div class="small">단계: ${escapeHtml(doc.stage || '-')} · 파일: ${escapeHtml(doc.template || '-')}</div>
          <div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:8px">
            <button class="docBtn" data-upload="${escapeHtml(doc.key)}">원본 HWPX 등록</button>
            <input type="file" accept=".hwpx" data-file="${escapeHtml(doc.key)}" style="display:none">
            <button class="docBtn" data-analyze="${escapeHtml(doc.key)}" ${doc.templateReady ? '' : 'disabled'}>구조 분석</button>
            <button class="docBtn" data-generate="${escapeHtml(doc.key)}" ${doc.templateReady ? '' : 'disabled'}>현재 사안으로 생성</button>
          </div>
          <div class="docResult" data-result="${escapeHtml(doc.key)}"></div>
        </div>
      `).join('');

      documentList.querySelectorAll('[data-upload]').forEach(btn => {
        btn.addEventListener('click', () => {
          const input = documentList.querySelector(`[data-file="${CSS.escape(btn.dataset.upload)}"]`);
          input?.click();
        });
      });
      documentList.querySelectorAll('[data-file]').forEach(input => {
        input.addEventListener('change', () => registerTemplate(input.dataset.file, input.files?.[0]));
      });
      documentList.querySelectorAll('[data-analyze]').forEach(btn => {
        btn.addEventListener('click', () => analyze(btn.dataset.analyze));
      });
      documentList.querySelectorAll('[data-generate]').forEach(btn => {
        btn.addEventListener('click', () => generate(btn.dataset.generate));
      });
    } catch (e) {
      documentList.innerHTML = `<div class="docResult" style="color:#b91c1c">문서 목록을 불러오지 못했습니다: ${escapeHtml(e.message)}</div>`;
    }
  }

  async function registerTemplate(key, file) {
    const box = documentList.querySelector(`[data-result="${CSS.escape(key)}"]`);
    if (!file) return;
    if (!String(file.name || '').toLowerCase().endsWith('.hwpx')) {
      if (box) box.innerHTML = '<span style="color:#b91c1c">HWPX 파일만 등록할 수 있습니다.</span>';
      return;
    }
    if (box) box.textContent = '공식 HWPX 원본을 등록하고 구조를 분석하는 중입니다.';
    try {
      const encoded = await fileToBase64(file);
      const result = await api('/api/documents/register', {
        method:'POST',
        body:JSON.stringify({documentKey:key, fileName:file.name, base64:encoded})
      });
      const a = result.analysis || {};
      if (box) box.innerHTML = [
        `<span style="color:#15803d">원본 등록 완료: ${escapeHtml(result.template)}</span>`,
        result.archivedPrevious ? `<br>이전 템플릿 자동보관: ${escapeHtml(result.archivedPrevious)}` : '',
        `<br>패키지 ${escapeHtml(a.packageFiles ?? '-')}개 · XML ${escapeHtml(a.xmlFileCount ?? '-')}개 · 기존 토큰 ${escapeHtml(a.tokenCount ?? 0)}개`,
        a.mimetypeStored ? '<br><span style="color:#15803d">HWPX mimetype 구조 정상</span>' : '<br><span style="color:#b45309">mimetype 압축상태 확인 필요</span>'
      ].join('');
      await renderDocuments();
      const refreshedBox = documentList.querySelector(`[data-result="${CSS.escape(key)}"]`);
      if (refreshedBox) refreshedBox.innerHTML = `<span style="color:#15803d">원본 등록 및 1차 구조 분석 완료: ${escapeHtml(file.name)}</span>`;
    } catch (e) {
      if (box) box.innerHTML = `<span style="color:#b91c1c">원본 등록 실패: ${escapeHtml(e.message)}</span>`;
    }
  }

  async function analyze(key) {
    const box = documentList.querySelector(`[data-result="${CSS.escape(key)}"]`);
    if (box) box.textContent = 'HWPX 구조를 분석하는 중입니다.';
    try {
      const result = await api(`/api/documents/analysis?key=${encodeURIComponent(key)}`);
      const a = result.analysis || {};
      const groups = a.textSamples || [];
      const sampleLines = [];
      groups.slice(0, 5).forEach(group => {
        const items = (group.items || []).slice(0, 12);
        if (items.length) sampleLines.push(`${group.file}: ${items.join(' / ')}`);
      });
      if (box) box.innerHTML = [
        `<b>구조 분석 완료</b>`,
        `<br>파일크기: ${escapeHtml(a.size ?? '-')} bytes · 패키지: ${escapeHtml(a.packageFiles ?? '-')}개 · XML: ${escapeHtml(a.xmlFileCount ?? '-')}개`,
        `<br>기존 토큰: ${escapeHtml((a.tokens || []).join(', ') || '없음')}`,
        sampleLines.length ? `<br><br><b>매핑용 텍스트 샘플</b><br>${sampleLines.map(escapeHtml).join('<br>')}` : '<br>추출 가능한 텍스트 샘플이 없습니다.'
      ].join('');
    } catch (e) {
      if (box) box.innerHTML = `<span style="color:#b91c1c">구조 분석 실패: ${escapeHtml(e.message)}</span>`;
    }
  }

  async function generate(key) {
    const box = documentList.querySelector(`[data-result="${CSS.escape(key)}"]`);
    if (box) box.textContent = '문서를 생성하는 중입니다.';
    try {
      const caseData = getCurrentCase();
      if (!caseData) throw new Error('현재 사안이 없습니다. 사안을 먼저 접수하거나 저장하세요.');
      const settings = readStorage('settings', {});
      const result = await api('/api/documents/generate', {
        method: 'POST',
        body: JSON.stringify({documentKey:key, case:caseData, settings})
      });
      const missing = result.missingTokens || [];
      if (box) {
        box.innerHTML = `생성 완료: <a href="${escapeHtml(result.downloadUrl)}">${escapeHtml(result.fileName)}</a>` +
          (missing.length ? `<br><span style="color:#b45309">미치환 토큰: ${escapeHtml(missing.join(', '))}</span>` : '<br><span style="color:#15803d">등록된 토큰 치환 완료</span>');
      }
    } catch (e) {
      if (box) box.innerHTML = `<span style="color:#b91c1c">생성 실패: ${escapeHtml(e.message)}</span>`;
    }
  }

  documentBtn.addEventListener('click', async () => {
    if (enginePanel) enginePanel.classList.remove('open');
    documentPanel.classList.toggle('open');
    if (documentPanel.classList.contains('open')) await renderDocuments();
  });

  frame.addEventListener('load', () => {
    if (documentPanel.classList.contains('open')) renderDocuments();
  });
})();
