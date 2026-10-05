(() => {
  const list=document.getElementById('documentList');
  if(!list)return;
  const FORM10='form10_case_report';
  let experimentalUnlocked=false;
  let policy=null;
  let loading=false;

  const style=document.createElement('style');
  style.textContent=`.fidelityGate{margin-top:8px;border-radius:9px;padding:8px 9px;font-size:11px;line-height:1.5}.fidelityGate.locked{background:#fff7ed;border:1px solid #fed7aa;color:#9a3412}.fidelityGate.ok{background:#ecfdf5;border:1px solid #bbf7d0;color:#166534}.fidelityGate button{margin-top:6px;border:1px solid currentColor;background:#fff;border-radius:6px;padding:4px 7px;font-size:11px;cursor:pointer}`;
  document.head.appendChild(style);

  async function getJson(url){const r=await fetch(url);if(!r.ok)return null;return r.json().catch(()=>null);}
  async function loadPolicy(){
    if(loading)return;loading=true;
    try{
      const structure=await getJson(`/api/documents/structure?key=${encodeURIComponent(FORM10)}`);
      const build=await getJson(`/api/documents/build-report?key=${encodeURIComponent(FORM10)}`);
      const s=structure?.report||null,b=build?.report||null;
      policy={
        structure:s,build:b,
        officialVerified:!!(s?.official2026HwpxVerified||b?.official2026HwpxVerified||b?.adaptiveOfficial2026Verified),
        adaptive: b?.sourceKind==='2026_pdf_adaptive'||s?.sourceYearDetected===2025||s?.reference2025Match===true,
      };
    }finally{loading=false;apply();}
  }
  function apply(){
    const card=list.querySelector(`.docItem[data-key="${FORM10}"]`);if(!card)return;
    let gate=card.querySelector('.fidelityGate');if(!gate){gate=document.createElement('div');gate.className='fidelityGate';const readiness=card.querySelector('[data-readiness]');if(readiness)readiness.insertAdjacentElement('beforebegin',gate);else card.appendChild(gate);}
    const gen=card.querySelector(`[data-generate="${FORM10}"]`);
    if(policy?.officialVerified){
      gate.className='fidelityGate ok';gate.innerHTML='<b>공식 2026 HWPX 검증 완료</b><br>등록한 공식 원본의 구조를 기준으로 출력합니다.';
      card.dataset.fidelityLocked='0';card.dataset.experimentalAllowed='0';
      if(gen&&gen.textContent.includes('잠금'))gen.textContent='현재 사안으로 생성';return;
    }
    card.dataset.fidelityLocked='1';
    card.dataset.experimentalAllowed=experimentalUnlocked?'1':'0';
    gate.className='fidelityGate locked';
    const basis=policy?.adaptive?'현재 등록본은 2025 HWPX 구조 또는 2026 PDF 기반 적응형입니다.':'공식 2026 HWPX 여부가 아직 확인되지 않았습니다.';
    gate.innerHTML=`<b>정식 HWPX 생성 잠금</b><br>${basis}<br>학교 제출용은 공식 2026 HWPX 원본을 등록해 구조를 확정한 뒤 사용하세요.<br><button type="button" data-experimental>${experimentalUnlocked?'시험본 생성 잠그기':'시험본 생성만 임시 허용'}</button>`;
    const btn=gate.querySelector('[data-experimental]');
    btn?.addEventListener('click',()=>{
      if(!experimentalUnlocked&&!confirm('이 출력은 공식 2026 HWPX와 1:1 검증되지 않은 시험본입니다. 학교 제출용으로 사용하지 않고 구조 확인용으로만 생성하시겠습니까?'))return;
      experimentalUnlocked=!experimentalUnlocked;apply();
      card.querySelector(`[data-preflight="${FORM10}"]`)?.click();
    });
    if(gen){
      if(!experimentalUnlocked){gen.disabled=true;gen.textContent='정식 생성 잠금';}
      else{gen.textContent='시험본 생성';setTimeout(()=>card.querySelector(`[data-preflight="${FORM10}"]`)?.click(),0);}
    }
  }
  const observer=new MutationObserver(()=>{apply();if(!policy)loadPolicy();});
  observer.observe(list,{childList:true,subtree:true});
  setTimeout(loadPolicy,300);
})();