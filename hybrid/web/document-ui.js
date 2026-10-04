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
          <button class="docBtn" data-generate="${escapeHtml(doc.key)}" ${doc.templateReady ? '' : 'disabled'}>현재 사안으로 생성</button>
          <div class="docResult" data-result="${escapeHtml(doc.key)}"></div>
        </div>
      `).join('');
      documentList.querySelectorAll('[data-generate]').forEach(btn => {
        btn.addEventListener('click', () => generate(btn.dataset.generate));
      });
    } catch (e) {
      documentList.innerHTML = `<div class="docResult" style="color:#b91c1c">문서 목록을 불러오지 못했습니다: ${escapeHtml(e.message)}</div>`;
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
