# Contributing

Thanks for your interest. This is a small focused project for one
specific car, but contributions are welcome where they fit.

## Before you start

Read [SAFETY.md](SAFETY.md). This is hardware control code; bugs
have physical consequences. Code review for this repo cares about
safety more than it cares about idiomatic Python.

## Reporting bugs

Open a GitHub issue using the bug report template. The template asks
for the artifacts we know we need:

- The session `.log` and `.csv` from `./logs/`
- A screenshot of the bus diagnostic panel
- Whether 30 MPH MODE was on or off
- One paragraph on what you were doing

Without those, we will probably ask you for them anyway.

## Suggesting features

Open an issue using the feature request template. Be specific about
the use case. "Make it faster" is not a feature; "raise the keyboard
steer rate to 120 deg/s when 30 MPH MODE is on" is.

## Making code changes

1. Fork and branch from `main`.
2. Keep changes focused. One logical change per pull request.
3. Preserve the safety architecture. If you are touching any of the
   E-STOP paths, the angle clamp, the rate limiter, or any of the
   watchdogs, your PR description must explain why.
4. Match the existing style: 4-space indent, double-quoted strings
   in the docstrings (single-quoted in code is fine), no em dashes
   anywhere (use `--` or commas).
5. Run the program once on real hardware before submitting if you
   can. If you cannot, say so in the PR.

## What we will and will not merge

We will merge:

- Fixes for real bugs with reproducers
- Documentation improvements
- New CAN protocol support that does not change existing behavior
- Logging improvements
- Better diagnostic UI

We will not merge:

- Removal or weakening of safety failsafes
- Changes that introduce dependencies on a comma device or a panda
  (the whole point of v4 was to remove those)
- Untested code paths claiming to "make the rack faster" or
  "increase torque" without bench-test evidence
- Cosmetic refactors with no functional benefit

## Versioning

`__version__` in `tesla_control.py` follows a loose semantic-versioning
scheme. Bump:

- patch (4.1.x) for bug fixes that don't change behavior
- minor (4.x.0) for new features that don't break the CLI / GUI
- major (x.0.0) for protocol or architecture changes

Document every version bump in [CHANGELOG.md](CHANGELOG.md).
