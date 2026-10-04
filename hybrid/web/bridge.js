(() => {
  const PREFIX = 'sv_assist_v2_';
  const frame = document.getElementById('legacyFrame');
  const badge = document.getElementById('engineBadge');
  const syncText = document.getElementById('syncText');
  const panel = document.getElementById('panel');
  const panelBtn = document.getElementById('panelBtn');
  const validateBtn = document.getElementById('validateBtn');
  const restoreBtn = document.getElementById('restoreBtn');
  const panelSummary = document.getElementById('panelSummary');
  const panelOutput = document.getElementById('panelOutput');
  const workflowDock = document.getElementById('workflowDock');
  const dockToggle = document.getElementById('dockToggle');
  const dockCaseLabel = document.getElementById('dockCaseLabel');
  const stageTrack = document.getElementById('stageTrack');
  const dockStage = document.getElementById('dockStage');
  const dockCompletion = document.getElementById('dockCompletion');
  const dockDeadline = document.getElementById('dockDeadline');
  const dockNext = document.getElementById('dockNext');

  let engineOnline = false;
  let syncTimer = null;
  let navTimer = null;
  let patchInstalled = false;
  let lastFingerprint = '';

  async function api(path, options = {}) {
    const res = await fetch(path, {
      ...options,
      headers: {'Content-Type':'application/json', ...(options.headers || {})}
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    return data;
  }

  function setStatus(ok, text) {
    engineOnline = ok;
    badge.textContent = ok ? 'Python 연결됨' : '웹 단독 모드';
    badge.className = `hybridBadge ${ok ? 'ok' : 'warn'}`;
    syncText.textContent = text || (ok ? 'SQLite 동기화 사용' : '기존 localStorage만 사용');
  }

  function parseStorage(ls, key, fallback) {
    try {
      const raw = ls.getItem(PREFIX + key);
      return raw ? JSON.parse(raw) : fallback;
    } catch (_) { return fallback; }
  }

  function readLegacyState() {
    const w = frame.contentWindow;
    if (!w) return null;
    const ls = w.localStorage;
    return {
      cases: parseStorage(ls, 'cases', []),
      counter: parseStorage(ls, 'counter', 1),
      settings: parseStorage(ls, 'settings', {})
    };
  }

  function currentCaseFromLegacy() {
    const w = frame.contentWindow;
    if (!w) return null;
    try {
      const doc = w.document;
      const formPage = doc.getElementById('page-newcase');
      if (formPage?.classList.contains('active') && typeof w.getFormData === 'function') {
        const data = w.getFormData();
        if (data && (data.caseNo || data.recvAt || data.summary)) return data;
      }
    } catch (_) {}

    const state = readLegacyState();
    const cases = state?.cases || [];
    if (!cases.length) return null;
    return cases.find(c => c.status !== '종결') || cases[0];
  }

  async function syncLegacyState(reason = '자동 동기화') {
    if (!engineOnline) return;
    const state = readLegacyState();
    if (!state) return;
    try {
      const result = await api('/api/state', {method:'POST', body:JSON.stringify(state)});
      syncText.textContent = `${reason} · ${result.imported ?? state.cases.length}건 SQLite 반영`;
    } catch (e) {
      setStatus(false, 'Python 동기화 실패 · 기존 웹 저장은 유지됨');
      panelOutput.textContent = `동기화 오류\n${e.message}`;
    }
  }

  function scheduleSync(reason) {
    clearTimeout(syncTimer);
    syncTimer = setTimeout(async () => {
      await syncLegacyState(reason);
      scheduleNavigatorRefresh(true);
    }, 250);
  }

  function installStoragePatch() {
    if (patchInstalled) return;
    const w = frame.contentWindow;
    if (!w || !w.Storage) return;
    const proto = w.Storage.prototype;
    const originalSetItem = proto.setItem;
    const originalRemoveItem = proto.removeItem;
    const originalClear = proto.clear;

    proto.setItem = function(key, value) {
      const result = originalSetItem.call(this, key, value);
      if (String(key).startsWith(PREFIX)) scheduleSync('저장 동기화');
      return result;
    };
    proto.removeItem = function(key) {
      const result = originalRemoveItem.call(this, key);
      if (String(key).startsWith(PREFIX)) scheduleSync('삭제 동기화');
      return result;
    };
    proto.clear = function() {
      const result = originalClear.call(this);
      scheduleSync('전체 변경 동기화');
      return result;
    };
    patchInstalled = true;
  }

  function installFrameActivityWatch() {
    const w = frame.contentWindow;
    if (!w) return;
    try {
      const doc = w.document;
      ['input','change','click'].forEach(evt => {
        doc.addEventListener(evt, () => scheduleNavigatorRefresh(false), {passive:true});
      });
    } catch (_) {}
  }

  async function healthCheck() {
    try {
      const h = await api('/api/health');
      setStatus(true, `Python ${h.version || ''} · 규칙 ${h.rulesVersion || '-'} · SQLite 준비됨`);
      panelSummary.textContent = `엔진: ${h.engine || 'python'} / 버전: ${h.version || '-'} / 업무규칙: ${h.rulesVersion || '-'}`;
      return true;
    } catch (e) {
      setStatus(false, 'Python 서버 미연결 · 기존 웹 기능은 계속 사용 가능');
      panelSummary.textContent = 'Python 엔진과 연결되지 않았습니다.';
      panelOutput.textContent = '기존 HTML/JavaScript 기능은 그대로 사용할 수 있습니다. 하이브리드 실행기로 시작했는지 확인하세요.';
      renderNavigatorOffline();
      return false;
    }
  }

  async function initialSync() {
    if (!engineOnline) return;
    try {
      const local = readLegacyState();
      const server = await api('/api/state');
      const localCount = local?.cases?.length || 0;
      const serverCount = server?.cases?.length || 0;
      if (localCount > 0) {
        await syncLegacyState('초기 데이터 이관');
        panelOutput.textContent = `브라우저 기존 데이터 ${localCount}건을 SQLite에 안전 복사했습니다.\n기존 localStorage 원본은 삭제하지 않았습니다.`;
      } else if (serverCount > 0) {
        panelOutput.textContent = `SQLite에는 ${serverCount}건이 있고 현재 브라우저 저장자료는 비어 있습니다.\n필요하면 아래 복원 버튼으로 기존 화면에 불러올 수 있습니다.`;
      } else {
        panelOutput.textContent = '브라우저와 SQLite 모두 신규 상태입니다.';
      }
    } catch (e) {
      panelOutput.textContent = `초기 동기화 확인 실패\n${e.message}`;
    }
  }

  function formatValidation(v) {
    if (!v) return '검증 결과가 없습니다.';
    const lines = [];
    lines.push(v.ok ? '✓ Python 검증 통과' : '⚠ Python 검증 확인 필요');
    lines.push(`업무규칙 버전: ${v.rulesVersion || '-'}`);
    const errors = v.errors || [];
    const warnings = v.warnings || [];
    if (errors.length) {
      lines.push('', '[오류]');
      errors.forEach((x, i) => lines.push(`${i+1}. ${typeof x === 'string' ? x : (x.message || JSON.stringify(x))}`));
    }
    if (warnings.length) {
      lines.push('', '[주의]');
      warnings.forEach((x, i) => lines.push(`${i+1}. ${typeof x === 'string' ? x : (x.message || JSON.stringify(x))}`));
    }
    if (!errors.length && !warnings.length) lines.push('추가 확인사항이 없습니다.');
    return lines.join('\n');
  }

  function formatDeadlines(items) {
    if (!items || !items.length) return '[기한]\n산정할 기한이 없습니다.';
    const lines = ['[기한]'];
    items.forEach((x, i) => {
      let state = '미산정';
      if (x.status === 'completed') state = '완료';
      else if (x.status === 'overdue') state = `기한 경과 ${Math.abs(x.remainingMinutes || 0)}분`;
      else if (x.status === 'pending') state = `남은 시간 약 ${Math.max(0, Math.floor((x.remainingMinutes || 0)/60))}시간`;
      else if (x.status === 'base_missing') state = '기준일시 미입력';
      lines.push(`${i+1}. ${x.label}: ${state}${x.dueAt ? ` / 기한 ${x.dueAt.replace('T',' ')}` : ''}`);
    });
    return lines.join('\n');
  }

  function formatNextActions(wf) {
    const actions = wf?.nextActions || [];
    if (!actions.length) return '[다음 업무]\n추가 안내가 없습니다.';
    return '[다음 업무]\n' + actions.map((x, i) => `${i+1}. ${x}`).join('\n');
  }

  function deadlinePriority(items) {
    const active = (items || []).filter(x => x.status === 'overdue' || x.status === 'pending');
    active.sort((a,b) => (a.remainingMinutes ?? 999999) - (b.remainingMinutes ?? 999999));
    return active[0] || null;
  }

  function setDockValue(el, text, tone='') {
    el.textContent = text;
    el.className = `dockValue${tone ? ' '+tone : ''}`;
  }

  function renderStages(steps) {
    const fallback = ['접수','초기대응','사실조사','전담기구','심의','조치이행','종결'].map(name => ({name,state:'pending'}));
    const list = steps?.length ? steps : fallback;
    stageTrack.innerHTML = list.map(s => `<div class="stage ${s.state || 'pending'}">${s.name}</div>`).join('');
  }

  function renderNavigatorOffline() {
    dockCaseLabel.textContent = 'Python 엔진 미연결 · 기존 화면은 계속 사용 가능합니다.';
    renderStages([]);
    setDockValue(dockStage, '웹 단독 모드', 'warn');
    setDockValue(dockCompletion, '-');
    setDockValue(dockDeadline, 'Python 연결 후 계산', 'warn');
    setDockValue(dockNext, '하이브리드 실행기로 프로그램을 시작하세요.', 'warn');
  }

  function renderNavigatorEmpty() {
    dockCaseLabel.textContent = '진행 중인 사안이 없습니다.';
    renderStages([]);
    setDockValue(dockStage, '대기');
    setDockValue(dockCompletion, '-');
    setDockValue(dockDeadline, '없음', 'ok');
    setDockValue(dockNext, '신규 사안을 접수하면 업무 절차를 안내합니다.');
  }

  function renderNavigator(data, result) {
    const wf = result.workflow || {};
    const validation = result.validation || {};
    const deadlines = wf.deadlines || result.deadlines || [];
    const near = deadlinePriority(deadlines);
    const errors = validation.errors || [];
    const warnings = validation.warnings || [];
    const actions = wf.nextActions || [];

    dockCaseLabel.textContent = `${data.caseNo || '번호 미정'} · ${data.status || '상태 미정'}`;
    renderStages(wf.steps || []);
    setDockValue(dockStage, wf.stage || '-');
    const completion = wf.completion;
    setDockValue(dockCompletion, typeof completion === 'number' ? `${completion}%` : '-');

    if (near) {
      if (near.status === 'overdue') setDockValue(dockDeadline, `${near.label} · 기한 경과`, 'danger');
      else {
        const hrs = Math.max(0, Math.floor((near.remainingMinutes || 0) / 60));
        setDockValue(dockDeadline, `${near.label} · 약 ${hrs}시간 남음`, hrs <= 6 ? 'warn' : '');
      }
    } else {
      setDockValue(dockDeadline, '현재 임박 기한 없음', 'ok');
    }

    let next = actions[0] || '현재 단계의 기록을 확인하세요.';
    let tone = '';
    if (errors.length) {
      next = `필수 누락 ${errors.length}건 · ${errors[0].message || '입력사항 확인'}`;
      tone = 'danger';
    } else if (near?.status === 'overdue') {
      next = actions.find(x => String(x).includes('기한')) || next;
      tone = 'danger';
    } else if (warnings.length) {
      next = `확인 필요 ${warnings.length}건 · ${warnings[0].message || '주의사항 확인'}`;
      tone = 'warn';
    }
    setDockValue(dockNext, next, tone);
  }

  async function refreshNavigator(force=false) {
    if (!engineOnline) return renderNavigatorOffline();
    const data = currentCaseFromLegacy();
    if (!data) return renderNavigatorEmpty();
    const fingerprint = JSON.stringify([data.id,data.caseNo,data.status,data.recvAt,data.officeReport,data.officeDate,data.separation,data.sepPeriod,data.summary,data.updatedAt]);
    if (!force && fingerprint === lastFingerprint) return;
    lastFingerprint = fingerprint;
    try {
      const result = await api('/api/validate', {method:'POST', body:JSON.stringify(data)});
      renderNavigator(data, result);
    } catch (e) {
      dockCaseLabel.textContent = '업무 내비게이션 계산 실패';
      setDockValue(dockNext, e.message, 'danger');
    }
  }

  function scheduleNavigatorRefresh(force=false) {
    clearTimeout(navTimer);
    navTimer = setTimeout(() => refreshNavigator(force), 180);
  }

  async function validateCurrentCase() {
    panel.classList.add('open');
    if (!engineOnline) {
      panelOutput.textContent = 'Python 엔진이 연결되지 않아 서버 검증을 실행할 수 없습니다.';
      return;
    }
    try {
      const data = currentCaseFromLegacy();
      if (!data) throw new Error('검증할 사안이 없습니다.');
      const result = await api('/api/validate', {method:'POST', body:JSON.stringify(data)});
      const wf = result.workflow || {};
      const completion = wf.completion ?? '-';
      panelOutput.textContent = [
        formatValidation(result.validation),
        '',
        `[워크플로우]\n현재 단계: ${wf.stage || '-'}\n업무 완성도: ${completion}${typeof completion === 'number' ? '%' : ''}`,
        '',
        formatDeadlines(wf.deadlines || result.deadlines),
        '',
        formatNextActions(wf),
        '',
        wf.localRulesStatus === 'pending_verification'
          ? '※ 충북 A to Z의 지역 세부규칙은 원문 대조가 완료되는 항목부터 단계적으로 활성화합니다.'
          : ''
      ].filter(Boolean).join('\n');
    } catch (e) {
      panelOutput.textContent = `검증 실행 실패\n${e.message}`;
    }
  }

  async function restoreFromSqlite() {
    if (!engineOnline) return;
    try {
      const state = await api('/api/state');
      const w = frame.contentWindow;
      if (!w) throw new Error('기존 화면에 접근할 수 없습니다.');
      const ls = w.localStorage;
      ls.setItem(PREFIX+'cases', JSON.stringify(state.cases || []));
      ls.setItem(PREFIX+'counter', JSON.stringify(state.counter || 1));
      ls.setItem(PREFIX+'settings', JSON.stringify(state.settings || {}));
      panelOutput.textContent = `SQLite 데이터 ${state.cases?.length || 0}건을 기존 화면 저장소로 복원했습니다. 화면을 새로고침합니다.`;
      setTimeout(() => frame.contentWindow.location.reload(), 400);
    } catch (e) {
      panelOutput.textContent = `복원 실패\n${e.message}`;
    }
  }

  panelBtn.addEventListener('click', () => panel.classList.toggle('open'));
  validateBtn.addEventListener('click', validateCurrentCase);
  restoreBtn.addEventListener('click', restoreFromSqlite);
  dockToggle.addEventListener('click', () => {
    const collapsed = workflowDock.classList.toggle('collapsed');
    dockToggle.textContent = collapsed ? '펼치기' : '접기';
  });

  frame.addEventListener('load', async () => {
    installStoragePatch();
    installFrameActivityWatch();
    await healthCheck();
    await initialSync();
    await refreshNavigator(true);
  });

  healthCheck().then(() => scheduleNavigatorRefresh(true));
  setInterval(() => scheduleNavigatorRefresh(false), 30000);
})();
