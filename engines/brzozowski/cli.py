from typing import List

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


app = typer.Typer(help="Brzozowski derivative-based generation and interactive derivation.")


def _build(matching: List[str], not_matching: List[str]) -> Re:
    parts: List[Re] = [parse(m) for m in matching]
    parts += [mk_not(parse(m)) for m in not_matching]
    if not parts:
        return ALL_GOOD
    return mk_and(parts)


def _show(re: Re, debug: bool) -> str:
    return repr(re) if debug else pretty(re)


@app.command()
def generate(
        matching: Annotated[List[str], typer.Option(help="String must fully match these regex (intersected)")] = [],
        not_matching: Annotated[List[str], typer.Option(help="String must NOT fully match these regex")] = [],
        min_len: Annotated[int, typer.Option('--min-len')] = 1,
        max_len: Annotated[int, typer.Option('--max-len')] = 20,
        N: Annotated[int, typer.Option('-N', help="Number of samples")] = 1,
    ):
    re = _build(matching, not_matching)
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
        debug: Annotated[bool, typer.Option('--debug', help="Show internal AST instead of pretty-printed regex")] = False,
    ):
    """Resolve via Brzozowski derivatives: build DFA then collapse with state elimination."""
    re = _build(matching, not_matching)
    states, transitions, accepts, start_id = build_dfa(re)
    result = dfa_to_regex(states, transitions, accepts, start_id)
    print(_show(result, debug))


@app.command()
def dfa(
        matching: Annotated[List[str], typer.Option(help="Regex to intersect")] = [],
        not_matching: Annotated[List[str], typer.Option(help="Regex whose complement is intersected")] = [],
        debug: Annotated[bool, typer.Option('--debug', help="Show internal AST for each state instead of pretty-printed regex")] = False,
    ):
    """Build the DFA via Brzozowski derivatives and print its states and transitions."""
    re = _build(matching, not_matching)
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
        debug: Annotated[bool, typer.Option('--debug', help="Show internal AST instead of pretty-printed regex")] = False,
    ):
    re = _build(matching, not_matching)
    print(f"start [{_tag(re)}]: {_show(re, debug)}")
    print('Enter chars (multi-char input replays one at a time).')
    print('Empty line: evaluate fullmatch on input so far. Empty line again to exit; or Ctrl-D.')
    consumed = ''
    pending_exit = False
    while True:
        try:
            s = input(f'{consumed}> ')
        except EOFError:
            print()
            break
        if not s:
            tag = _final_tag(re)
            print(f'  ε [{tag}]: {_show(re, debug)}')
            if pending_exit:
                break
            print('  (empty line again to exit)')
            pending_exit = True
            continue
        pending_exit = False
        dead = False
        for c in s:
            re = deriv(c, re)
            consumed += c
            if re == NO_GOOD:
                print(f"  '{c}' [DEAD] at pos {len(consumed) - 1} — regex broken")
                dead = True
                break
            print(f"  '{c}' [{_tag(re)}]: {_show(re, debug)}")
        if dead:
            return
