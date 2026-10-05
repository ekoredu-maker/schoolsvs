(() => {
  const panel = document.getElementById('documentPanel');
  const list = document.getElementById('documentList');
  if (!panel || !list || document.getElementById('official2026HwpxBox')) return;

  const box = document.createElement('div');
  box.id = 'official2026HwpxBox';
  box.style.cssText = 'margin:10px 0;padding:11px;border:1px solid #b9d7c7;border-radius:10px;background:#f0fdf4';
  box.innerHTML = `
    <div style="font-size:13px;font-weight:800;color:#166534">2026 공식 HWPX 연결</div>
    <div style="font-size:11px;line-height:1.5;color:#475569;margin-top:4px">
      충청북도교육청 「2026. 학교폭력 사안처리 세부설명 A to Z(서식모음집).hwpx」를 한 번 선택하면
      서식10과 서식12를 자동으로 분리·구조검증합니다. 선택한 파일은 localhost 프로그램 안에서만 처리합니다.
    </div>
    <div style="display:flex;gap:7px;align-items:center;flex-wrap:wrap;margin-top:8px">
      <button type="button" id="official2026HwpxBtn" class="docBtn" style="margin-top:0;background:#166534;border-color:#166534">2026 공식 HWPX 일괄 등록</button>
      <input id="official2026HwpxFile" type="file" accept=".hwpx" style="display:none">
      <span id="official2026HwpxStatus" style="font-size:11px;color:#64748b">서식10·12 원본 미등록 시 사용</span>
    </div>`;
  list.parentNode.insertBefore(box, list);

  const btn = document.getElementById('official2026HwpxBtn');
  const input = document.getElementById('official2026HwpxFile');
  const status = document.getElementById('official2026HwpxStatus');

  const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fileToBase64 = file => new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || '').split(',').pop() || '');
    reader.onerror = () => reject(reader.error || new Error('HWPX 파일을 읽지 못했습니다.'));
    reader.readAsDataURL(file);
  });
  async function post(path, body) {
    const response = await fetch(path, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
    return data;
  }

  btn.addEventListener('click', () => input.click());
  input.addEventListener('change', async () => {
    const file = input.files?.[0];
    input.value = '';
    if (!file) return;
    if (!String(file.name || '').toLowerCase().endsWith('.hwpx')) {
      status.innerHTML = '<span style="color:#b91c1c">HWPX 파일을 선택하세요.</span>';
      return;
    }
    btn.disabled = true;
    status.textContent = '공식 서식모음집을 읽고 서식10·12를 분리하는 중입니다.';
    try {
      const base64 = await fileToBase64(file);
      const results = [];
      for (const [key, label] of [['form10_case_report','서식10'], ['form12_investigation_report','서식12']]) {
        const result = await post('/api/documents/register', {documentKey:key, fileName:file.name, base64});
        results.push(`${label} ${result.sourcePreparation?.extractedFromBundle ? '자동분리·등록' : '등록'}`);
      }
      status.innerHTML = `<span style="color:#15803d;font-weight:700">${escapeHtml(results.join(' / '))} 완료</span>`;
      document.dispatchEvent(new CustomEvent('schoolsvs:template-built', {detail:{official2026:true}}));
    } catch (error) {
      status.innerHTML = `<span style="color:#b91c1c">등록 실패: ${escapeHtml(error.message)}</span>`;
    } finally {
      btn.disabled = false;
    }
  });
})();
