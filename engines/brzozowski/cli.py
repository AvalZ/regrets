import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import List, Optional

import typer
from typing_extensions import Annotated

from engines.brzozowski.re_ast import (
    Re, ALL_GOOD, NO_GOOD, EPS, mk_and, mk_not, nullable,
)
from engines.brzozowski.re_ast import derive as deriv
from engines.brzozowski.parser import parse
from engines.brzozowski.pretty import pretty
from engines.brzozowski.generator import generate as gen_strings
from engines.brzozowski.dfa import build_dfa, dfa_to_regex, chars_to_re, PRINTABLE
from engines.brzozowski.session import DfaBuilder, parse_char_class
from engines.brzozowski.derive_session import DeriveSession


app = typer.Typer(help="Brzozowski derivative-based generation and interactive derivation.")


def _read_patterns(path: Optional[Path]) -> List[str]:
    if path is None:
        return []
    out = []
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if line and not line.startswith('#'):
            out.append(line)
    return out


def _build(
    matching: List[str],
    not_matching: List[str],
    matching_file: Optional[Path] = None,
    not_matching_file: Optional[Path] = None,
) -> Re:
    all_matching = list(matching) + _read_patterns(matching_file)
    all_not_matching = list(not_matching) + _read_patterns(not_matching_file)
    parts: List[Re] = [parse(m) for m in all_matching]
    parts += [mk_not(parse(m)) for m in all_not_matching]
    if not parts:
        return ALL_GOOD
    return mk_and(parts)


_MATCHING_FILE_HELP = "Path to file; one regex per line (# comments, blank lines skipped). Intersected with --matching."
_NOT_MATCHING_FILE_HELP = "Path to file; one regex per line (# comments, blank lines skipped). Each complemented and intersected."


def _show(re: Re, debug: bool) -> str:
    return repr(re) if debug else pretty(re)


@contextmanager
def _spinner(message: str):
    """Render a ticking spinner to stderr while the block runs. No-op for non-TTY."""
    if not sys.stderr.isatty():
        yield
        return
    frames = '|/-\\'
    stop = threading.Event()
    start = time.monotonic()

    def tick():
        i = 0
        while not stop.is_set():
            elapsed = time.monotonic() - start
            sys.stderr.write(f'\r{frames[i % len(frames)]} {message} ({elapsed:.1f}s)')
            sys.stderr.flush()
            i += 1
            stop.wait(0.1)

    t = threading.Thread(target=tick, daemon=True)
    t.start()
    try:
        yield
    finally:
        stop.set()
        t.join()
        sys.stderr.write('\r\033[K')
        sys.stderr.flush()


@app.command()
def generate(
        matching: Annotated[List[str], typer.Option(help="String must fully match these regex (intersected)")] = [],
        not_matching: Annotated[List[str], typer.Option(help="String must NOT fully match these regex")] = [],
        matching_file: Annotated[Optional[Path], typer.Option('--matching-file', help=_MATCHING_FILE_HELP)] = None,
        not_matching_file: Annotated[Optional[Path], typer.Option('--not-matching-file', help=_NOT_MATCHING_FILE_HELP)] = None,
        min_len: Annotated[int, typer.Option('--min-len')] = 1,
        max_len: Annotated[int, typer.Option('--max-len')] = 20,
        N: Annotated[int, typer.Option('-N', help="Number of samples")] = 1,
    ):
    re = _build(matching, not_matching, matching_file, not_matching_file)
    found = False
    for s in gen_strings(re, n=N, min_len=min_len, max_len=max_len):
        found = True
        print(s)
    if not found:
        print('No available samples for given constraints')


@app.command()
def show(
        matching: Annotated[List[str], typer.Option(help="Regex to intersect")] = [],
        not_matching: Annotated[List[str], typer.Option(help="Regex whose complement is intersected")] = [],
        matching_file: Annotated[Optional[Path], typer.Option('--matching-file', help=_MATCHING_FILE_HELP)] = None,
        not_matching_file: Annotated[Optional[Path], typer.Option('--not-matching-file', help=_NOT_MATCHING_FILE_HELP)] = None,
        debug: Annotated[bool, typer.Option('--debug', help="Show internal AST instead of pretty-printed regex")] = False,
    ):
    """Resolve via Brzozowski derivatives: build DFA then collapse with state elimination."""
    re = _build(matching, not_matching, matching_file, not_matching_file)
    with _spinner('Building DFA and collapsing to regex'):
        states, transitions, accepts, start_id = build_dfa(re)
        result = dfa_to_regex(states, transitions, accepts, start_id)
    print(_show(result, debug))


