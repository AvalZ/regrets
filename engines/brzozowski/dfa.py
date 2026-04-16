from collections import OrderedDict
from typing import Dict, FrozenSet, List, Set, Tuple

from engines.brzozowski.re_ast import (
    Re, OneOf, CharClass, EPS, NO_GOOD,
    nullable, derive, mk_cat, mk_or, mk_kleene,
)


PRINTABLE: FrozenSet[str] = frozenset(chr(c) for c in range(32, 128))
MAX_STATES = 1000


def chars_to_re(chars: FrozenSet[str], alphabet: FrozenSet[str]) -> Re:
    if chars == alphabet:
        return OneOf(CharClass(frozenset(), negated=True))  # "."
    complement = alphabet - chars
    if len(complement) < len(chars):
        return OneOf(CharClass(frozenset(complement), negated=True))
    return OneOf(CharClass(frozenset(chars), negated=False))


def build_dfa(start: Re, alphabet: FrozenSet[str] = PRINTABLE):
    """Minimal DFA via Brzozowski derivatives. Transitions carry char classes.

    Returns (states, transitions, accepts, start_id) where
      states: List[Re]
      transitions: Dict[src_id, Dict[dst_id, frozenset]]
      accepts: Set[int]
      start_id: int
    """
    alpha_sorted = sorted(alphabet)
    states: List[Re] = [start]
    index = {start: 0}
    transitions: Dict[int, Dict[int, FrozenSet[str]]] = {}
    queue = [0]
    while queue:
        i = queue.pop(0)
        s = states[i]
        groups: Dict[Re, Set[str]] = {}
        for c in alpha_sorted:
            d = derive(c, s)
            if d == NO_GOOD:
                continue
            groups.setdefault(d, set()).add(c)
        for target, chars in groups.items():
            if target not in index:
                if len(states) >= MAX_STATES:
                    raise RuntimeError(f"DFA exceeded {MAX_STATES} states — pattern too complex")
                index[target] = len(states)
                states.append(target)
                queue.append(index[target])
            transitions.setdefault(i, {})[index[target]] = frozenset(chars)
    accepts = {i for i, s in enumerate(states) if nullable(s)}
    return states, transitions, accepts, 0


def dfa_to_regex(
    states: List[Re],
    transitions: Dict[int, Dict[int, FrozenSet[str]]],
    accepts: Set[int],
    start_id: int,
    alphabet: FrozenSet[str] = PRINTABLE,
) -> Re:
    """State-elimination: collapse the DFA into a single regex."""
    n = len(states)
    if n == 0 or not accepts:
        return NO_GOOD
    labels: Dict[int, Dict[int, Re]] = {}
    for src, outs in transitions.items():
        for dst, chars in outs.items():
            labels.setdefault(src, {})[dst] = chars_to_re(chars, alphabet)
    START = n
    FINAL = n + 1
    labels.setdefault(START, {})[start_id] = EPS
    for a in accepts:
        labels.setdefault(a, {})[FINAL] = EPS
    for s in range(n):
        self_out = labels.get(s, {})
        self_loop = self_out.pop(s, None)
        star = mk_kleene(self_loop) if self_loop is not None else EPS
        predecessors = [p for p, outs in labels.items() if s in outs and p != s]
        successors = list(self_out.keys())
        for p in predecessors:
            r_ps = labels[p].pop(s)
            for q in successors:
                r_sq = self_out[q]
                parts = [r_ps]
                if self_loop is not None:
                    parts.append(star)
                parts.append(r_sq)
                new_edge = mk_cat(parts)
                existing = labels.get(p, {}).get(q)
                combined = mk_or([existing, new_edge]) if existing is not None else new_edge
                labels.setdefault(p, {})[q] = combined
        labels.pop(s, None)
    return labels.get(START, {}).get(FINAL, NO_GOOD)
