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


def derive(c: str, re: Re) -> Re:
    if isinstance(re, OneOf):
        return EPS if re.cc.contains(c) else NO_GOOD
    if isinstance(re, Kleene):
        return mk_cat([derive(c, re.r), re])
    if isinstance(re, ReCat):
        head = re.rs[0]
        tail = list(re.rs[1:])
        if nullable(head):
            return mk_or([
                mk_cat([derive(c, head)] + tail),
                derive(c, mk_cat(tail)),
            ])
        return mk_cat([derive(c, head)] + tail)
    if isinstance(re, ReAnd):
        return mk_and([derive(c, r) for r in re.rs])
    if isinstance(re, ReOr):
        return mk_or([derive(c, r) for r in re.rs])
    if isinstance(re, ReNot):
        return mk_not(derive(c, re.r))
    raise TypeError(re)


def accepts(re: Re, s: str) -> bool:
    for c in s:
        re = derive(c, re)
        if re == NO_GOOD:
            return False
    return nullable(re)
