import { boot, fmtErr, escapeHtml, tagSpan, runWithLoading } from './regrets.js';
import { mountSessionUI } from './sessionui.js';

const statusEl = document.getElementById('status');
const form = document.getElementById('form');
const patternEl = document.getElementById('pattern');
const btnNegate = document.getElementById('btn-negate');
const outResult = document.getElementById('out-result');
const btnReset = document.getElementById('btn-reset');
const btnStep = document.getElementById('btn-step');
const btnEof = document.getElementById('btn-eof');
const charsEl = document.getElementById('chars');
const consumedEl = document.getElementById('consumed');
const outDerive = document.getElementById('out-derive');
const sessionMount = document.getElementById('session-mount');

let api = null;
let deriveState = null;
let currentPattern = '';

function appendLine(html) {
  outDerive.innerHTML += '\n' + html;
  outDerive.scrollTop = outDerive.scrollHeight;
}

function resetDerive() {
  if (!currentPattern) {
    outDerive.textContent = 'Negate a regex first.';
    return;
  }
  try {
    deriveState = api.startDeriveNegated(currentPattern);
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
  if (!deriveState) {
    resetDerive();
    if (!deriveState) return;
  }
  if (!s) return;
  for (const c of s) {
    const r = deriveState.step(c).toJs({ dict_converter: Object.fromEntries });
    consumedEl.textContent += c;
    appendLine(`  '${escapeHtml(c)}' [${tagSpan(r.tag)}]: ${escapeHtml(r.pretty)}`);
    if (r.dead) break;
  }
}

const sessionUI = mountSessionUI({
  container: sessionMount,
  makeSession: () => {
    const pat = patternEl.value.trim();
    if (!pat) throw new Error('enter a pattern first');
    return api.makeSessionNegated(pat);
  },
});

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const pat = patternEl.value.trim();
  if (!pat) return;
  await runWithLoading([btnNegate], outResult, 'Building DFA and collapsing to regex', () =>
    api.negateSingle(pat)
  );
  if (!outResult.textContent.startsWith('error:')) {
    currentPattern = pat;
    resetDerive();
  }
});

btnReset.addEventListener('click', resetDerive);

btnStep.addEventListener('click', () => {
  stepChars(charsEl.value);
  charsEl.value = '';
  charsEl.focus();
});

btnEof.addEventListener('click', () => {
  if (!deriveState) {
    resetDerive();
    if (!deriveState) return;
  }
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
    [patternEl, btnNegate, btnReset, btnStep, btnEof, charsEl].forEach((el) => (el.disabled = false));
    sessionUI.enable();
    patternEl.focus();
  })
  .catch((err) => {
    statusEl.textContent = 'Boot failed: ' + fmtErr(err);
    console.error('regrets boot error:', err);
  });
