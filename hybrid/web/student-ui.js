(() => {
  const frame = document.getElementById('legacyFrame');
  if (!frame) return;
  const PREFIX = 'sv_assist_v2_';

  function ensureUi(){
    if (document.getElementById('studentPanel')) return;
    const style = document.createElement('style');
    style.textContent = `
      .studentPanel{position:fixed;right:14px;top:58px;width:min(820px,calc(100vw - 28px));max-height:84vh;overflow:auto;background:#fff;border:1px solid #cbd5e1;border-radius:14px;box-shadow:0 18px 45px rgba(15,23,42,.22);padding:14px;z-index:125;display:none}.studentPanel.open{display:block}.studentHead{display:flex;align-items:center;gap:8px;margin-bottom:8px}.studentHead h3{margin:0;color:#1f4b7a}.studentClose{margin-left:auto;border:1px solid #cbd5e1;background:#fff;border-radius:7px;padding:5px 8px;cursor:pointer}.studentNote{font-size:11px;color:#64748b;line-height:1.5;margin-bottom:10px}.studentCard{border:1px solid #dbe4ec;border-radius:12px;padding:10px;margin:9px 0;background:#fbfdff}.studentCardHead{display:flex;align-items:center;gap:7px;margin-bottom:8px}.studentRole{font-size:11px;font-weight:800;padding:3px 7px;border-radius:999px;background:#e0ecf7;color:#244b6f}.studentName{font-weight:800;color:#203040}.studentGrid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}.studentField label{display:block;font-size:10px;font-weight:700;color:#607488;margin-bottom:3px}.studentField input,.studentField select{width:100%;box-sizing:border-box;border:1px solid #cbd5e1;border-radius:7px;padding:6px;font:inherit;font-size:12px;background:#fff}.studentChecks{grid-column:1/-1;display:flex;gap:10px;flex-wrap:wrap;font-size:11px;color:#41576b}.studentFoot{display:flex;align-items:center;gap:8px;margin-top:10px}.studentSave{border:0;background:#1f4b7a;color:#fff;border-radius:8px;padding:7px 12px;cursor:pointer}.studentStatus{font-size:12px;color:#607488}.studentTopBtn{border:1px solid rgba(255,255,255,.35);background:transparent;color:#fff;border-radius:8px;padding:6px 10px;cursor:pointer}.studentTopBtn:hover{background:rgba(255,255,255,.12)}@media(max-width:820px){.studentGrid{grid-template-columns:1fr 1fr}}@media(max-width:560px){.studentGrid{grid-template-columns:1fr}}
    `;
    document.head.appendChild(style);

    const bar = document.querySelector('.hybridBar');
    const atozBtn = document.getElementById('atozBtn');
    const btn = document.createElement('button');
    btn.id = 'studentBtn';
    btn.className = 'studentTopBtn';
    btn.textContent = '관련학생 상세';
    if (atozBtn) bar?.insertBefore(btn, atozBtn);
    else bar?.appendChild(btn);

    const panel = document.createElement('div');
    panel.id = 'studentPanel';
    panel.className = 'studentPanel';
    panel.innerHTML = `
      <div class="studentHead"><h3>관련학생 상세정보</h3><button id="studentClose" class="studentClose">닫기</button></div>
      <div class="studentNote">기존 화면의 피해·가해관련학생 명단을 기준으로 서식10·12·20·21·22에서 재사용할 상세정보를 저장합니다. 2026 서식10에 맞춰 학생별 보호자 통보와 관계회복 프로그램 안내여부도 함께 관리합니다. 학생 이름과 역할 변경은 기존 화면에서 하세요.</div>
      <div id="studentList"></div>
      <div class="studentFoot"><button id="studentSave" class="studentSave">현재 사안에 저장</button><span id="studentStatus" class="studentStatus">사안을 선택하세요.</span></div>
    `;
    document.body.appendChild(panel);
  }

  ensureUi();
  const panel = document.getElementById('studentPanel');
  const listEl = document.getElementById('studentList');
  const statusEl = document.getElementById('studentStatus');
  let activeCase = null;
  let activeProfiles = [];

  function w(){ return frame.contentWindow || null; }
  function readCases(){
    try { return JSON.parse(w()?.localStorage.getItem(PREFIX + 'cases') || '[]'); }
    catch (_) { return []; }
  }
  function writeCases(cases){ w()?.localStorage.setItem(PREFIX + 'cases', JSON.stringify(cases)); }
  function currentData(){
    try {
      if (typeof w()?.getFormData === 'function') return w().getFormData();
    } catch (_) {}
    const cases = readCases();
    return cases.find(c => c.status !== '종결') || cases[0] || null;
  }
  function storedCase(data){
    const cases = readCases();
    return cases.find(c => (data?.id && c.id === data.id) || (data?.caseNo && c.caseNo === data.caseNo)) || null;
  }
  function esc(v){ return String(v ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch])); }

  function legacyPeople(data){
    const out = [];
    const groups = [['victim', data?.victims || []], ['perp', data?.perps || []]];
    groups.forEach(([role, items]) => {
      (Array.isArray(items) ? items : []).forEach((item, index) => {
        if (!item || typeof item !== 'object') return;
        const name = String(item.name || '').trim();
        if (!name) return;
        out.push({ role, index, item, name });
      });
    });
    return out;
  }

  function findExisting(existing, person){
    return existing.find(p => p.role === person.role && Number(p.legacyIndex) === person.index)
      || existing.find(p => p.role === person.role && String(p.name || '').trim() === person.name)
      || null;
  }

  function seedProfiles(data){
    const saved = storedCase(data) || data || {};
    const existing = saved?._hybrid?.studentProfiles;
    const source = Array.isArray(existing) ? existing : [];
    return legacyPeople(data || saved).map(person => {
      const old = findExisting(source, person) || {};
      const item = person.item || {};
      return {
        profileId: old.profileId || `${person.role}-${person.index}`,
        role: person.role,
        legacyIndex: person.index,
        name: person.name,
        schoolName: old.schoolName || item.school || saved.school || '',
        grade: old.grade || item.grade || '',
        classNo: old.classNo || item.classNo || item.class || '',
        number: old.number || item.number || item.no || '',
        gender: old.gender || item.gender || item.sex || '',
        guardianName: old.guardianName || item.guardianName || item.parentName || '',
        guardianContact: old.guardianContact || item.guardianContact || item.parentContact || '',
        guardianNoticeAt: old.guardianNoticeAt || '',
        guardianNoticeMethod: old.guardianNoticeMethod || '',
        recoveryGuidance: old.recoveryGuidance || '',
        relatedSchoolCaseNo: old.relatedSchoolCaseNo || '',
        athlete: !!old.athlete,
        disabled: !!old.disabled,
        specialEducation: !!old.specialEducation,
        multicultural: !!old.multicultural,
        northKoreanDefector: !!old.northKoreanDefector,
      };
    });
  }

  function field(name, label, value, type='text', extra=''){
    return `<div class="studentField"><label>${label}</label><input ${type === 'datetime-local' ? 'type="datetime-local"' : ''} data-field="${name}" value="${esc(value)}" ${extra}></div>`;
  }

  function render(data){
    activeCase = storedCase(data);
    activeProfiles = seedProfiles(data);
    if (!activeProfiles.length) {
      listEl.innerHTML = '<div class="studentNote">기존 화면에서 피해관련학생과 가해관련학생을 먼저 입력하세요.</div>';
      statusEl.textContent = activeCase ? '관련학생 명단이 없습니다.' : '사안을 먼저 저장하세요.';
      return;
    }
    listEl.innerHTML = activeProfiles.map((p, idx) => `
      <div class="studentCard" data-index="${idx}">
        <div class="studentCardHead"><span class="studentRole">${p.role === 'victim' ? '피해관련' : '가해관련'}</span><span class="studentName">${esc(p.name)}</span></div>
        <div class="studentGrid">
          ${field('schoolName','소속학교',p.schoolName)}
          ${field('grade','학년',p.grade)}
          ${field('classNo','반',p.classNo)}
          ${field('number','번호',p.number)}
          <div class="studentField"><label>성별</label><select data-field="gender"><option value="">선택</option><option value="남" ${p.gender==='남'?'selected':''}>남</option><option value="여" ${p.gender==='여'?'selected':''}>여</option></select></div>
          ${field('guardianName','보호자 성명',p.guardianName)}
          ${field('guardianContact','보호자 연락처',p.guardianContact)}
          ${field('relatedSchoolCaseNo','공동사안 관련학교 사안번호',p.relatedSchoolCaseNo)}
          ${field('guardianNoticeAt','보호자 통보 일시',p.guardianNoticeAt,'datetime-local')}
          ${field('guardianNoticeMethod','보호자 통보 방법',p.guardianNoticeMethod)}
          <div class="studentField"><label>관계회복 프로그램 안내여부</label><select data-field="recoveryGuidance"><option value="">선택</option><option value="O" ${p.recoveryGuidance==='O'||p.recoveryGuidance==='○'?'selected':''}>안내 ○</option><option value="X" ${p.recoveryGuidance==='X'?'selected':''}>미안내 X</option></select></div>
          <div class="studentChecks">
            <label><input type="checkbox" data-flag="athlete" ${p.athlete?'checked':''}> 학생선수</label>
            <label><input type="checkbox" data-flag="disabled" ${p.disabled?'checked':''}> 장애학생</label>
            <label><input type="checkbox" data-flag="specialEducation" ${p.specialEducation?'checked':''}> 특수교육대상자</label>
            <label><input type="checkbox" data-flag="multicultural" ${p.multicultural?'checked':''}> 다문화학생</label>
            <label><input type="checkbox" data-flag="northKoreanDefector" ${p.northKoreanDefector?'checked':''}> 탈북학생</label>
          </div>
        </div>
      </div>
    `).join('');
    statusEl.textContent = `${activeCase?.caseNo || data?.caseNo || '현재 사안'} · ${activeProfiles.length}명`;
  }

  function collect(){
    const profiles = activeProfiles.map(p => ({...p}));
    listEl.querySelectorAll('.studentCard').forEach(card => {
      const idx = Number(card.dataset.index);
      const p = profiles[idx];
      if (!p) return;
      card.querySelectorAll('[data-field]').forEach(el => { p[el.dataset.field] = String(el.value || '').trim(); });
      card.querySelectorAll('[data-flag]').forEach(el => { p[el.dataset.flag] = !!el.checked; });
    });
    return profiles;
  }

  function readiness(profiles){
    const required = ['schoolName','grade','classNo','number','gender','guardianNoticeAt','guardianNoticeMethod','recoveryGuidance'];
    const total = profiles.length * required.length;
    const filled = profiles.reduce((sum,p) => sum + required.filter(k => String(p[k] || '').trim()).length, 0);
    return total ? Math.round(filled / total * 100) : 0;
  }

  function save(){
    const data = currentData();
    const cases = readCases();
    const idx = cases.findIndex(c => (data?.id && c.id === data.id) || (data?.caseNo && c.caseNo === data.caseNo));
    if (idx < 0) {
      statusEl.textContent = '기본 사안을 먼저 저장한 뒤 관련학생 상세정보를 저장하세요.';
      return;
    }
    const profiles = collect();
    cases[idx] = {
      ...cases[idx],
      _hybrid: {
        ...(cases[idx]._hybrid || {}),
        studentProfileSchemaVersion: 'cb-atoz-2026-v0.15',
        studentProfiles: profiles,
      },
      updatedAt: new Date().toISOString(),
    };
    writeCases(cases);
    activeCase = cases[idx];
    activeProfiles = profiles;
    statusEl.textContent = `${cases[idx].caseNo || '현재 사안'} · ${profiles.length}명 저장 · 서식10 핵심정보 ${readiness(profiles)}%`;
  }

  document.getElementById('studentBtn')?.addEventListener('click', () => { render(currentData()); panel.classList.toggle('open'); });
  document.getElementById('studentClose')?.addEventListener('click', () => panel.classList.remove('open'));
  document.getElementById('studentSave')?.addEventListener('click', save);
})();
