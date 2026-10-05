(() => {
  const PREFIX = 'sv_assist_v2_';
  const FORM10 = 'form10_case_report';
  const FORM12 = 'form12_investigation_report';
  const STRICT = new Set([FORM10, FORM12]);
  const frame = document.getElementById('legacyFrame');
  const documentBtn = document.getElementById('documentBtn');
  const documentPanel = document.getElementById('documentPanel');
  const documentList = document.getElementById('documentList');
  const enginePanel = document.getElementById('panel');
  if (!frame || !documentBtn || !documentPanel || !documentList) return;

  function ensureStyles() {
    if (document.getElementById('docPreflightStyle')) return;
    const style = document.createElement('style');
    style.id = 'docPreflightStyle';
    style.textContent = `
      .preflight{margin-top:9px;border:1px solid #dbe4ec;border-radius:10px;padding:9px;background:#f8fafc}
      .preflightHead{display:flex;align-items:center;gap:7px;font-size:12px;font-weight:800;color:#334155}
      .preflightScore{margin-left:auto;padding:3px 7px;border-radius:999px;background:#e2e8f0;color:#475569}
      .preflightScore.ready{background:#dcfce7;color:#166534}.preflightScore.warn{background:#ffedd5;color:#9a3412}
      .preflightSections{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:7px}
      .preflightSection{border:1px solid #e2e8f0;background:#fff;border-radius:8px;padding:7px;font-size:11px;line-height:1.45}
      .preflightSection.ok{border-color:#bbf7d0}.preflightSection.bad{border-color:#fed7aa}
      .preflightSection b{display:flex;justify-content:space-between;gap:8px}.preflightMissing{margin-top:4px;color:#9a3412}
      .preflightRecommended{margin-top:4px;color:#475569}.preflightActions{display:flex;gap:5px;flex-wrap:wrap;margin-top:7px}
      .preflightFix{border:1px solid #94a3b8;background:#fff;border-radius:6px;padding:4px 7px;font-size:11px;cursor:pointer}
      .docMetaStatus{font-size:11px;color:#64748b;margin-top:4px}
      @media(max-width:640px){.preflightSections{grid-template-columns:1fr}}
    `;
    document.head.appendChild(style);
  }
  ensureStyles();

  async function api(path, options = {}) {
    const res = await fetch(path, {...options, headers:{'Content-Type':'application/json', ...(options.headers || {})}});
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const error = new Error(data.error || `HTTP ${res.status}`);
      error.payload = data;
      throw error;
    }
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
        if (stored) return {...stored, ...data, _hybrid:{...(stored._hybrid || {}), ...(data._hybrid || {})}};
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

  function formShortName(key) {
    if (key === FORM10) return '서식10';
    if (key === FORM12) return '서식12';
    return '문서';
  }

  function renderPreflight(key, readiness) {
    const box = documentList.querySelector(`[data-readiness="${CSS.escape(key)}"]`);
    const generateBtn = documentList.querySelector(`[data-generate="${CSS.escape(key)}"]`);
    if (!box) return;
    const sections = readiness.sections || [];
    const ready = !!readiness.ready;
    if (generateBtn) generateBtn.disabled = !ready;
    const short = formShortName(key);
    box.innerHTML = `
      <div class="preflight">
        <div class="preflightHead">${short} 생성 사전점검
          <span class="preflightScore ${ready ? 'ready' : 'warn'}">내용 ${escapeHtml(readiness.score ?? 0)}% · ${ready ? '생성 가능' : '보완 필요'}</span>
        </div>
        <div class="preflightSections">
          ${sections.map(s => `
            <div class="preflightSection ${s.ready ? 'ok' : 'bad'}">
              <b><span>${s.ready ? '✓' : '△'} ${escapeHtml(s.label)}</span><span>${escapeHtml(s.score ?? 0)}%</span></b>
              ${s.missing?.length ? `<div class="preflightMissing">필수: ${s.missing.map(escapeHtml).join(' · ')}</div>` : '<div style="color:#15803d;margin-top:4px">필수정보 확인 완료</div>'}
              ${s.recommended?.length ? `<div class="preflightRecommended">권장 확인: ${s.recommended.slice(0,4).map(escapeHtml).join(' · ')}${s.recommended.length>4?' 외 '+(s.recommended.length-4)+'건':''}</div>` : ''}
              ${s.notice ? `<div class="preflightRecommended">${escapeHtml(s.notice)}</div>` : ''}
            </div>
          `).join('')}
        </div>
        ${!readiness.templateReady ? `<div class="preflightMissing" style="margin-top:7px">${short} HWPX 원본이 아직 등록되지 않았습니다.</div>` : ''}
        ${readiness.templateReady && !readiness.builtTemplateReady ? `<div class="preflightMissing" style="margin-top:7px">${short} 생성용 템플릿을 아직 제작하지 않았습니다.</div>` : ''}
        <div class="preflightActions">
          ${key===FORM10 ? '<button class="preflightFix" data-open-atoz>A to Z 추가정보</button>' : ''}
          ${key===FORM12 ? '<button class="preflightFix" data-open-investigation>사안조사 기록</button>' : ''}
          <button class="preflightFix" data-open-students>관련학생 상세</button>
          <button class="preflightFix" data-refresh-readiness>다시 점검</button>
        </div>
      </div>`;
    box.querySelector('[data-open-atoz]')?.addEventListener('click', () => document.getElementById('atozBtn')?.click());
    box.querySelector('[data-open-investigation]')?.addEventListener('click', () => document.getElementById('investigationBtn')?.click());
    box.querySelector('[data-open-students]')?.addEventListener('click', () => document.getElementById('studentBtn')?.click());
    box.querySelector('[data-refresh-readiness]')?.addEventListener('click', () => checkReadiness(key));
  }

  async function checkReadiness(key, silent = false) {
    const box = documentList.querySelector(`[data-readiness="${CSS.escape(key)}"]`);
    const generateBtn = documentList.querySelector(`[data-generate="${CSS.escape(key)}"]`);
    const caseData = getCurrentCase();
    if (!caseData) {
      if (generateBtn) generateBtn.disabled = true;
      if (box) box.innerHTML = '<div class="small" style="color:#b45309;margin-top:7px">점검할 사안이 없습니다. 사안을 먼저 접수하거나 저장하세요.</div>';
      return null;
    }
    if (!silent && box) box.innerHTML = `<div class="small" style="margin-top:7px">${formShortName(key)} 생성 준비도를 점검하는 중입니다.</div>`;
    try {
      const result = await api('/api/documents/readiness', {method:'POST', body:JSON.stringify({documentKey:key, case:caseData, settings:readStorage('settings', {})})});
      renderPreflight(key, result.readiness || {});
      return result.readiness || null;
    } catch (e) {
      if (generateBtn) generateBtn.disabled = true;
      if (box) box.innerHTML = `<div class="small" style="color:#b91c1c;margin-top:7px">사전점검 실패: ${escapeHtml(e.message)}</div>`;
      return null;
    }
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
      documentList.innerHTML = docs.map(doc => {
        const strict = STRICT.has(doc.key);
        const sourceStatus = doc.templateReady ? '원본 등록' : '원본 미등록';
        const builtStatus = doc.builtTemplateReady ? '생성용 준비' : '생성용 미제작';
        return `
          <div class="docItem" data-key="${escapeHtml(doc.key)}">
            <div class="docHead">
              <div class="docName">${escapeHtml(doc.label)}</div>
              <span class="docStatus ${doc.builtTemplateReady ? 'ready' : 'missing'}">${escapeHtml(builtStatus)}</span>
            </div>
            <div class="small">단계: ${escapeHtml(doc.stage || '-')} · 파일: ${escapeHtml(doc.template || '-')}</div>
            <div class="docMetaStatus">${sourceStatus}${doc.structureProfileReady ? ' · 구조검증 있음' : ''}</div>
            <div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:8px">
              ${doc.automation==='manual_only' ? '' : `<button class="docBtn" data-upload="${escapeHtml(doc.key)}">원본 HWPX 등록</button><input type="file" accept=".hwpx" data-file="${escapeHtml(doc.key)}" style="display:none">`}
              <button class="docBtn" data-analyze="${escapeHtml(doc.key)}" ${doc.templateReady ? '' : 'disabled'}>구조 분석</button>
              ${strict ? `<button class="docBtn" data-preflight="${escapeHtml(doc.key)}">생성 전 점검</button>` : ''}
              <button class="docBtn" data-generate="${escapeHtml(doc.key)}" ${(doc.builtTemplateReady && !strict) ? '' : 'disabled'}>현재 사안으로 생성</button>
            </div>
            ${strict ? `<div data-readiness="${escapeHtml(doc.key)}"></div>` : ''}
            <div class="docResult" data-result="${escapeHtml(doc.key)}"></div>
          </div>`;
      }).join('');

      documentList.querySelectorAll('[data-upload]').forEach(btn => btn.addEventListener('click', () => documentList.querySelector(`[data-file="${CSS.escape(btn.dataset.upload)}"]`)?.click()));
      documentList.querySelectorAll('[data-file]').forEach(input => input.addEventListener('change', () => registerTemplate(input.dataset.file, input.files?.[0])));
      documentList.querySelectorAll('[data-analyze]').forEach(btn => btn.addEventListener('click', () => analyze(btn.dataset.analyze)));
      documentList.querySelectorAll('[data-preflight]').forEach(btn => btn.addEventListener('click', () => checkReadiness(btn.dataset.preflight)));
      documentList.querySelectorAll('[data-generate]').forEach(btn => btn.addEventListener('click', () => generate(btn.dataset.generate)));

      for (const key of [FORM10, FORM12]) {
        if (docs.some(d => d.key === key)) await checkReadiness(key, true);
      }
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
    if (box) box.textContent = 'HWPX 원본을 등록하고 구조를 분석하는 중입니다.';
    try {
      const encoded = await fileToBase64(file);
      const result = await api('/api/documents/register', {method:'POST', body:JSON.stringify({documentKey:key, fileName:file.name, base64:encoded})});
      const prep = result.sourcePreparation;
      if (box) box.innerHTML = `<span style="color:#15803d">원본 등록 완료: ${escapeHtml(result.template)}</span>` +
        (prep?.extractedFromBundle ? `<br><span style="color:#475569">서식모음집에서 해당 서식 영역만 자동 분리했습니다.</span>` : '');
      await renderDocuments();
    } catch (e) {
      if (box) box.innerHTML = `<span style="color:#b91c1c">원본 등록 실패: ${escapeHtml(e.message)}</span>`;
    }
  }

  async function analyze(key) {
    const box = documentList.querySelector(`[data-result="${CSS.escape(key)}"]`);
    if (box) box.textContent = 'HWPX 구조를 분석하는 중입니다.';
    try {
      const result = await api(`/api/documents/inspect?key=${encodeURIComponent(key)}`);
      const a = result.inspection || {};
      const groups = a.textSamples || [];
      const sampleLines = [];
      groups.slice(0,5).forEach(group => {
        const items=(group.items||[]).slice(0,12);
        if(items.length) sampleLines.push(`${group.file}: ${items.join(' / ')}`);
      });
      if (box) box.innerHTML = [
        '<b>구조 분석 완료</b>',
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
    try {
      const caseData = getCurrentCase();
      if (!caseData) throw new Error('현재 사안이 없습니다. 사안을 먼저 접수하거나 저장하세요.');
      if (STRICT.has(key)) {
        const readiness = await checkReadiness(key, true);
        if (!readiness?.ready) throw new Error(`${formShortName(key)} 생성 전 필수 점검을 완료하세요.`);
      }
      if (box) box.textContent = '문서를 생성하는 중입니다.';
      const result = await api('/api/documents/generate', {method:'POST', body:JSON.stringify({documentKey:key, case:caseData, settings:readStorage('settings', {})})});
      const missing = result.missingTokens || [];
      if (box) box.innerHTML = `생성 완료: <a href="${escapeHtml(result.downloadUrl)}">${escapeHtml(result.fileName)}</a>` +
        (missing.length ? `<br><span style="color:#b45309">미치환 토큰: ${escapeHtml(missing.join(', '))}</span>` : '<br><span style="color:#15803d">등록된 토큰 치환 완료</span>');
    } catch (e) {
      if (e.payload?.readiness && STRICT.has(key)) renderPreflight(key, e.payload.readiness);
      if (box) box.innerHTML = `<span style="color:#b91c1c">생성 실패: ${escapeHtml(e.message)}</span>`;
    }
  }

  documentBtn.addEventListener('click', async () => {
    if (enginePanel) enginePanel.classList.remove('open');
    documentPanel.classList.toggle('open');
    if (documentPanel.classList.contains('open')) await renderDocuments();
  });

  document.addEventListener('schoolsvs:template-built', () => {
    if (documentPanel.classList.contains('open')) renderDocuments();
  });
})();
