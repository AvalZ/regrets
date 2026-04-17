from typing import Dict, FrozenSet, List, Optional, Set

from .re_ast import Re, NO_GOOD, OneOf, nullable, derive
from .dfa import chars_to_re, dfa_to_regex, PRINTABLE
from .pretty import pretty


def parse_char_class(s: str, alphabet: FrozenSet[str]) -> FrozenSet[str]:
    from .parser import parse
    re = parse(s)
    if isinstance(re, OneOf):
        cc = re.cc
        if cc.negated:
            return frozenset(alphabet) - frozenset(cc.chars)
        return frozenset(cc.chars) & frozenset(alphabet)
    raise ValueError(f"expected a char or char class, got {s!r}")


def _dot_escape(s: str) -> str:
    return s.replace('\\', '\\\\').replace('"', '\\"')


class DfaBuilder:
    def __init__(self, root_re: Re, alphabet: FrozenSet[str] = PRINTABLE):
        self.alphabet: FrozenSet[str] = alphabet
        self.states: List[Re] = [root_re]
        self.index: Dict[Re, int] = {root_re: 0}
        self.transitions: Dict[int, Dict[int, FrozenSet[str]]] = {}
        self.accepts: Set[int] = {0} if nullable(root_re) else set()
        self.frontier: Set[int] = {0}
        self.depth: Dict[int, int] = {0: 0}
        self.explored: Dict[int, Set[str]] = {0: set()}

    def _intern(self, re: Re, parent_depth: int) -> int:
        if re in self.index:
            return self.index[re]
        sid = len(self.states)
        self.states.append(re)
        self.index[re] = sid
        if nullable(re):
            self.accepts.add(sid)
        self.frontier.add(sid)
        self.depth[sid] = parent_depth + 1
        self.explored[sid] = set()
        return sid

    def expand_state(self, sid: int, chars: Optional[FrozenSet[str]] = None) -> List[int]:
        if sid not in self.frontier:
            return []
        src_re = self.states[sid]
        src_explored = self.explored[sid]
        if chars is None:
            to_explore = self.alphabet - src_explored
        else:
            to_explore = (chars & self.alphabet) - src_explored
        if not to_explore:
            return []

        groups: Dict[Re, Set[str]] = {}
        for c in to_explore:
            d = derive(c, src_re)
            if d == NO_GOOD:
                continue
            groups.setdefault(d, set()).add(c)

        new_ids: List[int] = []
        for target, cset in groups.items():
            was_new = target not in self.index
            dst = self._intern(target, self.depth[sid])
            if was_new:
                new_ids.append(dst)
            prev = self.transitions.setdefault(sid, {}).get(dst, frozenset())
            self.transitions[sid][dst] = prev | frozenset(cset)

        src_explored |= to_explore
        if src_explored >= self.alphabet:
            self.frontier.discard(sid)
        return new_ids

    def expand_bfs(self, levels: int = 1) -> List[int]:
        all_new: List[int] = []
        for _ in range(levels):
            snapshot = list(self.frontier)
            if not snapshot:
                break
            for sid in snapshot:
                all_new.extend(self.expand_state(sid, None))
        return all_new

    def show_merged(self) -> Re:
        return dfa_to_regex(self.states, self.transitions, self.accepts, 0)

    def show_merged_pretty(self) -> str:
        return pretty(self.show_merged())

    def expand_state_str(self, sid: int, chars_str: Optional[str]) -> List[int]:
        if not chars_str:
            return self.expand_state(sid, None)
        chars = parse_char_class(chars_str, self.alphabet)
        return self.expand_state(sid, chars)

    def info(self) -> dict:
        return {
            'n_states': len(self.states),
            'n_frontier': len(self.frontier),
            'n_accepts': len(self.accepts),
            'max_depth': max(self.depth.values()) if self.depth else 0,
        }

    def frontier_list(self) -> List[dict]:
        out = []
        for sid in sorted(self.frontier):
            unexplored = self.alphabet - self.explored.get(sid, set())
            out.append({
                'id': sid,
                'pretty': pretty(self.states[sid]),
                'depth': self.depth[sid],
                'n_unexplored': len(unexplored),
                'accept': sid in self.accepts,
            })
        return out

    def state_summary(self, sid: int) -> dict:
        return {
            'id': sid,
            'pretty': pretty(self.states[sid]),
            'depth': self.depth.get(sid, 0),
            'accept': sid in self.accepts,
            'frontier': sid in self.frontier,
            'n_unexplored': len(self.alphabet - self.explored.get(sid, set())),
        }

    def to_dot(self, compress: bool = True) -> str:
        n = len(self.states)
        out_succ = {i: list(self.transitions.get(i, {}).keys()) for i in range(n)}
        in_pred: Dict[int, List[int]] = {i: [] for i in range(n)}
        for src in range(n):
            for dst in out_succ[src]:
                in_pred[dst].append(src)

        def is_interior(i: int) -> bool:
            if i == 0 or i in self.accepts or i in self.frontier:
                return False
            if len(out_succ[i]) != 1 or len(in_pred[i]) != 1:
                return False
            if out_succ[i][0] == i or in_pred[i][0] == i:
                return False
            return True

        interior: Set[int] = {i for i in range(n) if is_interior(i)} if compress else set()

        def edge_label(src: int, dst: int) -> str:
            return pretty(chars_to_re(self.transitions[src][dst], self.alphabet))

        lines = [
            'digraph DFA {',
            '  rankdir=LR;',
            '  bgcolor="transparent";',
            '  node [fontname="Helvetica", fontsize=12];',
            '  edge [fontname="Helvetica", fontsize=11];',
            '  __start [shape=point, width=0.1, color="#888"];',
        ]

        edges = []
        visited_edges: Set = set()
        for src in range(n):
            if src in interior:
                continue
            for dst in out_succ[src]:
                if (src, dst) in visited_edges:
                    continue
                visited_edges.add((src, dst))
                labels = [edge_label(src, dst)]
                cur = dst
                while cur in interior:
                    nxt = out_succ[cur][0]
                    labels.append(edge_label(cur, nxt))
                    visited_edges.add((cur, nxt))
                    cur = nxt
                edges.append((src, cur, labels))

        kept = [i for i in range(n) if i not in interior]
        for i in kept:
            shape = 'doublecircle' if i in self.accepts else 'circle'
            attrs = [f'shape={shape}', f'label="{i}"', f'tooltip="{_dot_escape(pretty(self.states[i]))}"']
            if i in self.frontier:
                attrs.append('style=dashed')
                attrs.append('color="#888"')
            lines.append(f'  {i} [{", ".join(attrs)}];')
        lines.append('  __start -> 0;')
        for src, dst, labels in edges:
            body = _dot_escape(' · '.join(labels)) if len(labels) > 1 else _dot_escape(labels[0])
            lines.append(f'  {src} -> {dst} [label="{body}"];')
        for sid in sorted(self.frontier):
            rest = _dot_escape(pretty(self.states[sid]))
            pseudo = f'frontier_rest_{sid}'
            lines.append(f'  {pseudo} [shape=none, label="", width=0.01, height=0.01];')
            lines.append(
                f'  {sid} -> {pseudo} [label="{rest}", style=dashed, '
                f'arrowhead=open, color="#888", fontcolor="#888"];'
            )
        lines.append('}')
        return '\n'.join(lines)
