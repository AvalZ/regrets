import re

import pytest
from typer.testing import CliRunner

from main import app, build_solver, fetch_regex
from z3 import sat


runner = CliRunner()


def solve(**kwargs):
    kwargs.setdefault('matching', [])
    kwargs.setdefault('not_matching', [])
    kwargs.setdefault('partial_matching', [])
    kwargs.setdefault('not_partial_matching', [])
    kwargs.setdefault('min_len', 1)
    kwargs.setdefault('max_len', 20)
    solver, bypass = build_solver(**kwargs)
    assert solver.check() == sat
    return solver.model()[bypass].as_string()


def test_matching_fullmatch():
    s = solve(matching=['[a-z]{5}'])
    assert re.fullmatch(r'[a-z]{5}', s)


def test_not_matching_fullmatch():
    s = solve(matching=['[a-c]{3}'], not_matching=['abc'])
    assert re.fullmatch(r'[a-c]{3}', s)
    assert s != 'abc'


def test_not_matching_is_full_not_partial():
    # Regression: not_matching must exclude only exact matches, not substrings.
    # 'abcabc' contains 'abc' but is not equal to 'abc' — should remain sat.
    s = solve(matching=['abcabc'], not_matching=['abc'])
    assert s == 'abcabc'


def test_partial_matching():
    s = solve(partial_matching=['hello'], max_len=30)
    assert 'hello' in s


def test_not_partial_matching():
    s = solve(matching=['[a-z]{5}'], not_partial_matching=['z'])
    assert re.fullmatch(r'[a-z]{5}', s)
    assert 'z' not in s


def test_length_bounds():
    s = solve(matching=['.*'], min_len=5, max_len=10)
    assert 5 <= len(s) <= 10


def test_printable_ascii_only():
    s = solve(matching=['.{10}'], min_len=10, max_len=10)
    assert len(s) == 10
    assert all(32 <= ord(c) < 128 for c in s)


def test_unsat_contradiction():
    from main import build_solver
    solver, _ = build_solver(
        matching=['a'], not_matching=['a'],
        partial_matching=[], not_partial_matching=[],
        min_len=1, max_len=1,
    )
    assert solver.check() != sat


def test_fetch_regex_from_file(tmp_path):
    f = tmp_path / "patterns.txt"
    f.write_text("foo\nbar\n\n")
    patterns = [s for _, s in fetch_regex(str(f))]
    assert patterns == ["foo", "bar"]


def test_fetch_regex_partial_wrapping():
    _, s = next(fetch_regex("foo", partial=True))
    assert s == ".*foo.*"


def test_cli_generate_smoke():
    result = runner.invoke(app, ['--matching', '[0-9]{3}', '-N', '1'])
    assert result.exit_code == 0
    out = result.stdout.strip()
    assert re.fullmatch(r'[0-9]{3}', out)


def test_cli_unsat_prints_once():
    result = runner.invoke(app, [
        '--matching', 'a', '--not-matching', 'a',
        '--min-len', '1', '--max-len', '1', '-N', '5',
    ])
    assert result.exit_code == 0
    assert result.stdout.count('No available samples') == 1
