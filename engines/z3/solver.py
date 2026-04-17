import os
import sre_parse
from typing import Iterator, List, Tuple

import z3
from z3 import Solver, String, InRe, Complement, Length

from engines.z3.parser import regex_to_z3_expr


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
