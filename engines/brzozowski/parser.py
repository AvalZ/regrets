import sre_constants
import sre_parse

from engines.brzozowski.re_ast import (
    Re, OneOf, CharClass, EPS,
    mk_cat, mk_or, mk_kleene,
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
    if node_type == sc.AT:
        raise NotImplementedError(f'regex anchor {node_value} not implemented')
    raise NotImplementedError(f'regex construct {node} not implemented')


def regex_to_re(parsed: sre_parse.SubPattern) -> Re:
    if not parsed.data:
        raise ValueError('regex is empty')
    if len(parsed.data) == 1:
        return _construct_to_re(parsed[0])
    return mk_cat([_construct_to_re(c) for c in parsed.data])


def parse(pattern: str) -> Re:
    return regex_to_re(sre_parse.parse(pattern))
