"""Generate tables/normal_f64_zig1024.json, the Float64 normal ziggurat of SPEC.md Appendix A.

Run without arguments to write the file. Run with --check to verify the committed file byte for
byte. Requires mpmath.
"""

import argparse
import json
import sys
from pathlib import Path

import mpmath as mp

N = 1024
DIGITS = 50
PATH = Path(__file__).resolve().parent.parent / "tables" / "normal_f64_zig1024.json"

mp.mp.dps = DIGITS


def f(x):
    return mp.exp(-x * x / 2)


def layer_area(r):
    return r * f(r) + mp.sqrt(mp.pi / 2) * mp.erfc(r / mp.sqrt(2))


def widths(r):
    """X_0, ..., X_(N-1) for X_1 = r, and the excess of the top layer over 1."""
    v = layer_area(r)
    xs = [v / f(r), r]
    while len(xs) < N:
        t = f(xs[-1]) + v / xs[-1]
        if t >= 1:
            return xs, mp.mpf(1)  # The stack closes below layer N - 1, so r is too small.
        xs.append(mp.sqrt(-2 * mp.log(t)))
    return xs, f(xs[-1]) + v / xs[-1] - 1


def solve():
    lo, hi = mp.mpf(3), mp.mpf(5)
    for _ in range(4 * DIGITS):
        mid = (lo + hi) / 2
        if widths(mid)[1] > 0:
            lo = mid
        else:
            hi = mid
    xs, _ = widths((lo + hi) / 2)
    return xs + [mp.mpf(0)]


def nearest(x):
    with mp.workprec(53):
        return float(+x)


def tables():
    xs = solve()
    return {
        "layers": N,
        "R": nearest(xs[1]).hex(),
        "W": [nearest(mp.ldexp(xs[i], -53)).hex() for i in range(N)],
        "K": [int(mp.floor(mp.ldexp(xs[i + 1] / xs[i], 53))) for i in range(N)],
        "Y": [nearest(f(xs[i])).hex() for i in range(N)] + [(1.0).hex()],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="verify the committed file")
    text = json.dumps(tables(), indent=2) + "\n"
    if not parser.parse_args().check:
        PATH.parent.mkdir(exist_ok=True)
        PATH.write_text(text, newline="\n")
        return 0
    if PATH.read_bytes() != text.encode():
        print(f"{PATH} differs from the generated tables", file=sys.stderr)
        return 1
    print(f"{PATH.name} matches")
    return 0


if __name__ == "__main__":
    sys.exit(main())
