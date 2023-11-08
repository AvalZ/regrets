from z3 import *
from parser import regex_to_z3_expr
import sre_parse

import typer
from typing import List
from typing_extensions import Annotated

app = typer.Typer()

@app.command()
def generate(
        matching: Annotated[List[str], typer.Option(help="The string must fully match these regex")] = [],
        not_matching: Annotated[List[str], typer.Option(help="The string must NOT fully match these regex")] = [],
        partial_matching: Annotated[List[str], typer.Option(help="The string must partially match these regex")] = [],
        not_partial_matching: Annotated[List[str], typer.Option(help="The string must NOT partially match these regex")] = [],
        min_len: Annotated[int, typer.Option('--min-len', help="Minimum length for generated samples")] = 1,
        max_len: Annotated[int, typer.Option('--max-len', help="Maximum length for generated samples")] = 100,
        N: Annotated[int, typer.Option(help="Number of samples to generate")] = 1,
        verbose: Annotated[bool, typer.Option('-v', '--verbose', help="Verbose output")] = False
    ):
    solver = Solver()

    bypass = String('bypass')

    # Fully Match these regex
    for regex in matching:
        r = regex_to_z3_expr(sre_parse.parse(regex))
        solver.add(InRe(bypass, r))

    # Don't fully match these regex
    for regex in not_matching:
        r = regex_to_z3_expr(sre_parse.parse(regex))
        solver.add(InRe(bypass, Complement(r)))

    # Partially match these regex
    for regex in partial_matching:
        r = regex_to_z3_expr(sre_parse.parse(f".*{regex}.*"))
        solver.add(InRe(bypass, r))

    # Don't partially match these regex
    for regex in not_partial_matching:
        r = regex_to_z3_expr(sre_parse.parse(f".*{regex}.*"))
        solver.add(InRe(bypass, Complement(r)))

    solver.add(Length(bypass) >= min_len)
    solver.add(Length(bypass) <= max_len)

    # Only use printable ASCII
    for i in range(max_len):
        solver.add(bypass[i].to_int() > 32)
        solver.add(bypass[i].to_int() < 127)

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
