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
    """BFS over the derivative graph; yield up to n distinct accepting strings."""
    if re == NO_GOOD:
        return
    yielded = 0
    seen = set()
    # Cap visits per (state, depth) at n: keeps the frontier bounded but lets paths
    # of any length flow through repeated states (e.g. .* / ALL_GOOD).
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
        for c in alphabet:
            nxt = derive(c, cur)
            if nxt == NO_GOOD:
                continue
            key = (nxt, len(path) + 1)
            cnt = visit_count.get(key, 0)
            if cnt >= n:
                continue
            visit_count[key] = cnt + 1
            frontier.append((nxt, path + c))
