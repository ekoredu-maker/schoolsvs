(() => {
  const FORM10 = 'form10_case_report';
  const documentList = document.getElementById('documentList');
  if (!documentList) return;

  async function api(path) {
    const res = await fetch(path, {headers:{'Content-Type':'application/json'}});
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    return data;
  }

  function esc(v) {
    return String(v ?? '').replace(/[&<>"']/g, s => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[s]));
  }

  function addButton() {
    const item = documentList.querySelector(`.docItem[data-key="${FORM10}"]`);
    if (!item || item.querySelector('[data-structure-check]')) return;
    const analyze = item.querySelector('[data-analyze]');
    const btn = document.createElement('button');
    btn.className = 'docBtn';
    btn.dataset.structureCheck = FORM10;
    btn.textContent = '구조 검증';
    if (analyze) analyze.insertAdjacentElement('afterend', btn); else item.appendChild(btn);
    btn.addEventListener('click', () => verifyStructure(item));
  }

  async function verifyStructure(item) {
    const box = item.querySelector(`[data-result="${FORM10}"]`);
    if (box) box.textContent = '충북 서식10 구조 프로파일과 대조하는 중입니다.';
    try {
      const result = await api(`/api/documents/structure?key=${encodeURIComponent(FORM10)}`);
      const r = result.report || {};
      const diffs = r.observed2026Differences || [];
      const status2025 = r.reference2025Match ? '일치' : '불일치/부분일치';
      const status2026 = r.productionReadyFor2026 ? '구조 신호 확인' : '최종 확정 전';
      if (box) box.innerHTML = `
        <div style="margin-top:8px;border:1px solid #dbe4ec;border-radius:9px;padding:9px;background:#f8fafc;font-size:11px;line-height:1.5">
          <b>충북 서식10 구조 검증</b><br>
          표 구조: ${esc(r.rows)}행 × ${esc(r.cols)}열 · 관리직 표기: ${esc(r.managerTitle || '-')}<br>
          2025 HWPX 구조 기준: <b>${esc(status2025)}</b><br>
          2026 최종서식 상태: <b style="color:${r.productionReadyFor2026 ? '#166534' : '#9a3412'}">${esc(status2026)}</b><br>
          <span style="color:#64748b">${esc(r.productionNote || '')}</span>
          ${diffs.length ? `<div style="margin-top:7px"><b>2026 PDF와 확인된 차이</b><br>${diffs.map(d => `• ${esc(d.key)}: ${esc(d.reference2025)} → ${esc(d.guidance2026)}${d.status === 'needs_2026_hwpx_confirmation' ? ' (HWPX 확인 필요)' : ''}`).join('<br>')}</div>` : ''}
        </div>`;
    } catch (e) {
      if (box) box.innerHTML = `<span style="color:#b45309">구조 검증자료가 아직 없습니다. 먼저 서식10 HWPX 또는 전체 서식모음집을 등록하세요. (${esc(e.message)})</span>`;
    }
  }

  const observer = new MutationObserver(addButton);
  observer.observe(documentList, {childList:true, subtree:true});
  addButton();
})();
