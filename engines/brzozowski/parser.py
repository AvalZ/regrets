import sre_constants
import sre_parse

from engines.brzozowski.re_ast import (
    Re, OneOf, CharClass, EPS, ALL_GOOD, LookBehind,
    mk_cat, mk_or, mk_kleene, mk_and, mk_not,
)


_DIGIT = frozenset(chr(c) for c in range(ord('0'), ord('9') + 1))
_WORD = (
    frozenset(chr(c) for c in range(ord('a'), ord('z') + 1))
    | frozenset(chr(c) for c in range(ord('A'), ord('Z') + 1))
    | _DIGIT
    | frozenset({'_'})
)
_SPACE = frozenset({' ', '\t', '\n', '\r', '\f', '\v'})


def _category(node_value) -> Re:
    sc = sre_constants
    if node_value == sc.CATEGORY_DIGIT:
        return OneOf(CharClass(_DIGIT, negated=False))
    if node_value == sc.CATEGORY_NOT_DIGIT:
        return OneOf(CharClass(_DIGIT, negated=True))
    if node_value == sc.CATEGORY_SPACE:
        return OneOf(CharClass(_SPACE, negated=False))
    if node_value == sc.CATEGORY_NOT_SPACE:
        return OneOf(CharClass(_SPACE, negated=True))
    if node_value == sc.CATEGORY_WORD:
        return OneOf(CharClass(_WORD, negated=False))
    if node_value == sc.CATEGORY_NOT_WORD:
        return OneOf(CharClass(_WORD, negated=True))
    raise NotImplementedError(f'category {node_value} not implemented')


def _collect_in_chars(items) -> frozenset:
    out = set()
    for node in items:
        node_type, node_value = node
        if node_type == sre_constants.LITERAL:
            out.add(chr(node_value))
        elif node_type == sre_constants.RANGE:
            low, high = node_value
            out.update(chr(c) for c in range(low, high + 1))
        elif node_type == sre_constants.CATEGORY:
            cc = _category(node_value).cc
            if cc.negated:
                raise NotImplementedError('negated category inside [...] not supported')
            out.update(cc.chars)
        else:
            raise NotImplementedError(f'unsupported [...] item: {node}')
    return frozenset(out)


def _construct_to_re(node) -> Re:
    sc = sre_constants
    node_type, node_value = node
    if node_type == sc.LITERAL:
        return OneOf(CharClass(frozenset({chr(node_value)}), negated=False))
    if node_type == sc.NOT_LITERAL:
        return OneOf(CharClass(frozenset({chr(node_value)}), negated=True))
    if node_type == sc.SUBPATTERN:
        _, _, _, value = node_value
        return regex_to_re(value)
    if node_type == sc.ANY:
        return OneOf(CharClass(frozenset(), negated=True))
    if node_type == sc.MAX_REPEAT:
        low, high, value = node_value
        inner = regex_to_re(value)
        if (low, high) == (0, sc.MAXREPEAT):
            return mk_kleene(inner)
        if (low, high) == (1, sc.MAXREPEAT):
            return mk_cat([inner, mk_kleene(inner)])
        if (low, high) == (0, 1):
            return mk_or([EPS, inner])
        if high == sc.MAXREPEAT:
            return mk_cat([inner] * low + [mk_kleene(inner)])
        required = [inner] * low
        optional = [mk_or([EPS, inner])] * (high - low)
        return mk_cat(required + optional)
    if node_type == sc.IN:
        # \d/\D/\w/\W/\s/\S parse as IN containing a single CATEGORY — preserve its negation.
        if len(node_value) == 1 and node_value[0][0] == sc.CATEGORY:
            return _category(node_value[0][1])
        first_subnode_type, _ = node_value[0]
        if first_subnode_type == sc.NEGATE:
            chars = _collect_in_chars(node_value[1:])
            return OneOf(CharClass(chars, negated=True))
        chars = _collect_in_chars(node_value)
        return OneOf(CharClass(chars, negated=False))
    if node_type == sc.BRANCH:
        _, value = node_value
        return mk_or([regex_to_re(v) for v in value])
    if node_type == sc.RANGE:
        low, high = node_value
        return OneOf(CharClass(frozenset(chr(c) for c in range(low, high + 1)), negated=False))
    if node_type == sc.CATEGORY:
        return _category(node_value)
    raise NotImplementedError(f'regex construct {node} not implemented')


