from collections import deque
from typing import Iterator, Sequence

from engines.brzozowski.re_ast import Re, NO_GOOD, derive, nullable


PRINTABLE = [chr(c) for c in range(32, 128)]


def generate(
    re: Re,
    n: int = 1,
    min_len: int = 1,
    max_len: int = 100,
    alphabet: Sequence[str] = PRINTABLE,
) -> Iterator[str]:
    """BFS over the derivative graph; yield up to n distinct accepting strings.

    Groups the alphabet into derivative-equivalence classes per state, cached
    across BFS pops — so for a state revisited at many depths we only pay the
    96 `derive` calls once, not once per visit.
    """
    if re == NO_GOOD:
        return
    alpha = list(alphabet)
    trans_cache: dict = {}

    def transitions(state):
        cached = trans_cache.get(state)
        if cached is not None:
            return cached
        groups: dict = {}
        for c in alpha:
            d = derive(c, state)
            if d == NO_GOOD:
                continue
            groups.setdefault(d, []).append(c)
        out = list(groups.items())
        trans_cache[state] = out
        return out

    yielded = 0
    seen = set()
    visit_count = {(re, 0): 1}
    frontier = deque([(re, '')])
    while frontier and yielded < n:
        cur, path = frontier.popleft()
        if min_len <= len(path) <= max_len and nullable(cur) and path not in seen:
            seen.add(path)
            yield path
            yielded += 1
            if yielded >= n:
                return
        if len(path) >= max_len:
            continue
        for nxt, chars in transitions(cur):
            key = (nxt, len(path) + 1)
            cnt = visit_count.get(key, 0)
            if cnt >= n:
                continue
            remaining = n - cnt
            # Take up to `remaining` distinct representative chars from this class
            # so the surface output has variety without blowing up the frontier.
            take = chars if len(chars) <= remaining else chars[:remaining]
            for c in take:
                frontier.append((nxt, path + c))
            visit_count[key] = cnt + len(take)
