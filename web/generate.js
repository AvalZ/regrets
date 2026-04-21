import { boot, fmtErr, escapeHtml } from './regrets.js';

const statusEl = document.getElementById('status');
const form = document.getElementById('form');
const patternEl = document.getElementById('pattern');
const btnGenerate = document.getElementById('btn-generate');
const outResult = document.getElementById('out-result');
const nEl = document.getElementById('gen-n');
const minEl = document.getElementById('gen-min');
const maxEl = document.getElementById('gen-max');
const negateEl = document.getElementById('gen-negate');

let api = null;

function render(arr, ms) {
  if (!arr.length) {
    outResult.textContent = `(no strings found)\n\n(searched in ${ms} ms)`;
    return;
  }
  const lines = arr.map((s, i) => `${String(i + 1).padStart(3)}. ${JSON.stringify(s)}`);
  outResult.textContent = `${lines.join('\n')}\n\n(${arr.length} string(s) in ${ms} ms)`;
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const pat = patternEl.value.trim();
  if (!pat) return;
  const n = parseInt(nEl.value, 10) || 10;
  const mn = parseInt(minEl.value, 10) || 0;
  const mx = parseInt(maxEl.value, 10) || 20;
  const negate = negateEl.checked;

  btnGenerate.disabled = true;
  outResult.textContent = `⏳ generating up to ${n} ${negate ? 'counter-examples' : 'strings'}…`;
  await new Promise((r) => setTimeout(r, 0));
  const t0 = performance.now();
  try {
    const fn = negate ? api.generateNegated : api.generateSingle;
    const proxy = fn(pat, n, mn, mx);
    const arr = proxy.toJs ? proxy.toJs() : Array.from(proxy);
    if (proxy.destroy) proxy.destroy();
    const ms = (performance.now() - t0).toFixed(0);
    render(arr, ms);
  } catch (err) {
    outResult.innerHTML = `error: ${escapeHtml(fmtErr(err))}`;
  } finally {
    btnGenerate.disabled = false;
  }
});

boot({ statusEl })
  .then(({ api: a }) => {
    api = a;
    [patternEl, btnGenerate].forEach((el) => (el.disabled = false));
    patternEl.focus();
  })
  .catch((err) => {
    statusEl.textContent = 'Boot failed: ' + fmtErr(err);
    console.error('regrets boot error:', err);
  });
