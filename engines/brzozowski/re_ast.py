# Brzozowski-derivative regex engine.
# Ported from https://crypto.stanford.edu/~blynn/haskell/re.html

from dataclasses import dataclass
from typing import FrozenSet, Tuple


@dataclass(frozen=True)
class CharClass:
    chars: FrozenSet[str]
    negated: bool

    def contains(self, c: str) -> bool:
        return (c not in self.chars) if self.negated else (c in self.chars)


class Re:
    pass


@dataclass(frozen=True)
class OneOf(Re):
    cc: CharClass


@dataclass(frozen=True)
class Kleene(Re):
    r: Re


@dataclass(frozen=True)
class ReCat(Re):
    rs: Tuple[Re, ...]


@dataclass(frozen=True)
class ReOr(Re):
    rs: Tuple[Re, ...]


@dataclass(frozen=True)
class ReAnd(Re):
    rs: Tuple[Re, ...]


@dataclass(frozen=True)
class ReNot(Re):
    r: Re


# Fixed-width 1 lookbehind: predicate over the last consumed character.
# state ∈ {'start', 'in', 'out'}: 'start' = no char consumed yet; 'in' = last char ∈ cc; 'out' = last char ∉ cc.
# nullable iff (negated and state in {'start','out'}) or (not negated and state == 'in').
@dataclass(frozen=True)
class LookBehind(Re):
    cc: CharClass
    negated: bool
    state: str = 'start'


NO_GOOD: Re = OneOf(CharClass(frozenset(), negated=False))
ALL_GOOD: Re = Kleene(OneOf(CharClass(frozenset(), negated=True)))
EPS: Re = Kleene(NO_GOOD)


def nullable(re: Re) -> bool:
    if isinstance(re, OneOf):
        return False
    if isinstance(re, Kleene):
        return True
    if isinstance(re, ReCat):
        return all(nullable(r) for r in re.rs)
    if isinstance(re, ReOr):
        return any(nullable(r) for r in re.rs)
    if isinstance(re, ReAnd):
        return all(nullable(r) for r in re.rs)
    if isinstance(re, ReNot):
        return not nullable(re.r)
    if isinstance(re, LookBehind):
        if re.negated:
            return re.state in ('start', 'out')
        return re.state == 'in'
    raise TypeError(re)


def mk_cat(xs):
    flat = []
    for x in xs:
        if isinstance(x, ReCat):
            flat.extend(x.rs)
        else:
            flat.append(x)
    if NO_GOOD in flat:
        return NO_GOOD
    zs = [r for r in flat if r != EPS]
    if not zs:
        return EPS
    if len(zs) == 1:
        return zs[0]
    return ReCat(tuple(zs))


def mk_or(xs):
    flat = []
    for x in xs:
        if isinstance(x, ReOr):
            flat.extend(x.rs)
        else:
            flat.append(x)
    if ALL_GOOD in flat:
        return ALL_GOOD
    zs = sorted(set(r for r in flat if r != NO_GOOD), key=repr)
    if not zs:
        return NO_GOOD
    if len(zs) == 1:
        return zs[0]
    return ReOr(tuple(zs))


def mk_and(xs):
    flat = []
    for x in xs:
        if isinstance(x, ReAnd):
            flat.extend(x.rs)
        else:
            flat.append(x)
    if NO_GOOD in flat:
        return NO_GOOD
    zs = sorted(set(r for r in flat if r != ALL_GOOD), key=repr)
    if not zs:
        return ALL_GOOD
    if len(zs) == 1:
        return zs[0]
    return ReAnd(tuple(zs))


def mk_kleene(r: Re) -> Re:
    while isinstance(r, Kleene):
        r = r.r
    return Kleene(r)


def mk_not(r: Re) -> Re:
    if r == NO_GOOD:
        return ALL_GOOD
    if r == ALL_GOOD:
        return NO_GOOD
    if isinstance(r, ReNot):
        return r.r
    return ReNot(r)


def _advance_lbs(re: Re, c: str) -> Re:
    """Walk AST, updating every LookBehind.state to reflect that `c` was just consumed.
    LB state holds the class of the most recent char in the derivation path; every derive
    step advances all surviving LBs by one character."""
    if isinstance(re, LookBehind):
        new_state = 'in' if re.cc.contains(c) else 'out'
        if new_state == re.state:
            return re
        return LookBehind(re.cc, re.negated, new_state)
    if isinstance(re, OneOf):
        return re
    if isinstance(re, Kleene):
        inner = _advance_lbs(re.r, c)
        return re if inner is re.r else Kleene(inner)
    if isinstance(re, ReCat):
        new_rs = tuple(_advance_lbs(r, c) for r in re.rs)
        return re if all(a is b for a, b in zip(new_rs, re.rs)) else ReCat(new_rs)
    if isinstance(re, ReOr):
        new_rs = tuple(_advance_lbs(r, c) for r in re.rs)
        return re if all(a is b for a, b in zip(new_rs, re.rs)) else ReOr(new_rs)
    if isinstance(re, ReAnd):
        new_rs = tuple(_advance_lbs(r, c) for r in re.rs)
        return re if all(a is b for a, b in zip(new_rs, re.rs)) else ReAnd(new_rs)
    if isinstance(re, ReNot):
        inner = _advance_lbs(re.r, c)
        return re if inner is re.r else ReNot(inner)
    return re


def _derive_raw(c: str, re: Re) -> Re:
    if isinstance(re, OneOf):
        return EPS if re.cc.contains(c) else NO_GOOD
    if isinstance(re, LookBehind):
        # Zero-width: can't consume a character. When at cat head, ReCat handles it via nullability.
        return NO_GOOD
    if isinstance(re, Kleene):
        return mk_cat([_derive_raw(c, re.r), re])
    if isinstance(re, ReCat):
        head = re.rs[0]
        tail = list(re.rs[1:])
        if isinstance(head, LookBehind):
            if nullable(head):
                return _derive_raw(c, mk_cat(tail))
            return NO_GOOD
        if nullable(head):
            return mk_or([
                mk_cat([_derive_raw(c, head)] + tail),
                _derive_raw(c, mk_cat(tail)),
            ])
        return mk_cat([_derive_raw(c, head)] + tail)
    if isinstance(re, ReAnd):
        return mk_and([_derive_raw(c, r) for r in re.rs])
    if isinstance(re, ReOr):
        return mk_or([_derive_raw(c, r) for r in re.rs])
    if isinstance(re, ReNot):
        return mk_not(_derive_raw(c, re.r))
    raise TypeError(re)


def derive(c: str, re: Re) -> Re:
    # Raw derivative uses pre-advance LB states (reflecting the prefix BEFORE c). Post-pass
    # advances surviving LBs so that subsequent checks see `c` as the last-consumed char.
    return _advance_lbs(_derive_raw(c, re), c)


def accepts(re: Re, s: str) -> bool:
    for c in s:
        re = derive(c, re)
        if re == NO_GOOD:
            return False
    return nullable(re)
