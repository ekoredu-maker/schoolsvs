(() => {
  const frame = document.getElementById('legacyFrame');
  if (!frame) return;

  const CASES_KEY = 'sv_assist_v2_cases';
  let armed = false;

  function dataMenuOpen(){
    return !!document.querySelector('#schoolsvsDataMenu .simpleMenu.open');
  }

  function restoreVisibleApp(){
    const w = frame.contentWindow;
    const doc = w?.document;
    if (!w || !doc) return;
    try {
      const login = doc.getElementById('loginScreen');
      const app = doc.getElementById('app');
      if (login) login.style.display = 'none';
      if (app) app.style.display = 'flex';

      if (typeof w.afterLogin === 'function') w.afterLogin();
      else {
        if (typeof w.renderAll === 'function') w.renderAll();
        if (typeof w.showPage === 'function') w.showPage('cases');
      }
      if (typeof w.showPage === 'function') w.showPage('cases');
    } catch (e) {
      console.error('[SchoolSVS] imported backup refresh failed', e);
    }
  }

  function armNextFrameLoad(){
    if (armed) return;
    armed = true;
    frame.addEventListener('load', () => {
      if (!armed) return;
      armed = false;
      setTimeout(restoreVisibleApp, 120);
    }, {once:true});
  }

  window.addEventListener('storage', event => {
    if (event.key !== CASES_KEY) return;
    if (!dataMenuOpen()) return;
    armNextFrameLoad();
  });
})();