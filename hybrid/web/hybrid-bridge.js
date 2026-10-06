(() => {
  const PREFIX = 'sv_assist_v2_';

  async function request(path, options = {}) {
    const res = await fetch(path, {
      headers: {'Content-Type': 'application/json', ...(options.headers || {})},
      ...options,
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Python 엔진 요청에 실패했습니다.');
    return data;
  }

  async function health() {
    return request('/api/health');
  }

  async function migrateLocalStorage() {
    const read = (key, fallback) => {
      try {
        const raw = localStorage.getItem(PREFIX + key);
        return raw ? JSON.parse(raw) : fallback;
      } catch (_) {
        return fallback;
      }
    };

    const payload = {
      cases: read('cases', []),
      counter: read('counter', 1),
      settings: read('settings', {}),
    };
    return request('/api/state', {method: 'POST', body: JSON.stringify(payload)});
  }

  async function loadState() {
    return request('/api/state');
  }

  async function saveCase(caseData) {
    return request('/api/cases', {method: 'POST', body: JSON.stringify(caseData)});
  }

  async function validate(caseData) {
    return request('/api/validate', {method: 'POST', body: JSON.stringify(caseData)});
  }

  async function workflow(caseId) {
    return request('/api/workflow/' + encodeURIComponent(caseId));
  }

  window.SchoolSVSHybrid = {
    health,
    migrateLocalStorage,
    loadState,
    saveCase,
    validate,
    workflow,
  };
})();
