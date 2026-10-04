(() => {
  const PREFIX = 'sv_assist_v2_';
  const frame = document.getElementById('legacyFrame');
  const dockRoute = document.getElementById('dockRoute');
  const routeButtons = document.getElementById('routeButtons');
  const dockStage = document.getElementById('dockStage');
  const dockNext = document.getElementById('dockNext');
  const stageTrack = document.getElementById('stageTrack');
  if (!frame || !dockRoute || !routeButtons) return;

  async function api(path, options = {}) {
    const res = await fetch(path, {
      ...options,
      headers: {'Content-Type':'application/json', ...(options.headers || {})}
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    return data;
  }

  function readCases() {
    try {
      const raw = frame.contentWindow.localStorage.getItem(PREFIX + 'cases');
      return raw ? JSON.parse(raw) : [];
    } catch (_) { return []; }
  }

  function writeCases(cases) {
    frame.contentWindow.localStorage.setItem(PREFIX + 'cases', JSON.stringify(cases));
  }

  function getCurrentCase() {
    const w = frame.contentWindow;
    try {
      const formPage = w.document.getElementById('page-newcase');
      if (formPage?.classList.contains('active') && typeof w.getFormData === 'function') {
        const data = w.getFormData();
        const cases = readCases();
        const stored = cases.find(c => c.id === data.id || (data.caseNo && c.caseNo === data.caseNo));
        return stored ? {...stored, ...data, _hybrid: stored._hybrid || {}} : data;
      }
    } catch (_) {}
    const cases = readCases();
    return cases.find(c => c.status !== '종결') || cases[0] || null;
  }

  function saveRouteToCase(caseData, route) {
    const cases = readCases();
    const idx = cases.findIndex(c => c.id === caseData.id || (caseData.caseNo && c.caseNo === caseData.caseNo));
    if (idx < 0) throw new Error('먼저 사안을 저장한 뒤 처리 분기를 선택하세요.');
    const old = cases[idx];
    cases[idx] = {
      ...old,
      _hybrid: {
        ...(old._hybrid || {}),
        route,
        routeSelectedAt: new Date().toISOString()
      },
      updatedAt: new Date().toISOString()
    };
    writeCases(cases);
    return cases[idx];
  }

  function renderMergedWorkflow(wf) {
    if (dockStage) dockStage.textContent = wf.stage || '-';
    if (stageTrack && Array.isArray(wf.steps)) {
      stageTrack.innerHTML = wf.steps.map(s => `<div class="stage ${s.state || 'pending'}">${s.name}</div>`).join('');
    }
    if (dockNext && Array.isArray(wf.nextActions) && wf.nextActions.length) {
      dockNext.textContent = wf.nextActions[0];
      dockNext.className = 'dockValue' + (String(wf.nextActions[0]).includes('기한 경과') ? ' danger' : '');
    }
  }

  async function refresh() {
    const data = getCurrentCase();
    if (!data) {
      dockRoute.textContent = '사안 접수 후 검토';
      routeButtons.innerHTML = '';
      return;
    }
    try {
      const result = await api('/api/validate', {method:'POST', body:JSON.stringify(data)});
      const wf = result.workflow || {};
      const route = wf.route || {};
      const selected = route.selected;
      renderMergedWorkflow(wf);
      dockRoute.className = 'dockValue';
      dockRoute.textContent = selected ? (route.selectedLabel || selected) : (route.enabled ? '담당자 선택 필요' : '전담기구 단계 이후 선택');
      routeButtons.innerHTML = (route.options || []).map(opt => `
        <button class="routeBtn ${selected === opt.key ? 'active' : ''}"
                data-route="${opt.key}" ${route.enabled ? '' : 'disabled'}>${opt.label}</button>
      `).join('');
      routeButtons.querySelectorAll('.routeBtn').forEach(btn => {
        btn.addEventListener('click', async () => {
          try {
            const current = getCurrentCase();
            if (!current) throw new Error('현재 사안을 찾을 수 없습니다.');
            saveRouteToCase(current, btn.dataset.route);
            await refresh();
          } catch (e) {
            dockRoute.textContent = e.message;
            dockRoute.className = 'dockValue warn';
          }
        });
      });
    } catch (e) {
      dockRoute.textContent = '분기 계산 실패';
      routeButtons.innerHTML = '';
    }
  }

  frame.addEventListener('load', () => {
    refresh();
    try {
      frame.contentWindow.document.addEventListener('click', () => setTimeout(refresh, 250), {passive:true});
      frame.contentWindow.document.addEventListener('change', () => setTimeout(refresh, 250), {passive:true});
      frame.contentWindow.document.addEventListener('input', () => setTimeout(refresh, 250), {passive:true});
    } catch (_) {}
  });
  setInterval(refresh, 5000);
})();
