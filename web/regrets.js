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
  if (err instanceof Error) {
    const msg = err.message || '';
    const stack = err.stack || '';
    if (msg && stack && !stack.includes(msg)) return `${msg}\n${stack}`;
    return stack || msg || String(err);
  }
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


def negate_single(pattern):
    re = mk_not(parse(pattern))
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


def _dot_escape(s):
    return s.replace('\\\\', '\\\\\\\\').replace('"', '\\\\"')


def _edge_label(transitions, src, dst):
    return pretty(chars_to_re(transitions[src][dst], PRINTABLE))


def _collapse_chains(states, transitions, accepts, start_id):
    n = len(states)
    out_succ = {i: list(transitions.get(i, {}).keys()) for i in range(n)}
    in_pred = {i: [] for i in range(n)}
    for src in range(n):
        for dst in out_succ[src]:
            in_pred[dst].append(src)

    def is_interior(i):
        if i == start_id or i in accepts:
            return False
        succs = out_succ[i]
        preds = in_pred[i]
        if len(succs) != 1 or len(preds) != 1:
            return False
        if succs[0] == i or preds[0] == i:
            return False
        return True

    interior = {i for i in range(n) if is_interior(i)}
    edges = []
    visited_edges = set()
    for src in range(n):
        if src in interior:
            continue
        for dst in out_succ[src]:
            if (src, dst) in visited_edges:
                continue
            visited_edges.add((src, dst))
            labels = [_edge_label(transitions, src, dst)]
            cur = dst
            while cur in interior:
                nxt = out_succ[cur][0]
                labels.append(_edge_label(transitions, cur, nxt))
                visited_edges.add((cur, nxt))
                cur = nxt
            edges.append((src, cur, labels))
    kept = [i for i in range(n) if i not in interior]
    return kept, edges


def dfa_dot(matching_raw, not_matching_raw, compress=True):
    re = build_re(matching_raw, not_matching_raw)
    states, transitions, accepts, start_id = build_dfa(re)
    lines = [
        'digraph DFA {',
        '  rankdir=LR;',
        '  bgcolor="transparent";',
        '  node [fontname="Helvetica", fontsize=12];',
        '  edge [fontname="Helvetica", fontsize=11];',
        '  __start [shape=point, width=0.1, color="#888"];',
    ]
    if compress:
        kept, edges = _collapse_chains(states, transitions, accepts, start_id)
    else:
        kept = list(range(len(states)))
        edges = []
        for src in sorted(transitions):
            for dst in sorted(transitions[src]):
                edges.append((src, dst, [_edge_label(transitions, src, dst)]))
    for i in kept:
        shape = 'doublecircle' if i in accepts else 'circle'
        tip = _dot_escape(pretty(states[i]))
        lines.append(f'  {i} [shape={shape}, label="{i}", tooltip="{tip}"];')
    lines.append(f'  __start -> {start_id};')
    for src, dst, labels in edges:
        if len(labels) == 1:
            label = _dot_escape(labels[0])
        else:
            label = _dot_escape(''.join(labels))
        lines.append(f'  {src} -> {dst} [label="{label}"];')
    lines.append('}')
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


def start_derive_negated(pattern):
    return DeriveSession(mk_not(parse(pattern)))
`);

  const api = {
    showMerged: pyodide.globals.get('show_merged'),
    convertSingle: pyodide.globals.get('convert_single'),
    negateSingle: pyodide.globals.get('negate_single'),
    dfaText: pyodide.globals.get('dfa_text'),
    dfaDot: pyodide.globals.get('dfa_dot'),
    startDerive: pyodide.globals.get('start_derive'),
    startDeriveSingle: pyodide.globals.get('start_derive_single'),
    startDeriveNegated: pyodide.globals.get('start_derive_negated'),
  };

  setStatus('Ready.');
  return { pyodide, api };
}
