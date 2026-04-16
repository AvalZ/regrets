from z3 import Solver, String, InRe, Complement, Length, sat
from parser import regex_to_z3_expr
import sre_parse

import os
import typer
from typing import Iterator, List, Tuple
from typing_extensions import Annotated
import z3

app = typer.Typer()


def fetch_regex(regex: str, partial: bool = False) -> Iterator[Tuple[z3.ReRef, str]]:
    # Accept either a single regex or a file path containing one regex per line.
    if os.path.exists(regex):
        with open(regex, 'r') as regex_file:
            for line in regex_file:
                pattern = line.strip()
                if not pattern:
                    continue
                pattern = f".*{pattern}.*" if partial else pattern
                yield regex_to_z3_expr(sre_parse.parse(pattern)), pattern
    else:
        pattern = f".*{regex}.*" if partial else regex
        yield regex_to_z3_expr(sre_parse.parse(pattern)), pattern


def build_solver(
    matching: List[str],
    not_matching: List[str],
    partial_matching: List[str],
    not_partial_matching: List[str],
    min_len: int,
    max_len: int,
    verbose: bool = False,
) -> Tuple[Solver, z3.SeqRef]:
    solver = Solver()
    bypass = String('bypass')

    if verbose and (matching or not_matching):
        print("# Full matches")
    for m in matching:
        for r, s in fetch_regex(m):
            if verbose:
                print(f" [+] {s}")
            solver.add(InRe(bypass, r))
    for m in not_matching:
        for r, s in fetch_regex(m):
            if verbose:
                print(f" [-] {s}")
            solver.add(InRe(bypass, Complement(r)))

    if verbose and (partial_matching or not_partial_matching):
        print("## Partial Matches")
    for m in partial_matching:
        for r, s in fetch_regex(m, partial=True):
            if verbose:
                print(f"  +  {s}")
            solver.add(InRe(bypass, r))
    for m in not_partial_matching:
        for r, s in fetch_regex(m, partial=True):
            if verbose:
                print(f"  -  {s}")
            solver.add(InRe(bypass, Complement(r)))

    solver.add(Length(bypass) >= min_len)
    solver.add(Length(bypass) <= max_len)

    # Restrict to printable ASCII.
    for i in range(max_len):
        solver.add(bypass[i].to_int() > 31)
        solver.add(bypass[i].to_int() < 128)

    return solver, bypass


@app.command()
def generate(
        matching: Annotated[List[str], typer.Option(help="The string must fully match these regex")] = [],
        not_matching: Annotated[List[str], typer.Option(help="The string must NOT fully match these regex")] = [],
        partial_matching: Annotated[List[str], typer.Option(help="The string must partially match these regex")] = [],
        not_partial_matching: Annotated[List[str], typer.Option(help="The string must NOT partially match these regex")] = [],
        min_len: Annotated[int, typer.Option('--min-len', help="Minimum length for generated samples")] = 1,
        max_len: Annotated[int, typer.Option('--max-len', help="Maximum length for generated samples")] = 100,
        N: Annotated[int, typer.Option('-N', help="Number of samples to generate")] = 1,
        verbose: Annotated[bool, typer.Option('-v', '--verbose', help="Verbose output")] = False,
    ):
    solver, bypass = build_solver(
        matching, not_matching, partial_matching, not_partial_matching,
        min_len, max_len, verbose,
    )

    for _ in range(N):
        if solver.check() != sat:
            print('No available samples for given constraints')
            break
        sample = solver.model()[bypass]
        if verbose:
            print('Sample: ', end='')
        print(sample.as_string())
        solver.add(bypass != sample)


if __name__ == '__main__':
    app()
