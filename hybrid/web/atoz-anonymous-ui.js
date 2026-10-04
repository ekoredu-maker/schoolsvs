(() => {
  let installed = false;

  function install() {
    if (installed) return true;
    const form = document.getElementById('atozForm');
    const nameInput = form?.elements?.reporterName;
    const saveBtn = document.getElementById('atozSave');
    if (!form || !nameInput || !saveBtn) return false;

    const field = nameInput.closest('.atozField');
    if (!field) return false;

    const wrap = document.createElement('div');
    wrap.style.cssText = 'margin-top:6px;font-size:11px;color:#52677b';
    wrap.innerHTML = '<label style="font-weight:400;margin:0"><input type="checkbox" id="reporterAnonymous"> 신고자 익명 처리</label>';
    field.appendChild(wrap);
    const checkbox = wrap.querySelector('#reporterAnonymous');

    function syncFromName() {
      const anonymous = String(nameInput.value || '').trim() === '익명';
      checkbox.checked = anonymous;
      nameInput.readOnly = anonymous;
      if (anonymous) nameInput.placeholder = '익명';
    }

    checkbox.addEventListener('change', () => {
      if (checkbox.checked) {
        if (String(nameInput.value || '').trim() && nameInput.value !== '익명') {
          nameInput.dataset.previousReporterName = nameInput.value;
        }
        nameInput.value = '익명';
        nameInput.readOnly = true;
      } else {
        nameInput.readOnly = false;
        nameInput.value = nameInput.dataset.previousReporterName || '';
        nameInput.placeholder = '';
      }
      nameInput.dispatchEvent(new Event('input', {bubbles:true}));
    });

    // 기존 A to Z 저장 핸들러보다 먼저 값을 보정한다.
    saveBtn.addEventListener('click', () => {
      if (checkbox.checked) nameInput.value = '익명';
    }, true);

    document.getElementById('atozBtn')?.addEventListener('click', () => setTimeout(syncFromName, 30));
    nameInput.addEventListener('input', () => {
      if (!nameInput.readOnly) checkbox.checked = String(nameInput.value || '').trim() === '익명';
    });

    syncFromName();
    installed = true;
    return true;
  }

  const timer = setInterval(() => {
    if (install()) clearInterval(timer);
  }, 100);
  setTimeout(() => clearInterval(timer), 10000);
})();
