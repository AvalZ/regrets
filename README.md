# Regrets

Use Z3 or Brzozowski derivatives to generate strings that match multiple regex — and to intersect, complement, and flatten them into a single regex.

> The plural of `regex` is `regrets`

![To generate #1 albums, 'jay --help' recommends the -z flag.](https://imgs.xkcd.com/comics/perl_problems.png)

**WARNING**: `regrets` is still in development! If you have any feedback or suggestions to improve it, [let me know](https://github.com/AvalZ/regrets/discussions/new?category=feedback)!

## Setup

 - Clone this repository
 - Install [Poetry](https://python-poetry.org/docs/#installation)
 - Run `poetry install`
 - Invoke via `poetry run regrets` (or `poetry run python main.py`)

## Engines

`regrets` ships two engines under separate subcommands:

| Engine | Subcommand | Strengths |
|--------|------------|-----------|
| Z3 | `z3` | SMT-based; supports partial matching |
| Brzozowski derivatives | `brzozowski` | Fast; exposes DFA, state-elimination, and step-through derivation |

Top-level help:

```
$ python main.py --help
$ python main.py z3 --help
$ python main.py brzozowski --help
```

## Z3 engine

Generate strings matching one or more regex (intersected):

```
$ python main.py z3 generate --matching "[A-Za-z0-9]{3,10}"
AnP
```

Multiple constraints:

```
$ python main.py z3 generate --matching "[A-Za-z0-9]{3,10}" --matching "abcd[0-9]+"
abcd4
```

Negative constraints (full and partial):

```
$ python main.py z3 generate \
    --matching "[A-Za-z0-9]{3,10}" \
    --matching "abcd[0-9]+" \
    --not-matching "[a-z]{4}[1-4]"
abcd6

$ python main.py z3 generate --matching "[A-Za-z0-9]{3,10}" --not-partial-matching "[a-z]"
0KX
```

## Brzozowski engine

Four commands on top of a shared Brzozowski-derivative core:

### `generate` — sample matching strings

```
$ python main.py brzozowski generate --matching "[a-z]+z.*" -N 3 --max-len 4
az
bz
cz
```

### `show` — flatten intersections and complements into a single regex

Uses derivative-based DFA construction, then state elimination. The `&` / `~` meta-operators disappear — output is a plain regex.

```
$ python main.py brzozowski show --matching "[a-z]+" --matching ".*z.*"
(z|[a-y]+z)([a-z]*)

$ python main.py brzozowski show --matching "[a-c]{3}" --not-matching "abc"
ab[ab]|(a[ac]|[bc][a-c])[a-c]
```

### `dfa` — inspect the derivative DFA

```
$ python main.py brzozowski dfa --matching "abc"
States (4):
  0 [start]: abc
  1: bc
  2: c
  3 [accept]: ε
Transitions:
  0 --a--> 1
  1 --b--> 2
  2 --c--> 3
```

### `derive` — step through the derivative interactively

Type characters; see the residual regex and match status after each step. Empty line evaluates fullmatch on input so far.

```
$ python main.py brzozowski derive --matching "abc"
start [partial]: abc
> ab
  'a' [partial]: bc
  'b' [partial]: c
ab> c
  'c' [MATCH]: ε
abc>
  ε [MATCH]: ε
  (empty line again to exit)
```

### PCRE constructs

The Brzozowski parser accepts a useful subset of PCRE:

| Construct | Semantics |
|-----------|-----------|
| `(?=X)` | Positional intersection: suffix matches `X` (and the rest of the regex) |
| `(?!X)` | Positional complement: suffix does NOT match `X` |
| `(?<=x)` / `(?<!x)` | Fixed-width-1 lookbehind (single char or character class only) |
| `\b` / `\B` | Word / non-word boundary (expanded to dual lookaround alternation) |

Lookaheads are sugar for AND / NOT on the suffix consumed by the rest of the regex. Example — `show` flattens them into a plain regex:

```
$ python main.py brzozowski show --matching "(?=[a-z]+)(?=.*z.*).{1,4}"
z|[a-y]{3}z|[a-y]{2}z|[a-y]z|z[a-z]|...

$ python main.py brzozowski show --matching "\bword\b"
word
```

Variable-width lookbehinds raise `NotImplementedError` — on the todo list.

### Reading patterns from a file

Every brzozowski command accepts `--matching-file` / `--not-matching-file`. One regex per line, `#` comments and blank lines skipped:

```
$ cat patterns.txt
# must be lowercase
[a-z].*
# must contain a digit
.*\d.*

$ python main.py brzozowski generate --matching-file patterns.txt -N 3 --min-len 2 --max-len 4
a0
a1
a2
```

## Current Limitations

 - The Brzozowski engine supports lookaheads, fixed-width-1 lookbehinds, and word boundaries (`\b` / `\B`); variable-width lookbehinds and backreferences are not supported.
 - The Z3 parser (credits to [Andrew Helwer](https://ahelwer.ca/post/2022-01-19-z3-rbac/)) does not support all regex constructs (e.g., lazy quantifiers `*?`, `+?`, `??`). PRs welcome.
 - Z3 can be very slow on complex regex. Be patient.
 - Deterministic output: repeated Z3 runs with the same parameters yield the same samples. Bump `-N` for more variety. The Brzozowski generator performs BFS over the derivative graph and deduplicates by path.

## How to Contribute

PRs for missing features and overcoming limitations are always welcome!

Any [feedback](https://github.com/AvalZ/regrets/discussions/new?category=feedback) on usability or performance is appreciated.

If you're using `regrets` in your projects, [let me know your use case](https://github.com/AvalZ/regrets/discussions/new?category=show-and-tell)!
