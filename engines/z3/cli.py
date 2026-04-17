from typing import List

import typer
from typing_extensions import Annotated
from z3 import sat

from engines.z3.solver import build_solver

app = typer.Typer(help="SMT-based generation using the Z3 solver.")


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
