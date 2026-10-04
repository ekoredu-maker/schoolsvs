(() => {
  const frame = document.getElementById('legacyFrame');
  const btn = document.getElementById('atozBtn');
  const panel = document.getElementById('atozPanel');
  const form = document.getElementById('atozForm');
  const status = document.getElementById('atozStatus');
  const PREFIX = 'sv_assist_v2_';
  let activeCaseId = null;
  let patchedWindow = null;

  const fields = [
    'reporterName','reporterRole','recognitionPath','receiverName','receiverRole',
    'investigationMode','no2ActionDate','otherMatters','otherSchoolName',
    'otherSchoolNotifyAt','otherSchoolNotifyMethod','otherSchoolRecipient','otherSchoolContact',
    'victimInterviewTime','perpInterviewTime','victimRecoveryOpinion','perpRecoveryOpinion'
  ];
  const exceptionKeys = [
    'victimOpposed','notInEducationActivity','alreadySeparatedByEmergency',
    'differentSchool','offCampusExperience','selfResolutionFourCriteria'
  ];

  function legacyWindow(){ return frame?.contentWindow || null; }

  function currentFormDataRaw(){
    const w = legacyWindow();
    if (!w || typeof w.getFormData !== 'function') return null;
    try { return w.getFormData(); } catch (_) { return null; }
  }

  function readCases(){
    const w = legacyWindow();
    if (!w) return [];
    try { return JSON.parse(w.localStorage.getItem(PREFIX + 'cases') || '[]'); }
    catch (_) { return []; }
  }

  function writeCases(cases){
    const w = legacyWindow();
    if (!w) return;
    w.localStorage.setItem(PREFIX + 'cases', JSON.stringify(cases));
  }

  function locateCase(){
    const raw = currentFormDataRaw();
    const cases = readCases();
    if (raw?.id) {
      const found = cases.find(c => c.id === raw.id);
      if (found) return found;
    }
    if (raw?.caseNo) {
      const found = cases.find(c => c.caseNo === raw.caseNo);
      if (found) return found;
    }
    return cases.find(c => c.status !== '종결') || cases[0] || raw || null;
  }

  function readAtoz(data){ return (((data || {})._hybrid || {}).atoz || {}); }

  function fillPanel(data){
    const a = readAtoz(data);
    activeCaseId = data?.id || null;
    fields.forEach(key => {
      const el = form.elements[key];
      if (el) el.value = a[key] || '';
    });
    exceptionKeys.forEach(key => {
      const el = form.elements[key];
      if (el) el.checked = !!((a.separationExceptions || {})[key]);
    });
    form.elements.otherSchoolRelated.checked = !!a.otherSchoolRelated;
    form.elements.guardianNoticeChecked.checked = !!a.guardianNoticeChecked;
    form.elements.interviewAvailabilityChecked.checked = !!a.interviewAvailabilityChecked;
    status.textContent = data ? `${data.caseNo || '번호 미정'} 추가정보` : '현재 사안을 찾지 못했습니다.';
  }

  function collect(){
    const a = {};
    fields.forEach(key => { a[key] = String(form.elements[key]?.value || '').trim(); });
    a.otherSchoolRelated = !!form.elements.otherSchoolRelated.checked;
    a.guardianNoticeChecked = !!form.elements.guardianNoticeChecked.checked;
    a.interviewAvailabilityChecked = !!form.elements.interviewAvailabilityChecked.checked;
    a.separationExceptions = {};
    exceptionKeys.forEach(key => { a.separationExceptions[key] = !!form.elements[key]?.checked; });
    a.schemaVersion = 'cb-atoz-2026-v0.9';
    a.updatedAt = new Date().toISOString();
    return a;
  }

  function mergeInto(data){
    if (!data || typeof data !== 'object') return data;
    const stored = locateStoredForData(data);
    const extra = readAtoz(stored);
    if (!Object.keys(extra).length) return data;
    return {
      ...data,
      _hybrid: { ...(data._hybrid || {}), ...(stored?._hybrid || {}), atoz: extra }
    };
  }

  function locateStoredForData(data){
    const cases = readCases();
    return cases.find(c => (data.id && c.id === data.id) || (data.caseNo && c.caseNo === data.caseNo)) || null;
  }

  function patchGetFormData(){
    const w = legacyWindow();
    if (!w || patchedWindow === w || typeof w.getFormData !== 'function') return;
    const original = w.getFormData;
    if (original.__schoolsvsAtozWrapped) { patchedWindow = w; return; }
    function wrappedGetFormData(){
      const data = original.apply(this, arguments);
      return mergeInto(data);
    }
    wrappedGetFormData.__schoolsvsAtozWrapped = true;
    wrappedGetFormData.__original = original;
    w.getFormData = wrappedGetFormData;
    patchedWindow = w;
  }

  function save(){
    const cases = readCases();
    const raw = currentFormDataRaw();
    const idx = cases.findIndex(c => (activeCaseId && c.id === activeCaseId) || (raw?.id && c.id === raw.id) || (raw?.caseNo && c.caseNo === raw.caseNo));
    const a = collect();
    if (idx >= 0) {
      cases[idx] = { ...cases[idx], _hybrid: { ...(cases[idx]._hybrid || {}), atoz: a }, updatedAt: new Date().toISOString() };
      writeCases(cases);
      status.textContent = `${cases[idx].caseNo || '현재 사안'} · A to Z 추가정보 저장됨`;
    } else {
      const w = legacyWindow();
      if (w) w.localStorage.setItem(PREFIX + 'atoz_draft', JSON.stringify(a));
      status.textContent = '신규 사안 추가정보를 임시 저장했습니다. 사안을 저장하면 자동 연결됩니다.';
    }
    patchGetFormData();
  }

  function applyDraftToSaved(){
    const w = legacyWindow();
    if (!w) return;
    const raw = w.localStorage.getItem(PREFIX + 'atoz_draft');
    if (!raw) return;
    let draft; try { draft = JSON.parse(raw); } catch (_) { return; }
    const cases = readCases();
    if (!cases.length) return;
    const data = currentFormDataRaw();
    let idx = -1;
    if (data?.id) idx = cases.findIndex(c => c.id === data.id);
    if (idx < 0 && data?.caseNo) idx = cases.findIndex(c => c.caseNo === data.caseNo);
    if (idx < 0) idx = cases.length - 1;
    cases[idx] = { ...cases[idx], _hybrid:{ ...(cases[idx]._hybrid || {}), atoz:draft } };
    writeCases(cases);
    w.localStorage.removeItem(PREFIX + 'atoz_draft');
  }

  btn?.addEventListener('click', () => {
    fillPanel(locateCase());
    panel.classList.toggle('open');
  });
  document.getElementById('atozClose')?.addEventListener('click', () => panel.classList.remove('open'));
  document.getElementById('atozSave')?.addEventListener('click', save);

  frame?.addEventListener('load', () => {
    patchedWindow = null;
    setTimeout(() => { patchGetFormData(); applyDraftToSaved(); }, 100);
    try {
      frame.contentWindow.document.addEventListener('click', () => setTimeout(() => { patchGetFormData(); applyDraftToSaved(); }, 80), {passive:true});
    } catch (_) {}
  });
})();
