// Shared Pyodide bootstrap + helpers for all regrets pages.

const PY_FILES = [
  'engines/brzozowski/re_ast.py',
  'engines/brzozowski/parser.py',
  'engines/brzozowski/pretty.py',
  'engines/brzozowski/dfa.py',
  'engines/brzozowski/session.py',
  'engines/brzozowski/derive_session.py',
  'engines/brzozowski/generator.py',
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

const GEN_TEMPLATE = `
  <fieldset>
    <legend>Generate sample strings</legend>
    <div class="row">
      <label style="font-size: 0.85rem;">N:
        <input type="number" data-el="gen-n" value="10" min="1" max="500" style="width: 4.5rem;">
      </label>
      <label style="font-size: 0.85rem;">min len:
        <input type="number" data-el="gen-min" value="0" min="0" max="200" style="width: 4.5rem;">
      </label>
      <label style="font-size: 0.85rem;">max len:
        <input type="number" data-el="gen-max" value="20" min="0" max="500" style="width: 4.5rem;">
      </label>
      <button type="button" data-action="gen" disabled>Generate</button>
    </div>
    <pre data-el="gen-out">(click Generate to sample accepting strings)</pre>
  </fieldset>
`;

export function mountGenerateUI({ container, generate: genFn }) {
  container.innerHTML = GEN_TEMPLATE;
  const q = (s) => container.querySelector(s);
  const btn = q('[data-action="gen"]');
  const nEl = q('[data-el="gen-n"]');
  const minEl = q('[data-el="gen-min"]');
  const maxEl = q('[data-el="gen-max"]');
  const outEl = q('[data-el="gen-out"]');

  btn.addEventListener('click', async () => {
    const n = parseInt(nEl.value, 10) || 10;
    const mn = parseInt(minEl.value, 10) || 0;
    const mx = parseInt(maxEl.value, 10) || 20;
    btn.disabled = true;
    outEl.textContent = `⏳ generating up to ${n} string(s)…`;
    await new Promise((r) => setTimeout(r, 0));
    const t0 = performance.now();
    try {
      const proxy = genFn(n, mn, mx);
      const arr = proxy.toJs ? proxy.toJs() : Array.from(proxy);
      if (proxy.destroy) proxy.destroy();
      const ms = (performance.now() - t0).toFixed(0);
      if (!arr.length) {
        outEl.textContent = `(no strings found with length in [${mn}, ${mx}])\n\n(searched in ${ms} ms)`;
      } else {
        const lines = arr.map((s, i) => `${String(i + 1).padStart(3)}. ${JSON.stringify(s)}`);
        outEl.textContent = `${lines.join('\n')}\n\n(${arr.length} string(s) in ${ms} ms)`;
      }
    } catch (err) {
      outEl.textContent = `error: ${fmtErr(err)}`;
    } finally {
      btn.disabled = false;
    }
  });

  return {
    enable() { btn.disabled = false; },
    disable() { btn.disabled = true; },
  };
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
from engines.brzozowski.session import DfaBuilder
from engines.brzozowski.derive_session import DeriveSession
from engines.brzozowski.generator import generate as _generate


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


def start_derive(matching_raw, not_matching_raw):
    return DeriveSession(build_re(matching_raw, not_matching_raw))


def start_derive_single(pattern):
    return DeriveSession(parse(pattern))


def start_derive_negated(pattern):
    return DeriveSession(mk_not(parse(pattern)))


def make_session(matching_raw, not_matching_raw):
    return DfaBuilder(build_re(matching_raw, not_matching_raw))


def make_session_single(pattern):
    return DfaBuilder(parse(pattern))


def make_session_negated(pattern):
    return DfaBuilder(mk_not(parse(pattern)))


def _gen_list(re, n, min_len, max_len):
    return list(_generate(
        re,
        n=max(1, int(n)),
        min_len=max(0, int(min_len)),
        max_len=max(0, int(max_len)),
    ))


def generate_single(pattern, n=10, min_len=0, max_len=20):
    return _gen_list(parse(pattern), n, min_len, max_len)


def generate_negated(pattern, n=10, min_len=0, max_len=20):
    return _gen_list(mk_not(parse(pattern)), n, min_len, max_len)


def generate_merged(matching_raw, not_matching_raw, n=10, min_len=0, max_len=20):
    return _gen_list(build_re(matching_raw, not_matching_raw), n, min_len, max_len)
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
    makeSession: pyodide.globals.get('make_session'),
    makeSessionSingle: pyodide.globals.get('make_session_single'),
    makeSessionNegated: pyodide.globals.get('make_session_negated'),
    generateSingle: pyodide.globals.get('generate_single'),
    generateNegated: pyodide.globals.get('generate_negated'),
    generateMerged: pyodide.globals.get('generate_merged'),
  };

  setStatus('Ready.');
  return { pyodide, api };
}
