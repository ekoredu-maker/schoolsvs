(() => {
  const list=document.getElementById('documentList');
  if(!list)return;
  const FORM10='form10_case_report';
  let policy=null;
  let loading=false;

  const style=document.createElement('style');
  style.textContent=`.fidelityGate{margin-top:8px;border-radius:9px;padding:8px 9px;font-size:11px;line-height:1.5}.fidelityGate.locked{background:#fff7ed;border:1px solid #fed7aa;color:#9a3412}.fidelityGate.ok{background:#ecfdf5;border:1px solid #bbf7d0;color:#166534}`;
  document.head.appendChild(style);

  async function getJson(url){const r=await fetch(url);if(!r.ok)return null;return r.json().catch(()=>null);}
  async function loadPolicy(){
    if(loading)return;loading=true;
    try{
      const [structure,build,documents]=await Promise.all([
        getJson(`/api/documents/structure?key=${encodeURIComponent(FORM10)}`),
        getJson(`/api/documents/build-report?key=${encodeURIComponent(FORM10)}`),
        getJson('/api/documents')
      ]);
      const s=structure?.report||null,b=build?.report||null;
      const d=(documents?.documents||[]).find(x=>x.key===FORM10)||null;
      policy={
        structure:s,build:b,direct:!!d?.directOfficial2026,
        officialVerified:!!(d?.directOfficial2026||s?.official2026HwpxVerified||b?.official2026HwpxVerified||b?.adaptiveOfficial2026Verified),
        adaptive:b?.sourceKind==='2026_pdf_adaptive'||s?.sourceYearDetected===2025||s?.reference2025Match===true,
      };
    }finally{loading=false;apply();}
  }
  function apply(){
    const card=list.querySelector(`.docItem[data-key="${FORM10}"]`);if(!card)return;
    let gate=card.querySelector('.fidelityGate');
    if(!gate){
      gate=document.createElement('div');gate.className='fidelityGate';
      const readiness=card.querySelector('[data-readiness]');
      if(readiness)readiness.insertAdjacentElement('beforebegin',gate);else card.appendChild(gate);
    }
    const gen=card.querySelector(`[data-generate="${FORM10}"]`);
    if(policy?.officialVerified){
      gate.className='fidelityGate ok';
      gate.innerHTML=policy.direct
        ? '<b>2026 공식 HWPX 직접생성 모드</b><br>확인된 공식 구조를 유지하고 값 셀만 Python이 입력합니다.'
        : '<b>공식 2026 HWPX 검증 완료</b><br>등록한 공식 원본의 구조를 기준으로 출력합니다.';
      card.dataset.fidelityLocked='0';
      if(gen&&gen.textContent.includes('잠금'))gen.textContent='현재 사안으로 생성';
      return;
    }
    card.dataset.fidelityLocked='1';
    gate.className='fidelityGate locked';
    const basis=policy?.adaptive
      ? '현재 등록본은 2025 HWPX 구조 또는 2026 PDF 기반 적응형 자료입니다.'
      : '공식 2026 HWPX 원본 여부가 아직 확인되지 않았습니다.';
    gate.innerHTML=`<b>학교 제출용 HWPX 생성 잠금</b><br>${basis}<br>공식 2026 HWPX 원본을 등록하고 구조를 확인한 뒤 정식 생성을 활성화합니다.`;
    if(gen){gen.disabled=true;gen.textContent='공식 서식 확인 후 생성';}
  }
  const observer=new MutationObserver(()=>{apply();if(!policy)loadPolicy();});
  observer.observe(list,{childList:true,subtree:true});
  document.addEventListener('schoolsvs:template-built',()=>{policy=null;loadPolicy();});
  setTimeout(loadPolicy,300);

  if(!document.querySelector('script[data-schoolsvs-backup-refresh]')){
    const script=document.createElement('script');
    script.src='backup-import-refresh.js';
    script.dataset.schoolsvsBackupRefresh='1';
    document.body.appendChild(script);
  }
})();