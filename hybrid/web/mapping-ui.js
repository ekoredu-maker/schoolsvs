(() => {
  const documentList = document.getElementById('documentList');
  if (!documentList) return;

  async function api(path, options = {}) {
    const res = await fetch(path, {
      ...options,
      headers: {'Content-Type':'application/json', ...(options.headers || {})}
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    return data;
  }

  function esc(v) {
    return String(v ?? '').replace(/[&<>"']/g, s => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[s]));
  }

  function ensureOverlay() {
    let overlay = document.getElementById('mappingOverlay');
    if (overlay) return overlay;
    overlay = document.createElement('div');
    overlay.id = 'mappingOverlay';
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(15,23,42,.48);z-index:300;display:none;align-items:center;justify-content:center;padding:24px';
    overlay.innerHTML = `
      <div style="width:min(980px,96vw);max-height:88vh;overflow:auto;background:#fff;border-radius:14px;box-shadow:0 24px 70px rgba(0,0,0,.28);padding:18px">
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px">
          <h3 id="mappingTitle" style="margin:0;color:#173a5c">HWPX 필드 매핑</h3>
          <span id="mappingProgress" style="font-size:12px;color:#64748b"></span>
          <button id="mappingClose" style="margin-left:auto;border:1px solid #cbd5e1;background:#fff;border-radius:8px;padding:6px 10px;cursor:pointer">닫기</button>
        </div>
        <div id="mappingNotice" style="font-size:12px;color:#64748b;margin-bottom:10px"></div>
        <div id="mappingRows"></div>
        <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:14px">
          <button id="mappingSaveDraft" style="border:1px solid #94a3b8;background:#fff;border-radius:8px;padding:7px 12px;cursor:pointer">초안 저장</button>
          <button id="mappingSaveReviewed" style="border:1px solid #173a5c;background:#173a5c;color:#fff;border-radius:8px;padding:7px 12px;cursor:pointer">검토완료 저장</button>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    overlay.querySelector('#mappingClose').addEventListener('click', () => overlay.style.display='none');
    overlay.addEventListener('click', e => { if (e.target === overlay) overlay.style.display='none'; });
    return overlay;
  }

  function addMappingButtons() {
    documentList.querySelectorAll('.docItem').forEach(item => {
      if (item.querySelector('[data-map]')) return;
      const key = item.dataset.key;
      const btn = document.createElement('button');
      btn.className = 'docBtn';
      btn.dataset.map = key;
      btn.textContent = '필드 매핑';
      btn.style.marginLeft = '6px';
      const generate = item.querySelector('[data-generate]');
      if (generate) generate.insertAdjacentElement('afterend', btn); else item.appendChild(btn);
      btn.addEventListener('click', () => openMapping(key));
    });
  }

  async function openMapping(key) {
    const overlay = ensureOverlay();
    overlay.style.display = 'flex';
    const title = overlay.querySelector('#mappingTitle');
    const notice = overlay.querySelector('#mappingNotice');
    const rows = overlay.querySelector('#mappingRows');
    const progress = overlay.querySelector('#mappingProgress');
    title.textContent = 'HWPX 필드 매핑';
    notice.textContent = '매핑 정보를 불러오는 중입니다.';
    rows.innerHTML = '';
    try {
      const result = await api(`/api/documents/mapping?key=${encodeURIComponent(key)}`);
      const ws = result.workspace || {};
      title.textContent = `${ws.label || key} · 필드 매핑`;
      const p = ws.progress || {};
      progress.textContent = `확정 ${p.confirmed || 0}/${p.total || 0}`;
      notice.textContent = ws.analysisReady
        ? '원본 HWPX 분석 결과에서 후보 문구를 추천했습니다. 위치가 맞는 항목만 확인 체크 후 저장하세요.'
        : '원본 HWPX가 아직 분석되지 않았습니다. 먼저 원본을 등록하면 앵커 후보를 추천할 수 있습니다.';
      const saved = new Map((ws.mapping?.items || []).map(x => [x.token, x]));
      rows.innerHTML = (ws.suggestions || []).map(s => {
        const old = saved.get(s.token) || {};
        const candidates = s.candidates || [];
        const candidateOptions = candidates.map(c => `<option value="${esc(c.text)}" data-file="${esc(c.xmlFile)}" ${old.anchor === c.text ? 'selected' : ''}>${esc(c.text)}${c.xmlFile ? ' · '+esc(c.xmlFile) : ''}</option>`).join('');
        return `<div class="mapRow" data-token="${esc(s.token)}" data-source="${esc(s.source)}" style="display:grid;grid-template-columns:150px 170px 1fr 90px;gap:8px;align-items:center;padding:9px 0;border-bottom:1px solid #e2e8f0">
          <div><b style="font-size:12px">${esc(s.label || s.token)}</b><div style="font-size:11px;color:#64748b">${esc(s.token)}</div></div>
          <div style="font-size:12px;color:#334155">${esc(s.source)}</div>
          <div>
            <select class="mapAnchor" style="width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:7px">
              <option value="">${ws.analysisReady ? '앵커 후보 선택' : '분석자료 없음'}</option>${candidateOptions}
            </select>
            <input class="mapManual" value="${esc(old.anchor || '')}" placeholder="직접 앵커 문구 입력" style="width:calc(100% - 14px);margin-top:5px;padding:6px;border:1px solid #cbd5e1;border-radius:7px">
          </div>
          <label style="font-size:12px"><input type="checkbox" class="mapConfirmed" ${old.confirmed ? 'checked' : ''}> 확인</label>
        </div>`;
      }).join('');
      rows.querySelectorAll('.mapRow').forEach(row => {
        const select = row.querySelector('.mapAnchor');
        const input = row.querySelector('.mapManual');
        select.addEventListener('change', () => { if (select.value) input.value = select.value; });
      });
      overlay.dataset.key = key;
      overlay.querySelector('#mappingSaveDraft').onclick = () => saveMapping(overlay, 'draft');
      overlay.querySelector('#mappingSaveReviewed').onclick = () => saveMapping(overlay, 'reviewed');
    } catch (e) {
      notice.textContent = `매핑 불러오기 실패: ${e.message}`;
    }
  }

  async function saveMapping(overlay, status) {
    const key = overlay.dataset.key;
    const items = [...overlay.querySelectorAll('.mapRow')].map(row => ({
      token: row.dataset.token,
      source: row.dataset.source,
      anchor: row.querySelector('.mapManual').value.trim(),
      confirmed: row.querySelector('.mapConfirmed').checked,
      strategy: 'review'
    })).filter(x => x.anchor || x.confirmed);
    const notice = overlay.querySelector('#mappingNotice');
    try {
      const result = await api('/api/documents/mapping', {
        method:'POST', body:JSON.stringify({documentKey:key, items, status})
      });
      const confirmed = (result.mapping?.items || []).filter(x => x.confirmed).length;
      overlay.querySelector('#mappingProgress').textContent = `확정 ${confirmed}/${overlay.querySelectorAll('.mapRow').length}`;
      notice.textContent = status === 'reviewed'
        ? '검토완료 상태로 저장했습니다. 실제 서식 생성 전에는 원본 한글 문서와 출력 비교가 필요합니다.'
        : '매핑 초안을 저장했습니다.';
    } catch (e) {
      notice.textContent = `저장 실패: ${e.message}`;
    }
  }

  const observer = new MutationObserver(addMappingButtons);
  observer.observe(documentList, {childList:true, subtree:true});
  addMappingButtons();
})();
