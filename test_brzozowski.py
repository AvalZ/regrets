import re as pyre

import pytest
from typer.testing import CliRunner

from main import app
from engines.brzozowski.re_ast import (
    NO_GOOD, ALL_GOOD, EPS,
    accepts, derive, nullable, mk_and, mk_not,
)
from engines.brzozowski.parser import parse
from engines.brzozowski.generator import generate
from engines.brzozowski.pretty import pretty


CASES = [
    # Literals
    ("a", "a", True), ("a", "b", False),
    ("abc", "abc", True), ("abc", "ab", False),
    # Alternation
    ("a|b", "a", True), ("a|b", "b", True), ("a|b", "c", False),
    # Quantifiers
    ("a*", "", True), ("a*", "aaaa", True),
    ("a+", "", False), ("a+", "a", True),
    ("a?", "", True), ("a?", "a", True), ("a?", "aa", False),
    ("a{2,3}", "a", False), ("a{2,3}", "aa", True),
    ("a{2,3}", "aaa", True), ("a{2,3}", "aaaa", False),
    # Any char
    (".", "x", True), (".", "", False),
    # Char classes
    ("[abc]", "a", True), ("[abc]", "d", False),
    ("[^abc]", "d", True), ("[^abc]", "a", False),
    ("[a-z]", "m", True), ("[a-z]", "M", False),
    # Categories
    (r"\d", "5", True), (r"\d", "a", False),
    (r"\D", "a", True), (r"\D", "5", False),
    (r"\w", "_", True), (r"\w", "-", False),
    (r"\W", "-", True),
    (r"\s", " ", True), (r"\s", "x", False),
    # Concat + groups
    ("(ab)+", "abab", True), ("(ab)+", "aba", False),
    # Negated literal
    ("[^a]", "b", True), ("[^a]", "a", False),
]


@pytest.mark.parametrize("pattern,sample,expected", CASES)
def test_accepts_matches_python_re(pattern, sample, expected):
    assert bool(pyre.fullmatch(pattern, sample)) == expected
    assert accepts(parse(pattern), sample) == expected


def test_empty_regex_raises():
    with pytest.raises(ValueError):
        parse("")


@pytest.mark.parametrize("pattern", ["^a", "a$", r"\ba"])
def test_unsupported_anchors_raise(pattern):
    with pytest.raises(NotImplementedError):
        parse(pattern)


def test_derive_dead_state():
    assert derive('x', parse("abc")) == NO_GOOD


def test_derive_progresses_through_literal():
    re = parse("abc")
    re = derive('a', re)
    assert not nullable(re)
    re = derive('b', re)
    assert not nullable(re)
    re = derive('c', re)
    assert nullable(re)


def test_intersection_via_mk_and():
    re = mk_and([parse(r"[a-z]+"), parse(r".*z.*")])
    assert accepts(re, "zaz")
    assert accepts(re, "z")
    assert not accepts(re, "abc")  # no z
    assert not accepts(re, "Z")    # uppercase


def test_negation_via_mk_not():
    re = mk_and([parse(r".{3}"), mk_not(parse(r"abc"))])
    assert accepts(re, "abd")
    assert not accepts(re, "abc")
    assert not accepts(re, "ab")


def test_generate_smoke():
    samples = list(generate(parse(r"[a-c]{3}"), n=5, min_len=3, max_len=3))
    assert len(samples) == 5
    for s in samples:
        assert pyre.fullmatch(r"[a-c]{3}", s)


def test_generate_intersection():
    re = mk_and([parse(r"[a-z]{1,4}"), parse(r".*z.*")])
    samples = list(generate(re, n=3, min_len=1, max_len=4))
    assert samples
    for s in samples:
        assert pyre.fullmatch(r"[a-z]{1,4}", s)
        assert 'z' in s


def test_generate_negation():
    re = mk_and([parse(r"[a-c]{3}"), mk_not(parse(r"abc"))])
    samples = list(generate(re, n=3, min_len=3, max_len=3))
    assert samples
    for s in samples:
        assert pyre.fullmatch(r"[a-c]{3}", s)
        assert s != "abc"


def test_generate_unsat():
    re = mk_and([parse(r"a"), mk_not(parse(r"a"))])
    assert list(generate(re, n=3, min_len=1, max_len=3)) == []


def test_pretty_basic():
    assert pretty(parse("abc")) == "abc"
    assert pretty(parse(".")) == "."
    assert pretty(parse("a*")) == "a*"
    assert pretty(EPS) == "ε"
    assert pretty(NO_GOOD) == "∅"
    assert pretty(ALL_GOOD) == ".*"


def test_pretty_charclass_compact():
    out = pretty(parse("[a-z]"))
    assert out == "[a-z]"


@pytest.mark.parametrize("pattern,expected", [
    ("a+", "a+"),
    ("a?", "a?"),
    ("a{3}", "a{3}"),
    ("a{2,5}", "a{2,5}"),
    ("[a-z]{1,3}", "[a-z]{1,3}"),
    ("abc", "abc"),
])
def test_pretty_quantifier_shortcuts(pattern, expected):
    assert pretty(parse(pattern)) == expected


runner = CliRunner()


def test_cli_generate_smoke():
    result = runner.invoke(app, ['brzozowski', 'generate', '--matching', '[0-9]{3}', '-N', '1'])
    assert result.exit_code == 0
    assert pyre.fullmatch(r'[0-9]{3}', result.stdout.strip())


def test_cli_generate_unsat_message():
    result = runner.invoke(app, [
        'brzozowski', 'generate',
        '--matching', 'a', '--not-matching', 'a',
        '--min-len', '1', '--max-len', '1',
    ])
    assert result.exit_code == 0
    assert 'No available samples' in result.stdout


def test_cli_derive_match():
    result = runner.invoke(
        app,
        ['brzozowski', 'derive', '--matching', 'abc'],
        input='abc\n\n',
    )
    assert result.exit_code == 0
    assert 'MATCH' in result.stdout


def test_cli_derive_dead_marks_position():
    result = runner.invoke(
        app,
        ['brzozowski', 'derive', '--matching', 'abc'],
        input='abx\n',
    )
    assert result.exit_code == 0
    assert 'DEAD' in result.stdout
    assert 'pos 2' in result.stdout


def test_cli_show_intersection():
    result = runner.invoke(app, [
        'brzozowski', 'show',
        '--matching', '[a-z]+', '--matching', '.*z.*',
    ])
    assert result.exit_code == 0
    out = result.stdout.strip()
    assert '&' in out
    assert 'z' in out


def test_cli_show_negation():
    result = runner.invoke(app, [
        'brzozowski', 'show', '--not-matching', 'abc',
    ])
    assert result.exit_code == 0
    assert '~' in result.stdout


def test_cli_show_debug():
    result = runner.invoke(app, ['brzozowski', 'show', '--matching', 'abc', '--debug'])
    assert result.exit_code == 0
    assert 'ReCat' in result.stdout or 'OneOf' in result.stdout


def test_cli_derive_debug_shows_ast():
    result = runner.invoke(
        app,
        ['brzozowski', 'derive', '--matching', 'a', '--debug'],
        input='\n',
    )
    assert result.exit_code == 0
    assert 'OneOf' in result.stdout
