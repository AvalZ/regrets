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


@pytest.mark.parametrize("pattern", ["^a", "a$"])
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


def test_mk_not_all_good_collapses_to_no_good():
    # ~.* accepts no string at all (including ε), so it must collapse to NO_GOOD.
    assert mk_not(ALL_GOOD) == NO_GOOD
    # And via parse of a pattern semantically equivalent to .*
    assert mk_not(parse(".*")) == NO_GOOD


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


def test_pretty_multi_alt_with_eps_collapses_to_optional():
    from engines.brzozowski.re_ast import ReOr, EPS as _EPS
    re = ReOr((_EPS, parse("a"), parse("b"), parse("c")))
    assert pretty(re) == "(a|b|c)?"


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


def test_cli_derive_empty_line_on_non_nullable_is_dead():
    # Anchored fullmatch: hitting Enter on a partial state == empty input → DEAD.
    result = runner.invoke(
        app,
        ['brzozowski', 'derive', '--matching', 'abc'],
        input='a\n\n',
    )
    assert result.exit_code == 0
    assert 'ε [DEAD]' in result.stdout
    assert 'partial' in result.stdout  # the 'a' step still shows partial


def test_cli_derive_empty_line_on_nullable_is_match():
    result = runner.invoke(
        app,
        ['brzozowski', 'derive', '--matching', 'abc'],
        input='abc\n\n',
    )
    assert result.exit_code == 0
    assert 'ε [MATCH]' in result.stdout


def test_cli_derive_prompt_prefix_shows_consumed():
    result = runner.invoke(
        app,
        ['brzozowski', 'derive', '--matching', 'abc'],
        input='ab\nc\n\n',
    )
    assert result.exit_code == 0
    assert 'ab>' in result.stdout
    assert 'abc>' in result.stdout


def test_cli_derive_pending_exit_requires_two_empties():
    # First empty: prints hint. Second empty: exits.
    result = runner.invoke(
        app,
        ['brzozowski', 'derive', '--matching', 'abc'],
        input='\n\n',
    )
    assert result.exit_code == 0
    assert '(empty line again to exit)' in result.stdout


def test_cli_show_resolves_to_dfa_regex():
    # DFA resolution should flatten [a-z]+ ∧ .*z.* to a single regex with a z in it.
    result = runner.invoke(app, [
        'brzozowski', 'show',
        '--matching', '[a-z]+', '--matching', '.*z.*',
    ])
    assert result.exit_code == 0
    out = result.stdout.strip()
    assert 'z' in out
    # State-elimination drops the & / ~ meta operators (everything is literal regex now).
    assert '&' not in out
    assert '~' not in out


def test_cli_show_negation_expanded():
    result = runner.invoke(app, ['brzozowski', 'show', '--not-matching', 'abc'])
    assert result.exit_code == 0
    out = result.stdout.strip()
    assert '~' not in out  # elimination turns ~abc into an explicit alternation


def test_cli_show_trivial_passthrough():
    result = runner.invoke(app, ['brzozowski', 'show', '--matching', 'abc'])
    assert result.exit_code == 0
    assert result.stdout.strip() == 'abc'


def test_cli_show_debug():
    result = runner.invoke(app, ['brzozowski', 'show', '--matching', 'abc', '--debug'])
    assert result.exit_code == 0
    assert 'ReCat' in result.stdout or 'OneOf' in result.stdout


def test_cli_dfa_prints_states_and_transitions():
    result = runner.invoke(app, ['brzozowski', 'dfa', '--matching', 'abc'])
    assert result.exit_code == 0
    assert 'States' in result.stdout
    assert 'Transitions' in result.stdout
    assert 'start' in result.stdout
    assert 'accept' in result.stdout
    assert '-->' in result.stdout


def test_dfa_to_regex_semantics_match_original():
    # Resolved regex should accept the same strings as the intersection.
    from engines.brzozowski.dfa import build_dfa, dfa_to_regex
    original = mk_and([parse(r"[a-c]{1,3}"), parse(r".*b.*")])
    resolved = dfa_to_regex(*build_dfa(original))
    for s in ['b', 'ab', 'bc', 'abc', 'bcb']:
        assert accepts(original, s) == accepts(resolved, s)
    for s in ['a', 'c', 'ac', '', 'aaa', 'ccc']:
        assert accepts(original, s) == accepts(resolved, s)


