from typing import List, Tuple

from .re_ast import Re, NO_GOOD, nullable, derive
from .pretty import pretty


def _tag(re: Re) -> str:
    if re == NO_GOOD:
        return 'DEAD'
    return 'MATCH' if nullable(re) else 'partial'


def _final_tag(re: Re) -> str:
    return 'MATCH' if nullable(re) else 'DEAD'


class DeriveSession:
    """Linear step-by-step derivation with optional undo/redo.

    History entries are (char, prev_re, prev_dead) tuples.  step() pushes onto
    _undo and clears _redo (branching semantics).  back() pops _undo to _redo;
    forward() pops _redo to _undo.  Stepping while dead is a no-op so that
    history stays in sync with `consumed`."""

    def __init__(self, re: Re):
        self._initial: Re = re
        self.re: Re = re
        self.consumed: str = ''
        self.dead: bool = False
        self._undo: List[Tuple[str, Re, bool]] = []
        self._redo: List[Tuple[str, Re, bool]] = []

    def snapshot(self) -> dict:
        return {
            'consumed': self.consumed,
            'pretty': pretty(self.re),
            'tag': _tag(self.re),
            'dead': self.dead,
            'can_back': bool(self._undo),
            'can_forward': bool(self._redo),
        }

    def step(self, c: str) -> dict:
        if self.dead:
            return {
                'char': c, 'pretty': pretty(self.re), 'tag': 'DEAD', 'dead': True,
                'can_back': bool(self._undo), 'can_forward': False,
            }
        self._undo.append((c, self.re, self.dead))
        self._redo.clear()
        self.re = derive(c, self.re)
        self.consumed += c
        if self.re == NO_GOOD:
            self.dead = True
            return {'char': c, 'pretty': '∅', 'tag': 'DEAD', 'dead': True,
                    'can_back': True, 'can_forward': False}
        return {'char': c, 'pretty': pretty(self.re), 'tag': _tag(self.re), 'dead': False,
                'can_back': True, 'can_forward': False}

    def back(self) -> bool:
        if not self._undo:
            return False
        c, prev_re, prev_dead = self._undo.pop()
        self._redo.append((c, self.re, self.dead))
        self.re = prev_re
        self.dead = prev_dead
        self.consumed = self.consumed[:-1]
        return True

    def forward(self) -> bool:
        if not self._redo:
            return False
        c, next_re, next_dead = self._redo.pop()
        self._undo.append((c, self.re, self.dead))
        self.re = next_re
        self.dead = next_dead
        self.consumed += c
        return True

    def reset(self) -> None:
        self.re = self._initial
        self.consumed = ''
        self.dead = False
        self._undo.clear()
        self._redo.clear()

    def eof(self) -> dict:
        return {'pretty': pretty(self.re), 'tag': _final_tag(self.re)}
