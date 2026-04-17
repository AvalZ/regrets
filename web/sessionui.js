import { fmtErr } from './regrets.js';

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

const TEMPLATE = `
  <fieldset class="session-ui">
    <legend>DFA session (incremental)</legend>
    <div class="row">
      <button data-action="new" disabled>new session</button>
      <label style="font-size: 0.85rem;">BFS depth:
        <input type="number" data-el="depth" value="3" min="0" max="50" style="width: 4rem;">
      </label>
      <button data-action="bfs" disabled>expand BFS</button>
      <button data-action="show" disabled>show merged regex (over-approx)</button>
      <label style="font-size: 0.85rem; opacity: 0.85;">
        <input type="checkbox" data-el="compress" checked> compress chains
      </label>
      <span data-el="info" style="font-size: 0.8rem; opacity: 0.7;"></span>
    </div>
    <div class="row" style="margin-top: 0.3rem;">
      <span style="font-size: 0.8rem; opacity: 0.6;">(scroll to zoom · drag to pan · frontier = dashed, remaining regex on dashed exit arrow)</span>
    </div>
    <pre data-el="out-show" style="display:none">(merged regex appears here)</pre>
    <div data-el="out-dfa" class="dfa-out" style="display:none"></div>
    <fieldset style="margin-top: 0.75rem;">
      <legend style="font-size: 0.85rem;">expand one frontier state</legend>
      <div class="row">
        <label style="font-size: 0.85rem;">state:
          <select data-el="frontier" disabled><option value="">(no frontier)</option></select>
        </label>
        <label style="font-size: 0.85rem;">input:
          <input type="text" data-el="chars" placeholder="blank=symbolic, or a, [a-z], [^0-9]" style="width: 14rem;">
        </label>
        <button data-action="step" disabled>expand state</button>
      </div>
    </fieldset>
  </fieldset>
`;

export function mountSessionUI({ container, makeSession }) {
  container.innerHTML = TEMPLATE;
  const q = (s) => container.querySelector(s);
  const btnNew = q('[data-action="new"]');
  const btnBfs = q('[data-action="bfs"]');
  const btnShow = q('[data-action="show"]');
  const btnStep = q('[data-action="step"]');
  const depthEl = q('[data-el="depth"]');
  const compressEl = q('[data-el="compress"]');
  const frontierEl = q('[data-el="frontier"]');
  const charsEl = q('[data-el="chars"]');
  const infoEl = q('[data-el="info"]');
  const outDfa = q('[data-el="out-dfa"]');
  const outShow = q('[data-el="out-show"]');

  let session = null;

  function updateFrontier() {
    const arr = session.frontier_list().toJs({ dict_converter: Object.fromEntries });
    frontierEl.innerHTML = '';
    if (arr.length === 0) {
      const opt = document.createElement('option');
      opt.value = '';
      opt.textContent = '(no frontier — DFA complete)';
      frontierEl.appendChild(opt);
      frontierEl.disabled = true;
      btnStep.disabled = true;
      return;
    }
    frontierEl.disabled = false;
    btnStep.disabled = false;
    for (const row of arr) {
      const opt = document.createElement('option');
      opt.value = String(row.id);
      const tip = row.pretty.length > 60 ? row.pretty.slice(0, 60) + '…' : row.pretty;
      opt.textContent = `#${row.id} (d=${row.depth}, unexplored=${row.n_unexplored}) ${tip}`;
      frontierEl.appendChild(opt);
    }
  }

  function updateInfo() {
    const i = session.info().toJs({ dict_converter: Object.fromEntries });
    infoEl.textContent = `${i.n_states} states · ${i.n_frontier} frontier · ${i.n_accepts} accept · depth ${i.max_depth}`;
  }

  async function renderGraph() {
    outDfa.style.display = 'block';
    outDfa.textContent = '⏳ rendering…';
    const t0 = performance.now();
    try {
      const dot = session.to_dot(compressEl.checked);
      const viz = await getViz();
      const svg = viz.renderSVGElement(dot);
      const ms = (performance.now() - t0).toFixed(0);
      outDfa.innerHTML = '';
      outDfa.appendChild(makeZoomable(svg));
      const caption = document.createElement('div');
      caption.className = 'caption';
      caption.textContent = `(rendered in ${ms} ms)`;
      outDfa.appendChild(caption);
    } catch (err) {
      console.error('dfa render error:', err);
      outDfa.textContent = `error: ${fmtErr(err)}`;
    }
  }

  async function refreshAll() {
    updateInfo();
    updateFrontier();
    await renderGraph();
  }

  async function withBusy(btns, work) {
    btns.forEach((b) => (b.disabled = true));
    try {
      await work();
    } finally {
      btns.forEach((b) => (b.disabled = false));
    }
    if (session) updateFrontier();
  }

  btnNew.addEventListener('click', async () => {
    await withBusy([btnNew, btnBfs, btnShow, btnStep], async () => {
      try {
        if (session && session.destroy) session.destroy();
        session = makeSession();
        if (!session) return;
        const n = Math.max(0, parseInt(depthEl.value, 10) || 0);
        if (n > 0) session.expand_bfs(n);
        await refreshAll();
      } catch (err) {
        console.error('new session error:', err);
        outDfa.style.display = 'block';
        outDfa.textContent = `error: ${fmtErr(err)}`;
      }
    });
  });

  btnBfs.addEventListener('click', async () => {
    if (!session) {
      outDfa.style.display = 'block';
      outDfa.textContent = 'start a session first';
      return;
    }
    await withBusy([btnNew, btnBfs, btnShow, btnStep], async () => {
      try {
        const n = Math.max(1, parseInt(depthEl.value, 10) || 1);
        session.expand_bfs(n);
        await refreshAll();
      } catch (err) {
        console.error('expand bfs error:', err);
        outDfa.textContent = `error: ${fmtErr(err)}`;
      }
    });
  });

  btnStep.addEventListener('click', async () => {
    if (!session) return;
    const sid = parseInt(frontierEl.value, 10);
    if (Number.isNaN(sid)) return;
    const chars = charsEl.value.trim();
    await withBusy([btnNew, btnBfs, btnShow, btnStep], async () => {
      try {
        session.expand_state_str(sid, chars || null);
        charsEl.value = '';
        await refreshAll();
      } catch (err) {
        console.error('expand state error:', err);
        outDfa.textContent = `error: ${fmtErr(err)}`;
      }
    });
  });

  btnShow.addEventListener('click', async () => {
    if (!session) {
      outShow.style.display = 'block';
      outShow.textContent = 'start a session first';
      return;
    }
    outShow.style.display = 'block';
    outShow.textContent = '⏳ building regex from current DFA…';
    await new Promise((r) => setTimeout(r, 0));
    const t0 = performance.now();
    try {
      const s = session.show_merged_pretty();
      const ms = (performance.now() - t0).toFixed(0);
      const i = session.info().toJs({ dict_converter: Object.fromEntries });
      const note = i.n_frontier > 0
        ? `\n\n⚠ over-approximation: ${i.n_frontier} frontier state(s) treated as dead`
        : '';
      outShow.textContent = `${s}${note}\n\n(computed in ${ms} ms)`;
    } catch (err) {
      console.error('show merged error:', err);
      outShow.textContent = `error: ${fmtErr(err)}`;
    }
  });

  compressEl.addEventListener('change', () => {
    if (session) renderGraph();
  });

  return {
    enable() {
      [btnNew, btnBfs, btnShow].forEach((b) => (b.disabled = false));
    },
    disable() {
      [btnNew, btnBfs, btnShow, btnStep].forEach((b) => (b.disabled = true));
    },
  };
}
