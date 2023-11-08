# Regrets

Use Z3 to generate strings that match multiple regex!

> The plural of `regex` is `regrets`

![To generate #1 albums, 'jay --help' recommends the -z flag.](https://imgs.xkcd.com/comics/perl_problems.png)

## Getting Started

You can use `regrets` to generate strings that would be matched by a given regex

```
$ python main.py --matching "[A-Za-z0-9]{3,10}"

AnP
```

Notice that the `--matching` option can be repeated multiple times.
This will generate strings that match all provided regex.

```
python main.py --matching "[A-Za-z0-9]{3,10}" --matching "abcd[0-9]*"

abcd4
```


## Limitations

 - `regrets` does NOT support PCRE *at the moment* (yeah I know, that kinda sucks... but many regex can still be converted or adapted to the non-PCRE counterpart, e.g., [Negative Lookaheads](https://avalz.it/tricks/simulating-negative-lookaheads-in-non-pcre-engines/))
 - The current [regex-to-Z3 converter](parser.py) (credits to [Andrew Helwer](https://ahelwer.ca/post/2022-01-19-z3-rbac/) for the original code) does not support all regex constructs *at the moment* (e.g., lazy quantifiers such as `*?`, `+?`, and `??`). PRs are welcome!
 - Z3 is very powerful, but it can sometimes be VERY (and I mean VERY) slow if the regex is very complex. Be patient, failure is reported quite quickly, so if it's still running it means that a string exists :D
 - Multiple runs of `regrets` with the same parameters will yield the same results. This is due to the deterministic nature of Z3. If you want different results, simply run `regrets` with a high `-N` parameter (an update that excludes previously seen strings is coming soon)
