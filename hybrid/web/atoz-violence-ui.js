(() => {
  const frame = document.getElementById('legacyFrame');
  if (!frame) return;
  const PREFIX = 'sv_assist_v2_';
  const OPTIONS = ['신체폭력','언어폭력','금품갈취','강요','따돌림','성폭력','사이버폭력','기타','아동학대'];
  let installed = false;

  function w(){ return frame.contentWindow || null; }
  function readCases(){
    try { return JSON.parse(w()?.localStorage.getItem(PREFIX + 'cases') || '[]'); }
    catch (_) { return []; }
  }
  function writeCases(cases){ w()?.localStorage.setItem(PREFIX + 'cases', JSON.stringify(cases)); }
  function rawData(){
    try { return typeof w()?.getFormData === 'function' ? w().getFormData() : null; }
    catch (_) { return null; }
  }
  function current(){
    const data = rawData();
    const cases = readCases();
    return cases.find(c => (data?.id && c.id === data.id) || (data?.caseNo && c.caseNo === data.caseNo))
      || cases.find(c => c.status !== '종결') || cases[0] || data || null;
  }
  function readAtoz(data){ return (((data || {})._hybrid || {}).atoz || {}); }

  function selectedFrom(data){
    const saved = readAtoz(data).violenceTypes;
    if (Array.isArray(saved) && saved.length) return new Set(saved.map(String));
    const legacy = String(data?.violenceType || '').trim();
    return new Set(OPTIONS.includes(legacy) ? [legacy] : []);
  }

  function fill(){
    const box = document.getElementById('atozViolenceTypes');
    if (!box) return;
    const data = current();
    const selected = selectedFrom(data);
    box.querySelectorAll('input[data-violence]').forEach(input => {
      input.checked = selected.has(input.dataset.violence);
    });
    const note = document.getElementById('atozViolenceNote');
    if (note) {
      note.textContent = String(data?.violenceType || '') === '복합(2개 이상)' && !selected.size
        ? '기존 사안이 복합 유형입니다. 서식10에 표시할 실제 유형을 2개 이상 선택하세요.'
        : '서식10은 중복 체크가 가능하므로 실제 해당 유형을 모두 선택합니다.';
    }
  }

  function collect(){
    return [...document.querySelectorAll('#atozViolenceTypes input[data-violence]:checked')]
      .map(input => input.dataset.violence);
  }

  function saveDetail(){
    const selected = collect();
    const data = rawData();
    const cases = readCases();
    let idx = data?.id ? cases.findIndex(c => c.id === data.id) : -1;
    if (idx < 0 && data?.caseNo) idx = cases.findIndex(c => c.caseNo === data.caseNo);
    if (idx >= 0) {
      const old = readAtoz(cases[idx]);
      cases[idx] = {
        ...cases[idx],
        _hybrid: {
          ...(cases[idx]._hybrid || {}),
          atoz: {...old, violenceTypes:selected, schemaVersion:'cb-atoz-2026-v0.16'}
        }
      };
      writeCases(cases);
      return;
    }
    try {
      const raw = w()?.localStorage.getItem(PREFIX + 'atoz_draft');
      const draft = raw ? JSON.parse(raw) : {};
      draft.violenceTypes = selected;
      draft.schemaVersion = 'cb-atoz-2026-v0.16';
      w()?.localStorage.setItem(PREFIX + 'atoz_draft', JSON.stringify(draft));
    } catch (_) {}
  }

  function install(){
    if (installed) return true;
    const form = document.getElementById('atozForm');
    const saveBtn = document.getElementById('atozSave');
    const openBtn = document.getElementById('atozBtn');
    if (!form || !saveBtn || !openBtn) return false;

    const field = document.createElement('div');
    field.className = 'atozField full';
    field.innerHTML = `
      <label>학교폭력 유형 · 서식10 중복체크</label>
      <div id="atozViolenceTypes" class="atozChecks">
        ${OPTIONS.map(v => `<label><input type="checkbox" data-violence="${v}"> ${v}</label>`).join('')}
      </div>
      <div id="atozViolenceNote" style="font-size:10px;color:#64748b;margin-top:5px"></div>`;
    const investigation = form.querySelector('select[name="investigationMode"]')?.closest('.atozField');
    if (investigation) form.insertBefore(field, investigation);
    else form.appendChild(field);

    openBtn.addEventListener('click', () => setTimeout(fill, 30));
    saveBtn.addEventListener('click', () => setTimeout(saveDetail, 0));
    installed = true;
    return true;
  }

  if (!install()) {
    const observer = new MutationObserver(() => { if (install()) observer.disconnect(); });
    observer.observe(document.body, {childList:true, subtree:true});
  }
})();
