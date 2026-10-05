(() => {
  const frame = document.getElementById('legacyFrame');
  const bar = document.querySelector('.hybridBar');
  const dock = document.getElementById('workflowDock');
  if (!frame || !bar || !dock) return;

  const style = document.createElement('style');
  style.id = 'schoolsvsSimpleModeStyle';
  style.textContent = `
    body.schoolSimple{background:#f3f6f9}
    body.schoolSimple .hybridBar{height:50px;background:#f8fafc;color:#1f2937;border-bottom:1px solid #d8e1ea;box-shadow:none;padding:0 12px;gap:8px}
    body.schoolSimple .hybridTitle{font-size:15px;color:#173a5c;letter-spacing:-.2px}
    body.schoolSimple #engineBadge{width:9px;height:9px;min-width:9px;padding:0;border-radius:50%;font-size:0;background:#d97706}
    body.schoolSimple #engineBadge.ok{background:#22a06b} body.schoolSimple #engineBadge.warn{background:#d97706}
    body.schoolSimple #syncText,body.schoolSimple #validateBtn,body.schoolSimple #panelBtn,
    body.schoolSimple .atozTopBtn,body.schoolSimple .studentTopBtn,body.schoolSimple .invTopBtn{display:none!important}
    body.schoolSimple:not(.schoolAdvanced) .docItem [data-analyze],body.schoolSimple:not(.schoolAdvanced) .docItem [data-map]{display:none!important}
    body.schoolSimple:not(.schoolAdvanced) #mappingOverlay{display:none!important}
    body.schoolSimple .hybridBtn{color:#294f72;border:1px solid #c8d4df;background:#fff;padding:7px 11px;border-radius:9px;font-weight:700}
    body.schoolSimple .hybridBtn:hover{background:#eef4f8}
    body.schoolSimple #documentBtn{background:#173a5c;color:#fff;border-color:#173a5c}
    body.schoolSimple #documentPanel{width:min(700px,calc(100vw - 28px));max-height:84vh}
    body.schoolSimple #workflowDock{padding:7px 12px;background:#fff;border-bottom:1px solid #d8e1ea;box-shadow:none}
    body.schoolSimple #workflowDock.collapsed .dockTop{margin:0}
    body.schoolSimple .dockTitle{font-size:12px;color:#52677b}
    body.schoolSimple .caseLabel{font-size:12px;color:#334155;font-weight:700}
    body.schoolSimple .dockToggle{font-size:11px;padding:4px 7px}
    body.schoolSimple #compactWorkflowSummary{font-size:12px;color:#52677b;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:58vw}
    body.schoolSimple #legacyFrame{background:#fff}
    .simpleMenuWrap{position:relative}
    .simpleMenu{display:none;position:absolute;right:0;top:40px;min-width:220px;background:#fff;border:1px solid #d8e1ea;border-radius:12px;box-shadow:0 14px 34px rgba(15,23,42,.16);padding:6px;z-index:240}
    .simpleMenu.open{display:block}.simpleMenu button{display:block;width:100%;text-align:left;border:0;background:#fff;color:#334155;border-radius:8px;padding:9px 10px;cursor:pointer;font:inherit;font-size:12px}.simpleMenu button:hover{background:#f1f5f9}.simpleMenu .muted{font-size:10px;color:#8291a0;padding:5px 10px 3px}
    .savePill{display:inline-flex;align-items:center;gap:6px;font-size:11px;color:#52677b;padding:5px 8px;border-radius:999px;background:#eef3f7;white-space:nowrap}.savePill::before{content:'';width:7px;height:7px;border-radius:50%;background:#94a3b8}.savePill.ok::before{background:#22a06b}.savePill.busy::before{background:#d97706}.savePill.error::before{background:#c53f3f}
    @media(max-width:760px){body.schoolSimple #compactWorkflowSummary{max-width:40vw}.savePill{display:none}.simpleMenu{right:-35px}}
  `;
  document.head.appendChild(style);
  document.body.classList.add('schoolSimple');

  const docBtn = document.getElementById('documentBtn');
  if (docBtn) docBtn.textContent = '문서출력';
  dock.classList.add('collapsed');
  const toggle = document.getElementById('dockToggle');
  if (toggle) toggle.textContent = '펼치기';

  const compact = document.createElement('span');
  compact.id = 'compactWorkflowSummary';
  compact.textContent = '현재 사안을 확인하는 중입니다.';
  const caseLabel = document.getElementById('dockCaseLabel');
  caseLabel?.insertAdjacentElement('afterend', compact);

  function updateCompact(){
    if (!dock.classList.contains('collapsed')) { compact.style.display='none'; return; }
    compact.style.display='inline';
    const stage = document.getElementById('dockStage')?.textContent?.trim() || '-';
    const deadline = document.getElementById('dockDeadline')?.textContent?.trim() || '';
    const next = document.getElementById('dockNext')?.textContent?.trim() || '';
    compact.textContent = `${stage} · ${deadline}${next ? ' · ' + next : ''}`;
  }
  new MutationObserver(updateCompact).observe(dock,{subtree:true,childList:true,characterData:true,attributes:true});
  toggle?.addEventListener('click',()=>setTimeout(updateCompact,0));
  updateCompact();

  const savePill = document.createElement('span');
  savePill.id = 'autosaveBadge';
  savePill.className = 'savePill';
  savePill.textContent = '자동저장 준비';
  bar.insertBefore(savePill, docBtn || bar.lastChild);

  function menuButton(label, action){
    const b=document.createElement('button'); b.type='button'; b.textContent=label; b.addEventListener('click',action); return b;
  }
  function makeMenu(label, items){
    const wrap=document.createElement('div'); wrap.className='simpleMenuWrap';
    const trigger=document.createElement('button'); trigger.className='hybridBtn'; trigger.type='button'; trigger.textContent=label;
    const menu=document.createElement('div'); menu.className='simpleMenu';
    items(menu,trigger);
    trigger.addEventListener('click',(e)=>{e.stopPropagation(); document.querySelectorAll('.simpleMenu.open').forEach(x=>{if(x!==menu)x.classList.remove('open')}); menu.classList.toggle('open');});
    wrap.append(trigger,menu); bar.appendChild(wrap); return {wrap,menu};
  }

  makeMenu('보완정보', menu=>{
    menu.append(
      menuButton('관련학생 상세정보',()=>document.getElementById('studentBtn')?.click()),
      menuButton('초기대응 · A to Z 정보',()=>document.getElementById('atozBtn')?.click()),
      menuButton('사안조사 기록',()=>document.getElementById('investigationBtn')?.click())
    );
  });
  makeMenu('더보기', menu=>{
    const muted=document.createElement('div'); muted.className='muted'; muted.textContent='필요할 때만 사용하는 고급 기능'; menu.appendChild(muted);
    menu.append(
      menuButton('업무흐름 전체 펼치기',()=>document.getElementById('dockToggle')?.click()),
      menuButton('상세 점검',()=>document.getElementById('validateBtn')?.click()),
      menuButton('엔진 · 데이터 상태',()=>document.getElementById('panelBtn')?.click()),
      menuButton('문서 고급도구 표시/숨기기',()=>document.body.classList.toggle('schoolAdvanced'))
    );
  });
  document.addEventListener('click',()=>document.querySelectorAll('.simpleMenu.open').forEach(x=>x.classList.remove('open')));

  function simplifyLegacy(){
    try{
      const doc=frame.contentDocument; if(!doc || doc.getElementById('hybridSimpleLegacyStyle')) return;
      const s=doc.createElement('style'); s.id='hybridSimpleLegacyStyle';
      s.textContent=`
        .topbar{display:none!important}.shell{min-height:100vh!important}.sidebar{top:0!important;height:100vh!important;width:218px!important;padding-top:8px!important}
        .content{padding:15px!important}.pageHead{margin-bottom:11px!important}.pageHead p{display:none!important}.pageHead h1{font-size:1.25rem!important}
        .card{box-shadow:none!important;border-color:#dce4eb!important;padding:15px!important;margin-bottom:12px!important}.cardTitle{margin-bottom:11px!important;padding-bottom:8px!important}
        footer{display:none!important}body{padding-bottom:0!important;background:#f5f7f9!important}.notice{margin-bottom:9px!important;padding:10px 12px!important}.tabs{margin-bottom:10px!important}
        input,select,textarea{padding:9px 10px!important}.row{margin-bottom:9px!important}.personCard{padding:12px!important}.steps{margin-bottom:11px!important}
      `;
      doc.head.appendChild(s);
    }catch(_){ }
  }
  frame.addEventListener('load',()=>setTimeout(simplifyLegacy,80));
  setTimeout(simplifyLegacy,120);
})();