(() => {
  const frame = document.getElementById('legacyFrame');
  if (!frame) return;
  const PREFIX = 'sv_assist_v2_';
  const SCHEMA = 'cb-atoz-2026-form12-v0.19';

  const CRITERIA = [
    ['noLongTreatment','2주 이상 치료 필요 진단서가 제출되지 않은 경우'],
    ['noPropertyDamage','재산상 피해가 없거나 즉시 복구·복구 약속이 있는 경우'],
    ['notPersistent','학교폭력이 지속적이지 않은 경우'],
    ['notRetaliation','신고·진술·자료제공 등에 대한 보복행위가 아닌 경우'],
  ];
  const FACTORS = [
    ['severity','학교폭력의 심각성'], ['persistence','학교폭력의 지속성'],
    ['intentionality','학교폭력의 고의성'], ['remorse','가해학생의 반성 정도'],
    ['reconciliation','가해학생·보호자와 피해학생·보호자 간 화해 정도'],
    ['guidancePossibility','해당 조치로 인한 가해학생의 선도 가능성'],
    ['victimDisability','피해학생이 장애학생인지 여부'],
  ];

  function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
  function w(){return frame.contentWindow||null;}
  function readCases(){try{return JSON.parse(w()?.localStorage.getItem(PREFIX+'cases')||'[]');}catch(_){return[];}}
  function writeCases(cases){w()?.localStorage.setItem(PREFIX+'cases',JSON.stringify(cases));}
  function currentData(){try{if(typeof w()?.getFormData==='function')return w().getFormData();}catch(_){} const c=readCases();return c.find(x=>x.status!=='종결')||c[0]||null;}
  function storedCase(data){return readCases().find(c=>(data?.id&&c.id===data.id)||(data?.caseNo&&c.caseNo===data.caseNo))||null;}

  function ensureUi(){
    if(document.getElementById('investigationPanel'))return;
    const style=document.createElement('style');
    style.textContent=`.invPanel{position:fixed;right:14px;top:58px;width:min(980px,calc(100vw - 28px));max-height:86vh;overflow:auto;background:#fff;border:1px solid #cbd5e1;border-radius:14px;box-shadow:0 18px 45px rgba(15,23,42,.22);padding:15px;z-index:130;display:none}.invPanel.open{display:block}.invHead{display:flex;align-items:center;gap:8px}.invHead h3{margin:0;color:#1f4b7a}.invClose{margin-left:auto;border:1px solid #cbd5e1;background:#fff;border-radius:7px;padding:5px 8px;cursor:pointer}.invNote{font-size:11px;color:#64748b;line-height:1.55;margin:8px 0 12px}.invSection{border:1px solid #dbe4ec;border-radius:11px;padding:11px;margin:9px 0;background:#fbfdff}.invSection h4{margin:0 0 8px;color:#294f72}.invGrid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.invField label{display:block;font-size:10px;font-weight:700;color:#607488;margin-bottom:3px}.invField input,.invField select,.invField textarea{width:100%;box-sizing:border-box;border:1px solid #cbd5e1;border-radius:7px;padding:6px;font:inherit;font-size:12px;background:#fff}.invField textarea{min-height:72px;resize:vertical}.invFull{grid-column:1/-1}.invCriteria{display:grid;grid-template-columns:2fr 1fr;gap:6px;align-items:center;margin:5px 0;font-size:11px}.invFactor{margin:7px 0}.invFactor label{font-size:11px;font-weight:700;color:#41576b}.invFactor textarea{width:100%;box-sizing:border-box;min-height:55px;border:1px solid #cbd5e1;border-radius:7px;padding:6px;font:inherit;font-size:12px}.invFoot{display:flex;align-items:center;gap:8px;margin-top:10px}.invSave{border:0;background:#1f4b7a;color:#fff;border-radius:8px;padding:8px 13px;cursor:pointer}.invStatus{font-size:12px;color:#607488}.invTopBtn{border:1px solid rgba(255,255,255,.35);background:transparent;color:#fff;border-radius:8px;padding:6px 10px;cursor:pointer}@media(max-width:760px){.invGrid{grid-template-columns:1fr}.invCriteria{grid-template-columns:1fr}}`;
    document.head.appendChild(style);

    const bar=document.querySelector('.hybridBar');
    const docBtn=document.getElementById('documentBtn');
    const btn=document.createElement('button');btn.id='investigationBtn';btn.className='invTopBtn';btn.textContent='사안조사 기록';
    if(docBtn)bar?.insertBefore(btn,docBtn);else bar?.appendChild(btn);

    const panel=document.createElement('div');panel.id='investigationPanel';panel.className='invPanel';
    panel.innerHTML=`<div class="invHead"><h3>서식12 사안조사 기록</h3><button id="investigationClose" class="invClose">닫기</button></div>
      <div class="invNote">2026 충북 A to Z 서식12의 조사기록을 구조화합니다. 판단요소는 점수나 조치 수준을 자동판정하지 않고 조사 과정에서 확인된 사실만 기록합니다.</div>
      <div class="invSection"><h4>조사 기본정보</h4><div class="invGrid">
        <div class="invField"><label>조사구분</label><select data-inv="kind"><option value="">선택</option><option value="first">1차 조사</option><option value="supplement">보완조사</option></select></div>
        <div class="invField"><label>사안조사 일자</label><input type="date" data-inv="investigationDate"></div>
        <div class="invField"><label>작성자/조사관 성명</label><input data-inv="authorName"></div>
        <div class="invField"><label>작성자/조사관 연락처</label><input data-inv="authorContact"></div>
        <div class="invField invFull"><label>사안 경위(전후·접수·조사·양측 주장 등을 시간 흐름에 따라)</label><textarea data-inv="chronology"></textarea></div>
      </div></div>
      <div class="invSection"><h4>학교장 자체해결 객관적 요건 의견</h4><div id="invCriteria"></div>
        <div class="invGrid"><div class="invField invFull"><label>조사자 종합 의견</label><textarea data-inv="selfResolutionOpinion"></textarea></div><div class="invField"><label>자체해결 동의 여부 기록</label><input data-inv="selfResolutionConsent" placeholder="예: 피해학생·보호자 동의 확인 전"></div></div></div>
      <div class="invSection"><h4>쟁점 사안</h4><div id="invIssues"></div></div>
      <div class="invSection"><h4>시행령 제19조 판단요소 관련 확인 사실</h4><div class="invNote">점수를 기재하는 영역이 아닙니다. 각 요소와 관련하여 조사에서 확인된 사실을 기록합니다.</div><div id="invFactors"></div></div>
      <div class="invSection"><h4>기타 조사정보</h4><div class="invGrid">
        <div class="invField invFull"><label>긴급조치 여부</label><textarea data-inv="emergencyMeasures"></textarea></div>
        <div class="invField invFull"><label>가해학생 학교폭력 재발 현황</label><textarea data-inv="recurrenceHistory"></textarea></div>
        <div class="invField invFull"><label>특이사항 및 고려사항</label><textarea data-inv="specialNotes"></textarea></div>
        <div class="invField invFull"><label>기타 사항(보완조사의 경우 사례회의 주요 보완사항 등)</label><textarea data-inv="otherNotes"></textarea></div>
      </div></div>
      <div class="invFoot"><button id="investigationSave" class="invSave">현재 사안에 저장</button><span id="investigationStatus" class="invStatus">사안을 선택하세요.</span></div>`;
    document.body.appendChild(panel);

    document.getElementById('invCriteria').innerHTML=CRITERIA.map(([k,l])=>`<div class="invCriteria"><span>${esc(l)}</span><select data-criterion="${k}"><option value="">선택</option><option value="met">충족</option><option value="not_met">미충족</option><option value="checking">확인 중</option></select></div>`).join('');
    document.getElementById('invIssues').innerHTML=[0,1].map(i=>`<div class="invSection" style="background:#fff"><h4>주요 쟁점 ${i+1}</h4><div class="invGrid">
      <div class="invField invFull"><label>쟁점</label><input data-issue="title" data-issue-index="${i}"></div>
      <div class="invField invFull"><label>피해(관련)학생 주장</label><textarea data-issue="victimClaim" data-issue-index="${i}"></textarea></div>
      <div class="invField invFull"><label>가해(관련)학생 주장</label><textarea data-issue="perpClaim" data-issue-index="${i}"></textarea></div>
      <div class="invField invFull"><label>목격학생 진술 등</label><textarea data-issue="witnessStatement" data-issue-index="${i}"></textarea></div>
      <div class="invField invFull"><label>근거자료(출처·장소·날짜·시간 등)</label><textarea data-issue="evidence" data-issue-index="${i}"></textarea></div>
      </div></div>`).join('');
    document.getElementById('invFactors').innerHTML=FACTORS.map(([k,l])=>`<div class="invFactor"><label>${esc(l)}</label><textarea data-factor="${k}"></textarea></div>`).join('');
  }

  ensureUi();
  const panel=document.getElementById('investigationPanel');
  const status=document.getElementById('investigationStatus');

  function load(){
    const data=currentData();const saved=storedCase(data)||data||{};const inv=saved?._hybrid?.investigation||{};
    panel.querySelectorAll('[data-inv]').forEach(el=>{const key=el.dataset.inv;let v=inv[key]??'';if(key==='investigationDate'&&!v)v=saved.investigationDate||'';if(key==='authorName'&&!v)v=saved.investigatorName||'';el.value=String(v||'').slice(0,key==='investigationDate'?10:99999);});
    const criteria=inv.selfResolutionCriteria||{};panel.querySelectorAll('[data-criterion]').forEach(el=>el.value=criteria[el.dataset.criterion]||'');
    const factors=inv.judgmentFactors||{};panel.querySelectorAll('[data-factor]').forEach(el=>el.value=factors[el.dataset.factor]||'');
    const issues=Array.isArray(inv.issues)?inv.issues:[];panel.querySelectorAll('[data-issue]').forEach(el=>{const item=issues[Number(el.dataset.issueIndex)]||{};el.value=item[el.dataset.issue]||'';});
    status.textContent=`${saved.caseNo||'현재 사안'} · 조사기록 불러옴`;
  }

  function collect(){
    const inv={schemaVersion:SCHEMA};
    panel.querySelectorAll('[data-inv]').forEach(el=>inv[el.dataset.inv]=String(el.value||'').trim());
    inv.selfResolutionCriteria={};panel.querySelectorAll('[data-criterion]').forEach(el=>inv.selfResolutionCriteria[el.dataset.criterion]=String(el.value||''));
    inv.judgmentFactors={};panel.querySelectorAll('[data-factor]').forEach(el=>inv.judgmentFactors[el.dataset.factor]=String(el.value||'').trim());
    const issues=[{},{}];panel.querySelectorAll('[data-issue]').forEach(el=>issues[Number(el.dataset.issueIndex)][el.dataset.issue]=String(el.value||'').trim());
    inv.issues=issues.filter(x=>Object.values(x).some(Boolean));
    return inv;
  }

  async function save(){
    const data=currentData();const cases=readCases();let idx=data?.id?cases.findIndex(c=>c.id===data.id):-1;if(idx<0&&data?.caseNo)idx=cases.findIndex(c=>c.caseNo===data.caseNo);
    if(idx<0){status.textContent='기본 사안을 먼저 저장하세요.';return;}
    const inv=collect();cases[idx]={...cases[idx],_hybrid:{...(cases[idx]._hybrid||{}),investigation:inv},investigationDate:inv.investigationDate||cases[idx].investigationDate,updatedAt:new Date().toISOString()};
    writeCases(cases);
    try{
      const res=await fetch('/api/documents/readiness',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({documentKey:'form12_investigation_report',case:cases[idx]})});
      const result=await res.json();status.textContent=`저장 완료 · 서식12 내용 준비도 ${result.readiness?.score??'-'}%`;
    }catch(_){status.textContent='조사기록 저장 완료';}
  }

  document.getElementById('investigationBtn')?.addEventListener('click',()=>{load();panel.classList.toggle('open');});
  document.getElementById('investigationClose')?.addEventListener('click',()=>panel.classList.remove('open'));
  document.getElementById('investigationSave')?.addEventListener('click',save);
})();
