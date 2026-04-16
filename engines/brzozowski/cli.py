from typing import List

import typer
from typing_extensions import Annotated

from engines.brzozowski.re_ast import (
    Re, ALL_GOOD, NO_GOOD, mk_and, mk_not, nullable,
)
from engines.brzozowski.re_ast import derive as deriv
from engines.brzozowski.parser import parse
from engines.brzozowski.pretty import pretty
from engines.brzozowski.generator import generate as gen_strings


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
    """Print the combined regex after intersection/negation, simplified via smart constructors."""
    re = _build(matching, not_matching)
    print(_show(re, debug))


@app.command()
def derive(
        matching: Annotated[List[str], typer.Option(help="Regex to derive against (intersected if multiple)")] = [],
        not_matching: Annotated[List[str], typer.Option(help="Regex whose complement is intersected")] = [],
        debug: Annotated[bool, typer.Option('--debug', help="Show internal AST instead of pretty-printed regex")] = False,
    ):
    re = _build(matching, not_matching)
    status = 'MATCH (ε accepted)' if nullable(re) else 'partial'
    print(f"start [{status}]: {_show(re, debug)}")
    print('Enter chars (multi-char input replays one at a time). Empty line / Ctrl-D to exit.')
    while True:
        try:
            s = input('> ')
        except EOFError:
            print()
            break
        if not s:
            break
        for i, c in enumerate(s):
            re = deriv(c, re)
            if re == NO_GOOD:
                print(f"  '{c}' (pos {i}): DEAD — regex broken at this char")
                return
            tag = 'MATCH' if nullable(re) else 'partial'
            print(f"  '{c}' [{tag}]: {_show(re, debug)}")
