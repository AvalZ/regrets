# Regrets

Use Z3 or Brzozowski derivatives to generate strings that match multiple regex!

> The plural of `regex` is `regrets`

![To generate #1 albums, 'jay --help' recommends the -z flag.](https://imgs.xkcd.com/comics/perl_problems.png)

**WARNING**: `regrets` is still in development! If you have any feedback or suggestions to improve it, [let me know](https://github.com/AvalZ/regrets/discussions/new?category=feedback)!

## Setup

To use `regrets`, you need to

 - Clone this repository
 - Install [Poetry](https://python-poetry.org/docs/#installation)
 - Run `poetry install` to install all dependencies
 - Run `regrets` via `poetry run regrets` (or `poetry run python main.py`)

## How to use

`regrets` ships two engines as subcommands:

 - `z3` — SMT-based, supports partial matching
 - `brzozowski` — derivative-based, fast, also exposes the DFA and step-through derivation

Run `--help` on any subcommand to see its options.

### Z3

Generate strings that match a regex:

```
$ python main.py z3 generate --matching "[A-Za-z0-9]{3,10}"

AnP
```

Multiple `--matching` intersect:

```
$ python main.py z3 generate --matching "[A-Za-z0-9]{3,10}" --matching "abcd[0-9]+"

abcd4
```

Add `--not-matching` to exclude full matches, or `--not-partial-matching` to exclude substrings:

```
$ python main.py z3 generate --matching "[A-Za-z0-9]{3,10}" --not-partial-matching "[a-z]"

0KX
```

### Brzozowski

Same generation style:

```
$ python main.py brzozowski generate --matching "[a-z]+z.*" -N 3 --max-len 4

az
bz
cz
```

Plus a few extras only this engine offers:

`show` flattens intersections and complements into a single regex (no more `&` / `~`):

```
$ python main.py brzozowski show --matching "[a-z]+" --matching ".*z.*"

(z|[a-y]+z)([a-z]*)
```

`dfa` prints the derivative DFA:

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

`derive` steps through one character at a time, showing the residual regex:

```
$ python main.py brzozowski derive --matching "abc"

start [partial]: abc
> ab
  'a' [partial]: bc
  'b' [partial]: c
ab> c
  'c' [MATCH]: ε
```

### PCRE constructs

The Brzozowski engine accepts a subset of PCRE:

 - `(?=X)` / `(?!X)` — lookaheads (the rest of the regex is AND'd / NOT'd with `X`)
 - `(?<=x)` / `(?<!x)` — lookbehinds, fixed-width 1 (single char or character class)
 - `\b` / `\B` — word boundary / non-boundary

`show` flattens these like any other regex:

```
$ python main.py brzozowski show --matching "\bword\b"

word
```

### Pattern files

Pass many regex at once with `--matching-file` / `--not-matching-file` (one regex per line, `#` comments and blank lines ignored):

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

 - The Brzozowski engine handles lookaheads, fixed-width-1 lookbehinds, and word boundaries — variable-width lookbehinds and backreferences are not supported yet
 - The Z3 [regex parser](engines/z3/parser.py) (credits to [Andrew Helwer](https://ahelwer.ca/post/2022-01-19-z3-rbac/) for the original code) does not support all regex constructs *at the moment* (e.g., lazy quantifiers such as `*?`, `+?`, and `??`). PRs are welcome!
 - Z3 is very powerful, but it can sometimes be VERY (and I mean VERY) slow if the regex is very complex. Be patient :D
 - Multiple runs of `regrets` with the same parameters will yield the same results. This is due to the deterministic nature of Z3. If you want different results, simply run `regrets` with a high `-N` parameter (an update that excludes previously seen strings is coming soon)

## How to Contribute

PRs for missing features and overcoming limitations are always welcome!

But also, any [feedback](https://github.com/AvalZ/regrets/discussions/new?category=feedback) regarding usability or performance of `regrets` would be great!

Also, if you're using (and possibly enjoying) `regrets` in your projects, [let me know your use case](https://github.com/AvalZ/regrets/discussions/new?category=show-and-tell)!
