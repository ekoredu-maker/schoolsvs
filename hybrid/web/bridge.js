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

  let engineOnline = false;
  let syncTimer = null;
  let patchInstalled = false;

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

  function readLegacyState() {
    const w = frame.contentWindow;
    if (!w) return null;
    const ls = w.localStorage;
    const parse = (key, fallback) => {
      try {
        const raw = ls.getItem(PREFIX + key);
        return raw ? JSON.parse(raw) : fallback;
      } catch (_) { return fallback; }
    };
    return {
      cases: parse('cases', []),
      counter: parse('counter', 1),
      settings: parse('settings', {})
    };
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
    syncTimer = setTimeout(() => syncLegacyState(reason), 250);
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

  async function healthCheck() {
    try {
      const h = await api('/api/health');
      setStatus(true, `Python ${h.version || ''} · SQLite 준비됨`);
      panelSummary.textContent = `엔진: ${h.engine || 'python'} / 포트: ${h.port || '-'} / 버전: ${h.version || '-'}`;
      return true;
    } catch (e) {
      setStatus(false, 'Python 서버 미연결 · 기존 웹 기능은 계속 사용 가능');
      panelSummary.textContent = 'Python 엔진과 연결되지 않았습니다.';
      panelOutput.textContent = '기존 HTML/JavaScript 기능은 그대로 사용할 수 있습니다. 하이브리드 실행기로 시작했는지 확인하세요.';
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

  async function validateCurrentCase() {
    panel.classList.add('open');
    if (!engineOnline) {
      panelOutput.textContent = 'Python 엔진이 연결되지 않아 서버 검증을 실행할 수 없습니다.';
      return;
    }
    try {
      const w = frame.contentWindow;
      if (!w || typeof w.getFormData !== 'function') throw new Error('현재 화면에서 사안 입력 폼을 읽을 수 없습니다.');
      const data = w.getFormData();
      const result = await api('/api/validate', {method:'POST', body:JSON.stringify(data)});
      const wf = result.workflow || {};
      panelOutput.textContent = formatValidation(result.validation) + `\n\n[워크플로우]\n단계: ${wf.stage || wf.current_stage || '-'}\n완성도: ${wf.completion ?? wf.completion_rate ?? '-'}${typeof (wf.completion ?? wf.completion_rate) === 'number' ? '%' : ''}`;
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

  frame.addEventListener('load', async () => {
    installStoragePatch();
    await healthCheck();
    await initialSync();
  });

  healthCheck();
})();