def test_lookahead_is_and_constraint():
    # (?=X) behaves like full-string AND with X.
    re = parse(r"(?=.*a.*)(?=.*b.*).*")
    assert accepts(re, "ab")
    assert accepts(re, "ba")
    assert accepts(re, "cab")
    assert not accepts(re, "a")
    assert not accepts(re, "b")
    assert not accepts(re, "")


def test_negative_lookahead_is_not_constraint():
    # (?!X) behaves like full-string NOT X, intersected with the surrounding regex.
    re = parse(r"(?!abc).{1,3}")
    assert accepts(re, "abd")
    assert accepts(re, "ab")
    assert not accepts(re, "abc")


def test_lookahead_equivalent_to_mk_and():
    a = parse(r"(?=[a-z]+)(?=.*z.*).{1,4}")
    b = mk_and([parse(r"[a-z]+"), parse(r".*z.*"), parse(r".{1,4}")])
    for s in ["z", "az", "zaz", "abcd", "Z", "", "aaaaa"]:
        assert accepts(a, s) == accepts(b, s)


def test_lookahead_is_positional():
    # Lookahead constrains the suffix consumed after its position.
    assert accepts(parse(r"a(?=.)b"), "ab")
    assert not accepts(parse(r"a(?=x)b"), "ab")  # suffix "b" must also match "x"
    assert accepts(parse(r"a(?!x)b"), "ab")      # suffix "b" must not match "x"
    assert not accepts(parse(r"a(?!b)b"), "ab")  # suffix "b" matches "b", negated fails


def test_variable_width_lookbehind_rejected():
    with pytest.raises(NotImplementedError):
        parse(r"(?<=ab)c")


def test_fixed_width_lookbehind():
    # (?<=a)b : prev char is 'a', then 'b'.
    assert accepts(parse(r"(?<=a)b"), "b") is False      # no prev char
    assert accepts(parse(r"a(?<=a)b"), "ab") is True
    assert accepts(parse(r"x(?<=a)b"), "xb") is False    # prev is 'x'
    # (?<!a)b : prev char is not 'a' (or no prev), then 'b'.
    assert accepts(parse(r"(?<!a)b"), "b") is True       # start-of-string passes negative LB
    assert accepts(parse(r"a(?<!a)b"), "ab") is False
    assert accepts(parse(r"x(?<!a)b"), "xb") is True


def test_word_boundary():
    # \b: matches at word/non-word transitions incl. string ends.
    re = parse(r"\bword\b")
    assert accepts(re, "word") is True
    assert not accepts(re, "wordx")
    assert not accepts(re, "xword")
    re2 = parse(r"\b\w+\b")
    assert accepts(re2, "hello")
    assert accepts(re2, "a")
    assert not accepts(re2, "")


@pytest.mark.parametrize("pattern", [
    r"\bword\b", r"\b\w+\b", r"foo\Bbar", r"(?<=a)b", r"(?<!a)b",
    r"\ba", r"a\b", r"\b\d+\b", r"(?<=[A-Z])[a-z]+",
])
def test_lookbehind_matches_python_re(pattern):
    strings = ['', 'word', 'wordx', 'xword', 'foobar', 'foo bar', 'ab', 'xb', 'a', 'Ab', 'Abcd', '123', 'a1', '1a', '_x']
    r = parse(pattern)
    for s in strings:
        assert accepts(r, s) == bool(pyre.fullmatch(pattern, s)), f"{pattern!r} on {s!r}"


def test_non_word_boundary():
    # \B matches between two \w or between two non-\w (never at string ends with mixed classes).
    re = parse(r"foo\Bbar")
    assert accepts(re, "foobar")  # 'o' and 'b' both \w → not a boundary → \B matches
    # \B at start-of-string adjacent to \w is NOT a match (start-to-\w is a boundary).
    assert not accepts(parse(r"\Bword"), "word")


def test_cli_show_flattens_lookahead():
    result = runner.invoke(app, [
        'brzozowski', 'show',
        '--matching', r'(?=[a-z]+)(?=.*z.*).{1,4}',
    ])
    assert result.exit_code == 0
    out = result.stdout.strip()
    assert 'z' in out
    assert '&' not in out
    assert '~' not in out
    assert '(?' not in out


def test_cli_derive_debug_shows_ast():
    result = runner.invoke(
        app,
        ['brzozowski', 'derive', '--matching', 'a', '--debug'],
        input='\n',
    )
    assert result.exit_code == 0
    assert 'OneOf' in result.stdout