@app.command()
def dfa(
        matching: Annotated[List[str], typer.Option(help="Regex to intersect")] = [],
        not_matching: Annotated[List[str], typer.Option(help="Regex whose complement is intersected")] = [],
        matching_file: Annotated[Optional[Path], typer.Option('--matching-file', help=_MATCHING_FILE_HELP)] = None,
        not_matching_file: Annotated[Optional[Path], typer.Option('--not-matching-file', help=_NOT_MATCHING_FILE_HELP)] = None,
        debug: Annotated[bool, typer.Option('--debug', help="Show internal AST for each state instead of pretty-printed regex")] = False,
    ):
    """Build the DFA via Brzozowski derivatives and print its states and transitions."""
    re = _build(matching, not_matching, matching_file, not_matching_file)
    with _spinner('Building DFA'):
        states, transitions, accepts, start_id = build_dfa(re)
    print(f"States ({len(states)}):")
    for i, s in enumerate(states):
        tags = []
        if i == start_id:
            tags.append('start')
        if i in accepts:
            tags.append('accept')
        tag_str = f" [{','.join(tags)}]" if tags else ""
        print(f"  {i}{tag_str}: {_show(s, debug)}")
    print("Transitions:")
    for src in sorted(transitions):
        for dst in sorted(transitions[src]):
            label = pretty(chars_to_re(transitions[src][dst], PRINTABLE))
            print(f"  {src} --{label}--> {dst}")


def _tag(re: Re) -> str:
    if re == NO_GOOD:
        return 'DEAD'
    return 'MATCH' if nullable(re) else 'partial'


def _final_tag(re: Re) -> str:
    # End-of-input verdict (anchored fullmatch): nullable → MATCH, else DEAD.
    return 'MATCH' if nullable(re) else 'DEAD'


@app.command()
def derive(
        matching: Annotated[List[str], typer.Option(help="Regex to derive against (intersected if multiple)")] = [],
        not_matching: Annotated[List[str], typer.Option(help="Regex whose complement is intersected")] = [],
        matching_file: Annotated[Optional[Path], typer.Option('--matching-file', help=_MATCHING_FILE_HELP)] = None,
        not_matching_file: Annotated[Optional[Path], typer.Option('--not-matching-file', help=_NOT_MATCHING_FILE_HELP)] = None,
        debug: Annotated[bool, typer.Option('--debug', help="Show internal AST instead of pretty-printed regex")] = False,
    ):
    re = _build(matching, not_matching, matching_file, not_matching_file)
    sess = DeriveSession(re)
    print(f"start [{_tag(sess.re)}]: {_show(sess.re, debug)}")
    print('Enter chars (multi-char input replays one at a time).')
    print('Commands: :back/:b undo · :fwd/:f redo · :reset/:r restart.')
    print('Empty line: evaluate fullmatch on input so far. Empty line again to exit; or Ctrl-D.')
    pending_exit = False
    while True:
        try:
            s = input(f'{sess.consumed}> ')
        except EOFError:
            print()
            break
        if not s:
            tag = _final_tag(sess.re)
            print(f'  ε [{tag}]: {_show(sess.re, debug)}')
            if pending_exit:
                break
            print('  (empty line again to exit)')
            pending_exit = True
            continue
        pending_exit = False
        cmd = s.strip().lower()
        if cmd in (':back', ':b'):
            if sess.back():
                print(f"  [BACK] now '{sess.consumed}' [{_tag(sess.re)}]: {_show(sess.re, debug)}")
            else:
                print('  (nothing to undo)')
            continue
        if cmd in (':fwd', ':f', ':forward'):
            if sess.forward():
                print(f"  [FWD] now '{sess.consumed}' [{_tag(sess.re)}]: {_show(sess.re, debug)}")
            else:
                print('  (nothing to redo)')
            continue
        if cmd in (':reset', ':r'):
            sess.reset()
            print(f"  [RESET] [{_tag(sess.re)}]: {_show(sess.re, debug)}")
            continue
        for c in s:
            if sess.dead:
                print(f"  '{c}' ignored — DEAD; :back to undo, :reset to restart")
                break
            sess.step(c)
            if sess.dead:
                print(f"  '{c}' [DEAD] at pos {len(sess.consumed) - 1} — :back to undo, :reset to restart")
                break
            print(f"  '{c}' [{_tag(sess.re)}]: {_show(sess.re, debug)}")


_SESSION_HELP = """\
commands:
  bfs [N]                 symbolic BFS expansion, N levels (default 1)
  step <sid> [input]      expand one frontier state; input = char, [class], [^class]; blank = full symbolic
  show                    state-eliminate current DFA to regex (frontier treated as dead)
  dfa                     print states + transitions (current partial DFA)
  info                    stats: #states, #frontier, #accepts, max depth
  frontier                list frontier states with their remaining regex
  state <sid>             show one state's regex + flags
  dot [path]              emit Graphviz DOT; path writes to file, else stdout
  help                    this message
  quit / exit / :q        leave session
"""


