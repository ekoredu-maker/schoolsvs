(() => {
  const frame = document.getElementById('legacyFrame');
  const badge = document.getElementById('autosaveBadge');
  if (!frame) return;
  const PREFIX = 'sv_assist_v2_';
  const LOCAL_SNAPSHOT = PREFIX + 'hybrid_crash_snapshot';
  let timer = null;
  let periodic = null;
  let watchedDoc = null;
  let recoveryChecked = false;
  let saving = false;

  function setBadge(text, tone=''){
    if (!badge) return;
    badge.textContent = text;
    badge.className = `savePill${tone ? ' '+tone : ''}`;
  }
  function nowText(){
    const d=new Date(); return `${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}:${String(d.getSeconds()).padStart(2,'0')}`;
  }
  function parse(ls,key,fallback){try{const raw=ls.getItem(PREFIX+key);return raw?JSON.parse(raw):fallback;}catch(_){return fallback;}}
  function w(){return frame.contentWindow||null;}

  function formActive(){
    try{return !!w()?.document?.getElementById('page-newcase')?.classList.contains('active');}catch(_){return false;}
  }
  function getCase(){
    if(!formActive()) return null;
    try{if(typeof w()?.getFormData==='function') return w().getFormData();}catch(_){ }
    return null;
  }
  function readState(){
    const win=w(); if(!win) return null; const ls=win.localStorage;
    return {cases:parse(ls,'cases',[]),counter:parse(ls,'counter',1),settings:parse(ls,'settings',{})};
  }
  function matchStored(data,cases){
    if(!data) return null;
    return (cases||[]).find(c=>(data.id&&c.id===data.id)||(data.caseNo&&c.caseNo===data.caseNo))||null;
  }

  function collectAtoz(){
    const form=document.getElementById('atozForm'); if(!form) return null;
    const out={};
    Array.from(form.elements||[]).forEach(el=>{
      if(!el.name) return;
      if(el.type==='checkbox') out[el.name]=!!el.checked;
      else out[el.name]=String(el.value||'');
    });
    return out;
  }
  function collectStudents(){
    const cards=[...document.querySelectorAll('#studentList .studentCard')]; if(!cards.length) return null;
    return cards.map(card=>{
      const item={index:Number(card.dataset.index||0),fields:{},flags:{}};
      card.querySelectorAll('[data-field]').forEach(el=>item.fields[el.dataset.field]=String(el.value||''));
      card.querySelectorAll('[data-flag]').forEach(el=>item.flags[el.dataset.flag]=!!el.checked);
      return item;
    });
  }
  function collectInvestigation(){
    const panel=document.getElementById('investigationPanel'); if(!panel) return null;
    const out={fields:{},criteria:{},issues:[],factors:{}};
    panel.querySelectorAll('[data-inv]').forEach(el=>out.fields[el.dataset.inv]=String(el.value||''));
    panel.querySelectorAll('[data-criterion]').forEach(el=>out.criteria[el.dataset.criterion]=String(el.value||''));
    panel.querySelectorAll('[data-factor]').forEach(el=>out.factors[el.dataset.factor]=String(el.value||''));
    panel.querySelectorAll('[data-issue]').forEach(el=>{const i=Number(el.dataset.issueIndex||0);out.issues[i]=out.issues[i]||{};out.issues[i][el.dataset.issue]=String(el.value||'');});
    const has = Object.values(out.fields).some(Boolean)||Object.values(out.criteria).some(Boolean)||Object.values(out.factors).some(Boolean)||out.issues.some(x=>x&&Object.values(x).some(Boolean));
    return has?out:null;
  }
  function collectExtras(){return {atoz:collectAtoz(),students:collectStudents(),investigation:collectInvestigation()};}

  function meaningful(snapshot){
    const c=snapshot?.case||{};
    const people=[...(c.victims||[]),...(c.perps||[])].some(p=>String(p?.name||'').trim());
    const main=people||[c.incidentDate,c.incidentPlace,c.reportType,c.violenceType,c.summary,c.damage,c.evidence,c.separation,c.officeReport].some(v=>String(v||'').trim());
    const e=snapshot?.extras||{};
    const extra=!!(e.students?.length||e.investigation||e.atoz&&Object.values(e.atoz).some(v=>v===true||String(v||'').trim()));
    return main||extra;
  }

  function buildSnapshot(){
    const data=getCase(); if(!data) return null;
    const state=readState(); if(!state) return null;
    const stored=matchStored(data,state.cases);
    const snap={
      version:1,capturedAt:new Date().toISOString(),case:data,
      editingCaseId:stored?.id||null,storedUpdatedAt:stored?.updatedAt||null,
      extras:collectExtras()
    };
    return meaningful(snap)?snap:null;
  }

  async function persistSnapshot(reason='자동저장',keepalive=false){
    if(saving) return; const snap=buildSnapshot(); if(!snap) return;
    const state=readState(); if(!state) return;
    saving=true; setBadge('자동저장 중','busy');
    try{
      w()?.localStorage.setItem(LOCAL_SNAPSHOT,JSON.stringify(snap));
      const settings={...(state.settings||{}),_hybridCrashSnapshot:snap};
      const res=await fetch('/api/state',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({cases:state.cases||[],counter:state.counter||1,settings,mode:'merge'}),keepalive});
      if(!res.ok) throw new Error(`HTTP ${res.status}`);
      setBadge(`자동저장 ${nowText()}`,'ok');
    }catch(e){
      setBadge('PC 임시저장 확인 필요','error');
    }finally{saving=false;}
  }
  function schedule(reason='입력 자동저장'){
    clearTimeout(timer); setBadge('입력 중 · 저장 대기','busy');
    timer=setTimeout(()=>persistSnapshot(reason),700);
  }

  function installWatch(){
    try{
      const doc=w()?.document; if(!doc||doc===watchedDoc) return; watchedDoc=doc;
      ['input','change'].forEach(evt=>doc.addEventListener(evt,()=>{if(formActive())schedule();},{passive:true}));
    }catch(_){ }
  }
  document.addEventListener('input',e=>{if(e.target.closest('#atozPanel,#studentPanel,#investigationPanel'))schedule('보완정보 자동저장');},{passive:true});
  document.addEventListener('change',e=>{if(e.target.closest('#atozPanel,#studentPanel,#investigationPanel'))schedule('보완정보 자동저장');},{passive:true});

  function newest(a,b){
    if(!a)return b;if(!b)return a;
    return String(a.capturedAt||'')>=String(b.capturedAt||'')?a:b;
  }
  function staleAgainstSaved(snap,cases){
    if(!snap)return true; const saved=matchStored(snap.case,cases||[]); if(!saved)return false;
    const savedAt=Date.parse(saved.updatedAt||''); const captured=Date.parse(snap.capturedAt||'');
    return Number.isFinite(savedAt)&&Number.isFinite(captured)&&savedAt>=captured;
  }

  function recoveryBanner(snapshot){
    if(document.getElementById('crashRecoveryBar'))return;
    const box=document.createElement('div'); box.id='crashRecoveryBar';
    box.style.cssText='position:fixed;left:50%;top:62px;transform:translateX(-50%);z-index:400;width:min(720px,calc(100vw - 28px));background:#fff8e8;border:1px solid #efc66c;border-radius:12px;box-shadow:0 12px 28px rgba(15,23,42,.16);padding:11px 13px;display:flex;gap:10px;align-items:center;font:12px Malgun Gothic,sans-serif;color:#684b13';
    const t=document.createElement('div');t.style.flex='1';t.innerHTML=`<b>저장되지 않은 작업을 찾았습니다.</b><br>${String(snapshot.case?.caseNo||'신규 사안')} · ${new Date(snapshot.capturedAt).toLocaleString('ko-KR')} 자동저장본`;
    const restore=document.createElement('button');restore.textContent='복구';restore.style.cssText='border:0;background:#173a5c;color:#fff;border-radius:8px;padding:7px 12px;cursor:pointer';
    const discard=document.createElement('button');discard.textContent='무시';discard.style.cssText='border:1px solid #c9b36d;background:#fff;color:#684b13;border-radius:8px;padding:7px 10px;cursor:pointer';
    restore.addEventListener('click',()=>{restoreSnapshot(snapshot);box.remove();});
    discard.addEventListener('click',()=>{try{w()?.localStorage.removeItem(LOCAL_SNAPSHOT);}catch(_){ } box.remove();});
    box.append(t,restore,discard);document.body.appendChild(box);
  }

  function fillAtoz(data){
    const form=document.getElementById('atozForm'); if(!form||!data)return;
    Object.entries(data).forEach(([k,v])=>{const el=form.elements[k];if(!el)return;if(el.type==='checkbox')el.checked=!!v;else el.value=String(v??'');});
  }
  function fillStudents(items){
    if(!items?.length)return;
    document.getElementById('studentBtn')?.click();
    setTimeout(()=>items.forEach(item=>{
      const card=document.querySelector(`#studentList .studentCard[data-index="${item.index}"]`);if(!card)return;
      Object.entries(item.fields||{}).forEach(([k,v])=>{const el=card.querySelector(`[data-field="${CSS.escape(k)}"]`);if(el)el.value=String(v??'');});
      Object.entries(item.flags||{}).forEach(([k,v])=>{const el=card.querySelector(`[data-flag="${CSS.escape(k)}"]`);if(el)el.checked=!!v;});
    }),100);
  }
  function fillInvestigation(data){
    if(!data)return;document.getElementById('investigationBtn')?.click();
    setTimeout(()=>{
      Object.entries(data.fields||{}).forEach(([k,v])=>{const el=document.querySelector(`#investigationPanel [data-inv="${CSS.escape(k)}"]`);if(el)el.value=String(v??'');});
      Object.entries(data.criteria||{}).forEach(([k,v])=>{const el=document.querySelector(`#investigationPanel [data-criterion="${CSS.escape(k)}"]`);if(el)el.value=String(v??'');});
      Object.entries(data.factors||{}).forEach(([k,v])=>{const el=document.querySelector(`#investigationPanel [data-factor="${CSS.escape(k)}"]`);if(el)el.value=String(v??'');});
      (data.issues||[]).forEach((item,i)=>Object.entries(item||{}).forEach(([k,v])=>{const el=document.querySelector(`#investigationPanel [data-issue="${CSS.escape(k)}"][data-issue-index="${i}"]`);if(el)el.value=String(v??'');}));
    },100);
  }
  function restoreSnapshot(snap){
    const win=w();if(!win)return;const id=snap.editingCaseId;
    try{
      if(id&&typeof win.editCase==='function')win.editCase(id);else if(typeof win.showPage==='function')win.showPage('newcase');
      setTimeout(()=>{
        try{if(typeof win.applyFormData==='function')win.applyFormData(snap.case||{},!id);if(typeof win.saveDraftSilently==='function')win.saveDraftSilently();}catch(_){ }
        fillAtoz(snap.extras?.atoz);fillStudents(snap.extras?.students);fillInvestigation(snap.extras?.investigation);
        setBadge('자동저장본 복구됨','ok');
      },120);
    }catch(_){setBadge('자동저장본 복구 실패','error');}
  }

  async function checkRecovery(){
    if(recoveryChecked)return;recoveryChecked=true;
    let local=null;try{local=JSON.parse(w()?.localStorage.getItem(LOCAL_SNAPSHOT)||'null');}catch(_){ }
    let server=null,cases=[];
    try{const r=await fetch('/api/state');if(r.ok){const s=await r.json();server=s.settings?._hybridCrashSnapshot||null;cases=s.cases||[];}}catch(_){ }
    const snap=newest(local,server);if(snap&&meaningful(snap)&&!staleAgainstSaved(snap,cases))recoveryBanner(snap);
  }

  function onFrameReady(){watchedDoc=null;setTimeout(()=>{installWatch();checkRecovery();},180);}
  frame.addEventListener('load',onFrameReady);if(frame.contentDocument?.readyState==='complete')onFrameReady();
  periodic=setInterval(()=>{installWatch();if(formActive())persistSnapshot('주기 자동저장');},10000);
  window.addEventListener('pagehide',()=>{try{persistSnapshot('종료 직전 저장',true);}catch(_){ }});
  document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='hidden')persistSnapshot('화면 전환 저장',true);});
})();