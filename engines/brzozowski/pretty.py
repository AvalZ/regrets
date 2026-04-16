from engines.brzozowski.re_ast import (
    Re, OneOf, Kleene, ReCat, ReOr, ReAnd, ReNot, CharClass,
    EPS, NO_GOOD, ALL_GOOD,
)


# Precedence: higher binds tighter.
P_OR, P_AND, P_CAT, P_STAR, P_ATOM = 1, 2, 3, 4, 5


def pretty(re: Re) -> str:
    return _pretty(re, P_OR)


def _pretty(re: Re, ctx: int) -> str:
    if re == EPS:
        return 'ε'
    if re == NO_GOOD:
        return '∅'
    if re == ALL_GOOD:
        return '.*'
    if isinstance(re, OneOf):
        return _format_charclass(re.cc)
    if isinstance(re, Kleene):
        return _wrap(_pretty(re.r, P_ATOM) + '*', P_STAR, ctx)
    if isinstance(re, ReCat):
        return _wrap(_format_cat(re.rs), P_CAT, ctx)
    if isinstance(re, ReOr):
        # X? shortcut: ReOr([EPS, X]) — smart constructor sorts so EPS comes first.
        if len(re.rs) == 2 and re.rs[0] == EPS:
            return _wrap(_pretty(re.rs[1], P_ATOM) + '?', P_STAR, ctx)
        body = '|'.join(_pretty(r, P_OR) for r in re.rs)
        return _wrap(body, P_OR, ctx)
    if isinstance(re, ReAnd):
        body = '&'.join(_pretty(r, P_AND) for r in re.rs)
        return _wrap(body, P_AND, ctx)
    if isinstance(re, ReNot):
        return _wrap('~' + _pretty(re.r, P_ATOM), P_STAR, ctx)
    return repr(re)


def _format_cat(rs) -> str:
    """Collapse consecutive X, X?, Kleene(X) runs into {m}, {m,n}, +, *, ? shortcuts."""
    parts = []
    i = 0
    while i < len(rs):
        opt_inner = _unopt(rs[i])
        base = opt_inner if opt_inner is not None else rs[i]
        j = i
        required = 0
        while j < len(rs) and rs[j] == base:
            required += 1
            j += 1
        optional = 0
        while j < len(rs) and _unopt(rs[j]) == base:
            optional += 1
            j += 1
        has_star = False
        if optional == 0 and j < len(rs) and isinstance(rs[j], Kleene) and rs[j].r == base:
            has_star = True
            j += 1
        if required + optional == 0 and not has_star:
            parts.append(_pretty(rs[i], P_CAT))
            i += 1
            continue
        parts.append(_format_run(base, required, optional, has_star))
        i = j
    return ''.join(parts)


def _unopt(r: Re):
    """If r is X? (ReOr([EPS, X])), return X; else None."""
    if isinstance(r, ReOr) and len(r.rs) == 2 and r.rs[0] == EPS:
        return r.rs[1]
    return None


def _format_run(base: Re, required: int, optional: int, has_star: bool) -> str:
    atom = _pretty(base, P_ATOM)
    if has_star:
        if required == 0:
            return atom + '*'
        if required == 1:
            return atom + '+'
        return f'{atom}{{{required},}}'
    if optional == 0:
        if required == 1:
            return atom
        return f'{atom}{{{required}}}'
    if required == 0:
        if optional == 1:
            return atom + '?'
        return f'{atom}{{0,{optional}}}'
    return f'{atom}{{{required},{required + optional}}}'


def _wrap(s: str, prec: int, ctx: int) -> str:
    return f'({s})' if prec < ctx else s


def _format_charclass(cc: CharClass) -> str:
    if cc.negated and not cc.chars:
        return '.'
    if not cc.negated and len(cc.chars) == 1:
        return _escape_literal(next(iter(cc.chars)))
    body = _compact_ranges(sorted(cc.chars))
    return f'[{"^" if cc.negated else ""}{body}]'


def _escape_literal(c: str) -> str:
    if c in r'.^$*+?()[]{}|\\':
        return '\\' + c
    return c


def _escape_in(c: str) -> str:
    if c in r'\^]-':
        return '\\' + c
    return c


def _compact_ranges(chars):
    if not chars:
        return ''
    out = []
    start = prev = chars[0]
    for c in chars[1:]:
        if ord(c) == ord(prev) + 1:
            prev = c
            continue
        out.append(_emit_range(start, prev))
        start = prev = c
    out.append(_emit_range(start, prev))
    return ''.join(out)


def _emit_range(start: str, end: str) -> str:
    if start == end:
        return _escape_in(start)
    if ord(end) == ord(start) + 1:
        return _escape_in(start) + _escape_in(end)
    return f'{_escape_in(start)}-{_escape_in(end)}'