_WORD_CLASS = CharClass(_WORD, negated=False)


def _boundary(suffix: Re, negated: bool) -> Re:
    """Encode \\b (negated=False) or \\B (negated=True) at a position whose remaining regex is `suffix`.
    \\b = (?<=\\w)(?!\\w) | (?=\\w)(?<!\\w). Each alternative has a fixed-width LookBehind plus a
    suffix-shape constraint: "suffix starts with \\w" is `\\w·.*`; its negation handles end-of-input."""
    word_prefix = mk_cat([OneOf(_WORD_CLASS), ALL_GOOD])
    starts_word = mk_and([suffix, word_prefix])
    starts_non_word = mk_and([suffix, mk_not(word_prefix)])
    alt_after_word = mk_cat([LookBehind(_WORD_CLASS, negated=False), starts_non_word])
    alt_before_word = mk_cat([LookBehind(_WORD_CLASS, negated=True), starts_word])
    if negated:
        # \B: either both sides word, or both sides non-word.
        alt_in_word = mk_cat([LookBehind(_WORD_CLASS, negated=False), starts_word])
        alt_between_non = mk_cat([LookBehind(_WORD_CLASS, negated=True), starts_non_word])
        return mk_or([alt_in_word, alt_between_non])
    return mk_or([alt_after_word, alt_before_word])


def regex_to_re(parsed: sre_parse.SubPattern) -> Re:
    if not parsed.data:
        raise ValueError('regex is empty')
    return _build_seq(list(parsed.data))


def _build_seq(items) -> Re:
    sc = sre_constants
    prefix = []
    i = 0
    while i < len(items):
        node_type, node_value = items[i]
        if node_type == sc.AT:
            if node_value == sc.AT_BOUNDARY or node_value == sc.AT_NON_BOUNDARY:
                suffix = _build_seq(items[i + 1:])
                prefix.append(_boundary(suffix, negated=(node_value == sc.AT_NON_BOUNDARY)))
                return prefix[0] if len(prefix) == 1 else mk_cat(prefix)
            raise NotImplementedError(f'regex anchor {node_value} not implemented')
        if node_type in (sc.ASSERT, sc.ASSERT_NOT):
            lookahead_constraints = []
            while i < len(items) and items[i][0] in (sc.ASSERT, sc.ASSERT_NOT):
                a_type, (direction, sub) = items[i]
                body = regex_to_re(sub)
                if direction == 1:
                    lookahead_constraints.append(mk_not(body) if a_type == sc.ASSERT_NOT else body)
                elif direction == -1:
                    if not isinstance(body, OneOf):
                        raise NotImplementedError('variable-width lookbehind not supported')
                    prefix.append(LookBehind(body.cc, negated=(a_type == sc.ASSERT_NOT)))
                else:
                    raise NotImplementedError(f'assertion direction {direction}')
                i += 1
            if lookahead_constraints:
                suffix = _build_seq(items[i:])
                constrained = mk_and([suffix] + lookahead_constraints)
                prefix.append(constrained)
                return prefix[0] if len(prefix) == 1 else mk_cat(prefix)
            continue
        prefix.append(_construct_to_re(items[i]))
        i += 1
    if not prefix:
        return EPS
    return prefix[0] if len(prefix) == 1 else mk_cat(prefix)


def parse(pattern: str) -> Re:
    return regex_to_re(sre_parse.parse(pattern))
