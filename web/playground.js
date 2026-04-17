import { boot, fmtErr, escapeHtml, tagSpan, runWithLoading } from './regrets.js';

const statusEl = document.getElementById('status');
const matchingEl = document.getElementById('matching');
const notMatchingEl = document.getElementById('not-matching');
const btnShow = document.getElementById('btn-show');
const btnDfa = document.getElementById('btn-dfa');
const btnReset = document.getElementById('btn-reset');
const btnStep = document.getElementById('btn-step');
const btnEof = document.getElementById('btn-eof');
const charsEl = document.getElementById('chars');
const consumedEl = document.getElementById('consumed');
const chkCompress = document.getElementById('chk-compress');
const outShow = document.getElementById('out-show');
const outDfa = document.getElementById('out-dfa');
const outDerive = document.getElementById('out-derive');

let api = null;
let deriveState = null;

function appendLine(html) {
  outDerive.innerHTML += '\n' + html;
  outDerive.scrollTop = outDerive.scrollHeight;
}

function resetDerive() {
  try {
    deriveState = api.startDerive(matchingEl.value, notMatchingEl.value);
  } catch (err) {
    outDerive.innerHTML = `error: ${escapeHtml(fmtErr(err))}`;
    deriveState = null;
    return;
  }
  const snap = deriveState.snapshot().toJs({ dict_converter: Object.fromEntries });
  consumedEl.textContent = '';
  outDerive.innerHTML = `start [${tagSpan(snap.tag)}]: ${escapeHtml(snap.pretty)}`;
  charsEl.value = '';
  charsEl.focus();
}

function stepChars(s) {
  if (!deriveState) resetDerive();
  if (!s || !deriveState) return;
  for (const c of s) {
    const r = deriveState.step(c).toJs({ dict_converter: Object.fromEntries });
    consumedEl.textContent += c;
    appendLine(`  '${escapeHtml(c)}' [${tagSpan(r.tag)}]: ${escapeHtml(r.pretty)}`);
    if (r.dead) break;
  }
}

btnShow.addEventListener('click', () => {
  outDfa.style.display = 'none';
  runWithLoading([btnShow, btnDfa], outShow, 'Building DFA and collapsing to regex', () =>
    api.showMerged(matchingEl.value, notMatchingEl.value)
  );
});

let vizInstance = null;
async function getViz() {
  if (!vizInstance) vizInstance = await Viz.instance();
  return vizInstance;
}

function makeZoomable(svg) {
  const wrap = document.createElement('div');
  wrap.className = 'zoom-wrap';
  const inner = document.createElement('div');
  inner.className = 'zoom-inner';
  inner.appendChild(svg);
  wrap.appendChild(inner);

  let tx = 0, ty = 0, scale = 1;
  const apply = () => { inner.style.transform = `translate(${tx}px, ${ty}px) scale(${scale})`; };

  wrap.addEventListener('wheel', (e) => {
    e.preventDefault();
    const rect = wrap.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const factor = Math.exp(-e.deltaY * 0.0015);
    const newScale = Math.max(0.1, Math.min(20, scale * factor));
    const k = newScale / scale;
    tx = mx - (mx - tx) * k;
    ty = my - (my - ty) * k;
    scale = newScale;
    apply();
  }, { passive: false });

  let dragging = false, lastX = 0, lastY = 0;
  wrap.addEventListener('mousedown', (e) => {
    dragging = true; lastX = e.clientX; lastY = e.clientY;
    wrap.style.cursor = 'grabbing';
    e.preventDefault();
  });
  window.addEventListener('mousemove', (e) => {
    if (!dragging) return;
    tx += e.clientX - lastX;
    ty += e.clientY - lastY;
    lastX = e.clientX; lastY = e.clientY;
    apply();
  });
  window.addEventListener('mouseup', () => {
    if (!dragging) return;
    dragging = false;
    wrap.style.cursor = 'grab';
  });

  const reset = document.createElement('button');
  reset.textContent = 'reset view';
  reset.className = 'zoom-reset';
  reset.addEventListener('click', (e) => {
    e.stopPropagation();
    tx = 0; ty = 0; scale = 1; apply();
  });
  wrap.appendChild(reset);

  wrap.style.cursor = 'grab';
  return wrap;
}

btnDfa.addEventListener('click', async () => {
  if (!api) {
    outDfa.style.display = 'block';
    outDfa.textContent = 'not ready yet — wait for boot to finish';
    return;
  }
  outDfa.style.display = 'block';
  outDfa.textContent = '⏳ Building DFA… (browser will freeze briefly)';
  [btnShow, btnDfa].forEach((b) => (b.disabled = true));
  await new Promise((r) => setTimeout(r, 0));
  const t0 = performance.now();
  try {
    const dot = api.dfaDot(matchingEl.value, notMatchingEl.value, chkCompress.checked);
    const viz = await getViz();
    const svg = viz.renderSVGElement(dot);
    const ms = (performance.now() - t0).toFixed(0);
    outDfa.innerHTML = '';
    outDfa.appendChild(makeZoomable(svg));
    const caption = document.createElement('div');
    caption.className = 'caption';
    caption.textContent = `(computed in ${ms} ms)`;
    outDfa.appendChild(caption);
  } catch (err) {
    console.error('dfa render error:', err);
    outDfa.textContent = `error: ${fmtErr(err)}`;
  } finally {
    [btnShow, btnDfa].forEach((b) => (b.disabled = false));
  }
});

btnReset.addEventListener('click', resetDerive);

btnStep.addEventListener('click', () => {
  stepChars(charsEl.value);
  charsEl.value = '';
  charsEl.focus();
});

btnEof.addEventListener('click', () => {
  if (!deriveState) resetDerive();
  if (!deriveState) return;
  const r = deriveState.eof().toJs({ dict_converter: Object.fromEntries });
  appendLine(`  ε [${tagSpan(r.tag)}]: ${escapeHtml(r.pretty)}`);
});

charsEl.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    e.preventDefault();
    btnStep.click();
  }
});

boot({ statusEl })
  .then(({ api: a }) => {
    api = a;
    [btnShow, btnDfa, btnReset, btnStep, btnEof, charsEl].forEach((el) => (el.disabled = false));
  })
  .catch((err) => {
    statusEl.textContent = 'Boot failed: ' + fmtErr(err);
    console.error('regrets boot error:', err);
  });
