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

btnDfa.addEventListener('click', () => {
  outDfa.style.display = 'block';
  runWithLoading([btnShow, btnDfa], outDfa, 'Building DFA', () =>
    api.dfaText(matchingEl.value, notMatchingEl.value)
  );
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
