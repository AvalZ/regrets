import re
import sre_parse

import pytest
import z3

from engines.z3.parser import regex_to_z3_expr


def compile_to_z3(pattern: str) -> z3.ReRef:
    return regex_to_z3_expr(sre_parse.parse(pattern))


def matches(pattern: str, sample: str) -> bool:
    s = z3.String('s')
    solver = z3.Solver()
    solver.add(s == z3.StringVal(sample))
    solver.add(z3.InRe(s, compile_to_z3(pattern)))
    return solver.check() == z3.sat


@pytest.mark.parametrize("pattern,sample,expected", [
    # Literals
    ("a", "a", True),
    ("a", "b", False),
    ("abc", "abc", True),
    ("abc", "ab", False),
    # Alternation
    ("a|b", "a", True),
    ("a|b", "b", True),
    ("a|b", "c", False),
    # Quantifiers
    ("a*", "", True),
    ("a*", "aaaa", True),
    ("a+", "", False),
    ("a+", "a", True),
    ("a?", "", True),
    ("a?", "a", True),
    ("a?", "aa", False),
    ("a{2,3}", "a", False),
    ("a{2,3}", "aa", True),
    ("a{2,3}", "aaa", True),
    ("a{2,3}", "aaaa", False),
    # Any char
    (".", "x", True),
    (".", "", False),
    # Char classes
    ("[abc]", "a", True),
    ("[abc]", "d", False),
    ("[^abc]", "d", True),
    ("[^abc]", "a", False),
    ("[a-z]", "m", True),
    ("[a-z]", "M", False),
    # Categories
    (r"\d", "5", True),
    (r"\d", "a", False),
    (r"\D", "a", True),
    (r"\D", "5", False),
    (r"\w", "_", True),
    (r"\w", "-", False),
    (r"\W", "-", True),
    (r"\s", " ", True),
    (r"\s", "x", False),
    # Concat + groups
    ("(ab)+", "abab", True),
    ("(ab)+", "aba", False),
    # Negated literal
    ("[^a]", "b", True),
    ("[^a]", "a", False),
])
def test_pattern(pattern, sample, expected):
    # Cross-check that Python regex agrees (sanity of the test data itself).
    assert bool(re.fullmatch(pattern, sample)) == expected
    assert matches(pattern, sample) == expected


def test_empty_regex_raises():
    with pytest.raises(ValueError):
        regex_to_z3_expr(sre_parse.parse(""))


@pytest.mark.parametrize("pattern", ["^a", "a$", r"\ba", r"\Ba"])
def test_unsupported_anchors(pattern):
    with pytest.raises(NotImplementedError):
        compile_to_z3(pattern)