def _print_session_dfa(b: DfaBuilder, debug: bool) -> None:
    print(f"States ({len(b.states)}):")
    for i, s in enumerate(b.states):
        tags = []
        if i == 0:
            tags.append('start')
        if i in b.accepts:
            tags.append('accept')
        if i in b.frontier:
            tags.append('frontier')
        tag_str = f" [{','.join(tags)}]" if tags else ""
        print(f"  {i}{tag_str}: {_show(s, debug)}")
    print("Transitions:")
    for src in sorted(b.transitions):
        for dst in sorted(b.transitions[src]):
            label = pretty(chars_to_re(b.transitions[src][dst], b.alphabet))
            print(f"  {src} --{label}--> {dst}")


def _print_info(b: DfaBuilder) -> None:
    info = b.info()
    print(f"states={info['n_states']} frontier={info['n_frontier']} "
          f"accepts={info['n_accepts']} depth={info['max_depth']}")


def _print_frontier(b: DfaBuilder, debug: bool) -> None:
    rows = b.frontier_list()
    if not rows:
        print('(no frontier — DFA complete)')
        return
    for row in rows:
        flag = ' [accept]' if row['accept'] else ''
        label = row['pretty'] if not debug else repr(b.states[row['id']])
        print(f"  #{row['id']} d={row['depth']} unexplored={row['n_unexplored']}{flag}: {label}")


@app.command()
def session(
        matching: Annotated[List[str], typer.Option(help="Regex to intersect")] = [],
        not_matching: Annotated[List[str], typer.Option(help="Regex whose complement is intersected")] = [],
        matching_file: Annotated[Optional[Path], typer.Option('--matching-file', help=_MATCHING_FILE_HELP)] = None,
        not_matching_file: Annotated[Optional[Path], typer.Option('--not-matching-file', help=_NOT_MATCHING_FILE_HELP)] = None,
        bfs: Annotated[int, typer.Option('--bfs', help="Initial symbolic BFS expansion depth")] = 0,
        debug: Annotated[bool, typer.Option('--debug', help="Show internal AST instead of pretty-printed regex")] = False,
    ):
    """Incremental DFA builder. Grow symbolically (BFS) or pick frontier states to expand with concrete chars."""
    re = _build(matching, not_matching, matching_file, not_matching_file)
    b = DfaBuilder(re)
    if bfs > 0:
        b.expand_bfs(bfs)
    _print_info(b)
    print("Type 'help' for commands, 'quit' to exit.")
    while True:
        try:
            raw = input('session> ').strip()
        except EOFError:
            print()
            return
        if not raw:
            continue
        parts = raw.split(None, 1)
        cmd = parts[0].lower()
        rest = parts[1] if len(parts) > 1 else ''

        if cmd in ('quit', 'exit', ':q'):
            return
        if cmd == 'help':
            print(_SESSION_HELP)
            continue
        if cmd == 'info':
            _print_info(b)
            continue
        if cmd == 'frontier':
            _print_frontier(b, debug)
            continue
        if cmd == 'state':
            try:
                sid = int(rest)
            except ValueError:
                print('usage: state <sid>')
                continue
            if sid < 0 or sid >= len(b.states):
                print(f'no state {sid}')
                continue
            summary = b.state_summary(sid)
            flags = []
            if sid == 0:
                flags.append('start')
            if summary['accept']:
                flags.append('accept')
            if summary['frontier']:
                flags.append(f"frontier (unexplored={summary['n_unexplored']})")
            flag_str = f" [{', '.join(flags)}]" if flags else ''
            print(f"#{sid} d={summary['depth']}{flag_str}: {_show(b.states[sid], debug)}")
            continue
        if cmd == 'bfs':
            try:
                n = int(rest) if rest else 1
            except ValueError:
                print('usage: bfs [N]')
                continue
            added = b.expand_bfs(n)
            print(f'+{len(added)} states')
            _print_info(b)
            continue
        if cmd == 'step':
            sp = rest.split(None, 1)
            if not sp:
                print('usage: step <sid> [input]')
                continue
            try:
                sid = int(sp[0])
            except ValueError:
                print('usage: step <sid> [input]')
                continue
            if sid not in b.frontier:
                print(f'#{sid} not in frontier')
                continue
            chars_str = sp[1] if len(sp) > 1 else ''
            try:
                if chars_str:
                    chars = parse_char_class(chars_str, b.alphabet)
                    added = b.expand_state(sid, chars)
                else:
                    added = b.expand_state(sid, None)
            except ValueError as e:
                print(f'error: {e}')
                continue
            print(f'+{len(added)} states')
            _print_info(b)
            continue
        if cmd == 'show':
            with _spinner('State-eliminating'):
                merged = b.show_merged()
            note = '' if not b.frontier else f" (over-approx; {len(b.frontier)} frontier state(s) treated as dead)"
            print(_show(merged, debug) + note)
            continue
        if cmd == 'dfa':
            _print_session_dfa(b, debug)
            continue
        if cmd == 'dot':
            dot_src = b.to_dot()
            if rest:
                Path(rest).write_text(dot_src)
                print(f'wrote {rest}')
            else:
                print(dot_src)
            continue
        print(f"unknown command: {cmd!r}. type 'help'.")
