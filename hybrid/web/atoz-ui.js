(() => {
  const frame = document.getElementById('legacyFrame');
  if (!frame) return;
  const PREFIX = 'sv_assist_v2_';
  let activeCaseId = null;
  let patchedWindow = null;

  function ensureUi(){
    if (!document.getElementById('atozPanel')) {
      const style = document.createElement('style');
      style.textContent = `
        .atozPanel{position:fixed;right:14px;top:58px;width:min(620px,calc(100vw - 28px));max-height:82vh;overflow:auto;background:#fff;border:1px solid #cbd5e1;border-radius:14px;box-shadow:0 18px 45px rgba(15,23,42,.22);padding:14px;z-index:120;display:none}.atozPanel.open{display:block}.atozPanel h3{margin:0;color:#1f4b7a}.atozHead{display:flex;align-items:center;gap:8px;margin-bottom:10px}.atozClose{margin-left:auto;border:1px solid #cbd5e1;background:#fff;border-radius:7px;padding:5px 8px;cursor:pointer}.atozGrid{display:grid;grid-template-columns:1fr 1fr;gap:9px}.atozField{border:1px solid #e2e8f0;border-radius:9px;padding:8px;background:#fbfdff}.atozField.full{grid-column:1/-1}.atozField label{display:block;font-size:11px;font-weight:700;color:#52677b;margin-bottom:4px}.atozField input,.atozField select,.atozField textarea{width:100%;box-sizing:border-box;border:1px solid #cbd5e1;border-radius:7px;padding:7px;font:inherit;font-size:12px;background:#fff}.atozField textarea{min-height:62px;resize:vertical}.atozChecks{display:grid;grid-template-columns:1fr 1fr;gap:5px;font-size:12px}.atozChecks label{font-weight:400;margin:0}.atozFoot{display:flex;align-items:center;gap:8px;margin-top:10px}.atozSave{border:0;background:#1f4b7a;color:#fff;border-radius:8px;padding:7px 12px;cursor:pointer}.atozStatus{font-size:12px;color:#607488}.atozNote{font-size:11px;color:#64748b;line-height:1.45;margin:4px 0 10px}.atozTopBtn{border:1px solid rgba(255,255,255,.35);background:transparent;color:#fff;border-radius:8px;padding:6px 10px;cursor:pointer}.atozTopBtn:hover{background:rgba(255,255,255,.12)}@media(max-width:700px){.atozGrid{grid-template-columns:1fr}.atozField.full{grid-column:auto}.atozChecks{grid-template-columns:1fr}}
      `;
      document.head.appendChild(style);

      const bar = document.querySelector('.hybridBar');
      const panelBtn = document.getElementById('panelBtn');
      const topBtn = document.createElement('button');
      topBtn.id = 'atozBtn';
      topBtn.className = 'atozTopBtn';
      topBtn.textContent = 'A to Z 추가정보';
      bar?.insertBefore(topBtn, panelBtn || null);

      const panel = document.createElement('div');
      panel.id = 'atozPanel';
      panel.className = 'atozPanel';
      panel.innerHTML = `
        <div class="atozHead"><h3>초기대응 · 서식10 추가정보</h3><button id="atozClose" class="atozClose">닫기</button></div>
        <div class="atozNote">2026 충북 A to Z의 서식10 항목을 기존 사안정보에 보완합니다. 서식3 신고접수대장은 수기 작성 대상이므로 이 화면이 전자대장을 대신하지 않습니다.</div>
        <form id="atozForm" class="atozGrid">
          <div class="atozField"><label>신고자 성명</label><input name="reporterName"></div>
          <div class="atozField"><label>신고자 신분</label><input name="reporterRole" placeholder="학생·보호자·교직원 등"></div>
          <div class="atozField full"><label>접수·인지 경로</label><input name="recognitionPath" placeholder="학생 상담 중 인지, 보호자 신고 등"></div>
          <div class="atozField"><label>접수자·인지자 성명</label><input name="receiverName"></div>
          <div class="atozField"><label>접수자·인지자 신분</label><input name="receiverRole" placeholder="학교폭력담당교사 등"></div>
          <div class="atozField"><label>조사 방식</label><select name="investigationMode"><option value="">선택</option><option value="investigator">전담조사관 배정 요청</option><option value="school">학교 자체 조사</option></select></div>
          <div class="atozField"><label>가해관련학생 제2호 조치 시행일</label><input type="datetime-local" name="no2ActionDate"></div>
          <div class="atozField full"><label>즉시분리 미시행·예외 사유</label><div class="atozChecks">
            <label><input type="checkbox" name="victimOpposed"> 피해학생 반대의사</label>
            <label><input type="checkbox" name="notInEducationActivity"> 교육활동 중이 아님</label>
            <label><input type="checkbox" name="alreadySeparatedByEmergency"> 긴급선도조치로 이미 분리</label>
            <label><input type="checkbox" name="differentSchool"> 타학교 재학</label>
            <label><input type="checkbox" name="offCampusExperience"> 학교장 허가 교외체험학습</label>
            <label><input type="checkbox" name="selfResolutionFourCriteria"> 자체해결 객관적 4요건 해당</label>
          </div></div>
          <div class="atozField full"><label><input type="checkbox" name="guardianNoticeChecked"> 관련학생·보호자 통보 여부 및 시간을 기존 기록에서 확인함</label></div>
          <div class="atozField full"><label>기타 사항</label><textarea name="otherMatters" placeholder="경찰 신고·고소·소송 여부, 성관련 사안 수사기관 신고 일시 등"></textarea></div>
          <div class="atozField full"><label><input type="checkbox" name="otherSchoolRelated"> 타학교 관련 사안</label></div>
          <div class="atozField"><label>관련 학교명</label><input name="otherSchoolName"></div>
          <div class="atozField"><label>타학교 통보 일시</label><input type="datetime-local" name="otherSchoolNotifyAt"></div>
          <div class="atozField"><label>타학교 통보 방법</label><input name="otherSchoolNotifyMethod" placeholder="유선·소통메신저 등"></div>
          <div class="atozField"><label>통보받은 사람</label><input name="otherSchoolRecipient"></div>
          <div class="atozField full"><label>통보받은 사람 연락처</label><input name="otherSchoolContact"></div>
          <div class="atozField full"><label><input type="checkbox" name="interviewAvailabilityChecked"> 학생·보호자 조사 가능시간 확인 완료</label></div>
          <div class="atozField"><label>피해관련 면담 가능시간</label><input name="victimInterviewTime"></div>
          <div class="atozField"><label>가해관련 면담 가능시간</label><input name="perpInterviewTime"></div>
          <div class="atozField"><label>피해관련 관계회복 프로그램 의견</label><textarea name="victimRecoveryOpinion"></textarea></div>
          <div class="atozField"><label>가해관련 관계회복 프로그램 의견</label><textarea name="perpRecoveryOpinion"></textarea></div>
        </form>
        <div class="atozFoot"><button id="atozSave" class="atozSave">현재 사안에 저장</button><span id="atozStatus" class="atozStatus">사안을 선택한 뒤 입력하세요.</span></div>
      `;
      document.body.appendChild(panel);
    }
  }

  ensureUi();
  const btn = document.getElementById('atozBtn');
  const panel = document.getElementById('atozPanel');
  const form = document.getElementById('atozForm');
  const status = document.getElementById('atozStatus');

  const fields = [
    'reporterName','reporterRole','recognitionPath','receiverName','receiverRole',
    'investigationMode','no2ActionDate','otherMatters','otherSchoolName',
    'otherSchoolNotifyAt','otherSchoolNotifyMethod','otherSchoolRecipient','otherSchoolContact',
    'victimInterviewTime','perpInterviewTime','victimRecoveryOpinion','perpRecoveryOpinion'
  ];
  const exceptionKeys = ['victimOpposed','notInEducationActivity','alreadySeparatedByEmergency','differentSchool','offCampusExperience','selfResolutionFourCriteria'];

  function legacyWindow(){ return frame.contentWindow || null; }
  function readCases(){
    const w = legacyWindow();
    if (!w) return [];
    try { return JSON.parse(w.localStorage.getItem(PREFIX + 'cases') || '[]'); } catch (_) { return []; }
  }
  function writeCases(cases){ legacyWindow()?.localStorage.setItem(PREFIX + 'cases', JSON.stringify(cases)); }
  function rawFormData(){
    const w = legacyWindow();
    const fn = w?.getFormData;
    if (typeof fn !== 'function') return null;
    try {
      const original = fn.__original || fn;
      return original.call(w);
    } catch (_) { return null; }
  }
  function locateStoredForData(data){
    return readCases().find(c => (data?.id && c.id === data.id) || (data?.caseNo && c.caseNo === data.caseNo)) || null;
  }
  function locateCase(){
    const raw = rawFormData();
    const cases = readCases();
    return locateStoredForData(raw) || cases.find(c => c.status !== '종결') || cases[0] || raw || null;
  }
  function readAtoz(data){ return (((data || {})._hybrid || {}).atoz || {}); }

  function fillPanel(data){
    const a = readAtoz(data);
    activeCaseId = data?.id || null;
    fields.forEach(key => { if (form.elements[key]) form.elements[key].value = a[key] || ''; });
    exceptionKeys.forEach(key => { if (form.elements[key]) form.elements[key].checked = !!((a.separationExceptions || {})[key]); });
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
    const draftRaw = legacyWindow()?.localStorage.getItem(PREFIX + 'atoz_draft');
    let draft = null; try { draft = draftRaw ? JSON.parse(draftRaw) : null; } catch (_) {}
    const atoz = Object.keys(extra).length ? extra : (draft || {});
    if (!Object.keys(atoz).length) return data;
    return { ...data, _hybrid:{ ...(stored?._hybrid || {}), ...(data._hybrid || {}), atoz } };
  }

  function patchGetFormData(){
    const w = legacyWindow();
    if (!w || patchedWindow === w || typeof w.getFormData !== 'function') return;
    const original = w.getFormData;
    if (original.__schoolsvsAtozWrapped) { patchedWindow = w; return; }
    function wrapped(){ return mergeInto(original.apply(this, arguments)); }
    wrapped.__schoolsvsAtozWrapped = true;
    wrapped.__original = original.__original || original;
    w.getFormData = wrapped;
    patchedWindow = w;
  }

  function save(){
    const cases = readCases();
    const raw = rawFormData();
    const idx = cases.findIndex(c => (activeCaseId && c.id === activeCaseId) || (raw?.id && c.id === raw.id) || (raw?.caseNo && c.caseNo === raw.caseNo));
    const a = collect();
    if (idx >= 0) {
      cases[idx] = { ...cases[idx], _hybrid:{ ...(cases[idx]._hybrid || {}), atoz:a }, updatedAt:new Date().toISOString() };
      writeCases(cases);
      legacyWindow()?.localStorage.removeItem(PREFIX + 'atoz_draft');
      status.textContent = `${cases[idx].caseNo || '현재 사안'} · A to Z 추가정보 저장됨`;
    } else {
      legacyWindow()?.localStorage.setItem(PREFIX + 'atoz_draft', JSON.stringify(a));
      status.textContent = '신규 사안 임시저장 · 기본 사안을 저장하면 함께 연결됩니다.';
    }
    patchGetFormData();
  }

  function applyDraftToSaved(){
    const w = legacyWindow();
    if (!w) return;
    const rawDraft = w.localStorage.getItem(PREFIX + 'atoz_draft');
    if (!rawDraft) return;
    let draft; try { draft = JSON.parse(rawDraft); } catch (_) { return; }
    const cases = readCases();
    if (!cases.length) return;
    const raw = rawFormData();
    let idx = raw?.id ? cases.findIndex(c => c.id === raw.id) : -1;
    if (idx < 0 && raw?.caseNo) idx = cases.findIndex(c => c.caseNo === raw.caseNo);
    if (idx < 0) return;
    cases[idx] = { ...cases[idx], _hybrid:{ ...(cases[idx]._hybrid || {}), atoz:draft } };
    writeCases(cases);
    w.localStorage.removeItem(PREFIX + 'atoz_draft');
  }

  btn.addEventListener('click', () => { fillPanel(locateCase()); panel.classList.toggle('open'); });
  document.getElementById('atozClose').addEventListener('click', () => panel.classList.remove('open'));
  document.getElementById('atozSave').addEventListener('click', save);

  function onFrameReady(){
    patchedWindow = null;
    setTimeout(() => { patchGetFormData(); applyDraftToSaved(); }, 120);
    try {
      frame.contentWindow.document.addEventListener('click', () => setTimeout(() => { patchGetFormData(); applyDraftToSaved(); }, 80), {passive:true});
      frame.contentWindow.document.addEventListener('change', () => setTimeout(patchGetFormData, 80), {passive:true});
    } catch (_) {}
  }
  frame.addEventListener('load', onFrameReady);
  if (frame.contentDocument?.readyState === 'complete') onFrameReady();
})();
