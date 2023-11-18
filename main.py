from z3 import *
from parser import regex_to_z3_expr
import sre_parse

import os
import typer
from typing import List
from typing_extensions import Annotated

app = typer.Typer()

def fetch_regex(regex, partial=False):
    # Also accept a file list to regex
    if os.path.exists(regex):
        with open(regex, 'r') as regex_file:
            for regex in regex_file.readlines():
                regex = regex.strip()
                regex = f".*{regex}.*" if partial else regex
                yield regex_to_z3_expr(sre_parse.parse(regex)), regex
                
    else: 
        regex = f".*{regex}.*" if partial else regex
        yield regex_to_z3_expr(sre_parse.parse(regex)), regex


@app.command()
def generate(
        matching: Annotated[List[str], typer.Option(help="The string must fully match these regex")] = [],
        not_matching: Annotated[List[str], typer.Option(help="The string must NOT fully match these regex")] = [],
        partial_matching: Annotated[List[str], typer.Option(help="The string must partially match these regex")] = [],
        not_partial_matching: Annotated[List[str], typer.Option(help="The string must NOT partially match these regex")] = [],
        min_len: Annotated[int, typer.Option('--min-len', help="Minimum length for generated samples")] = 1,
        max_len: Annotated[int, typer.Option('--max-len', help="Maximum length for generated samples")] = 100,
        N: Annotated[int, typer.Option('-N', help="Number of samples to generate")] = 1,
        verbose: Annotated[bool, typer.Option('-v', '--verbose', help="Verbose output")] = False
    ):
    solver = Solver()

    bypass = String('bypass')

    if verbose and (matching or not_matching):
        print("# Full matches")

    # Fully Match these regex
    for m in matching:
        for r, regex_string in fetch_regex(m):
            if verbose:
                print(f" [+] {regex_string}")
            solver.add(InRe(bypass, r))

    # Don't fully match these regex
    for regex in not_matching:
        for r, regex_string in fetch_regex(regex, partial=True):
            if verbose:
                print(f" [-] {regex_string}")
            solver.add(InRe(bypass, Complement(r)))

    if verbose and (partial_matching or not_partial_matching):
        print("## Partial Matches")

    # Partially match these regex
    for regex in partial_matching:
        for r, regex_string in fetch_regex(regex, partial=True):
            if verbose:
                print(f"  +  {regex_string}")
            solver.add(InRe(bypass, r))

    # Don't partially match these regex
    for regex in not_partial_matching:
        for r, regex_string in fetch_regex(regex, partial=True):
            if verbose:
                print(f"  -  {regex_string}")
            solver.add(InRe(bypass, Complement(r)))

    solver.add(Length(bypass) >= min_len)
    solver.add(Length(bypass) <= max_len)

    # Only use printable ASCII
    for i in range(max_len):
        solver.add(bypass[i].to_int() > 31)
        solver.add(bypass[i].to_int() < 128)

    for _ in range(N):
        if solver.check():
            if verbose:
                print(f'Sample: ', end='')
            print(solver.model()[bypass].as_string())
            solver.add(bypass != solver.model()[bypass])
        else:
            print('No available samples for given constraints')

if __name__ == '__main__':
    app()
