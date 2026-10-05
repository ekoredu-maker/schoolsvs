(() => {
  const frame = document.getElementById('legacyFrame');
  const bar = document.querySelector('.hybridBar');
  if (!frame || !bar) return;

  const PREFIX = 'sv_assist_v2_';
  const FORMAT = 'schoolsvs-backup';
  const VERSION = '1.0';
  const SAMPLE_URL = '../sample-data/schoolsvs_sample_cases.json';

  function win(){ return frame.contentWindow || null; }
  function ls(){ try { return win()?.localStorage || null; } catch (_) { return null; } }
  function readJson(key, fallback){
    try {
      const raw = ls()?.getItem(PREFIX + key);
      return raw ? JSON.parse(raw) : fallback;
    } catch (_) { return fallback; }
  }
  function readLocalState(){
    return {
      cases: readJson('cases', []),
      counter: readJson('counter', 1),
      settings: readJson('settings', {})
    };
  }
  function stripInternalSettings(settings){
    const out = {};
    Object.entries(settings && typeof settings === 'object' ? settings : {}).forEach(([k,v]) => {
      if (String(k).startsWith('_hybrid')) return;
      out[k] = v;
    });
    return out;
  }
  function normalizeCase(item, index){
    if (!item || typeof item !== 'object') return null;
    const out = {...item};
    let id = String(out.id || '').trim();
    const caseNo = String(out.caseNo || out.case_no || '').trim();
    if (!id && caseNo) id = 'import_' + caseNo.replace(/[^0-9A-Za-z가-힣_-]+/g, '_');
    if (!id) id = `import_${Date.now()}_${index}`;
    out.id = id;
    return out;
  }
  function validatePayload(raw){
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) throw new Error('백업 파일의 최상위 구조가 올바르지 않습니다.');
    if (!Array.isArray(raw.cases)) throw new Error('cases 목록이 없는 파일입니다.');
    const cases = raw.cases.map(normalizeCase).filter(Boolean);
    if (!cases.length) throw new Error('가져올 사안이 없습니다.');
    return {
      format: raw.format || 'legacy-schoolsvs-backup',
      version: raw.version || 'legacy',
      exportedAt: raw.exportedAt || raw.createdAt || '',
      sampleData: !!raw.sampleData,
      description: raw.description || '',
      cases,
      counter: Number(raw.counter || 1) || 1,
      settings: raw.settings && typeof raw.settings === 'object' ? raw.settings : {}
    };
  }
  function sameCase(a,b){
    const aid = String(a?.id || '');
    const bid = String(b?.id || '');
    if (aid && bid && aid === bid) return true;
    const ano = String(a?.caseNo || '').trim();
    const bno = String(b?.caseNo || '').trim();
    return !!ano && !!bno && ano === bno;
  }
  function mergeCases(existing, incoming, overwriteConflicts){
    const result = [...(Array.isArray(existing) ? existing : [])];
    let added = 0, overwritten = 0, skipped = 0;
    incoming.forEach(item => {
      const idx = result.findIndex(old => sameCase(old, item));
      if (idx < 0) {
        result.push(item);
        added += 1;
      } else if (overwriteConflicts) {
        result[idx] = {...result[idx], ...item, _hybrid:{...(result[idx]?._hybrid || {}), ...(item?._hybrid || {})}};
        overwritten += 1;
      } else {
        skipped += 1;
      }
    });
    return {cases:result, added, overwritten, skipped};
  }
  function countConflicts(existing, incoming){
    return incoming.filter(item => existing.some(old => sameCase(old,item))).length;
  }
  async function apiState(payload){
    const res = await fetch('/api/state', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({...payload, mode:'merge'})
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    return data;
  }
  function safeNamePart(v){ return String(v).padStart(2,'0'); }
  function downloadJson(payload){
    const d = new Date();
    const stamp = `${d.getFullYear()}${safeNamePart(d.getMonth()+1)}${safeNamePart(d.getDate())}_${safeNamePart(d.getHours())}${safeNamePart(d.getMinutes())}`;
    const blob = new Blob([JSON.stringify(payload,null,2)], {type:'application/json;charset=utf-8'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `SchoolSVS_backup_${stamp}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1200);
  }
  async function exportBackup(){
    try {
      const local = readLocalState();
      let server = null;
      try {
        const res = await fetch('/api/state');
        if (res.ok) server = await res.json();
      } catch (_) {}
      const merged = [];
      const addUnique = items => (Array.isArray(items)?items:[]).forEach(item => {
        const idx = merged.findIndex(old => sameCase(old,item));
        if (idx < 0) merged.push(item); else merged[idx] = {...merged[idx], ...item, _hybrid:{...(merged[idx]?._hybrid||{}), ...(item?._hybrid||{})}};
      });
      addUnique(server?.cases || []);
      addUnique(local.cases || []);
      const payload = {
        format: FORMAT,
        version: VERSION,
        exportedAt: new Date().toISOString(),
        appId: 'schoolsvs-hybrid',
        cases: merged,
        counter: Math.max(Number(local.counter || 1), Number(server?.counter || 1)),
        settings: stripInternalSettings(local.settings || server?.settings || {})
      };
      downloadJson(payload);
      alert(`백업 파일을 만들었습니다.\n사안 ${merged.length}건이 포함되었습니다.`);
    } catch (e) {
      alert(`백업 내보내기에 실패했습니다.\n${e.message}`);
    }
  }
  async function importPayload(raw, sourceLabel='백업파일'){
    const payload = validatePayload(raw);
    const current = readLocalState();
    const conflictCount = countConflicts(current.cases || [], payload.cases);
    let overwrite = true;
    if (conflictCount > 0) {
      overwrite = confirm(
        `${sourceLabel}에 기존 자료와 같은 사안이 ${conflictCount}건 있습니다.\n\n` +
        `확인: 가져온 내용으로 해당 사안을 갱신\n취소: 충돌 사안은 건너뜀`
      );
    }
    const merged = mergeCases(current.cases || [], payload.cases, overwrite);
    let settings = current.settings && typeof current.settings === 'object' ? {...current.settings} : {};
    if (!payload.sampleData && Object.keys(payload.settings || {}).length) {
      const importSettings = confirm('백업에 포함된 학교/담당자 기본설정도 가져오시겠습니까?\n취소하면 현재 설정을 유지합니다.');
      if (importSettings) settings = {...settings, ...stripInternalSettings(payload.settings)};
    }
    const counter = Math.max(Number(current.counter || 1), Number(payload.counter || 1), merged.cases.length + 1);

    const storage = ls();
    if (!storage) throw new Error('브라우저 저장소에 접근할 수 없습니다.');
    storage.setItem(PREFIX + 'cases', JSON.stringify(merged.cases));
    storage.setItem(PREFIX + 'counter', JSON.stringify(counter));
    storage.setItem(PREFIX + 'settings', JSON.stringify(settings));

    await apiState({cases:merged.cases, counter, settings});

    const label = payload.sampleData ? '예시 데이터' : sourceLabel;
    alert(
      `${label} 가져오기가 완료되었습니다.\n\n` +
      `추가 ${merged.added}건 / 갱신 ${merged.overwritten}건 / 건너뜀 ${merged.skipped}건\n` +
      `현재 사안 ${merged.cases.length}건\n\n화면을 새로 불러옵니다.`
    );
    try { win()?.location.reload(); } catch (_) { location.reload(); }
  }
  async function importFile(file){
    if (!file) return;
    try {
      const text = await file.text();
      const raw = JSON.parse(text);
      await importPayload(raw, file.name);
    } catch (e) {
      alert(`백업 가져오기에 실패했습니다.\n${e.message}`);
    }
  }
  async function loadSampleData(){
    const ok = confirm(
      '서식 검증용 완전 가상사안 3건을 현재 자료에 병합합니다.\n' +
      '실제 학교/학생 정보는 포함되어 있지 않습니다.\n\n계속하시겠습니까?'
    );
    if (!ok) return;
    try {
      const res = await fetch(SAMPLE_URL, {cache:'no-store'});
      if (!res.ok) throw new Error(`예시 데이터 파일을 읽지 못했습니다. HTTP ${res.status}`);
      await importPayload(await res.json(), '내장 예시 데이터');
    } catch (e) {
      alert(`예시 데이터 가져오기에 실패했습니다.\n${e.message}`);
    }
  }

  const fileInput = document.createElement('input');
  fileInput.type = 'file';
  fileInput.accept = '.json,application/json';
  fileInput.style.display = 'none';
  fileInput.addEventListener('change', async () => {
    const file = fileInput.files?.[0];
    fileInput.value = '';
    if (file) await importFile(file);
  });
  document.body.appendChild(fileInput);

  function button(label, fn){
    const b = document.createElement('button');
    b.type = 'button'; b.textContent = label; b.addEventListener('click', fn);
    return b;
  }
  function installMenu(){
    if (document.getElementById('schoolsvsDataMenu')) return;
    const wrap = document.createElement('div');
    wrap.className = 'simpleMenuWrap';
    wrap.id = 'schoolsvsDataMenu';
    const trigger = document.createElement('button');
    trigger.className = 'hybridBtn';
    trigger.type = 'button';
    trigger.textContent = '데이터';
    const menu = document.createElement('div');
    menu.className = 'simpleMenu';
    const muted = document.createElement('div');
    muted.className = 'muted';
    muted.textContent = '백업 · 복원 · 서식 테스트';
    menu.append(
      muted,
      button('백업 내보내기', exportBackup),
      button('백업 가져오기', () => fileInput.click()),
      button('예시 데이터 불러오기', loadSampleData)
    );
    trigger.addEventListener('click', e => {
      e.stopPropagation();
      document.querySelectorAll('.simpleMenu.open').forEach(x => { if (x !== menu) x.classList.remove('open'); });
      menu.classList.toggle('open');
    });
    menu.addEventListener('click', e => e.stopPropagation());
    wrap.append(trigger,menu);
    bar.appendChild(wrap);
  }

  window.SchoolSVSBackup = {exportBackup, importPayload, loadSampleData};
  installMenu();
})();