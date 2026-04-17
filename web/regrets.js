// Shared Pyodide bootstrap + helpers for all regrets pages.

const PY_FILES = [
  'engines/brzozowski/re_ast.py',
  'engines/brzozowski/parser.py',
  'engines/brzozowski/pretty.py',
  'engines/brzozowski/dfa.py',
];

const CANDIDATE_BASES = ['../', './', '/'];

async function detectBase() {
  const probe = PY_FILES[0];
  for (const b of CANDIDATE_BASES) {
    try {
      const r = await fetch(b + probe, { method: 'HEAD' });
      if (r.ok) return b;
    } catch (_) { /* try next */ }
  }
  throw new Error(
    `Could not find ${probe}. Tried: ${CANDIDATE_BASES.map(b => b + probe).join(', ')}. ` +
    `Serve the repo root: 'python3 -m http.server' from the repo root, then open /web/.`
  );
}

export function fmtErr(err) {
  if (!err) return 'unknown';
  if (err instanceof Error) return err.stack || err.message || String(err);
  if (typeof err === 'object') {
    try { return JSON.stringify(err); } catch (_) { return String(err); }
  }
  return String(err);
}

export function escapeHtml(s) {
  return s.replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
}

export function tagSpan(t) {
  const cls = t === 'MATCH' ? 'match' : t === 'DEAD' ? 'dead' : 'partial';
  return `<span class="tag ${cls}">${t}</span>`;
}

export async function runWithLoading(buttons, targetEl, label, work, { showElapsed = true } = {}) {
  buttons.forEach((b) => (b.disabled = true));
  targetEl.textContent = `⏳ ${label}… (browser will freeze briefly)`;
  await new Promise((r) => setTimeout(r, 0));
  const t0 = performance.now();
  try {
    const result = work();
    const ms = (performance.now() - t0).toFixed(0);
    targetEl.textContent = showElapsed ? `${result}\n\n(computed in ${ms} ms)` : String(result);
  } catch (err) {
    targetEl.textContent = `error: ${fmtErr(err)}`;
  } finally {
    buttons.forEach((b) => (b.disabled = false));
  }
}

export async function boot({ statusEl } = {}) {
  const setStatus = (t) => { if (statusEl) statusEl.textContent = t; };
  setStatus('Booting Pyodide…');
  const pyodide = await loadPyodide({ indexURL: './vendor/pyodide/' });
  setStatus('Loading brzozowski sources…');

  const ROOT = '/regrets';
  for (const dir of [ROOT, `${ROOT}/engines`, `${ROOT}/engines/brzozowski`]) {
    try {
      pyodide.FS.mkdir(dir);
    } catch (e) {
      if (e && e.errno !== 20 /* EEXIST */) {
        throw new Error(`mkdir ${dir} failed: ${fmtErr(e)}`);
      }
    }
  }
  pyodide.FS.writeFile(`${ROOT}/engines/__init__.py`, '');
  pyodide.FS.writeFile(`${ROOT}/engines/brzozowski/__init__.py`, '');

  const base = await detectBase();
  for (const rel of PY_FILES) {
    const url = base + rel;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`fetch ${url} → ${res.status}`);
    pyodide.FS.writeFile(`${ROOT}/${rel}`, await res.text());
  }

  pyodide.runPython(`
import sys
if '/regrets' not in sys.path:
    sys.path.insert(0, '/regrets')
`);

  pyodide.runPython(`
from engines.brzozowski.re_ast import ALL_GOOD, NO_GOOD, nullable, derive, mk_and, mk_not
from engines.brzozowski.parser import parse
from engines.brzozowski.pretty import pretty
from engines.brzozowski.dfa import build_dfa, dfa_to_regex, chars_to_re, PRINTABLE


def _split_lines(raw):
    out = []
    for line in (raw or '').splitlines():
        s = line.strip()
        if s and not s.startswith('#'):
            out.append(s)
    return out


def build_re(matching_raw, not_matching_raw):
    matching = _split_lines(matching_raw)
    not_matching = _split_lines(not_matching_raw)
    parts = [parse(m) for m in matching]
    parts += [mk_not(parse(m)) for m in not_matching]
    if not parts:
        return ALL_GOOD
    return mk_and(parts)


def show_merged(matching_raw, not_matching_raw):
    re = build_re(matching_raw, not_matching_raw)
    states, transitions, accepts, start_id = build_dfa(re)
    merged = dfa_to_regex(states, transitions, accepts, start_id)
    return pretty(merged)


def convert_single(pattern):
    re = parse(pattern)
    states, transitions, accepts, start_id = build_dfa(re)
    merged = dfa_to_regex(states, transitions, accepts, start_id)
    return pretty(merged)


def dfa_text(matching_raw, not_matching_raw):
    re = build_re(matching_raw, not_matching_raw)
    states, transitions, accepts, start_id = build_dfa(re)
    lines = [f"States ({len(states)}):"]
    for i, s in enumerate(states):
        tags = []
        if i == start_id:
            tags.append('start')
        if i in accepts:
            tags.append('accept')
        tag_str = f" [{','.join(tags)}]" if tags else ''
        lines.append(f"  {i}{tag_str}: {pretty(s)}")
    lines.append('Transitions:')
    for src in sorted(transitions):
        for dst in sorted(transitions[src]):
            label = pretty(chars_to_re(transitions[src][dst], PRINTABLE))
            lines.append(f"  {src} --{label}--> {dst}")
    return '\\n'.join(lines)


def _tag(re):
    if re == NO_GOOD:
        return 'DEAD'
    return 'MATCH' if nullable(re) else 'partial'


def _final_tag(re):
    return 'MATCH' if nullable(re) else 'DEAD'


class DeriveSession:
    def __init__(self, re):
        self.re = re
        self.consumed = ''
        self.dead = False

    def snapshot(self):
        return {'consumed': self.consumed, 'pretty': pretty(self.re), 'tag': _tag(self.re), 'dead': self.dead}

    def step(self, c):
        if self.dead:
            return {'char': c, 'pretty': pretty(self.re), 'tag': 'DEAD', 'dead': True}
        self.re = derive(c, self.re)
        self.consumed += c
        if self.re == NO_GOOD:
            self.dead = True
            return {'char': c, 'pretty': '∅', 'tag': 'DEAD', 'dead': True}
        return {'char': c, 'pretty': pretty(self.re), 'tag': _tag(self.re), 'dead': False}

    def eof(self):
        return {'pretty': pretty(self.re), 'tag': _final_tag(self.re)}


def start_derive(matching_raw, not_matching_raw):
    return DeriveSession(build_re(matching_raw, not_matching_raw))


def start_derive_single(pattern):
    return DeriveSession(parse(pattern))
`);

  const api = {
    showMerged: pyodide.globals.get('show_merged'),
    convertSingle: pyodide.globals.get('convert_single'),
    dfaText: pyodide.globals.get('dfa_text'),
    startDerive: pyodide.globals.get('start_derive'),
    startDeriveSingle: pyodide.globals.get('start_derive_single'),
  };

  setStatus('Ready.');
  return { pyodide, api };
}
