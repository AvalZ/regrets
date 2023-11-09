# Regrets

Use Z3 to generate strings that match multiple regex!

> The plural of `regex` is `regrets`

![To generate #1 albums, 'jay --help' recommends the -z flag.](https://imgs.xkcd.com/comics/perl_problems.png)

**WARNING**: `regrets` is still in development! If you have any feedback or suggestions to improve it, [let me know](https://github.com/AvalZ/regrets/discussions/new?category=feedback)!

## Setup

To use `regrets`, you need to

 - Clone this repository
 - Install all requirements (Z3 and Typer, via `pip install -r requirements.txt`)
 - Run `regrets`!

## How to use

You can use `regrets` to generate strings that would be matched by a given regex

```
$ python main.py --matching "[A-Za-z0-9]{3,10}"

AnP
```

You can also have multiple `--matching` options!
This will generate strings that match all provided regex.

```
$ python main.py --matching "[A-Za-z0-9]{3,10}" --matching "abcd[0-9]+"

abcd4
```

If you want, you can also add a list of regex that the string should NOT match:

```
$ python main.py --matching "[A-Za-z0-9]{3,10}" --matching "abcd[0-9]+" --not-matching "[a-z]{4}[1-4]"

abcd6
```

You can also exclude patterns entirely. For example, do you want to exclude all lowercase chars (`[a-z]`)?

```
$ python main.py --matching "[A-Za-z0-9]{3,10}" --not-partial-matching "[a-z]"           

0KX
```

You can find all available options from `--help`


## Current Limitations

 - `regrets` does NOT support PCRE *at the moment* (yeah I know, that kinda sucks... but many regex can still be converted or adapted to the non-PCRE counterpart, e.g., [Negative Lookaheads](https://avalz.it/tricks/simulating-negative-lookaheads-in-non-pcre-engines/))
 - The current [regex-to-Z3 converter](parser.py) (credits to [Andrew Helwer](https://ahelwer.ca/post/2022-01-19-z3-rbac/) for the original code) does not support all regex constructs *at the moment* (e.g., lazy quantifiers such as `*?`, `+?`, and `??`). PRs are welcome!
 - Z3 is very powerful, but it can sometimes be VERY (and I mean VERY) slow if the regex is very complex. Be patient :D
 - Multiple runs of `regrets` with the same parameters will yield the same results. This is due to the deterministic nature of Z3. If you want different results, simply run `regrets` with a high `-N` parameter (an update that excludes previously seen strings is coming soon)

## How to Contribute

PRs for missing features and overcoming limitations are always welcome!

But also, any [feedback](https://github.com/AvalZ/regrets/discussions/new?category=feedback) regarding usability or performance of `regrets` would be great!

Also, if you're using (and possibly enjoying) `regrets` in your projects, [let me know your use case](https://github.com/AvalZ/regrets/discussions/new?category=show-and-tell)!
